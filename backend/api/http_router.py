"""
HTTP API 라우터 - 통합 에이전트 외부 인터페이스.

UI, PlayMCP, 기타 클라이언트를 위한 HTTP 엔드포인트.
"""
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from backend.api.agent_service import run_agent_task

router = APIRouter(prefix="/api", tags=["agent"])


# ============================================================
# Frontend Compatible Schemas (/api/analyze)
# ============================================================

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
    similar: List[Dict[str, Any]]
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
            ref = match.group(3) if match.lastindex >= 3 and match.group(3) else "main"
            return owner, repo, ref
    
    raise ValueError(f"Invalid GitHub URL format: {url}")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    저장소 분석 API (프론트엔드 호환).
    
    GitHub URL을 받아서 건강도 진단을 수행하고,
    프론트엔드가 기대하는 형식으로 응답합니다.
    
    **Note**: risks, actions, similar는 현재 Diagnosis Agent만 구현되어 있어
    Mock 데이터로 반환됩니다.
    """
    try:
        owner, repo, ref = parse_github_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Diagnosis Agent 호출
    result = run_agent_task(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        ref=ref,
        use_llm_summary=False
    )
    
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
    
    data = result.get("data", {})
    
    # 프론트엔드 형식으로 변환
    return AnalyzeResponse(
        job_id=f"{owner}/{repo}@{ref}",
        score=data.get("health_score", 0),
        analysis={
            "health_score": data.get("health_score", 0),
            "documentation_quality": data.get("documentation_quality", 0),
            "activity_maintainability": data.get("activity_maintainability", 0),
            "onboarding_score": data.get("onboarding_score", 0),
            "health_level": data.get("health_level", "unknown"),
            "onboarding_level": data.get("onboarding_level", "unknown"),
            "dependency_complexity_score": data.get("dependency_complexity_score", 0),
        },
        # Mock 데이터 - 다른 Agent 기능 미구현
        risks=_generate_mock_risks(data),
        actions=_generate_mock_actions(data),
        similar=[],  # Similar 추천은 미구현
        readme_summary=None,  # LLM 요약은 별도 호출 필요
    )


def _generate_mock_risks(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """진단 결과 기반 리스크 Mock 생성."""
    risks = []
    
    docs_issues = data.get("docs_issues_count", 0)
    if docs_issues > 0:
        risks.append({
            "id": 1,
            "type": "documentation",
            "severity": "medium" if docs_issues == 1 else "high",
            "description": f"문서화 관련 {docs_issues}개 이슈가 발견되었습니다",
        })
    
    activity_issues = data.get("activity_issues_count", 0)
    if activity_issues > 0:
        risks.append({
            "id": 2,
            "type": "maintenance",
            "severity": "medium" if activity_issues == 1 else "high",
            "description": f"활동성 관련 {activity_issues}개 이슈가 발견되었습니다",
        })
    
    dep_flags = data.get("dependency_flags", [])
    if dep_flags:
        risks.append({
            "id": 3,
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


def _generate_mock_actions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """진단 결과 기반 액션 Mock 생성."""
    actions = []
    
    if data.get("docs_issues_count", 0) > 0:
        actions.append({
            "id": 1,
            "title": "문서화 개선",
            "description": "README 및 CONTRIBUTING 가이드 보완",
            "duration": "2시간",
            "priority": "high" if data.get("documentation_quality", 100) < 50 else "medium",
        })
    
    if data.get("activity_issues_count", 0) > 0:
        actions.append({
            "id": 2,
            "title": "이슈 정리",
            "description": "오래된 이슈 정리 및 라벨링",
            "duration": "1시간",
            "priority": "medium",
        })
    
    if not actions:
        actions.append({
            "id": 0,
            "title": "코드 리뷰",
            "description": "프로젝트 구조 파악을 위한 코드 리뷰",
            "duration": "30분",
            "priority": "low",
        })
    
    return actions


# ============================================================
# Agent Task API (신규 통합 API)
# ============================================================

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

