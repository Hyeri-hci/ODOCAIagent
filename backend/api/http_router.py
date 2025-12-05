"""
HTTP API 라우터 - 통합 에이전트 외부 인터페이스.

UI, PlayMCP, 기타 클라이언트를 위한 HTTP 엔드포인트.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from backend.api.agent_service import run_agent_task

router = APIRouter(prefix="/api/agent", tags=["agent"])


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


@router.post("/task", response_model=AgentTaskResponse)
async def execute_agent_task(request: AgentTaskRequest) -> AgentTaskResponse:
    """
    통합 에이전트 작업 실행.
    
    지원 작업 유형:
    - diagnose_repo: 저장소 건강도 진단
    - build_onboarding_plan: 온보딩 플랜 생성
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
