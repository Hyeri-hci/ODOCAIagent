"""Plan Nodes: V2 Agentic Planning (plan_node, execute_plan_node)."""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.supervisor.models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)
from backend.common.events import EventType, emit_event

logger = logging.getLogger(__name__)


def plan_node(state: SupervisorState) -> Dict[str, Any]:
    """Builds execution plan based on intent classification."""
    from backend.agents.supervisor.planner import build_plan, PlanStatus
    
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent", DEFAULT_SUB_INTENT)
    
    emit_event(
        EventType.NODE_STARTED,
        actor="plan_node",
        inputs={"intent": intent, "sub_intent": sub_intent},
    )
    
    # Build plan from intent
    context = {
        "repo": state.get("repo"),
        "user_context": state.get("user_context", {}),
        "compare_repo": state.get("compare_repo"),
        "user_query": state.get("user_query", ""),
    }
    
    plan = build_plan(intent, sub_intent, context)
    
    emit_event(
        EventType.SUPERVISOR_PLAN_BUILT,
        actor="plan_node",
        outputs={
            "plan_id": plan.id,
            "step_count": len(plan.steps),
            "artifacts_required": plan.artifacts_required,
        },
    )
    
    return {
        "_plan": plan.id,
        "_plan_steps": [s.id for s in plan.steps],
        "_plan_object": plan,
    }


def execute_plan_node(state: SupervisorState) -> Dict[str, Any]:
    """Executes the plan with error handling and re-planning."""
    from backend.agents.supervisor.planner import (
        execute_plan,
        PlanStatus,
        replan_on_failure,
        ReplanReason,
    )
    
    plan = state.get("_plan_object")
    if not plan:
        return {"error_message": "실행할 계획이 없습니다."}
    
    emit_event(
        EventType.NODE_STARTED,
        actor="execute_plan_node",
        inputs={"plan_id": plan.id, "step_count": len(plan.steps)},
    )
    
    # Execute plan
    executed_plan = execute_plan(plan, dict(state))
    
    # Handle re-planning on failure
    if executed_plan.status == PlanStatus.FAILED:
        failed_steps = executed_plan.get_failed_steps()
        if failed_steps:
            failed_step = failed_steps[0]
            # Try re-planning
            new_plan = replan_on_failure(
                executed_plan,
                failed_step,
                ReplanReason.STEP_FAILED,
            )
            if new_plan:
                executed_plan = execute_plan(new_plan, dict(state))
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="execute_plan_node",
        outputs={
            "plan_id": executed_plan.id,
            "status": executed_plan.status.value,
            "execution_time_ms": executed_plan.total_execution_time_ms,
            "replan_count": executed_plan.replan_count,
        },
    )
    
    # Extract results from plan execution
    result: Dict[str, Any] = {
        "_executed_plan": executed_plan.id,
        "_plan_status": executed_plan.status.value,
    }
    
    # Collect step outputs
    for step_id, step_result in executed_plan.step_results.items():
        if step_result.success and step_result.result:
            # Merge results into state
            result.update(step_result.result)
    
    # Handle ask_user status
    if executed_plan.status == PlanStatus.ASK_USER:
        result["error_message"] = executed_plan.error_message
    elif executed_plan.status == PlanStatus.FAILED:
        result["error_message"] = executed_plan.error_message or "계획 실행 중 오류가 발생했습니다."
    
    return result
