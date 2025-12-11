"""
세션 관련 노드
"""

from typing import Dict, Any
import logging

from backend.agents.supervisor.models import SupervisorState
from backend.common.session import get_session_store

logger = logging.getLogger(__name__)


async def load_or_create_session_node(state: SupervisorState) -> Dict[str, Any]:
    """세션 로드 또는 생성"""
    session_store = get_session_store()
    
    session_id = state.get("session_id")
    
    if session_id:
        # 기존 세션 로드
        session = session_store.get_session(session_id)
        if session:
            logger.info(f"Session loaded: {session_id}")
            return {
                "is_new_session": False,
                "conversation_history": session.conversation_history,
                "accumulated_context": dict(session.accumulated_context)
            }
        else:
            logger.warning(f"Session not found or expired: {session_id}")
    
    # 새 세션 생성
    session = session_store.create_session(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main")
    )
    
    logger.info(f"New session created: {session.session_id}")
    
    return {
        "session_id": session.session_id,
        "is_new_session": True,
        "conversation_history": [],
        "accumulated_context": {}
    }
