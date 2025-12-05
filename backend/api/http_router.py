"""
HTTP API 라우터 - 통합 에이전트 외부 인터페이스.

UI, PlayMCP, 기타 클라이언트를 위한 HTTP 엔드포인트.
"""
import logging
import re
from fastapi import APIRouter, HTTPException
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
    """
    from backend.common.github_client import fetch_beginner_issues
    
    try:
        owner, repo, ref = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
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
    return AnalyzeResponse(
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
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest as LLMChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME
        
        client = fetch_llm_client()
        
        # 시스템 프롬프트 구성
        system_prompt = _build_chat_system_prompt(request.repo_url, request.analysis_context)
        
        # 대화 메시지 구성
        messages = [ChatMessage(role="system", content=system_prompt)]
        
        # 이전 대화 기록 추가
        for msg in (request.conversation_history or []):
            messages.append(ChatMessage(role=msg.role, content=msg.content))
        
        # 현재 사용자 메시지 추가
        messages.append(ChatMessage(role="user", content=request.message))
        
        # LLM 호출
        llm_request = LLMChatRequest(
            messages=messages,
            model=LLM_MODEL_NAME,
            temperature=0.7,
        )
        
        response = client.chat(llm_request, timeout=30)
        
        return ChatResponse(
            ok=True,
            message=response.content,
        )
        
    except Exception as e:
        logger.exception(f"Chat failed: {e}")
        # Fallback 응답
        fallback = _generate_fallback_response(request.message, request.analysis_context)
        return ChatResponse(
            ok=True,
            message=fallback,
            error=f"LLM 호출 실패, 기본 응답 사용: {str(e)}"
        )


def _build_chat_system_prompt(repo_url: Optional[str], analysis_context: Optional[Dict]) -> str:
    """채팅용 시스템 프롬프트 구성."""
    base_prompt = (
        "당신은 ODOC AI Agent입니다. 오픈소스 프로젝트 분석 및 기여 가이드 전문가입니다.\n"
        "사용자가 오픈소스 프로젝트에 대해 질문하면 친절하고 전문적으로 답변해주세요.\n"
        "답변은 항상 한글로 작성하고, 구체적이고 실행 가능한 조언을 제공하세요.\n"
    )
    
    if repo_url:
        base_prompt += f"\n현재 분석 중인 저장소: {repo_url}\n"
    
    if analysis_context:
        context_parts = []
        if "health_score" in analysis_context:
            context_parts.append(f"- 건강 점수: {analysis_context['health_score']}점")
        if "documentation_quality" in analysis_context:
            context_parts.append(f"- 문서 품질: {analysis_context['documentation_quality']}점")
        if "activity_maintainability" in analysis_context:
            context_parts.append(f"- 활동성: {analysis_context['activity_maintainability']}점")
        if "stars" in analysis_context:
            context_parts.append(f"- Stars: {analysis_context['stars']:,}")
        if "forks" in analysis_context:
            context_parts.append(f"- Forks: {analysis_context['forks']:,}")
        
        if context_parts:
            base_prompt += "\n분석 결과 요약:\n" + "\n".join(context_parts) + "\n"
    
    base_prompt += (
        "\n답변 시 다음 가이드라인을 따르세요:\n"
        "1. 질문에 직접적으로 답변하세요.\n"
        "2. 필요시 단계별 가이드를 제공하세요.\n"
        "3. 코드 예시가 필요하면 마크다운 코드 블록을 사용하세요.\n"
        "4. 불확실한 내용은 솔직하게 말하세요.\n"
    )
    
    return base_prompt


def _generate_fallback_response(message: str, context: Optional[Dict]) -> str:
    """LLM 실패 시 키워드 기반 fallback 응답."""
    message_lower = message.lower()
    
    if "기여" in message or "contribute" in message_lower or "어떻게" in message:
        return (
            "오픈소스 기여를 시작하는 방법을 안내해드릴게요:\n\n"
            "1. **저장소 Fork**: GitHub에서 저장소를 Fork합니다\n"
            "2. **로컬 Clone**: `git clone <your-fork-url>`\n"
            "3. **브랜치 생성**: `git checkout -b feature/your-feature`\n"
            "4. **변경 사항 작업**: 코드 수정 또는 문서 개선\n"
            "5. **커밋 & 푸시**: `git commit -m '설명'` 후 `git push`\n"
            "6. **PR 생성**: GitHub에서 Pull Request를 생성합니다\n\n"
            "처음이라면 'good first issue' 라벨이 붙은 이슈부터 시작하는 것을 추천드립니다!"
        )
    
    if "보안" in message or "security" in message_lower or "취약점" in message:
        return (
            "보안 관련 조언을 드릴게요:\n\n"
            "1. **의존성 업데이트**: `npm audit fix` 또는 `pip install --upgrade`로 취약점 패치\n"
            "2. **보안 스캐닝**: GitHub Security Advisories나 Dependabot 알림 확인\n"
            "3. **민감 정보 관리**: `.env` 파일 사용, 절대 커밋하지 않기\n"
            "4. **코드 리뷰**: 보안 관점에서 PR 리뷰 수행\n\n"
            "구체적인 취약점이 있다면 해당 라이브러리의 보안 권고사항을 확인하세요."
        )
    
    if "문서" in message or "readme" in message_lower or "documentation" in message_lower:
        return (
            "좋은 문서 작성을 위한 가이드입니다:\n\n"
            "**README.md 필수 섹션:**\n"
            "1. 프로젝트 소개 (WHAT) - 무엇을 하는 프로젝트인지\n"
            "2. 사용 이유 (WHY) - 왜 이 프로젝트가 필요한지\n"
            "3. 설치 방법 (HOW) - 어떻게 시작하는지\n"
            "4. 사용 예시 - 코드 예제\n"
            "5. 기여 가이드 - CONTRIBUTING.md 링크\n\n"
            "스크린샷이나 GIF를 추가하면 이해하기 쉬워집니다!"
        )
    
    if "점수" in message or "score" in message_lower or "평가" in message:
        score_info = ""
        if context and "health_score" in context:
            score = context["health_score"]
            if score >= 80:
                score_info = f"현재 점수 {score}점은 상위 10% 수준으로 매우 건강한 프로젝트입니다."
            elif score >= 60:
                score_info = f"현재 점수 {score}점은 평균 수준입니다. 문서화나 활동성 개선으로 점수를 높일 수 있습니다."
            else:
                score_info = f"현재 점수 {score}점은 개선이 필요합니다. 문서 보완과 이슈 해결에 집중하세요."
        else:
            score_info = "분석 결과를 확인해주세요."
        
        return (
            f"점수 해석을 도와드릴게요:\n\n{score_info}\n\n"
            "**점수 구성 요소:**\n"
            "- 문서 품질: README 완성도, 기여 가이드 유무\n"
            "- 활동성: 최근 커밋, PR 병합 속도, 이슈 해결률\n"
            "- 온보딩 용이성: 신규 기여자가 시작하기 쉬운 정도"
        )
    
    # 기본 응답
    return (
        "궁금한 점에 대해 답변드릴게요. 다음과 같은 주제로 질문해주시면 더 구체적인 답변을 드릴 수 있습니다:\n\n"
        "- **기여 방법**: 오픈소스에 어떻게 기여하나요?\n"
        "- **문서화**: README를 어떻게 개선하나요?\n"
        "- **보안**: 취약점은 어떻게 해결하나요?\n"
        "- **점수 해석**: 분석 점수의 의미는 무엇인가요?\n\n"
        "자유롭게 질문해주세요!"
    )
