"""Step Runners: Actual execution logic for each step type."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from backend.agents.supervisor.planner.models import (
    PlanStep,
    StepResult,
    StepStatus,
)
from typing import cast

logger = logging.getLogger(__name__)


# Registry of step runners
_STEP_RUNNERS: Dict[str, Callable[[PlanStep, Dict[str, Any]], StepResult]] = {}


def register_step_runner(
    name: str, 
    runner: Callable[[PlanStep, Dict[str, Any]], StepResult]
) -> None:
    """Registers a step runner."""
    _STEP_RUNNERS[name] = runner
    logger.debug(f"Registered step runner: {name}")


def get_step_runner(name: str) -> Optional[Callable[[PlanStep, Dict[str, Any]], StepResult]]:
    """Gets a step runner by name."""
    return _STEP_RUNNERS.get(name)


# Diagnosis Runner
def diagnosis_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Runs diagnosis for a repository."""
    from backend.agents.supervisor.runners import DiagnosisRunner
    
    start_time = time.time()
    params = inputs.get("params", {})
    state = inputs.get("state", {})
    
    repo = params.get("repo") or state.get("repo")
    if not repo:
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error_message="저장소 정보가 없습니다.",
        )
    
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}"
    user_context = params.get("user_context") or state.get("user_context", {})
    
    runner = DiagnosisRunner(repo_id=repo_id, user_context=user_context)
    result = runner.run()
    
    elapsed = (time.time() - start_time) * 1000
    
    if not result.success:
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error_message=result.error_message,
            execution_time_ms=elapsed,
        )
    
    diagnosis_result = runner.get_diagnosis_result()
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result={"diagnosis_result": diagnosis_result},
        artifacts_out=result.artifacts_out,
        execution_time_ms=elapsed,
    )


# Compare Runner
def compare_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Compares two repositories."""
    from backend.agents.supervisor.runners import CompareRunner
    
    start_time = time.time()
    params = inputs.get("params", {})
    step_outputs = inputs.get("step_outputs", {})
    
    # Get diagnosis results from previous steps
    repo_a_result = step_outputs.get("fetch_repo_a", {}).get("diagnosis_result")
    repo_b_result = step_outputs.get("fetch_repo_b", {}).get("diagnosis_result")
    
    repo_a = params.get("repo_a")
    repo_b = params.get("repo_b")
    
    if not repo_a or not repo_b:
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error_message="비교할 두 저장소 정보가 필요합니다.",
        )
    
    repo_a_id = f"{repo_a.get('owner', '')}/{repo_a.get('name', '')}"
    repo_b_id = f"{repo_b.get('owner', '')}/{repo_b.get('name', '')}"
    user_context = params.get("user_context", {})
    
    runner = CompareRunner(
        repo_a=repo_a_id,
        repo_b=repo_b_id,
        user_context=user_context,
    )
    
    # Inject pre-fetched results if available via set_artifact
    if repo_a_result:
        runner.set_artifact("diagnosis_a", repo_a_result)
    if repo_b_result:
        runner.set_artifact("diagnosis_b", repo_b_result)
    
    result = runner.run()
    elapsed = (time.time() - start_time) * 1000
    
    if not result.success:
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error_message=result.error_message,
            execution_time_ms=elapsed,
        )
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result={"compare_result": result.answer.text if result.answer else ""},
        artifacts_out=result.artifacts_out,
        execution_time_ms=elapsed,
    )


# Followup Runner
def followup_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Handles follow-up explanations via summarize_node."""
    from backend.agents.supervisor.nodes.summarize_node import summarize_node_v1
    from backend.agents.supervisor.models import SupervisorState
    
    start_time = time.time()
    params = inputs.get("params", {})
    state = dict(inputs.get("state", {}))
    
    # Set intent for followup
    state["intent"] = "followup"
    state["sub_intent"] = params.get("mode", "explain")
    
    result = summarize_node_v1(cast(SupervisorState, state))
    elapsed = (time.time() - start_time) * 1000
    
    if result.get("error_message"):
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error_message=result["error_message"],
            execution_time_ms=elapsed,
        )
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result=result,
        execution_time_ms=elapsed,
    )


# Overview Runner
def overview_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Generates repository overview via summarize_node."""
    from backend.agents.supervisor.nodes.summarize_node import summarize_node_v1
    from backend.agents.supervisor.models import SupervisorState
    
    start_time = time.time()
    state = dict(inputs.get("state", {}))
    
    # Set intent for overview
    state["intent"] = "overview"
    state["sub_intent"] = "repo"
    
    result = summarize_node_v1(cast(SupervisorState, state))
    elapsed = (time.time() - start_time) * 1000
    
    if result.get("error_message"):
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error_message=result["error_message"],
            execution_time_ms=elapsed,
        )
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result=result,
        execution_time_ms=elapsed,
    )


# Smalltalk Runner
def smalltalk_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Handles smalltalk/greetings via summarize_node."""
    from backend.agents.supervisor.nodes.summarize_node import summarize_node_v1
    from backend.agents.supervisor.models import SupervisorState
    
    start_time = time.time()
    params = inputs.get("params", {})
    state = dict(inputs.get("state", {}))
    
    # Set intent for smalltalk
    state["intent"] = "smalltalk"
    state["sub_intent"] = params.get("mode", "greeting")
    
    result = summarize_node_v1(cast(SupervisorState, state))
    elapsed = (time.time() - start_time) * 1000
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result=result,
        execution_time_ms=elapsed,
    )


# Help Runner
def help_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Handles help messages via summarize_node."""
    from backend.agents.supervisor.nodes.summarize_node import summarize_node_v1
    from backend.agents.supervisor.models import SupervisorState
    
    start_time = time.time()
    state = dict(inputs.get("state", {}))
    
    # Set intent for help
    state["intent"] = "help"
    state["sub_intent"] = "getting_started"
    
    result = summarize_node_v1(cast(SupervisorState, state))
    elapsed = (time.time() - start_time) * 1000
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result=result,
        execution_time_ms=elapsed,
    )


# Chat Runner (fallback)
def chat_step_runner(step: PlanStep, inputs: Dict[str, Any]) -> StepResult:
    """Handles general chat."""
    start_time = time.time()
    state = inputs.get("state", {})
    query = state.get("user_query", "")
    
    # Simple fallback response
    result = {
        "llm_summary": f"질문을 이해했습니다. 더 구체적인 저장소 URL과 함께 질문해 주시면 상세한 분석을 제공해 드릴 수 있습니다.",
        "answer_kind": "chat",
    }
    
    elapsed = (time.time() - start_time) * 1000
    
    return StepResult(
        step_id=step.id,
        status=StepStatus.SUCCESS,
        result=result,
        execution_time_ms=elapsed,
    )


# Register all default runners
def register_default_runners() -> None:
    """Registers all default step runners."""
    register_step_runner("diagnosis", diagnosis_step_runner)
    register_step_runner("compare", compare_step_runner)
    register_step_runner("followup", followup_step_runner)
    register_step_runner("overview", overview_step_runner)
    register_step_runner("smalltalk", smalltalk_step_runner)
    register_step_runner("help", help_step_runner)
    register_step_runner("chat", chat_step_runner)


# Auto-register on import
register_default_runners()
