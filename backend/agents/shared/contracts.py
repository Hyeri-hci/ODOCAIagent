"""
Contract definitions for the Agentic Orchestrator.

Phase 1: AnswerContract - Enforces sources for LLM responses.
Phase 2: PlanStep, SupervisorOutput - For planning and reasoning traceability.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# Answer Contract (Enforces sources for LLM responses)

class AnswerContract(BaseModel):
    """LLM Response Contract: All answers must specify their sources."""
    text: str = Field(..., min_length=1, description="Response text for the user.")
    sources: List[str] = Field(
        default_factory=list, 
        description="List of referenced artifact IDs."
    )
    source_kinds: List[str] = Field(
        default_factory=list,
        description="List of referenced artifact kinds (e.g., diagnosis_raw, python_metrics)."
    )
    
    @field_validator("sources", "source_kinds")
    @classmethod
    def validate_non_empty_lists(cls, v: List[str], info) -> List[str]:
        # Allows empty lists, but lengths of sources and source_kinds must match.
        return v
    
    def validate_sources_match(self) -> bool:
        """Validates that the lengths of sources and source_kinds match."""
        return len(self.sources) == len(self.source_kinds)


# Plan Step & Supervisor Output

class AgentType(str, Enum):
    """Available Agent types."""
    DIAGNOSIS = "diagnosis"
    SECURITY = "security"
    RECOMMENDATION = "recommendation"
    COMPARE = "compare"
    ONEPAGER = "onepager"
    SMALLTALK = "smalltalk"  # Lightweight agent for greetings/chitchat
    HELP = "help"            # Lightweight agent for help messages
    OVERVIEW = "overview"    # Lightweight agent for repo overviews


class ErrorAction(str, Enum):
    """Policy for handling errors."""
    RETRY = "retry"           # Retry with backoff/timeout adjustment
    FALLBACK = "fallback"     # Rerun with fallback parameters/path
    ASK_USER = "ask_user"     # Confirm with the user (for disambiguation)
    ABORT = "abort"           # Abort execution


class PlanStep(BaseModel):
    """A single step in an execution plan."""
    id: str = Field(..., description="Unique ID for the step (e.g., fetch_diag, calc_metrics).")
    agent: AgentType = Field(..., description="The type of agent to execute.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the agent.")
    needs: List[str] = Field(default_factory=list, description="List of preceding step IDs.")
    on_error: ErrorAction = Field(
        default=ErrorAction.FALLBACK, 
        description="Policy to apply on error."
    )


class SupervisorPlanOutput(BaseModel):
    """
    The output of the supervisor's planning phase.
    
    `reasoning_trace` is for internal logging only and should not be included in user responses.
    """
    reasoning_trace: str = Field(
        default="",
        description="Internal reasoning log (why this plan/node was chosen)."
    )
    intent: Literal[
        "explain", 
        "task_recommendation", 
        "compare", 
        "onepager", 
        "disambiguation"
    ] = Field(..., description="The final classified intent.")
    plan: List[PlanStep] = Field(
        default_factory=list, 
        description="The list of steps to execute."
    )
    artifacts_required: List[str] = Field(
        default_factory=list,
        description="Hints for required artifact kinds/IDs."
    )
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0, 
        description="Confidence score for the intent classification."
    )


class AgenticSupervisorOutput(BaseModel):
    """The final output of the Agentic Supervisor."""
    answer: AnswerContract = Field(..., description="The response to show the user.")
    intent: str = Field(..., description="The classified intent.")
    plan_executed: List[str] = Field(
        default_factory=list,
        description="List of executed PlanStep IDs."
    )
    artifacts_used: List[str] = Field(
        default_factory=list,
        description="List of referenced Artifact IDs."
    )
    session_id: str = Field(default="", description="Session ID.")
    turn_id: str = Field(default="", description="Turn ID.")
    execution_time_ms: float = Field(default=0.0, description="Total execution time in ms.")
    status: Literal["success", "partial", "error", "disambiguation"] = Field(
        default="success",
        description="The execution status."
    )
    error_message: Optional[str] = Field(default=None, description="Error message, if any.")


# Error Policy & Inference Hints

class ErrorKind(str, Enum):
    """Enumeration of error types."""
    PERMISSION = "permission"       # Permission error (e.g., private repo)
    NOT_FOUND = "not_found"         # Repository or resource not found
    NO_DATA = "no_data"             # Insufficient data (e.g., 0 commits)
    TIMEOUT = "timeout"             # Network timeout
    RATE_LIMIT = "rate_limit"       # API rate limit exceeded
    INVALID_INPUT = "invalid_input" # Invalid user input
    UNKNOWN = "unknown"             # Unknown error


# Default policy for each error kind
ERROR_POLICY: Dict[ErrorKind, ErrorAction] = {
    ErrorKind.PERMISSION: ErrorAction.ASK_USER,
    ErrorKind.NOT_FOUND: ErrorAction.ASK_USER,
    ErrorKind.NO_DATA: ErrorAction.FALLBACK,
    ErrorKind.TIMEOUT: ErrorAction.RETRY,
    ErrorKind.RATE_LIMIT: ErrorAction.RETRY,
    ErrorKind.INVALID_INPUT: ErrorAction.ASK_USER,
    ErrorKind.UNKNOWN: ErrorAction.ABORT,
}


class InferenceHints(BaseModel):
    """Output of the missing option inference step."""
    repo_guess: Optional[str] = Field(
        default=None, 
        description="Inferred repository (owner/repo format)."
    )
    owner: Optional[str] = None
    name: Optional[str] = None
    branch: str = Field(default="main", description="Default branch.")
    window_days: int = Field(default=90, description="Activity analysis window in days.")
    confidence: float = Field(
        default=0.0, 
        ge=0.0, 
        le=1.0, 
        description="Inference confidence score."
    )
    inferred_fields: List[str] = Field(
        default_factory=list,
        description="List of fields that were inferred."
    )


# Artifact-related types

class ArtifactKind(str, Enum):
    """Enumeration of artifact kinds."""
    DIAGNOSIS_RAW = "diagnosis_raw"
    PYTHON_METRICS = "python_metrics"
    README_ANALYSIS = "readme_analysis"
    ACTIVITY_METRICS = "activity_metrics"
    ONBOARDING_TASKS = "onboarding_tasks"
    SUMMARY = "summary"
    INFERENCE_HINTS = "inference_hints"
    PLOT = "plot"
    TABLE = "table"


class ArtifactRef(BaseModel):
    """A reference to an artifact."""
    id: str = Field(..., description="Unique ID of the artifact (sha256 based).")
    kind: ArtifactKind = Field(..., description="The kind of artifact.")
    session_id: str = Field(..., description="Session ID.")
    turn_id: Optional[str] = Field(default=None, description="Turn ID.")


# Agent Error

class AgentError(Exception):
    """Custom exception for errors during Agent execution."""
    
    def __init__(
        self, 
        message: str, 
        kind: ErrorKind = ErrorKind.UNKNOWN,
        suggested_fallback: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.kind = kind
        self._suggested_fallback = suggested_fallback or {}
    
    def suggested_fallback(self) -> Dict[str, Any]:
        """Provides suggested fallback parameters."""
        return self._suggested_fallback
