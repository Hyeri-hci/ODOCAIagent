"""Type definitions for the Supervisor agent state (V1 simplified)."""
from __future__ import annotations

from typing import Any, Literal, TypedDict, List, Dict


# V1 Core Intents (6 categories)
SupervisorIntent = Literal["analyze", "followup", "general_qa", "smalltalk", "help", "overview"]

# V1 Core SubIntents
SubIntent = Literal[
    "health",          # analyze: repo health diagnosis
    "onboarding",      # analyze: onboarding-focused diagnosis
    "compare",         # analyze: compare two repos
    "onepager",        # analyze: one-page summary
    "explain",         # followup: explain scores/metrics
    "evidence",        # followup: explain evidence/reasoning
    "refine",          # followup: refine/filter previous results
    "chat",            # general_qa: general conversation
    "concept",         # general_qa: concept explanation
    "greeting",        # smalltalk: greeting response
    "chitchat",        # smalltalk: casual chat
    "getting_started", # help: usage guide
    "repo",            # overview: repo introduction
]

# V1 Answer kinds for UI badges
AnswerKind = Literal[
    "report",    # analyze → health/onboarding
    "compare",   # analyze → compare
    "onepager",  # analyze → onepager
    "explain",   # followup → explain/evidence
    "refine",    # followup → refine tasks
    "chat",      # general_qa → chat
    "concept",   # general_qa → concept
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


class PrevTurnContext(TypedDict, total=False):
    """Context from previous turn for follow-up handling."""
    intent: SupervisorIntent
    sub_intent: SubIntent
    answer_kind: AnswerKind
    repo_id: str
    artifacts: Dict[str, Any]  # scores, labels, tasks 등
    sources: List[str]


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
    compare_repo: RepoInfo  # Second repo for compare
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
    
    # === Idempotency ===
    answer_id: str  # Unique ID for deduplication (frontend key)
    answer_contract: Dict[str, Any]  # AnswerContract serialized
    
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


# Idempotency Store for duplicate prevention
class IdempotencyStore:
    """In-memory store for idempotent execution (turn_id + step_id → result)."""
    
    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._store: Dict[str, Any] = {}  # key = f"{turn_id}:{step_id}"
        self._answer_ids: Dict[str, str] = {}  # key → answer_id
    
    def _make_key(self, turn_id: str, step_id: str) -> str:
        return f"{turn_id}:{step_id}"
    
    def store_result(self, turn_id: str, step_id: str, result: Any) -> str:
        """Stores result and returns answer_id."""
        if not self._enabled:
            import uuid
            return f"ans_{uuid.uuid4().hex[:12]}"
        
        key = self._make_key(turn_id, step_id)
        self._store[key] = result
        
        # Generate or reuse answer_id
        if key not in self._answer_ids:
            import uuid
            self._answer_ids[key] = f"ans_{uuid.uuid4().hex[:12]}"
        
        return self._answer_ids[key]
    
    def get_result(self, turn_id: str, step_id: str) -> Optional[Any]:
        """Gets cached result if exists."""
        if not self._enabled:
            return None
        
        key = self._make_key(turn_id, step_id)
        return self._store.get(key)
    
    def get_answer_id(self, turn_id: str, step_id: str) -> Optional[str]:
        """Gets answer_id if exists."""
        key = self._make_key(turn_id, step_id)
        return self._answer_ids.get(key)
    
    def clear(self) -> None:
        """Clears all stored results."""
        self._store.clear()
        self._answer_ids.clear()