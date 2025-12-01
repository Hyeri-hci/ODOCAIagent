"""Type definitions for the Supervisor agent state (V1 simplified)."""
from __future__ import annotations

from typing import Any, Literal, TypedDict, List, Dict


# V1 Core Intents (4 main categories)
SupervisorIntent = Literal["analyze", "followup", "general_qa", "smalltalk"]

# V1 Core SubIntents
SubIntent = Literal[
    "health",       # analyze: repo health diagnosis
    "onboarding",   # analyze: onboarding-focused diagnosis
    "explain",      # followup: explain scores/metrics
    "chat",         # general_qa: general conversation
    "greeting",     # smalltalk: greeting response
]

# V1 Answer kinds for UI badges
AnswerKind = Literal[
    "report",    # analyze → health/onboarding
    "explain",   # followup → explain
    "chat",      # general_qa → chat
    "greeting",  # smalltalk → greeting
]

# V1 Explain target types
ExplainTarget = Literal[
    "metric",              # Explain scores/metrics
    "task_recommendation", # Explain onboarding tasks
    "general",             # General explanation
]

# Default values
DEFAULT_INTENT: SupervisorIntent = "analyze"
DEFAULT_SUB_INTENT: SubIntent = "health"


class RepoInfo(TypedDict):
    """Basic repository information."""
    owner: str
    name: str
    url: str


class UserContext(TypedDict, total=False):
    """User context for personalization."""
    level: Literal["beginner", "intermediate", "advanced"]
    preferred_language: str


class SupervisorState(TypedDict, total=False):
    """V1 Supervisor State - minimal fields only."""
    
    # === Input ===
    user_query: str
    repo: RepoInfo
    user_context: UserContext
    
    # === Routing/Meta ===
    intent: SupervisorIntent
    sub_intent: SubIntent
    answer_kind: AnswerKind
    
    # === Agent Results ===
    diagnosis_result: Dict[str, Any]
    llm_summary: str
    last_brief: str
    
    # === Follow-up State ===
    last_answer_kind: AnswerKind
    last_explain_target: ExplainTarget
    last_task_list: List[Dict[str, Any]]
    
    # === Error Handling ===
    error_message: str
    
    # === Internal (not exposed to user) ===
    _session_id: str
    _turn_id: str


def decide_explain_target(state: SupervisorState) -> ExplainTarget:
    """Decides explain target based on previous turn state."""
    last_answer_kind = state.get("last_answer_kind")
    last_explain_target = state.get("last_explain_target")
    last_task_list = state.get("last_task_list")
    diagnosis_result = state.get("diagnosis_result")
    
    if last_answer_kind == "report":
        return "metric"
    
    if last_answer_kind == "explain" and last_explain_target == "metric":
        return "metric"
    
    if last_explain_target == "task_recommendation":
        return "task_recommendation"
    
    if last_task_list:
        return "task_recommendation"
    
    if diagnosis_result and isinstance(diagnosis_result, dict):
        if diagnosis_result.get("scores"):
            return "metric"
        if diagnosis_result.get("onboarding_tasks"):
            return "task_recommendation"
    
    return "general"