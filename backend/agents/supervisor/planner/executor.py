"""PlanExecutor: Executes plans with dependency resolution and error handling."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from backend.agents.supervisor.planner.models import (
    Plan,
    PlanStep,
    PlanStatus,
    StepStatus,
    StepResult,
    ErrorPolicy,
    ReplanReason,
)
from backend.common.events import EventType, emit_event

logger = logging.getLogger(__name__)


# Step execution function type
StepExecutor = Callable[[PlanStep, Dict[str, Any]], StepResult]

# Default max retries before escalation
DEFAULT_MAX_RETRIES = 1
MAX_REPLAN_ATTEMPTS = 2


class ExecutionContext:
    """Shared context during plan execution."""
    
    def __init__(self, plan: Plan, state: Dict[str, Any]):
        self.plan = plan
        self.state = state
        self.artifacts: Dict[str, Any] = {}
        self.step_outputs: Dict[str, Any] = {}
        self.replan_triggered = False
        self.ask_user_message: Optional[str] = None
    
    def get_artifact(self, key: str) -> Optional[Any]:
        return self.artifacts.get(key)
    
    def set_artifact(self, key: str, value: Any) -> None:
        self.artifacts[key] = value
    
    def get_step_output(self, step_id: str) -> Optional[Any]:
        return self.step_outputs.get(step_id)


class PlanExecutor:
    """Executes plans with topological ordering and error handling."""
    
    def __init__(
        self,
        step_executors: Optional[Dict[str, StepExecutor]] = None,
        max_parallel: int = 3,
        replan_callback: Optional[Callable[[Plan, ReplanReason], Plan]] = None,
    ):
        self.step_executors = step_executors or {}
        self.max_parallel = max_parallel
        self.replan_callback = replan_callback
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel)
    
    def execute(self, plan: Plan, state: Dict[str, Any]) -> Plan:
        """
        Executes a plan with mixed parallel/serial steps.
        
        Returns the plan with updated status and results.
        """
        start_time = time.time()
        context = ExecutionContext(plan, state)
        
        emit_event(
            EventType.SUPERVISOR_PLAN_BUILT,
            actor="plan_executor",
            outputs={
                "plan_id": plan.id,
                "step_count": len(plan.steps),
                "intent": plan.intent,
            },
        )
        
        plan.mark_running()
        
        try:
            self._execute_steps(context)
        except Exception as e:
            logger.exception(f"Plan execution failed: {e}")
            plan.mark_failed(str(e))
        
        elapsed = (time.time() - start_time) * 1000
        plan.total_execution_time_ms = elapsed
        
        # Determine final status
        if context.ask_user_message:
            plan.mark_ask_user(context.ask_user_message)
        elif plan.all_success():
            plan.mark_success()
        elif plan.get_failed_steps():
            if any(s.status == StepStatus.SUCCESS for s in plan.steps):
                plan.mark_partial("Some steps failed")
            else:
                plan.mark_failed("All steps failed")
        
        emit_event(
            EventType.NODE_FINISHED,
            actor="plan_executor",
            outputs={
                "plan_id": plan.id,
                "status": plan.status.value,
                "execution_time_ms": elapsed,
                "steps_executed": len(plan.execution_order),
            },
        )
        
        # Collect artifacts from successful steps
        plan.artifacts_collected = context.artifacts
        
        return plan
    
    def _execute_steps(self, context: ExecutionContext) -> None:
        """Executes steps in topological order with parallelism."""
        plan = context.plan
        
        while not plan.is_complete():
            ready_steps = plan.get_ready_steps()
            
            if not ready_steps:
                # Check for deadlock (no ready steps but not complete)
                pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
                if pending:
                    logger.error(f"Deadlock detected: {len(pending)} pending steps")
                    for s in pending:
                        s.mark_skipped("Deadlock: dependencies cannot be satisfied")
                break
            
            # Execute ready steps (parallel if multiple)
            if len(ready_steps) == 1:
                self._execute_single_step(ready_steps[0], context)
            else:
                self._execute_parallel_steps(ready_steps, context)
            
            # Check for ask_user escalation
            if context.ask_user_message:
                break
    
    def _execute_single_step(self, step: PlanStep, context: ExecutionContext) -> None:
        """Executes a single step with retry and error handling."""
        step.mark_running()
        
        emit_event(
            EventType.NODE_STARTED,
            actor=f"step:{step.id}",
            inputs={"runner": step.runner, "params": step.params},
        )
        
        result = self._run_step_with_policy(step, context)
        context.plan.add_step_result(result)
        
        if result.success:
            context.step_outputs[step.id] = result.result
            # Store artifacts
            for artifact_id in result.artifacts_out:
                context.artifacts[artifact_id] = result.result
        
        emit_event(
            EventType.NODE_FINISHED,
            actor=f"step:{step.id}",
            outputs={
                "status": result.status.value,
                "execution_time_ms": result.execution_time_ms,
            },
        )
    
    def _execute_parallel_steps(
        self, 
        steps: List[PlanStep], 
        context: ExecutionContext
    ) -> None:
        """Executes multiple independent steps in parallel."""
        futures = {}
        
        for step in steps:
            step.mark_running()
            emit_event(
                EventType.NODE_STARTED,
                actor=f"step:{step.id}",
                inputs={"runner": step.runner, "parallel": True},
            )
            future = self._executor.submit(self._run_step_with_policy, step, context)
            futures[future] = step
        
        for future in concurrent.futures.as_completed(futures):
            step = futures[future]
            try:
                result = future.result(timeout=step.timeout_sec)
                context.plan.add_step_result(result)
                
                if result.success:
                    context.step_outputs[step.id] = result.result
                    for artifact_id in result.artifacts_out:
                        context.artifacts[artifact_id] = result.result
                
            except concurrent.futures.TimeoutError:
                result = StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error_message="Step timed out",
                )
                context.plan.add_step_result(result)
            except Exception as e:
                result = StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error_message=str(e),
                )
                context.plan.add_step_result(result)
            
            emit_event(
                EventType.NODE_FINISHED,
                actor=f"step:{step.id}",
                outputs={"status": step.status.value},
            )
    
    def _run_step_with_policy(
        self, 
        step: PlanStep, 
        context: ExecutionContext
    ) -> StepResult:
        """Runs a step with error policy handling: retry → fallback → ask_user → abort."""
        
        # Try execution with retries
        for attempt in range(step.max_retries + 1):
            start_time = time.time()
            
            try:
                result = self._execute_step(step, context)
                result.execution_time_ms = (time.time() - start_time) * 1000
                
                if result.success:
                    return result
                
                # Handle failure based on policy
                step.retry_count = attempt + 1
                
            except Exception as e:
                logger.exception(f"Step {step.id} failed: {e}")
                result = StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error_message=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                step.retry_count = attempt + 1
            
            # Check if we should retry
            if attempt < step.max_retries and step.on_error == ErrorPolicy.RETRY:
                logger.info(f"Retrying step {step.id} (attempt {attempt + 2})")
                step.status = StepStatus.RETRYING
                continue
            
            # No more retries, apply error policy
            return self._apply_error_policy(step, result, context)
        
        return result
    
    def _execute_step(self, step: PlanStep, context: ExecutionContext) -> StepResult:
        """Actually executes a step using registered executor."""
        executor = self.step_executors.get(step.runner)
        
        if not executor:
            # Use default runner based on runner name
            executor = self._get_default_executor(step.runner)
        
        if not executor:
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error_message=f"No executor for runner: {step.runner}",
            )
        
        # Build inputs from context
        inputs = {
            "params": step.params,
            "state": context.state,
            "artifacts": context.artifacts,
            "step_outputs": context.step_outputs,
        }
        
        return executor(step, inputs)
    
    def _apply_error_policy(
        self, 
        step: PlanStep, 
        result: StepResult, 
        context: ExecutionContext
    ) -> StepResult:
        """Applies error policy after retries exhausted."""
        policy = step.on_error
        
        if policy == ErrorPolicy.FALLBACK:
            logger.info(f"Step {step.id}: applying fallback")
            fallback_result = self._try_fallback(step, context)
            if fallback_result and fallback_result.success:
                return fallback_result
            # Fallback failed, escalate to ask_user
            policy = ErrorPolicy.ASK_USER
        
        if policy == ErrorPolicy.ASK_USER:
            logger.info(f"Step {step.id}: escalating to ask_user")
            context.ask_user_message = self._build_ask_user_message(step, result)
            result.status = StepStatus.FAILED
            return result
        
        if policy == ErrorPolicy.ABORT:
            logger.warning(f"Step {step.id}: aborting plan")
            result.status = StepStatus.FAILED
            return result
        
        # Default: mark as failed
        return result
    
    def _try_fallback(
        self, 
        step: PlanStep, 
        context: ExecutionContext
    ) -> Optional[StepResult]:
        """Attempts fallback execution with relaxed parameters."""
        # Try with simplified params
        fallback_params = step.params.copy()
        fallback_params["fallback"] = True
        fallback_params["simplified"] = True
        
        # Remove optional fields that might cause issues
        for key in ["advanced_analysis", "full_readme", "detailed_activity"]:
            fallback_params.pop(key, None)
        
        original_params = step.params
        step.params = fallback_params
        
        try:
            result = self._execute_step(step, context)
            if result.success:
                logger.info(f"Step {step.id}: fallback succeeded")
            return result
        except Exception as e:
            logger.warning(f"Step {step.id}: fallback failed: {e}")
            return None
        finally:
            step.params = original_params
    
    def _build_ask_user_message(self, step: PlanStep, result: StepResult) -> str:
        """Builds a user-friendly message for ask_user escalation."""
        error = result.error_message or "알 수 없는 오류"
        
        if "not found" in error.lower():
            return f"저장소를 찾을 수 없습니다. 저장소 URL을 다시 확인해 주세요."
        if "permission" in error.lower() or "private" in error.lower():
            return f"저장소에 접근할 수 없습니다. 비공개 저장소인 경우 접근 권한이 필요합니다."
        if "rate limit" in error.lower():
            return f"GitHub API 요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."
        if "timeout" in error.lower():
            return f"요청 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해 주세요."
        
        return f"처리 중 문제가 발생했습니다: {error}"
    
    def _get_default_executor(self, runner_name: str) -> Optional[StepExecutor]:
        """Returns default executor for known runners."""
        from backend.agents.supervisor.planner.step_runners import get_step_runner
        return get_step_runner(runner_name)
    
    def shutdown(self) -> None:
        """Shuts down the thread pool."""
        self._executor.shutdown(wait=False)


def execute_plan(
    plan: Plan, 
    state: Dict[str, Any],
    step_executors: Optional[Dict[str, StepExecutor]] = None,
) -> Plan:
    """Convenience function to execute a plan."""
    executor = PlanExecutor(step_executors=step_executors)
    try:
        return executor.execute(plan, state)
    finally:
        executor.shutdown()
