"""
HTTP API 라우터 - 통합 에이전트 외부 인터페이스.

UI, PlayMCP, 기타 클라이언트를 위한 HTTP 엔드포인트.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.api.agent_service import run_agent_task, run_agent_task_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


# ============================================================
# Request/Response Models
# ============================================================

class AnalyzeRequest(BaseModel):
    """프론트엔드 호환 분석 요청."""
    repo_url: str = Field(..., description="GitHub 저장소 URL", examples=["https://github.com/owner/repo"])
    user_message: Optional[str] = Field(None, description="분석 요청 메시지 (예: 보안 중점으로 깊게 분석해줘)")
    priority: str = Field(default="thoroughness", description="분석 우선순위 (speed 또는 thoroughness)")


class AnalyzeResponse(BaseModel):
    """프론트엔드 호환 분석 응답."""
    job_id: str = Field(..., description="작업 ID (owner/repo@ref)")
    score: int = Field(..., ge=0, le=100, description="Health score (0-100)")
    analysis: dict[str, Any] = Field(..., description="상세 분석 결과")
    risks: list[dict[str, Any]] = Field(default_factory=list, description="위험 요소 목록")
    actions: list[dict[str, Any]] = Field(default_factory=list, description="권장 액션 목록")
    similar: list[dict[str, Any]] = Field(default_factory=list, description="유사 프로젝트 (Deprecated)")
    recommended_issues: Optional[list[dict[str, Any]]] = Field(None, description="추천 이슈 목록")
    readme_summary: Optional[str] = Field(None, description="README 요약")
    task_plan: Optional[list[dict[str, Any]]] = Field(None, description="메타 에이전트 작업 계획")
    task_results: Optional[dict[str, Any]] = Field(None, description="메타 에이전트 작업 결과")
    chat_response: Optional[str] = Field(None, description="채팅 응답")
    onboarding_plan: Optional[list[dict[str, Any]]] = Field(None, description="온보딩 플랜")
    security: Optional[dict[str, Any]] = Field(None, description="보안 분석 결과")


class HealthCheckResponse(BaseModel):
    """Health check 응답."""
    status: str = Field(..., description="서비스 상태", examples=["ok"])
    service: str = Field(..., description="서비스 이름", examples=["ODOCAIagent"])


class MetricsResponse(BaseModel):
    """성능 메트릭 응답."""
    summary: dict[str, Any] = Field(..., description="메트릭 요약")
    recent_tasks: list[dict[str, Any]] = Field(default_factory=list, description="최근 작업 목록")


class MetricsSummaryResponse(BaseModel):
    """메트릭 요약 응답."""
    task_count: int = Field(..., ge=0, description="총 작업 수")
    avg_duration: float = Field(..., ge=0, description="평균 실행 시간 (초)")
    success_rate: float = Field(..., ge=0, le=1, description="성공률 (0-1)")
    agent_stats: dict[str, Any] = Field(default_factory=dict, description="에이전트별 통계")


def parse_github_url(url: str) -> tuple[str, str, str]:
    """
    GitHub URL에서 owner, repo, ref 추출.
    
    지원 포맷:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/tree/branch
    - owner/repo
    - owner/repo@ref
    
    Args:
        url: GitHub URL 또는 owner/repo 형식 문자열
    
    Returns:
        tuple[str, str, str]: (owner, repo, ref)
    
    Raises:
        ValueError: URL 형식이 올바르지 않을 때
    """
    patterns = [
        r"github\.com/([^/]+)/([^/\s#?]+)(?:/tree/([^/\s#?]+))?",
        r"^([^/]+)/([^/@\s]+)(?:@(.+))?$",  # owner/repo@ref 형식
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            owner = match.group(1)
            repo = match.group(2).replace(".git", "")
            ref = match.group(3) if match.lastindex and match.lastindex >= 3 and match.group(3) else "main"
            return owner, repo, ref
    
    raise ValueError(f"Invalid GitHub URL format: {url}")


def _get_score_interpretation(score: int) -> str:
    """
    점수 해석 문구 반환.
    
    Args:
        score: Health score (0-100)
    
    Returns:
        str: 점수 해석 문구
    """
    if score >= 80:
        return "상위 10% 수준입니다 (OSS 평균: 65점)"
    elif score >= 60:
        return "평균적인 수준입니다 (OSS 평균: 65점)"
    elif score >= 40:
        return "평균보다 낮습니다 (OSS 평균: 65점)"
    else:
        return "심각한 개선이 필요합니다"


def _get_level_description(level: str) -> str:
    """
    건강도 레벨 설명 반환.
    
    Args:
        level: Health level (good/warning/bad)
    
    Returns:
        str: 레벨 설명
    """
    if level == "good":
        return "안정적인 프로젝트입니다"
    elif level == "warning":
        return "일부 개선이 필요한 상태입니다"
    else:
        return "지속 가능성이 우려되는 상태입니다"


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    저장소 분석 API (프론트엔드 호환).
    
    GitHub URL을 받아서 건강도 진단을 수행하고,
    프론트엔드가 기대하는 형식으로 응답합니다.
    
    메타 에이전트 지원: user_message와 priority 파라미터로
    동적 실행 계획 수립 및 조건부 에이전트 실행.
    
    캐시: user_message 없는 경우만 24시간 캐시 적용.
    """
    from backend.common.github_client import fetch_beginner_issues
    from backend.common.cache_manager import analysis_cache
    
    try:
        owner, repo, ref = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # user_message가 없으면 캐시 확인 (단순 진단용)
    if not request.user_message:
        cached_response = analysis_cache.get_analysis(owner, repo, ref)
        if cached_response:
            logger.info(f"Returning cached analysis for {owner}/{repo}@{ref}")
            return AnalyzeResponse(**cached_response)
    
    # Supervisor 호출 (메타 에이전트 통합 - 비동기)
    result = await run_agent_task_async(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        ref=ref,
        user_message=request.user_message,
        priority=request.priority,
        use_llm_summary=True
    )
    
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
    
    data = result.get("data", {})
    
    # 실제 이슈 데이터
    docs_issues = data.get("docs_issues", [])
    activity_issues = data.get("activity_issues", [])
    
    # 상세 메트릭
    days_since_last_commit = data.get("days_since_last_commit")
    total_commits_30d = data.get("total_commits_30d", 0)
    unique_contributors = data.get("unique_contributors", 0)
    readme_sections = data.get("readme_sections", {})
    
    # 새 상세 메트릭 (UX 개선)
    issue_close_rate = data.get("issue_close_rate", 0.0)
    median_pr_merge_days = data.get("median_pr_merge_days")
    median_issue_close_days = data.get("median_issue_close_days")
    open_issues_count = data.get("open_issues_count", 0)
    open_prs_count = data.get("open_prs_count", 0)
    
    # 저장소 메타데이터
    stars = data.get("stars", 0)
    forks = data.get("forks", 0)
    
    # Good First Issues 가져오기
    try:
        recommended_issues = fetch_beginner_issues(owner, repo, max_count=5)
    except Exception:
        recommended_issues = []
    
    # 프론트엔드 형식으로 변환
    response = AnalyzeResponse(
        job_id=f"{owner}/{repo}@{ref}",
        score=data.get("health_score", 0),
        analysis={
            "health_score": data.get("health_score", 0),
            "health_score_interpretation": _get_score_interpretation(data.get("health_score", 0)),
            "health_level": data.get("health_level", "unknown"),
            "health_level_description": _get_level_description(data.get("health_level", "unknown")),
            "documentation_quality": data.get("documentation_quality", 0),
            "activity_maintainability": data.get("activity_maintainability", 0),
            "onboarding_score": data.get("onboarding_score", 0),
            "onboarding_level": data.get("onboarding_level", "unknown"),
            "dependency_complexity_score": data.get("dependency_complexity_score", 0),
            # 상세 메트릭
            "days_since_last_commit": days_since_last_commit,
            "total_commits_30d": total_commits_30d,
            "unique_contributors": unique_contributors,
            "readme_sections": readme_sections,
            # 새 상세 메트릭 (UX 개선)
            "issue_close_rate": issue_close_rate,
            "issue_close_rate_pct": f"{issue_close_rate * 100:.1f}%" if issue_close_rate else "N/A",
            "median_pr_merge_days": median_pr_merge_days,
            "median_pr_merge_days_text": f"{median_pr_merge_days:.1f}일" if median_pr_merge_days else "N/A",
            "median_issue_close_days": median_issue_close_days,
            "median_issue_close_days_text": f"{median_issue_close_days:.1f}일" if median_issue_close_days else "N/A",
            "open_issues_count": open_issues_count,
            "open_prs_count": open_prs_count,
            # 저장소 메타데이터
            "stars": stars,
            "forks": forks,
        },
        risks=_generate_risks_from_issues(docs_issues, activity_issues, data),
        actions=_generate_actions_from_issues(docs_issues, activity_issues, data, recommended_issues),
        similar=[],
        recommended_issues=recommended_issues,
        readme_summary=data.get("summary_for_user"),
        task_plan=data.get("task_plan"),
        task_results=data.get("task_results"),
        chat_response=data.get("chat_response"),
        # 온보딩 플랜 (task_results 또는 직접 전달)
        onboarding_plan=(
            data.get("task_results", {}).get("onboarding", {}).get("onboarding_plan") or
            data.get("onboarding_plan")
        ),
        # 보안 분석 결과
        security=_extract_security_response(data.get("task_results", {}).get("security")),
    )
    
    # user_message 없는 경우만 캐시에 저장
    if not request.user_message:
        analysis_cache.set_analysis(owner, repo, ref, response.model_dump())
    
    return response


# 이슈 코드 -> 한글 설명 매핑
ISSUE_DESCRIPTIONS = {
    # 문서 이슈
    "weak_documentation": "문서화 품질이 낮습니다",
    "missing_what": "프로젝트 설명(WHAT)이 누락되었습니다",
    "missing_why": "프로젝트 목적/이유(WHY)가 누락되었습니다",
    "missing_how": "설치/사용 방법(HOW)이 누락되었습니다",
    "missing_contributing": "기여 가이드(CONTRIBUTING)가 없습니다",
    # 활동성 이슈
    "inactive_project": "프로젝트가 비활성 상태입니다",
    "no_recent_commits": "최근 커밋이 없습니다",
    "low_issue_closure": "이슈 해결률이 낮습니다",
    "slow_pr_merge": "PR 병합 속도가 느립니다",
}

ISSUE_ACTIONS = {
    "weak_documentation": {"title": "README 전체 보완", "duration": "3시간", "priority": "high"},
    "missing_what": {"title": "프로젝트 소개 추가", "duration": "30분", "priority": "high"},
    "missing_why": {"title": "프로젝트 목적 명시", "duration": "20분", "priority": "medium"},
    "missing_how": {"title": "설치 가이드 작성", "duration": "1시간", "priority": "high"},
    "missing_contributing": {"title": "CONTRIBUTING.md 작성", "duration": "1시간", "priority": "medium"},
    "inactive_project": {"title": "프로젝트 활성화 계획 수립", "duration": "2시간", "priority": "high"},
    "no_recent_commits": {"title": "미해결 이슈 작업", "duration": "가변", "priority": "medium"},
    "low_issue_closure": {"title": "이슈 트리아지 및 정리", "duration": "2시간", "priority": "medium"},
    "slow_pr_merge": {"title": "PR 리뷰 프로세스 개선", "duration": "1시간", "priority": "medium"},
}


def _generate_risks_from_issues(
    docs_issues: List[str],
    activity_issues: List[str],
    data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """실제 이슈 목록 기반 리스크 생성 (구체적 수치 포함)."""
    risks = []
    risk_id = 1
    
    # 상세 메트릭 가져오기
    days_since_last_commit = data.get("days_since_last_commit")
    median_pr_merge_days = data.get("median_pr_merge_days")
    issue_close_rate = data.get("issue_close_rate", 0.0)
    open_issues_count = data.get("open_issues_count", 0)
    open_prs_count = data.get("open_prs_count", 0)
    
    # 문서 이슈
    for issue in docs_issues:
        desc = ISSUE_DESCRIPTIONS.get(issue, f"문서 이슈: {issue}")
        risks.append({
            "id": risk_id,
            "type": "documentation",
            "severity": "high" if issue in ["weak_documentation", "missing_how"] else "medium",
            "description": desc,
        })
        risk_id += 1
    
    # 활동성 이슈 (구체적 수치 포함)
    for issue in activity_issues:
        desc = ISSUE_DESCRIPTIONS.get(issue, f"활동성 이슈: {issue}")
        detail = ""
        
        # 상세 정보 추가
        if issue == "no_recent_commits" and days_since_last_commit is not None:
            if days_since_last_commit <= 7:
                detail = f" (마지막 커밋: {days_since_last_commit}일 전 - 양호)"
            elif days_since_last_commit <= 30:
                detail = f" (마지막 커밋: {days_since_last_commit}일 전 - 주의)"
            else:
                detail = f" (마지막 커밋: {days_since_last_commit}일 전 - 비활성)"
        elif issue == "slow_pr_merge" and median_pr_merge_days is not None:
            if median_pr_merge_days > 14:
                detail = f" (PR 병합 중간값: {median_pr_merge_days:.1f}일 - 매우 느림, 권장: 7일 이내)"
            elif median_pr_merge_days > 7:
                detail = f" (PR 병합 중간값: {median_pr_merge_days:.1f}일 - 느림, 권장: 7일 이내)"
            else:
                detail = f" (PR 병합 중간값: {median_pr_merge_days:.1f}일)"
        elif issue == "low_issue_closure":
            detail = f" (이슈 해결률: {issue_close_rate * 100:.1f}%, 미해결 이슈: {open_issues_count}개)"
            
        risks.append({
            "id": risk_id,
            "type": "maintenance",
            "severity": "high" if issue == "inactive_project" else "medium",
            "description": desc + detail,
        })
        risk_id += 1
    
    # 의존성 플래그
    dep_flags = data.get("dependency_flags", [])
    if dep_flags:
        risks.append({
            "id": risk_id,
            "type": "dependency",
            "severity": "medium",
            "description": f"의존성 이슈: {', '.join(dep_flags)}",
        })
    
    if not risks:
        risks.append({
            "id": 0,
            "type": "info",
            "severity": "low",
            "description": "주요 리스크가 발견되지 않았습니다",
        })
    
    return risks


def _generate_actions_from_issues(
    docs_issues: List[str],
    activity_issues: List[str],
    data: Dict[str, Any],
    recommended_issues: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """실제 이슈 목록 기반 액션 생성 (Good First Issue 연결)."""
    actions = []
    action_id = 1
    
    all_issues = docs_issues + activity_issues
    
    for issue in all_issues:
        action_info = ISSUE_ACTIONS.get(issue)
        if action_info:
            actions.append({
                "id": action_id,
                "title": action_info["title"],
                "description": ISSUE_DESCRIPTIONS.get(issue, issue),
                "duration": action_info["duration"],
                "priority": action_info["priority"],
            })
            action_id += 1
    
    # Good First Issue 연결 - 추천 이슈가 있으면 액션으로 추가
    if recommended_issues:
        for idx, gh_issue in enumerate(recommended_issues[:3]):  # 최대 3개
            issue_title = gh_issue.get("title", "제목 없음")
            issue_url = gh_issue.get("url", "")
            issue_number = gh_issue.get("number", "?")
            labels = gh_issue.get("labels", [])
            label_text = ", ".join(labels[:2]) if labels else "good first issue"
            
            actions.append({
                "id": action_id,
                "title": f"추천 이슈 #{issue_number} 작업",
                "description": f"[{label_text}] {issue_title}",
                "duration": "가변",
                "priority": "high" if idx == 0 else "medium",
                "url": issue_url,
                "issue_number": issue_number,
            })
            action_id += 1
    
    if not actions:
        actions.append({
            "id": 0,
            "title": "코드 리뷰",
            "description": "프로젝트 구조 파악을 위한 코드 리뷰",
            "duration": "30분",
            "priority": "low",
        })
    
    return actions


def _extract_security_response(security_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Security 분석 결과를 프론트엔드 형식으로 변환."""
    if not security_data:
        return None
    
    return {
        "score": security_data.get("security_score"),
        "grade": security_data.get("grade"),
        "risk_level": security_data.get("risk_level", "unknown"),
        "vulnerability_count": security_data.get("vuln_count", 0),
        "critical": security_data.get("critical_count", 0),
        "high": security_data.get("high_count", 0),
        "medium": security_data.get("medium_count", 0),
        "low": security_data.get("low_count", 0),
        "summary": security_data.get("summary", ""),
        # 취약점 상세 목록 (CVE ID, 패키지명, 심각도, 설명 등)
        "vulnerability_details": security_data.get("vulnerability_details", []),
    }


# Agent Task API (신규 통합 API)

class AgentTaskRequest(BaseModel):
    """에이전트 작업 요청 스키마."""
    task_type: str = Field(..., description="diagnose_repo | build_onboarding_plan")
    owner: str = Field(..., description="GitHub 저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    ref: str = Field(default="main", description="브랜치 또는 커밋")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="사용자 컨텍스트")
    use_llm_summary: bool = Field(default=True, description="LLM 요약 사용 여부")
    debug_trace: bool = Field(default=False, description="실행 추적 활성화")


class AgentTaskResponse(BaseModel):
    """에이전트 작업 응답 스키마."""
    ok: bool
    task_type: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[List[Dict[str, Any]]] = None


@router.post("/agent/task", response_model=AgentTaskResponse)
async def execute_agent_task(request: AgentTaskRequest) -> AgentTaskResponse:
    """
    통합 에이전트 작업 실행.
    
    지원 작업 유형:
    - diagnose_repo: 저장소 건강도 진단
    - build_onboarding_plan: 온보딩 플랜 생성 (LLM 필요)
    """
    try:
        result = await run_agent_task_async(
            task_type=request.task_type,
            owner=request.owner,
            repo=request.repo,
            ref=request.ref,
            user_context=request.user_context,
            use_llm_summary=request.use_llm_summary,
            debug_trace=request.debug_trace,
        )
        
        return AgentTaskResponse(
            ok=result.get("ok", False),
            task_type=result.get("task_type", request.task_type),
            data=result.get("data"),
            error=result.get("error"),
            trace=result.get("trace"),
        )
        
    except Exception as e:
        return AgentTaskResponse(
            ok=False,
            task_type=request.task_type,
            error=str(e),
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    API 상태 확인.
    
    Returns:
        HealthCheckResponse: 서비스 상태 정보
    """
    return HealthCheckResponse(status="ok", service="ODOCAIagent")


# === Chat API ===

class ChatMessageInput(BaseModel):
    """채팅 메시지 입력."""
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    """채팅 요청."""
    message: str = Field(..., description="사용자 메시지")
    repo_url: Optional[str] = Field(default=None, description="분석 중인 저장소 URL")
    analysis_context: Optional[Dict[str, Any]] = Field(default=None, description="분석 결과 컨텍스트")
    conversation_history: List[ChatMessageInput] = Field(default_factory=list, description="이전 대화 기록")


class ChatResponse(BaseModel):
    """채팅 응답."""
    ok: bool
    message: str
    error: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """
    AI 어시스턴트와 대화.
    
    분석 결과에 대해 질문하거나 오픈소스 기여에 대한 조언을 받을 수 있습니다.
    """
    from backend.api.chat_service import get_chat_service, ChatServiceRequest, ChatMessage as ServiceChatMessage
    
    # 서비스 요청 변환
    service_request = ChatServiceRequest(
        message=request.message,
        repo_url=request.repo_url,
        analysis_context=request.analysis_context,
        conversation_history=[
            ServiceChatMessage(role=msg.role, content=msg.content)
            for msg in (request.conversation_history or [])
        ]
    )
    
    # ChatService 호출
    service = get_chat_service()
    response = service.chat(service_request, timeout=300)
    
    return ChatResponse(
        ok=response.ok,
        message=response.message,
        error=response.error,
    )


# Compare Analysis Schemas
class CompareRequest(BaseModel):
    """비교 분석 요청."""
    repositories: List[str] = Field(
        ..., 
        description="비교할 저장소 목록 (예: ['owner1/repo1', 'owner2/repo2'])",
        min_length=2,
        max_length=5,
    )


class CompareResponse(BaseModel):
    """비교 분석 응답."""
    ok: bool
    comparison: Optional[Dict[str, Any]] = None
    individual_results: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    warnings: List[str] = []
    error: Optional[str] = None


@router.post("/analyze/compare", response_model=CompareResponse)
async def compare_repositories(request: CompareRequest) -> CompareResponse:
    from backend.agents.supervisor.graph import get_supervisor_graph
    from backend.agents.supervisor.models import SupervisorInput, SupervisorState
    from backend.agents.supervisor.service import init_state_from_input
    
    repos = request.repositories
    
    if len(repos) < 2:
        raise HTTPException(status_code=400, detail="최소 2개의 저장소가 필요합니다.")
    
    if len(repos) > 5:
        raise HTTPException(status_code=400, detail="최대 5개의 저장소까지 비교 가능합니다.")
    
    try:
        first_repo = repos[0]
        try:
            owner, repo, _ = parse_github_url(first_repo)
        except ValueError:
            if "/" in first_repo:
                owner, repo = first_repo.split("/", 1)
            else:
                raise HTTPException(status_code=400, detail=f"잘못된 저장소 형식: {first_repo}")
        
        graph = get_supervisor_graph()
        config = {"configurable": {"thread_id": f"compare_{owner}/{repo}"}}
        
        inp = SupervisorInput(
            task_type="general_inquiry",
            owner=owner,
            repo=repo,
            user_context={"intent": "compare"},
        )
        
        initial_state = init_state_from_input(inp)
        initial_state_dict = initial_state.model_dump()
        initial_state_dict["detected_intent"] = "compare"
        initial_state_dict["compare_repos"] = repos
        
        result = graph.invoke(SupervisorState(**initial_state_dict), config=config)
        
        comparison_data = {
            "repositories": {},
        }
        
        for repo_str, data in result.get("compare_results", {}).items():
            comparison_data["repositories"][repo_str] = {
                "health_score": data.get("health_score", 0),
                "onboarding_score": data.get("onboarding_score", 0),
                "health_level": data.get("health_level", "unknown"),
                "onboarding_level": data.get("onboarding_level", "unknown"),
                "documentation_quality": data.get("documentation_quality", 0),
                "activity_maintainability": data.get("activity_maintainability", 0),
            }
        
        if comparison_data["repositories"]:
            scores = [(r, d["health_score"]) for r, d in comparison_data["repositories"].items()]
            scores.sort(key=lambda x: x[1], reverse=True)
            comparison_data["ranking"] = [r for r, _ in scores]
            comparison_data["best_health"] = scores[0][0] if scores else None
            
            onboard_scores = [(r, d["onboarding_score"]) for r, d in comparison_data["repositories"].items()]
            onboard_scores.sort(key=lambda x: x[1], reverse=True)
            comparison_data["best_onboarding"] = onboard_scores[0][0] if onboard_scores else None
        
        return CompareResponse(
            ok=True,
            comparison=comparison_data,
            individual_results=result.get("compare_results", {}),
            summary=result.get("compare_summary"),
            warnings=result.get("warnings", []),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Compare analysis failed: {e}")
        return CompareResponse(
            ok=False,
            error=str(e),
            warnings=[],
        )


# Performance Metrics API
@router.get("/admin/metrics", response_model=MetricsResponse)
async def get_performance_metrics(limit: int = 50) -> MetricsResponse:
    """
    성능 메트릭 조회.
    
    Args:
        limit: 조회할 최근 작업 수 (기본값: 50)
    
    Returns:
        MetricsResponse: 메트릭 요약 및 최근 작업 목록
    """
    from backend.common.metrics import get_metrics_tracker
    
    tracker = get_metrics_tracker()
    return MetricsResponse(
        summary=tracker.get_summary(),
        recent_tasks=tracker.get_recent_metrics(limit=limit),
    )


@router.get("/admin/metrics/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary() -> MetricsSummaryResponse:
    """
    메트릭 요약 조회.
    
    Returns:
        MetricsSummaryResponse: 집계된 메트릭 정보
    """
    from backend.common.metrics import get_metrics_tracker
    
    tracker = get_metrics_tracker()
    summary = tracker.get_summary()
    return MetricsSummaryResponse(
        task_count=summary.get("task_count", 0),
        avg_duration=summary.get("avg_duration", 0.0),
        success_rate=summary.get("success_rate", 0.0),
        agent_stats=summary.get("agent_stats", {}),
    )


# === Streaming Analysis API ===

class StreamingAnalyzeRequest(BaseModel):
    """스트리밍 분석 요청."""
    repo_url: str = Field(..., description="GitHub 저장소 URL")
    analysis_depth: Optional[str] = Field(
        default=None, 
        description="분석 깊이 (deep/standard/quick, None이면 자동 결정)"
    )


@router.post("/analyze/stream")
async def analyze_repository_stream(request: StreamingAnalyzeRequest):
    """
    스트리밍 분석 API - SSE로 진행 상황을 실시간 전달.
    """
    from backend.agents.supervisor.streaming_handler import ProgressStreamHandler, ProgressEventType
    from backend.agents.supervisor.graph import get_supervisor_graph
    from backend.agents.supervisor.models import SupervisorInput
    from backend.agents.supervisor.service import init_state_from_input
    from backend.common.github_client import fetch_beginner_issues
    from backend.common.cache_manager import analysis_cache
    
    try:
        owner, repo, ref = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    async def event_generator():
        handler = ProgressStreamHandler(owner=owner, repo=repo)
        
        # 분석 시작 이벤트
        start_event = handler.on_analysis_start()
        yield start_event.to_sse()
        await asyncio.sleep(0.1)  # 클라이언트가 이벤트를 받을 시간
        
        try:
            # 캐시 확인
            cached_response = analysis_cache.get_analysis(owner, repo, ref)
            if cached_response:
                cache_event = handler.on_progress_update(
                    "캐시된 결과를 찾았습니다!", 
                    50
                )
                yield cache_event.to_sse()
                
                complete_event = handler.on_analysis_complete(cached_response)
                yield complete_event.to_sse()
                
                # 최종 결과
                yield f"data: {json.dumps({'type': 'result', 'data': cached_response}, ensure_ascii=False)}\n\n"
                return
            
            # 의도 분석 시작
            intent_start = handler.on_node_start("intent_analysis_node")
            yield intent_start.to_sse()
            await asyncio.sleep(0.05)
            
            # Supervisor 그래프 실행 준비
            graph = get_supervisor_graph()
            config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}
            
            user_context = {"use_llm_summary": True}
            if request.analysis_depth:
                user_context["analysis_depth"] = request.analysis_depth
            
            inp = SupervisorInput(
                task_type="diagnose_repo",
                owner=owner,
                repo=repo,
                user_context=user_context,
            )
            
            initial_state = init_state_from_input(inp)
            
            # 의도 분석 완료
            intent_complete = handler.on_node_complete("intent_analysis_node", {
                "detected_intent": "diagnose",
                "analysis_depth": request.analysis_depth or "auto"
            })
            yield intent_complete.to_sse()
            
            # 결정 노드
            decision_start = handler.on_node_start("decision_node")
            yield decision_start.to_sse()
            await asyncio.sleep(0.05)
            
            decision_complete = handler.on_node_complete("decision_node", {
                "next_node": "run_diagnosis_node"
            })
            yield decision_complete.to_sse()
            
            # 진단 노드 시작
            diagnosis_start = handler.on_node_start("run_diagnosis_node")
            yield diagnosis_start.to_sse()
            
            # 실제 그래프 실행 (블로킹)
            # Note: 실제 프로덕션에서는 비동기 실행이 필요하지만,
            # 현재 LangGraph는 동기 실행이므로 스레드풀에서 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(graph.invoke, initial_state, config=config)
                
                # 진행률 업데이트 (예상 시간 기반)
                progress_steps = [30, 40, 50, 55]
                for pct in progress_steps:
                    if not future.done():
                        progress_event = handler.on_progress_update(
                            f"저장소 분석 중... ({pct}%)", 
                            pct
                        )
                        yield progress_event.to_sse()
                        await asyncio.sleep(1.5)
                
                # 결과 대기
                result = future.result(timeout=900)
            
            # 결과 처리
            if result is None:
                result = {}
            elif hasattr(result, "model_dump"):
                result = result.model_dump()
            
            # 진단 완료
            diagnosis_result = result.get("diagnosis_result", {})
            diagnosis_complete = handler.on_node_complete("run_diagnosis_node", {
                "diagnosis_result": diagnosis_result
            })
            yield diagnosis_complete.to_sse()
            
            # 품질 검사
            quality_start = handler.on_node_start("quality_check_node")
            yield quality_start.to_sse()
            await asyncio.sleep(0.1)
            
            quality_complete = handler.on_node_complete("quality_check_node", {})
            yield quality_complete.to_sse()
            
            # 에러 체크
            if result.get("error"):
                error_event = handler.on_node_error("run_diagnosis_node", result["error"])
                yield error_event.to_sse()
                yield f"data: {json.dumps({'type': 'error', 'error': result['error']}, ensure_ascii=False)}\n\n"
                return
            
            # 경고 메시지 전송
            for warning in result.get("warnings", []):
                warning_event = handler.on_warning(warning)
                yield warning_event.to_sse()
            
            # Good First Issues 수집
            try:
                recommended_issues = fetch_beginner_issues(owner, repo, max_count=5)
            except Exception:
                recommended_issues = []
            
            # 최종 응답 생성
            data = result.get("diagnosis_result") or result.get("data") or {}
            docs_issues = data.get("docs_issues", [])
            activity_issues = data.get("activity_issues", [])
            
            response_data = {
                "job_id": f"{owner}/{repo}@{ref}",
                "score": data.get("health_score", 0),
                "analysis": {
                    "health_score": data.get("health_score", 0),
                    "health_level": data.get("health_level", "unknown"),
                    "documentation_quality": data.get("documentation_quality", 0),
                    "activity_maintainability": data.get("activity_maintainability", 0),
                    "onboarding_score": data.get("onboarding_score", 0),
                    "analysis_depth_used": data.get("analysis_depth_used", "standard"),
                    "flow_adjustments": result.get("flow_adjustments", []),
                    "warnings": result.get("warnings", []),
                },
                "risks": _generate_risks_from_issues(docs_issues, activity_issues, data),
                "actions": _generate_actions_from_issues(docs_issues, activity_issues, data, recommended_issues),
                "recommended_issues": recommended_issues,
                "readme_summary": data.get("summary_for_user"),
            }
            
            # 캐시에 저장
            analysis_cache.set_analysis(owner, repo, ref, response_data)
            
            # 분석 완료 이벤트
            complete_event = handler.on_analysis_complete(response_data)
            yield complete_event.to_sse()
            
            # 최종 결과
            yield f"data: {json.dumps({'type': 'result', 'data': response_data}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.exception(f"Streaming analysis failed: {e}")
            error_event = handler.on_node_error("analysis", str(e))
            yield error_event.to_sse()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# GET 방식 SSE 엔드포인트 (프론트엔드 EventSource 호환)
@router.get("/analyze/stream")
async def analyze_repository_stream_get(
    repo_url: str,
    user_message: Optional[str] = None,
    message: Optional[str] = None,  # 프론트엔드 호환용 (user_message와 동일)
    priority: str = "thoroughness",          
    analysis_depth: Optional[str] = None,
    force_refresh: bool = False,  # 캐시 무시 옵션
):
    """
    스트리밍 분석 API (GET) - 프론트엔드 EventSource 호환.
    
    Args:
        user_message: 사용자 메시지 (메타 에이전트용)
        message: user_message의 별칭 (프론트엔드 호환)
        force_refresh: True이면 캐시를 무시하고 재분석 수행
    """
    # message 파라미터를 user_message로 병합
    local_user_message = user_message or message
    from backend.agents.supervisor.graph import get_supervisor_graph
    from backend.agents.supervisor.models import SupervisorInput
    from backend.agents.supervisor.service import init_state_from_input
    from backend.common.github_client import fetch_beginner_issues
    from backend.common.cache_manager import analysis_cache
    
    try:
        owner, repo, ref = parse_github_url(repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 프론트엔드 호환 단계 정의
    FRONTEND_STEPS = {
        "intent_analysis_node": {"step": "intent", "progress": 5, "message": "AI가 요청 의도 분석 중"},
        "decision_node": {"step": "github", "progress": 15, "message": "저장소 정보 수집 중"},
        "run_diagnosis_node": {"step": "docs", "progress": 35, "message": "문서 품질 분석 중"},
        "activity": {"step": "activity", "progress": 55, "message": "활동성 분석 중"},
        "structure": {"step": "structure", "progress": 70, "message": "구조 분석 중"},
        "scoring": {"step": "scoring", "progress": 85, "message": "건강도 점수 계산 중"},
        "quality_check_node": {"step": "quality", "progress": 92, "message": "AI가 결과 품질 검사 중"},
        "summary": {"step": "llm", "progress": 97, "message": "AI 요약 생성 중"},
    }
    
    async def event_generator():
        def send_event(step: str, progress: int, message: str, data: dict = None):
            event_data = {
                "step": step,
                "progress": progress,
                "message": message,
            }
            if data:
                event_data["data"] = data
            return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        
        # 시작 이벤트
        yield send_event("github", 5, f"{owner}/{repo} 저장소 정보 수집 중...")
        await asyncio.sleep(0.1)
        
        try:
            # 캐시 확인 (force_refresh가 아닐 때만)
            if not force_refresh:
                cached_response = analysis_cache.get_analysis(owner, repo, ref)
                if cached_response:
                    yield send_event("github", 50, "캐시된 결과를 찾았습니다!")
                    yield send_event("complete", 100, "분석 완료!", {"result": cached_response})
                    return
            else:
                logger.info(f"Force refresh requested for {owner}/{repo}@{ref}, skipping cache")
            
            # 의도 분석
            yield send_event("intent", 10, "AI가 요청 의도 분석 중...")
            await asyncio.sleep(0.05)
            
            # 문서 분석
            yield send_event("docs", 25, "문서 품질 분석 중...")
            
            # Supervisor 그래프 실행 준비
            graph = get_supervisor_graph()
            config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}

            # /api/analyze/stream은 분석 페이지 전용이므로 항상 진단 실행
            # 보안, 온보딩 등 추가 분석은 채팅에서 별도 요청
            user_context = {"use_llm_summary": True, "force_diagnosis": True}
            user_context["priority"] = priority

            if local_user_message:
                user_context["user_message"] = local_user_message
            
            if analysis_depth:
                user_context["analysis_depth"] = analysis_depth
            
            inp = SupervisorInput(
                task_type="diagnose_repo",
                owner=owner,
                repo=repo,
                user_context=user_context,
                user_message=local_user_message,
            )
            
            initial_state = init_state_from_input(inp)
            
            # 활동성 분석
            yield send_event("activity", 45, "활동성 분석 중...")
            
            # 그래프 비동기 실행 (ainvoke 사용)
            graph_task = asyncio.create_task(graph.ainvoke(initial_state, config=config))
            
            # 진행률 업데이트
            progress_updates = [
                ("structure", 55, "구조 분석 중..."),
                ("structure", 65, "의존성 분석 중..."),
                ("scoring", 75, "분석 결과 종합 중..."),
                ("scoring", 82, "AI가 플랜 생성 중..."),
            ]
            
            for step, pct, msg in progress_updates:
                if not graph_task.done():
                    yield send_event(step, pct, msg)
                    await asyncio.sleep(1.2)
            
            # 그래프 실행 완료 대기
            try:
                result = await asyncio.wait_for(graph_task, timeout=1800)  # 30분
            except asyncio.TimeoutError:
                yield send_event("error", 0, "분석 시간 초과", {"error": "분석이 30분을 초과했습니다."})
                return
            
            # 품질 검사
            yield send_event("quality", 90, "AI가 결과 품질 검사 중...")
            await asyncio.sleep(0.1)
            
            # 결과 처리
            if result is None:
                result = {}
            elif hasattr(result, "model_dump"):
                result = result.model_dump()
            
            # 에러 체크
            if result.get("error"):
                yield send_event("error", 0, result["error"], {"error": result["error"]})
                return
            
            # LLM 요약
            yield send_event("llm", 95, "AI 요약 생성 중...")
            
            # 디버깅: 결과 구조 확인
            logger.info(f"Raw result keys: {result.keys() if result else 'None'}")
            
            # 결과 추출 - agent_result 또는 diagnosis_result에서 가져오기
            # SupervisorState에서 agent_result가 실제 진단 결과
            agent_result = result.get("agent_result") or {}
            diagnosis_data = result.get("diagnosis_result") or agent_result
            data = diagnosis_data if diagnosis_data else result.get("data") or {}
            
            logger.info(f"agent_result keys: {agent_result.keys() if agent_result else 'None'}")
            logger.info(f"Data keys for response: {data.keys() if data else 'None'}")
            logger.info(f"health_score in data: {data.get('health_score')}")
            
            # Good First Issues 수집
            try:
                recommended_issues = fetch_beginner_issues(owner, repo, max_count=5)
            except Exception:
                recommended_issues = []
            
            # full_path.py 필드명과 http_router 필드명 매핑
            # full_path: docs_score, activity_score
            # http_router: documentation_quality, activity_maintainability
            documentation_quality = data.get("documentation_quality") or data.get("docs_score", 0)
            activity_maintainability = data.get("activity_maintainability") or data.get("activity_score", 0)
            
            # activity 데이터에서 추가 정보 추출
            activity_data = data.get("activity", {}) or {}
            if isinstance(activity_data, dict):
                days_since_last_commit = activity_data.get("days_since_last_commit") or data.get("days_since_last_commit")
                total_commits_30d = activity_data.get("total_commits_30d") or data.get("total_commits_30d", 0)
                unique_contributors = activity_data.get("unique_contributors") or data.get("unique_contributors", 0)
                issue_close_rate = activity_data.get("issue_close_rate") or data.get("issue_close_rate", 0)
                median_pr_merge_days = activity_data.get("median_pr_merge_days") or data.get("median_pr_merge_days")
                open_issues_count = activity_data.get("open_issues_count") or data.get("open_issues_count", 0)
                stars = activity_data.get("stars") or data.get("stars", 0)
                forks = activity_data.get("forks") or data.get("forks", 0)
            else:
                days_since_last_commit = data.get("days_since_last_commit")
                total_commits_30d = data.get("total_commits_30d", 0)
                unique_contributors = data.get("unique_contributors", 0)
                issue_close_rate = data.get("issue_close_rate", 0)
                median_pr_merge_days = data.get("median_pr_merge_days")
                open_issues_count = data.get("open_issues_count", 0)
                stars = data.get("stars", 0)
                forks = data.get("forks", 0)
            
            docs_issues = data.get("docs_issues", [])
            activity_issues = data.get("activity_issues", [])
            
            response_data = {
                "job_id": f"{owner}/{repo}@{ref}",
                "score": data.get("health_score", 0),
                "analysis": {
                    "health_score": data.get("health_score", 0),
                    "health_level": data.get("health_level", "unknown"),
                    "documentation_quality": documentation_quality,
                    "activity_maintainability": activity_maintainability,
                    "onboarding_score": data.get("onboarding_score", 0),
                    "onboarding_level": data.get("onboarding_level", "unknown"),
                    "analysis_depth_used": data.get("analysis_depth") or data.get("analysis_depth_used", "standard"),
                    "flow_adjustments": result.get("flow_adjustments", []),
                    "warnings": data.get("warnings") or result.get("warnings", []),
                    "days_since_last_commit": days_since_last_commit,
                    "total_commits_30d": total_commits_30d,
                    "unique_contributors": unique_contributors,
                    "issue_close_rate": issue_close_rate,
                    "median_pr_merge_days": median_pr_merge_days,
                    "open_issues_count": open_issues_count,
                    "stars": stars,
                    "forks": forks,
                    "dependency_complexity_score": data.get("dependency_complexity_score") or data.get("structure_score", 0),
                    "chat_response": result.get("chat_response"),
                },
                "risks": _generate_risks_from_issues(docs_issues, activity_issues, data),
                "actions": _generate_actions_from_issues(docs_issues, activity_issues, data, recommended_issues),
                "recommended_issues": recommended_issues,
                "readme_summary": data.get("summary_for_user") or data.get("llm_summary"),
                "chat_response": result.get("chat_response"),
                "onboarding_plan": (
                    result.get("task_results", {}).get("onboarding", {}).get("onboarding_plan") or
                    result.get("onboarding_plan") or
                    data.get("onboarding_plan")
                ),
                # Security 분석 결과
                "security": _extract_security_response(result.get("task_results", {}).get("security")),
            }
            
            # 캐시에 저장
            analysis_cache.set_analysis(owner, repo, ref, response_data)
            
            # 완료 이벤트
            yield send_event("complete", 100, "분석 완료!", {"result": response_data})
            
        except Exception as e:
            logger.exception(f"Streaming analysis (GET) failed: {e}")
            yield send_event("error", 0, f"분석 중 오류 발생: {str(e)}", {"error": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


# === Report Export API ===

class ExportReportRequest(BaseModel):
    """리포트 내보내기 요청."""
    report_type: str = Field(..., description="diagnosis | onboarding | security")
    owner: str = Field(..., description="저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    data: Dict[str, Any] = Field(..., description="리포트 데이터")
    include_ai_trace: bool = Field(default=True, description="AI 판단 과정 포함")


@router.post("/export/report")
async def export_report(request: ExportReportRequest):
    """
    분석 결과를 Markdown 리포트로 내보내기.
    
    지원 리포트 유형:
    - diagnosis: 진단 리포트
    - onboarding: 온보딩 가이드
    - security: 보안 분석 리포트
    """
    from backend.common.report_exporter import (
        export_diagnosis_report,
        export_onboarding_guide,
        export_security_report
    )
    
    try:
        if request.report_type == "diagnosis":
            markdown_content = export_diagnosis_report(
                result=request.data,
                owner=request.owner,
                repo=request.repo,
                include_ai_trace=request.include_ai_trace
            )
        elif request.report_type == "onboarding":
            experience_level = request.data.get("experience_level", "beginner")
            markdown_content = export_onboarding_guide(
                plan=request.data,
                owner=request.owner,
                repo=request.repo,
                experience_level=experience_level
            )
        elif request.report_type == "security":
            markdown_content = export_security_report(
                result=request.data,
                owner=request.owner,
                repo=request.repo
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 리포트 유형: {request.report_type}"
            )
        
        # Markdown 파일로 반환
        filename = f"{request.owner}_{request.repo}_{request.report_type}_report.md"
        
        from fastapi.responses import Response
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Report export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
