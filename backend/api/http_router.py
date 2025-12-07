"""
HTTP API 라우터 - 통합 에이전트 외부 인터페이스.

UI, PlayMCP, 기타 클라이언트를 위한 HTTP 엔드포인트.
"""
import asyncio
import json
import logging
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from backend.api.agent_service import run_agent_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


# Frontend Compatible Schemas (/api/analyze)
class AnalyzeRequest(BaseModel):
    """프론트엔드 호환 분석 요청."""
    repo_url: str = Field(..., description="GitHub 저장소 URL (예: https://github.com/owner/repo)")


class AnalyzeResponse(BaseModel):
    """프론트엔드 호환 분석 응답."""
    job_id: str
    score: int  # health_score
    analysis: Dict[str, Any]
    risks: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    similar: List[Dict[str, Any]]  # Deprecated in favor of recommended_issues
    recommended_issues: Optional[List[Dict[str, Any]]] = None
    readme_summary: Optional[str] = None


def parse_github_url(url: str) -> tuple[str, str, str]:
    """GitHub URL에서 owner, repo, ref 추출."""
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
    """점수 해석 문구 반환."""
    if score >= 80:
        return "상위 10% 수준입니다 (OSS 평균: 65점)"
    elif score >= 60:
        return "평균적인 수준입니다 (OSS 평균: 65점)"
    elif score >= 40:
        return "평균보다 낮습니다 (OSS 평균: 65점)"
    else:
        return "심각한 개선이 필요합니다"


def _get_level_description(level: str) -> str:
    """건강도 레벨 설명 반환."""
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
    
    캐시: 동일 저장소는 24시간 동안 캐시됩니다.
    """
    from backend.common.github_client import fetch_beginner_issues
    from backend.common.cache import analysis_cache
    
    try:
        owner, repo, ref = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 캐시 확인
    cached_response = analysis_cache.get_analysis(owner, repo, ref)
    if cached_response:
        logger.info(f"Returning cached analysis for {owner}/{repo}@{ref}")
        return AnalyzeResponse(**cached_response)
    
    # Diagnosis Agent 호출 (LLM 요약 활성화)
    result = run_agent_task(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        ref=ref,
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
    )
    
    # 캐시에 저장
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
        result = run_agent_task(
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


@router.get("/health")
async def health_check():
    """API 상태 확인."""
    return {"status": "ok", "service": "ODOCAIagent"}


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
    response = service.chat(service_request, timeout=60)
    
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
            task_type="diagnose_repo",
            owner=owner,
            repo=repo,
            user_context={"intent": "compare"}
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
@router.get("/admin/metrics")
async def get_performance_metrics(limit: int = 50):
    from backend.common.metrics import get_metrics_tracker
    
    tracker = get_metrics_tracker()
    return {
        "summary": tracker.get_summary(),
        "recent_tasks": tracker.get_recent_metrics(limit=limit),
    }


@router.get("/admin/metrics/summary")
async def get_metrics_summary():
    from backend.common.metrics import get_metrics_tracker
    
    tracker = get_metrics_tracker()
    return tracker.get_summary()


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
    from backend.common.cache import analysis_cache
    
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
                result = future.result(timeout=120)
            
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
            data = result.get("diagnosis_result", {})
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
