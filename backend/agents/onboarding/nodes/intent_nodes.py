"""
Onboarding Agent Intent Nodes
온보딩 에이전트의 의도를 파악하는 노드입니다.
"""

import logging
from typing import Dict, Any, Callable
from functools import wraps

from backend.agents.onboarding.models import OnboardingState

logger = logging.getLogger(__name__)

# === 예외 처리 데코레이터 ===

def safe_node(default_updates: Dict[str, Any] = None):
    """
    노드 함수에 안전한 예외 처리를 추가하는 데코레이터
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: OnboardingState) -> Dict[str, Any]:
            node_name = func.__name__.replace("_node", "")
            try:
                return await func(state)
            except Exception as e:
                logger.error(f"[Onboarding Agent] {node_name} failed: {e}", exc_info=True)
                
                updates = default_updates.copy() if default_updates else {}
                updates["error"] = str(e)
                updates["execution_path"] = (state.get("execution_path") or "") + f" → {node_name}(ERROR)"
                
                return updates
        return wrapper
    return decorator

@safe_node(default_updates={"experience_level": "beginner", "user_context": {}})
async def parse_intent_node(state: OnboardingState) -> Dict[str, Any]:
    """온보딩 의도 파싱 - 경험 수준 및 컨텍스트 처리"""
    logger.info(f"[Onboarding Agent] Parsing intent for {state['owner']}/{state['repo']}")
    
    experience_level = state.get("experience_level", "beginner")
    user_context = state.get("user_context", {})
    
    # 사용자 메시지에서 추가 힌트 추출 (있는 경우)
    user_message = state.get("user_message") or ""
    
    # 경험 수준 키워드 감지
    if "고급" in user_message or "advanced" in user_message.lower():
        experience_level = "advanced"
    elif "중급" in user_message or "intermediate" in user_message.lower():
        experience_level = "intermediate"
    elif "초보" in user_message or "beginner" in user_message.lower():
        experience_level = "beginner"
    
    logger.info(f"[Onboarding Agent] Determined experience level: {experience_level}")
    
    return {
        "experience_level": experience_level,
        "user_context": user_context,
        "execution_path": "onboarding_graph:parse_intent"
    }
