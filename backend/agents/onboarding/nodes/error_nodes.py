"""
Onboarding Agent Error Nodes
에러 처리를 담당하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.onboarding.models import OnboardingState, OnboardingOutput

logger = logging.getLogger(__name__)

async def error_handler_node(state: OnboardingState) -> Dict[str, Any]:
    """에러 발생 시 안전한 결과 반환"""
    logger.warning(f"[Onboarding Agent] Error handler triggered: {state.get('error')}")
    
    repo_id = f"{state['owner']}/{state['repo']}"
    error_msg = state.get("error", "Unknown error occurred")
    
    # None 체크를 포함한 안전한 기본값 설정
    candidate_issues = state.get("candidate_issues") or []
    plan = state.get("plan") or []
    
    # 에러 결과 생성
    result = OnboardingOutput(
        repo_id=repo_id,
        experience_level=state.get("experience_level", "beginner"),
        candidate_issues=candidate_issues,
        plan=plan,
        summary=f"온보딩 플랜 생성 중 오류가 발생했습니다: {error_msg}",
        error=error_msg
    )
    
    return {
        "result": result.dict(),
        "execution_path": (state.get("execution_path") or "") + " → error_handler"
    }
