"""Plan models: PlanStep, Plan, StepResult for Agentic Planning."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PlanStatus(str, Enum):
    """Execution status for a plan."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ABORTED = "aborted"
    ASK_USER = "ask_user"


class StepStatus(str, Enum):
    """Execution status for a single step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    RETRYING = "retrying"


class ErrorPolicy(str, Enum):
    """Policy for handling step errors."""
    RETRY = "retry"
    FALLBACK = "fallback"
    ASK_USER = "ask_user"
    ABORT = "abort"


class ReplanReason(str, Enum):
    """Reason for triggering re-planning."""
    STEP_FAILED = "step_failed"
    MISSING_ARTIFACT = "missing_artifact"
    TIMEOUT = "timeout"
    USER_REQUEST = "user_request"
    CONFIDENCE_LOW = "confidence_low"


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: str                                      # Unique ID (e.g., "fetch_diag", "calc_score")
    runner: str                                  # Runner name (e.g., "diagnosis", "compare")
    params: Dict[str, Any] = field(default_factory=dict)
    needs: List[str] = field(default_factory=list)  # Preceding step IDs
    on_error: ErrorPolicy = ErrorPolicy.FALLBACK
    timeout_sec: float = 30.0
    max_retries: int = 1
    
    # Runtime state
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_time_ms: float = 0.0
    
    def is_ready(self, completed_steps: set[str]) -> bool:
        """Checks if all dependencies are satisfied."""
        return all(dep in completed_steps for dep in self.needs)
    
    def mark_running(self) -> None:
        self.status = StepStatus.RUNNING
    
    def mark_success(self, result: Dict[str, Any], time_ms: float) -> None:
        self.status = StepStatus.SUCCESS
        self.result = result
        self.execution_time_ms = time_ms
    
    def mark_failed(self, error: str, time_ms: float) -> None:
        self.status = StepStatus.FAILED
        self.error_message = error
        self.execution_time_ms = time_ms
    
    def mark_skipped(self, reason: str) -> None:
        self.status = StepStatus.SKIPPED
        self.error_message = reason


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    status: StepStatus
    result: Optional[Dict[str, Any]] = None
    artifacts_out: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    
    @property
    def success(self) -> bool:
        return self.status == StepStatus.SUCCESS


@dataclass
class Plan:
    """Execution plan with steps, dependencies, and error handling."""
    id: str
    intent: str
    sub_intent: str
    steps: List[PlanStep] = field(default_factory=list)
    artifacts_required: List[str] = field(default_factory=list)
    reasoning_trace: str = ""
    
    # Runtime state
    status: PlanStatus = PlanStatus.PENDING
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    artifacts_collected: Dict[str, Any] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    total_execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    replan_count: int = 0
    
    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Gets a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_completed_steps(self) -> set[str]:
        """Returns set of completed step IDs."""
        return {
            step.id for step in self.steps 
            if step.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)
        }
    
    def get_ready_steps(self) -> List[PlanStep]:
        """Returns steps that are ready to execute (deps satisfied, not started)."""
        completed = self.get_completed_steps()
        return [
            step for step in self.steps
            if step.status == StepStatus.PENDING and step.is_ready(completed)
        ]
    
    def get_failed_steps(self) -> List[PlanStep]:
        """Returns steps that failed."""
        return [step for step in self.steps if step.status == StepStatus.FAILED]
    
    def is_complete(self) -> bool:
        """Checks if all steps are done (success, skipped, or failed with abort)."""
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.RETRYING):
                return False
        return True
    
    def all_success(self) -> bool:
        """Checks if all steps succeeded or were skipped."""
        return all(
            step.status in (StepStatus.SUCCESS, StepStatus.SKIPPED)
            for step in self.steps
        )
    
    def mark_running(self) -> None:
        self.status = PlanStatus.RUNNING
    
    def mark_success(self) -> None:
        self.status = PlanStatus.SUCCESS
    
    def mark_partial(self, error: str) -> None:
        self.status = PlanStatus.PARTIAL
        self.error_message = error
    
    def mark_failed(self, error: str) -> None:
        self.status = PlanStatus.FAILED
        self.error_message = error
    
    def mark_ask_user(self, question: str) -> None:
        self.status = PlanStatus.ASK_USER
        self.error_message = question
    
    def add_step_result(self, result: StepResult) -> None:
        """Records a step result and updates the corresponding step."""
        self.step_results[result.step_id] = result
        step = self.get_step(result.step_id)
        if step:
            step.status = result.status
            step.result = result.result
            step.error_message = result.error_message
            step.execution_time_ms = result.execution_time_ms
        
        if result.step_id not in self.execution_order:
            self.execution_order.append(result.step_id)


# Step Registry: maps runner names to execution functions
StepRunner = Callable[[PlanStep, Dict[str, Any]], StepResult]
STEP_RUNNERS: Dict[str, StepRunner] = {}


def register_step_runner(name: str, runner: StepRunner) -> None:
    """Registers a step runner function."""
    STEP_RUNNERS[name] = runner


def get_step_runner(name: str) -> Optional[StepRunner]:
    """Gets a step runner by name."""
    return STEP_RUNNERS.get(name)
