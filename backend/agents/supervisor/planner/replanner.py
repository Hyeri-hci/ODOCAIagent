"""Re-planner: Dynamic re-planning when steps fail."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.supervisor.planner.models import (
    Plan,
    PlanStep,
    PlanStatus,
    StepStatus,
    ErrorPolicy,
    ReplanReason,
)
from backend.agents.supervisor.planner.builder import PLAN_TEMPLATES, ARTIFACTS_REQUIRED

logger = logging.getLogger(__name__)


# Maximum re-plan attempts
MAX_REPLAN_ATTEMPTS = 2


class Replanner:
    """Handles dynamic re-planning when execution fails."""
    
    def __init__(self, original_plan: Plan):
        self.original_plan = original_plan
        self.replan_count = original_plan.replan_count
    
    def can_replan(self) -> bool:
        """Checks if re-planning is still allowed."""
        return self.replan_count < MAX_REPLAN_ATTEMPTS
    
    def replan(
        self,
        failed_step: PlanStep,
        reason: ReplanReason,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Plan]:
        """Creates a new plan after failure. Returns None if re-planning not possible."""
        if not self.can_replan():
            logger.warning(f"Max replan attempts ({MAX_REPLAN_ATTEMPTS}) reached")
            return None
        
        logger.info(f"Re-planning after {failed_step.id} failed: {reason.value}")
        
        # Determine replan strategy based on reason
        if reason == ReplanReason.STEP_FAILED:
            return self._replan_step_failure(failed_step, context)
        elif reason == ReplanReason.MISSING_ARTIFACT:
            return self._replan_missing_artifact(failed_step, context)
        elif reason == ReplanReason.TIMEOUT:
            return self._replan_timeout(failed_step, context)
        elif reason == ReplanReason.CONFIDENCE_LOW:
            return self._replan_low_confidence(failed_step, context)
        else:
            return self._replan_generic(failed_step, context)
    
    def _replan_step_failure(
        self,
        failed_step: PlanStep,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Plan]:
        """Re-plans after a step execution failure."""
        new_plan = self._create_modified_plan()
        
        # Remove failed step and its dependents
        removed_steps = self._find_dependent_steps(failed_step.id)
        removed_steps.add(failed_step.id)
        
        new_steps = []
        for step in self.original_plan.steps:
            if step.id in removed_steps:
                continue
            
            # Keep completed steps
            if step.status in (StepStatus.SUCCESS, StepStatus.SKIPPED):
                new_steps.append(step)
            else:
                # Reset pending steps
                new_step = self._clone_step(step)
                new_steps.append(new_step)
        
        # Add fallback step if available
        fallback_step = self._create_fallback_step(failed_step, context)
        if fallback_step:
            new_steps.append(fallback_step)
        
        new_plan.steps = new_steps
        new_plan.replan_count = self.replan_count + 1
        new_plan.reasoning_trace += f"\n[REPLAN] Step {failed_step.id} failed, added fallback"
        
        return new_plan
    
    def _replan_missing_artifact(
        self,
        failed_step: PlanStep,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Plan]:
        """Re-plans when required artifact is missing."""
        new_plan = self._create_modified_plan()
        
        # Try to add artifact collection step
        missing_kinds = context.get("missing_artifacts", []) if context else []
        
        new_steps = list(self.original_plan.steps)
        
        for kind in missing_kinds:
            fetch_step = self._create_artifact_fetch_step(kind, failed_step.id)
            if fetch_step:
                # Insert before the failed step
                insert_idx = next(
                    (i for i, s in enumerate(new_steps) if s.id == failed_step.id),
                    len(new_steps)
                )
                new_steps.insert(insert_idx, fetch_step)
                
                # Update dependencies
                failed_step_obj = next(
                    (s for s in new_steps if s.id == failed_step.id), None
                )
                if failed_step_obj and fetch_step.id not in failed_step_obj.needs:
                    failed_step_obj.needs.append(fetch_step.id)
        
        # Reset failed step
        for step in new_steps:
            if step.id == failed_step.id:
                step.status = StepStatus.PENDING
                step.error_message = None
        
        new_plan.steps = new_steps
        new_plan.replan_count = self.replan_count + 1
        new_plan.reasoning_trace += f"\n[REPLAN] Added artifact fetch for {missing_kinds}"
        
        return new_plan
    
    def _replan_timeout(
        self,
        failed_step: PlanStep,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Plan]:
        """Re-plans after timeout by increasing timeout or simplifying."""
        new_plan = self._create_modified_plan()
        
        new_steps = []
        for step in self.original_plan.steps:
            if step.id == failed_step.id:
                # Clone with increased timeout and simplified params
                new_step = self._clone_step(step)
                new_step.timeout_sec = min(step.timeout_sec * 2, 120.0)
                new_step.params["simplified"] = True
                new_step.params.pop("advanced_analysis", None)
                new_step.status = StepStatus.PENDING
                new_steps.append(new_step)
            elif step.status in (StepStatus.SUCCESS, StepStatus.SKIPPED):
                new_steps.append(step)
            else:
                new_steps.append(self._clone_step(step))
        
        new_plan.steps = new_steps
        new_plan.replan_count = self.replan_count + 1
        new_plan.reasoning_trace += f"\n[REPLAN] Timeout on {failed_step.id}, increased timeout"
        
        return new_plan
    
    def _replan_low_confidence(
        self,
        failed_step: PlanStep,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Plan]:
        """Re-plans when confidence is too low."""
        # For low confidence, escalate to ask_user
        new_plan = self._create_modified_plan()
        new_plan.mark_ask_user("분석 결과의 신뢰도가 낮습니다. 추가 정보를 입력해 주세요.")
        new_plan.replan_count = self.replan_count + 1
        return new_plan
    
    def _replan_generic(
        self,
        failed_step: PlanStep,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Plan]:
        """Generic re-plan: try fallback or ask_user."""
        # If step allows fallback, try it
        if failed_step.on_error == ErrorPolicy.FALLBACK:
            return self._replan_step_failure(failed_step, context)
        
        # Otherwise ask user
        new_plan = self._create_modified_plan()
        new_plan.mark_ask_user(f"단계 '{failed_step.id}' 실행 중 문제가 발생했습니다.")
        new_plan.replan_count = self.replan_count + 1
        return new_plan
    
    def _create_modified_plan(self) -> Plan:
        """Creates a copy of the original plan for modification."""
        return Plan(
            id=f"{self.original_plan.id}_r{self.replan_count + 1}",
            intent=self.original_plan.intent,
            sub_intent=self.original_plan.sub_intent,
            artifacts_required=list(self.original_plan.artifacts_required),
            artifacts_collected=dict(self.original_plan.artifacts_collected),
            step_results=dict(self.original_plan.step_results),
            reasoning_trace=self.original_plan.reasoning_trace,
        )
    
    def _clone_step(self, step: PlanStep) -> PlanStep:
        """Clones a step with reset status."""
        return PlanStep(
            id=step.id,
            runner=step.runner,
            params=dict(step.params),
            needs=list(step.needs),
            on_error=step.on_error,
            timeout_sec=step.timeout_sec,
            max_retries=step.max_retries,
            status=StepStatus.PENDING,
        )
    
    def _find_dependent_steps(self, step_id: str) -> set[str]:
        """Finds all steps that depend on the given step."""
        dependents: set[str] = set()
        
        for step in self.original_plan.steps:
            if step_id in step.needs:
                dependents.add(step.id)
                dependents.update(self._find_dependent_steps(step.id))
        
        return dependents
    
    def _create_fallback_step(
        self,
        failed_step: PlanStep,
        context: Optional[Dict[str, Any]],
    ) -> Optional[PlanStep]:
        """Creates a fallback step for the failed one."""
        # Fallback mappings
        fallback_runners = {
            "diagnosis": "diagnosis",  # Same with simplified params
            "compare": "chat",         # Fall back to chat response
            "overview": "chat",
        }
        
        fallback_runner = fallback_runners.get(failed_step.runner)
        if not fallback_runner:
            return None
        
        return PlanStep(
            id=f"{failed_step.id}_fallback",
            runner=fallback_runner,
            params={
                "fallback": True,
                "simplified": True,
                "original_step": failed_step.id,
            },
            needs=[s.id for s in self.original_plan.steps 
                   if s.status == StepStatus.SUCCESS],
            on_error=ErrorPolicy.ABORT,
            timeout_sec=15.0,
        )
    
    def _create_artifact_fetch_step(
        self,
        artifact_kind: str,
        dependent_step_id: str,
    ) -> Optional[PlanStep]:
        """Creates a step to fetch a missing artifact."""
        # Map artifact kinds to runners
        artifact_runners = {
            "diagnosis_raw": "diagnosis",
            "readme_analysis": "diagnosis",
            "activity_metrics": "diagnosis",
            "repo_metadata": "overview",
        }
        
        runner = artifact_runners.get(artifact_kind)
        if not runner:
            return None
        
        return PlanStep(
            id=f"fetch_{artifact_kind}",
            runner=runner,
            params={"target_artifact": artifact_kind},
            needs=[],
            on_error=ErrorPolicy.FALLBACK,
            timeout_sec=20.0,
        )


def replan_on_failure(
    plan: Plan,
    failed_step: PlanStep,
    reason: ReplanReason,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Plan]:
    """Convenience function for re-planning."""
    replanner = Replanner(plan)
    return replanner.replan(failed_step, reason, context)


def should_replan(plan: Plan, failed_step: PlanStep) -> bool:
    """Determines if re-planning should be attempted."""
    # Don't replan if max attempts reached
    if plan.replan_count >= MAX_REPLAN_ATTEMPTS:
        return False
    
    # Don't replan for abort policy
    if failed_step.on_error == ErrorPolicy.ABORT:
        return False
    
    # Don't replan for ask_user policy (let user decide)
    if failed_step.on_error == ErrorPolicy.ASK_USER:
        return False
    
    return True
