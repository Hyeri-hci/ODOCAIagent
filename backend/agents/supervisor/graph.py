"""Supervisor Graph V1: Simple 4-node workflow with idempotency."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from backend.agents.supervisor.models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)
from backend.agents.supervisor.intent_config import (
    get_intent_meta,
    is_v1_supported,
)
from backend.common.events import (
    EventType,
    emit_event,
    generate_session_id,
    generate_turn_id,
    set_session_id,
    set_turn_id,
    get_session_id,
    get_turn_id,
)
from backend.agents.shared.contracts import (
    normalize_runner_output,
    safe_get,
    safe_get_nested,
    RunnerStatus,
)
from backend.common.cache import idempotency_store

logger = logging.getLogger(__name__)


# Node 1: init_node
def init_node(state: SupervisorState) -> Dict[str, Any]:
    """Initializes session context and validates input."""
    existing_session_id = state.get("_session_id")
    if existing_session_id:
        set_session_id(existing_session_id)
    else:
        session_id = generate_session_id()
        set_session_id(session_id)
    
    turn_id = generate_turn_id()
    set_turn_id(turn_id)
    
    emit_event(
        EventType.NODE_STARTED,
        actor="supervisor",
        inputs={"node_name": "init_node"},
        outputs={
            "session_id": get_session_id(),
            "turn_id": get_turn_id(),
        }
    )
    
    return {
        "_session_id": get_session_id(),
        "_turn_id": turn_id,
    }


# Node 2: classify_node
def classify_node(state: SupervisorState) -> Dict[str, Any]:
    """Classifies user intent using simple rules or LLM."""
    from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
    
    emit_event(
        EventType.NODE_STARTED,
        actor="classify_node",
        inputs={"query_length": len(state.get("user_query", ""))},
    )
    
    result = classify_intent_node(state)
    
    intent = result.get("intent", DEFAULT_INTENT)
    sub_intent = result.get("sub_intent", DEFAULT_SUB_INTENT)
    
    # Set default answer_kind based on intent
    answer_kind = _get_default_answer_kind(intent, sub_intent)
    result["answer_kind"] = answer_kind
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="classify_node",
        outputs={
            "intent": intent,
            "sub_intent": sub_intent,
            "answer_kind": answer_kind,
        },
    )
    
    # Emit route selection event
    emit_event(
        EventType.SUPERVISOR_ROUTE_SELECTED,
        actor="supervisor",
        outputs={
            "selected_route": "diagnosis" if intent == "analyze" else "summarize",
            "intent": intent,
            "sub_intent": sub_intent,
        },
    )
    
    return result


def _get_default_answer_kind(intent: str, sub_intent: str) -> str:
    """Maps (intent, sub_intent) to default answer_kind."""
    if intent == "analyze":
        return "report"
    elif intent == "followup" and sub_intent == "explain":
        return "explain"
    elif intent == "smalltalk":
        return "greeting"
    else:
        return "chat"


# Node 3: diagnosis_node (conditional) with ExpertRunner
def diagnosis_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs diagnosis using DiagnosisRunner with error policy."""
    from backend.agents.supervisor.runners import DiagnosisRunner
    
    repo = state.get("repo")
    if not repo:
        return {"error_message": "저장소 정보가 없습니다."}
    
    # Skip if diagnosis_result already exists (followup case)
    if state.get("diagnosis_result"):
        return {}
    
    user_context = safe_get(state, "user_context", {})
    repo_id = f"{safe_get(repo, 'owner', '')}/{safe_get(repo, 'name', '')}"
    
    emit_event(
        EventType.NODE_STARTED,
        actor="diagnosis_node",
        inputs={"repo": repo_id},
    )
    
    # Run diagnosis using ExpertRunner
    runner = DiagnosisRunner(
        repo_id=repo_id,
        user_context=user_context,
    )
    result = runner.run()
    
    if not result.success:
        emit_event(
            EventType.NODE_FINISHED,
            actor="diagnosis_node",
            outputs={"status": "error", "error": result.error_message},
        )
        return {"error_message": result.error_message or "진단 중 오류가 발생했습니다."}
    
    # Get raw diagnosis result for state
    diagnosis_result = runner.get_diagnosis_result()
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="diagnosis_node",
        outputs={
            "status": "success",
            "degraded": result.degraded,
            "artifact_count": len(result.artifacts_out),
        },
    )
    
    return {
        "diagnosis_result": diagnosis_result,
        "_expert_result": result,  # Store for summarize node if needed
    }


# Node 3b: expert_node (for compare/onepager)
def expert_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs specialized expert runners (compare, onepager)."""
    from backend.agents.supervisor.runners import CompareRunner, OnepagerRunner
    
    intent = state.get("intent", "analyze")
    sub_intent = state.get("sub_intent", "health")
    repo = state.get("repo")
    user_context = safe_get(state, "user_context", {})
    
    if not repo:
        return {"error_message": "저장소 정보가 없습니다."}
    
    repo_id = f"{safe_get(repo, 'owner', '')}/{safe_get(repo, 'name', '')}"
    
    emit_event(
        EventType.NODE_STARTED,
        actor="expert_node",
        inputs={"intent": intent, "sub_intent": sub_intent, "repo": repo_id},
    )
    
    # Select appropriate runner
    if sub_intent == "compare":
        # For compare, need second repo from query parsing
        repo_b = safe_get(state, "compare_repo")
        if not repo_b:
            return {"error_message": "비교할 두 번째 저장소가 필요합니다."}
        
        repo_b_id = f"{safe_get(repo_b, 'owner', '')}/{safe_get(repo_b, 'name', '')}"
        runner = CompareRunner(
            repo_a=repo_id,
            repo_b=repo_b_id,
            user_context=user_context,
        )
    elif sub_intent == "onepager":
        runner = OnepagerRunner(
            repo_id=repo_id,
            user_context=user_context,
        )
    else:
        # Fallback to diagnosis
        from backend.agents.supervisor.runners import DiagnosisRunner
        runner = DiagnosisRunner(
            repo_id=repo_id,
            user_context=user_context,
        )
    
    result = runner.run()
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="expert_node",
        outputs={
            "status": "success" if result.success else "error",
            "degraded": result.degraded,
            "runner": runner.runner_name,
        },
    )
    
    if not result.success:
        return {"error_message": result.error_message}
    
    # Store expert result for summarize node
    return {
        "_expert_result": result,
        "_expert_answer": result.answer.model_dump() if result.answer else None,
    }


# Node 4: summarize_node (with idempotency)
def summarize_node_wrapper(state: SupervisorState) -> Dict[str, Any]:
    """Generates final response using V1 summarize logic with idempotency."""
    from backend.agents.supervisor.nodes.summarize_node import summarize_node_v1
    
    session_id = safe_get(state, "_session_id", "")
    turn_id = safe_get(state, "_turn_id", "")
    step_id = "summarize"
    
    # Check for cached result (idempotency)
    cached = idempotency_store.get_cached(session_id, turn_id, step_id)
    if cached:
        logger.info(f"Idempotency HIT: returning cached answer_id={cached.answer_id}")
        return cached.result
    
    emit_event(
        EventType.NODE_STARTED,
        actor="summarize_node",
        inputs={
            "intent": state.get("intent", DEFAULT_INTENT),
            "sub_intent": state.get("sub_intent", DEFAULT_SUB_INTENT),
        },
    )
    
    # Acquire lock to prevent duplicate execution
    with idempotency_store.acquire_lock(session_id, turn_id, step_id):
        # Double-check cache after acquiring lock
        cached = idempotency_store.get_cached(session_id, turn_id, step_id)
        if cached:
            return cached.result
        
        result = summarize_node_v1(state)
        
        # Generate and attach answer_id
        execution = idempotency_store.store_result(
            session_id=session_id,
            turn_id=turn_id,
            step_id=step_id,
            result=result,
        )
        result["answer_id"] = execution.answer_id
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="summarize_node",
        outputs={
            "answer_kind": result.get("answer_kind"),
            "text_length": len(result.get("llm_summary", "")),
            "answer_id": result.get("answer_id"),
        },
    )
    
    return result


# Routing: should_run_diagnosis (hierarchical routing)
def should_run_diagnosis(state: SupervisorState) -> str:
    """Hierarchical routing: route to appropriate node based on intent."""
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent", DEFAULT_SUB_INTENT)
    
    # Check for errors first
    if state.get("error_message"):
        return "summarize"
    
    # Fast path: smalltalk/help/overview → never diagnosis
    if intent in ("smalltalk", "help", "overview", "general_qa"):
        logger.debug(f"[route] Fast path: {intent}.{sub_intent} → summarize")
        return "summarize"
    
    # Check V1 support
    if not is_v1_supported(intent, sub_intent):
        return "summarize"
    
    meta = get_intent_meta(intent, sub_intent)
    
    # Check if repo is required but missing
    if meta["requires_repo"] and not state.get("repo"):
        return "summarize"
    
    # Compare/Onepager → expert_node
    if sub_intent in ("compare", "onepager"):
        logger.debug(f"[route] Expert path: {intent}.{sub_intent} → expert")
        return "expert"
    
    # Run diagnosis only for analyze intent
    if intent == "analyze" and not state.get("diagnosis_result"):
        return "diagnosis"
    
    # followup/explain needs diagnosis_result but should NOT re-run diagnosis
    if intent == "followup":
        # evidence/explain → summarize (uses existing diagnosis_result)
        return "summarize"
    
    return "summarize"


# Graph Builder
def build_supervisor_graph():
    """Builds V1 Supervisor Graph: init → classify → diagnosis/expert(conditional) → summarize."""
    graph = StateGraph(SupervisorState)

    # Add 5 nodes
    graph.add_node("init", init_node)
    graph.add_node("classify", classify_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("expert", expert_node)
    graph.add_node("summarize", summarize_node_wrapper)

    # Set entry point
    graph.set_entry_point("init")

    # Linear flow: init → classify
    graph.add_edge("init", "classify")
    
    # Conditional: classify → diagnosis OR expert OR summarize
    graph.add_conditional_edges(
        "classify",
        should_run_diagnosis,
        {
            "diagnosis": "diagnosis",
            "expert": "expert",
            "summarize": "summarize",
        },
    )

    # diagnosis → summarize → END
    graph.add_edge("diagnosis", "summarize")
    # expert → summarize → END
    graph.add_edge("expert", "summarize")
    graph.add_edge("summarize", END)

    logger.info("Built V1 Supervisor Graph (5 nodes)")
    return graph.compile()


def get_supervisor_graph():
    """Returns the V1 supervisor graph."""
    return build_supervisor_graph()


# V2 Agentic Planning Graph

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


def should_use_planning(state: SupervisorState) -> str:
    """Determines whether to use V1 direct path or V2 planning path."""
    intent = state.get("intent", DEFAULT_INTENT)
    
    # Fast paths: never use planning
    if intent in ("smalltalk", "help", "general_qa"):
        return "summarize"
    
    # Error path
    if state.get("error_message"):
        return "summarize"
    
    # V2 Planning for complex intents
    if intent in ("analyze",) and state.get("_use_planning"):
        return "plan"
    
    # Default to V1 direct routing
    return "direct"


def build_supervisor_graph_v2():
    """Builds V2 Supervisor Graph with Agentic Planning support."""
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("init", init_node)
    graph.add_node("classify", classify_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute_plan", execute_plan_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("summarize", summarize_node_wrapper)

    # Set entry point
    graph.set_entry_point("init")

    # Linear flow: init → classify
    graph.add_edge("init", "classify")
    
    # Conditional: classify → plan OR diagnosis OR summarize
    graph.add_conditional_edges(
        "classify",
        should_use_planning,
        {
            "plan": "plan",
            "direct": "diagnosis",
            "summarize": "summarize",
        },
    )
    
    # V2 Planning path
    graph.add_edge("plan", "execute_plan")
    graph.add_edge("execute_plan", "summarize")
    
    # V1 Direct path (fallback)
    graph.add_conditional_edges(
        "diagnosis",
        lambda s: "summarize",
        {"summarize": "summarize"},
    )
    
    graph.add_edge("summarize", END)

    logger.info("Built V2 Supervisor Graph with Planning (6 nodes)")
    return graph.compile()


def get_supervisor_graph_v2():
    """Returns the V2 supervisor graph with planning."""
    return build_supervisor_graph_v2()
