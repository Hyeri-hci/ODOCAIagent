"""Type definitions for the Supervisor agent state."""
from __future__ import annotations

from typing import Any, Literal, TypedDict, List, Optional, Dict


SupervisorIntent = Literal["analyze", "followup", "general_qa", "smalltalk", "help", "overview"]

SubIntent = Literal[
    "health",
    "onboarding",
    "compare",
    "explain",
    "refine",
    "concept",          # Explain a metric/concept
    "chat",             # General conversation
    "greeting",         # Smalltalk: greeting
    "chitchat",         # Smalltalk: chitchat
    "getting_started",  # Help: getting started
    "repo",             # Overview: repository summary
]

# Routing mode: Fast Chat vs. Expert Tool
RoutingMode = Literal["fast_chat", "expert_tool"]

# Kind of answer for UI badges
AnswerKind = Literal[
    "report",    # Diagnosis report (analyze → health/onboarding/compare)
    "explain",   # Score explanation (followup → explain)
    "refine",    # Task filtering (followup → refine)
    "concept",   # Concept explanation (general_qa → concept)
    "chat",      # General conversation (general_qa → chat)
    "greeting",  # Greeting response (smalltalk)
    "help",      # Help message (help)
    "overview",  # Repo overview (overview)
]

# Target for explanation in 'explain' mode
ExplainTarget = Literal[
    "metric",              # Explain scores/metrics (based on diagnosis_result)
    "task_recommendation", # Explain rationale for onboarding tasks
    "general",             # General conversation (no quantitative scores)
]

VALID_INTENTS: List[SupervisorIntent] = [
    "analyze", "followup", "general_qa", "smalltalk", "help", "overview"
]
VALID_SUB_INTENTS: List[SubIntent] = [
    "health", "onboarding", "compare", "explain", "refine", 
    "concept", "chat", "greeting", "chitchat", "getting_started", "repo"
]

# Default values
DEFAULT_INTENT: SupervisorIntent = "analyze"
DEFAULT_SUB_INTENT: SubIntent = "health"


class UserProfile(TypedDict, total=False):
    """User profile information persisted within a session."""
    level: Literal["beginner", "intermediate", "advanced"]  # Technical skill level
    interests: List[str]   # Keywords of interest (e.g., react, security, python)
    persona: Literal["simple", "detailed", "helpful"]  # Preferred response style


# For legacy compatibility (mapping 7 old intents to the new structure)
SupervisorTaskType = Literal[
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
    "concept_qa_metric",
    "concept_qa_process",
]

# Legacy task_type -> (intent, sub_intent) mapping
LEGACY_TASK_TYPE_MAP: dict[str, tuple[SupervisorIntent, SubIntent]] = {
    "diagnose_repo_health": ("analyze", "health"),
    "diagnose_repo_onboarding": ("analyze", "onboarding"),
    "compare_two_repos": ("analyze", "compare"),
    "refine_onboarding_tasks": ("followup", "refine"),
    "explain_scores": ("followup", "explain"),
    "concept_qa_metric": ("general_qa", "concept"),
    "concept_qa_process": ("general_qa", "concept"),
}


def convert_legacy_task_type(task_type: str) -> tuple[SupervisorIntent, SubIntent]:
    """Converts a legacy task_type to the new (intent, sub_intent) structure."""
    return LEGACY_TASK_TYPE_MAP.get(task_type, (DEFAULT_INTENT, DEFAULT_SUB_INTENT))

# Task types for each agent, to be detailed in their respective modules.
DiagnosisTaskType = str
SecurityTaskType = str
RecommendTaskType = str


class DiagnosisNeeds(TypedDict):
    """Flags to determine which phases the Diagnosis Agent should run."""
    need_health: bool
    need_readme: bool
    need_activity: bool
    need_onboarding: bool


def diagnosis_needs_from_task_type(task_type: str) -> DiagnosisNeeds:
    """Creates DiagnosisNeeds from a diagnosis_task_type."""
    # NOTE: need_onboarding is always True.
    # Tasks are always computed, but the number of tasks shown in the summary varies.
    # - health mode: show 3 tasks
    # - onboarding mode: show 5+ tasks
    return {
        "need_health": True,
        "need_readme": True,
        "need_activity": True,
        "need_onboarding": True,
    }


class RepoInfo(TypedDict):
    """Basic repository information."""
    owner: str
    name: str
    url: str


class UserContext(TypedDict, total=False):
    """User context information."""
    level: Literal["beginner", "intermediate", "advanced"]
    goal: str
    time_budget_hours: float
    preferred_language: str


class Turn(TypedDict):
    """A single turn in a conversation."""
    role: Literal["user", "assistant"]
    content: str


class SupervisorState(TypedDict, total=False):
    """The state of the Supervisor Agent workflow."""
    # Input
    user_query: str
    
    # New intent structure (v2)
    intent: SupervisorIntent
    sub_intent: SubIntent
    
    # Legacy compatibility (7 old intents)
    task_type: SupervisorTaskType

    # Repository information
    repo: RepoInfo
    compare_repo: RepoInfo
    repos: List[RepoInfo] # For comparing multiple repos in the future

    # User context
    user_context: UserContext
    
    # User profile (persisted in state for the session)
    user_profile: UserProfile

    # Task types for each agent (set by the mapping node)
    diagnosis_task_type: DiagnosisTaskType
    diagnosis_needs: DiagnosisNeeds
    security_task_type: SecurityTaskType
    recommend_task_type: RecommendTaskType

    # Agent execution results
    diagnosis_result: dict[str, Any]
    compare_diagnosis_result: dict[str, Any]

    # Final response
    llm_summary: str
    
    # Response metadata for UI
    answer_kind: AnswerKind
    last_brief: str
    
    # Target for 'explain' mode (used in followup/explain)
    explain_target: ExplainTarget
    explain_metrics: list[str]
    
    # Error message for direct response without LLM call
    error_message: str

    # Conversation history
    history: list[Turn]

    # Fields for multi-turn state management
    last_repo: RepoInfo
    last_intent: SupervisorIntent
    last_sub_intent: SubIntent
    last_answer_kind: AnswerKind
    last_explain_target: ExplainTarget
    last_task_list: list[dict]
    
    # Classification result for the current turn
    is_followup: bool
    followup_type: Literal[
        "refine_easier",
        "refine_harder",
        "refine_different",
        "ask_detail",
        "compare_similar",
        "continue_same",
        None
    ]
    
    # Progress callback for UI updates
    _progress_callback: Any
    
    # Agentic Orchestrator fields (v2)
    plan_output: Any  # SupervisorPlanOutput type, 'Any' to prevent circular import
    
    # Active Inference results
    _inference_hints: Dict[str, Any]
    _inference_confidence: float
    _needs_disambiguation: bool
    
    # Plan execution results
    _plan_execution_result: Dict[str, Any]
    _plan_status: str  # completed | partial | aborted | disambiguation
    
    # Final Agentic output
    _agentic_output: Dict[str, Any]
    
    # Internal reasoning logs (not exposed to user)
    _reasoning_trace: str
    _mapped_intent: str
    
    # Intent classification confidence
    _intent_confidence: float
    
    # Session/Turn IDs for observability
    _session_id: str
    _turn_id: str


def decide_explain_target(state: SupervisorState) -> ExplainTarget:
    """Decides the target for 'explain' mode based on the previous turn (for legacy compatibility)."""
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