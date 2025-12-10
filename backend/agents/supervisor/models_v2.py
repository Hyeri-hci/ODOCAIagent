"""
Supervisor State V2 - 간소화된 State
세션 기반 대화 지원
"""

from typing import Dict, Any, Optional, List, Literal, TypedDict


class SupervisorStateV2(TypedDict):
    """Supervisor Agent V2 State - TypedDict for LangGraph"""
    
    # 필수 필드
    owner: str
    repo: str
    ref: str
    user_message: str
    is_new_session: bool
    needs_clarification: bool
    awaiting_clarification: bool
    iteration: int
    max_iterations: int
    
    # 선택 필드
    session_id: Optional[str]
    supervisor_intent: Optional[Dict[str, Any]]
    clarification_questions: List[str]
    conversation_history: List[Dict[str, Any]]
    accumulated_context: Dict[str, Any]
    target_agent: Optional[Literal["diagnosis", "onboarding", "security", "chat"]]
    agent_params: Dict[str, Any]
    agent_result: Optional[Dict[str, Any]]
    final_answer: Optional[str]
    suggested_actions: List[Dict[str, Any]]
    next_node_override: Optional[str]
    error: Optional[str]
    trace_id: Optional[str]


# 하위 호환성을 위한 타입 별칭
SupervisorState = SupervisorStateV2
