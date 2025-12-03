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


# Runner Output Contract (Unified output for all runners/agents)
class RunnerStatus(str, Enum):
    """Execution status for runners."""
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    SKIPPED = "skipped"


class RunnerOutput(BaseModel):
    """Unified output contract for all agent runners."""
    status: RunnerStatus = Field(
        default=RunnerStatus.SUCCESS,
        description="Execution status."
    )
    result: Dict[str, Any] = Field(
        default_factory=dict,
        description="The main result payload."
    )
    artifacts_out: List[str] = Field(
        default_factory=list,
        description="List of artifact IDs created during execution."
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (timing, token count, etc.)."
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is ERROR."
    )
    
    @classmethod
    def success(
        cls, 
        result: Dict[str, Any], 
        artifacts_out: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> "RunnerOutput":
        """Factory for successful output."""
        return cls(
            status=RunnerStatus.SUCCESS,
            result=result,
            artifacts_out=artifacts_out or [],
            meta=meta or {}
        )
    
    @classmethod
    def error(cls, message: str, meta: Optional[Dict[str, Any]] = None) -> "RunnerOutput":
        """Factory for error output."""
        return cls(
            status=RunnerStatus.ERROR,
            result={},
            error_message=message,
            meta=meta or {}
        )


# Answer Contract Validator
def validate_answer_contract(answer: AnswerContract, enforce: bool = True) -> bool:
    """
    Validates the AnswerContract.
    
    Args:
        answer: The answer to validate
        enforce: If True, raises ValueError on empty sources
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If enforce=True and sources are empty
    """
    if not answer.text or not answer.text.strip():
        if enforce:
            raise ValueError("AnswerContract.text cannot be empty")
        return False
    
    if not answer.validate_sources_match():
        if enforce:
            raise ValueError("AnswerContract.sources and source_kinds length mismatch")
        return False
    
    # Note: Empty sources are allowed for greeting/chat modes
    # The caller should decide whether to enforce non-empty sources
    
    return True


def create_answer_with_sources(
    text: str,
    source_artifacts: List[str],
    source_kinds: Optional[List[str]] = None
) -> AnswerContract:
    """
    Creates an AnswerContract with proper source tracking.
    
    Args:
        text: Response text
        source_artifacts: List of artifact IDs used
        source_kinds: List of artifact kinds (auto-inferred if None)
    """
    if source_kinds is None:
        # Infer kinds from artifact IDs (format: {kind}_{hash})
        source_kinds = []
        for aid in source_artifacts:
            parts = aid.split("_")
            kind = parts[0] if parts else "unknown"
            source_kinds.append(kind)
    
    return AnswerContract(
        text=text,
        sources=source_artifacts,
        source_kinds=source_kinds
    )


# Runner Output Normalization (Null-safe)
def normalize_runner_output(raw: Any) -> RunnerOutput:
    """
    Normalizes any runner output to RunnerOutput contract.
    
    Handles:
    - None -> empty success
    - dict -> RunnerOutput
    - RunnerOutput -> pass-through
    - Exception -> error output
    
    This is the SINGLE normalization point for all runners.
    """
    # None -> empty success
    if raw is None:
        return RunnerOutput.success(result={})
    
    # Already RunnerOutput
    if isinstance(raw, RunnerOutput):
        return raw
    
    # Exception -> error
    if isinstance(raw, Exception):
        return RunnerOutput.error(str(raw))
    
    # Dict -> convert to RunnerOutput
    if isinstance(raw, dict):
        return _normalize_dict_output(raw)
    
    # Unknown type -> wrap in result
    return RunnerOutput.success(result={"value": raw})


def _normalize_dict_output(raw: Dict[str, Any]) -> RunnerOutput:
    """Normalizes a dictionary to RunnerOutput."""
    # Check if already RunnerOutput-like
    if "status" in raw and raw.get("status") in [s.value for s in RunnerStatus]:
        return RunnerOutput(
            status=RunnerStatus(raw.get("status", "success")),
            result=safe_get(raw, "result", {}),
            artifacts_out=safe_get(raw, "artifacts_out", []),
            meta=safe_get(raw, "meta", {}),
            error_message=raw.get("error_message"),
        )
    
    # Check for error indicators
    if raw.get("error") or raw.get("error_message"):
        return RunnerOutput.error(
            message=raw.get("error_message") or raw.get("error") or "Unknown error",
            meta={"original_keys": list(raw.keys())},
        )
    
    # Treat as successful result payload
    return RunnerOutput.success(result=raw)


def safe_get(d: Any, key: str, default: Any = None) -> Any:
    """Null-safe dictionary get. Works with None, non-dict, and missing keys."""
    if d is None:
        return default
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def safe_get_nested(d: Any, *keys: str, default: Any = None) -> Any:
    """Null-safe nested dictionary access."""
    current = d
    for key in keys:
        current = safe_get(current, key)
        if current is None:
            return default
    return current if current is not None else default


# Contract Validation Helpers
class ContractViolation(Exception):
    """Raised when a contract is violated."""
    def __init__(self, message: str, contract_name: str, field: str = ""):
        super().__init__(message)
        self.contract_name = contract_name
        self.field = field


def validate_runner_output(output: RunnerOutput, strict: bool = False) -> bool:
    """
    Validates a RunnerOutput.
    
    Args:
        output: The output to validate
        strict: If True, raises ContractViolation on issues
        
    Returns:
        True if valid
    """
    # Status must be valid
    if output.status not in RunnerStatus:
        if strict:
            raise ContractViolation(
                f"Invalid status: {output.status}",
                "RunnerOutput",
                "status"
            )
        return False
    
    # Error status must have error_message
    if output.status == RunnerStatus.ERROR and not output.error_message:
        if strict:
            raise ContractViolation(
                "ERROR status requires error_message",
                "RunnerOutput",
                "error_message"
            )
        return False
    
    # result must be dict
    if not isinstance(output.result, dict):
        if strict:
            raise ContractViolation(
                f"result must be dict, got {type(output.result)}",
                "RunnerOutput",
                "result"
            )
        return False
    
    return True
