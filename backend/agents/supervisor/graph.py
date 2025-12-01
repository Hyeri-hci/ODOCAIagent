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


# Node 3: diagnosis_node (conditional) with Normalization
def diagnosis_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs diagnosis agent if needed. Applies output normalization."""
    from backend.agents.supervisor.service import call_diagnosis_agent
    
    repo = state.get("repo")
    if not repo:
        return {"error_message": "저장소 정보가 없습니다."}
    
    # Skip if diagnosis_result already exists (followup case)
    if state.get("diagnosis_result"):
        return {}
    
    # Null-safe access to user_context
    user_context = safe_get(state, "user_context", {})
    user_level = safe_get(user_context, "level", "beginner")
    repo_id = f"{safe_get(repo, 'owner', '')}/{safe_get(repo, 'name', '')}"
    
    emit_event(
        EventType.NODE_STARTED,
        actor="diagnosis_node",
        inputs={"repo": repo_id, "user_level": user_level},
    )
    
    try:
        raw_result = call_diagnosis_agent(
            owner=repo["owner"],
            repo=repo["name"],
            user_level=user_level,
        )
        
        # Normalize runner output (single normalization point)
        normalized = normalize_runner_output(raw_result)
        
        if normalized.status == RunnerStatus.ERROR:
            logger.error(f"Diagnosis returned error: {normalized.error_message}")
            emit_event(
                EventType.NODE_FINISHED,
                actor="diagnosis_node",
                inputs={"repo": repo_id},
                outputs={"status": "error", "error": normalized.error_message},
            )
            return {"error_message": normalized.error_message or "진단 중 오류가 발생했습니다."}
        
        # Extract diagnosis result (Null-safe)
        diagnosis_result = normalized.result
        health_score = safe_get_nested(diagnosis_result, "scores", "health_score")
        
        emit_event(
            EventType.NODE_FINISHED,
            actor="diagnosis_node",
            inputs={"repo": repo_id},
            outputs={
                "health_score": health_score,
                "status": normalized.status.value,
            },
        )
        
        return {"diagnosis_result": diagnosis_result}
        
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        
        emit_event(
            EventType.NODE_FINISHED,
            actor="diagnosis_node",
            inputs={"repo": repo_id},
            outputs={"status": "error", "error": str(e)},
        )
        
        return {"error_message": f"진단 중 오류가 발생했습니다: {str(e)}"}


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


# Routing: should_run_diagnosis
def should_run_diagnosis(state: SupervisorState) -> str:
    """Determines whether to run diagnosis or skip to summarize."""
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent", DEFAULT_SUB_INTENT)
    
    # Check for errors first
    if state.get("error_message"):
        return "summarize"
    
    # Check V1 support
    if not is_v1_supported(intent, sub_intent):
        return "summarize"
    
    meta = get_intent_meta(intent, sub_intent)
    
    # Check if repo is required but missing
    if meta["requires_repo"] and not state.get("repo"):
        return "summarize"
    
    # Run diagnosis only for analyze intent
    if intent == "analyze" and not state.get("diagnosis_result"):
        return "diagnosis"
    
    # followup/explain needs diagnosis_result but should NOT re-run diagnosis
    if intent == "followup" and sub_intent == "explain":
        if not state.get("diagnosis_result"):
            # No previous diagnosis - need to inform user
            return "summarize"
    
    return "summarize"


# Graph Builder
def build_supervisor_graph():
    """Builds V1 Supervisor Graph: init → classify → diagnosis(conditional) → summarize."""
    graph = StateGraph(SupervisorState)

    # Add 4 nodes
    graph.add_node("init", init_node)
    graph.add_node("classify", classify_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("summarize", summarize_node_wrapper)

    # Set entry point
    graph.set_entry_point("init")

    # Linear flow: init → classify
    graph.add_edge("init", "classify")
    
    # Conditional: classify → diagnosis OR summarize
    graph.add_conditional_edges(
        "classify",
        should_run_diagnosis,
        {
            "diagnosis": "diagnosis",
            "summarize": "summarize",
        },
    )

    # diagnosis → summarize → END
    graph.add_edge("diagnosis", "summarize")
    graph.add_edge("summarize", END)

    logger.info("Built V1 Supervisor Graph (4 nodes)")
    return graph.compile()


def get_supervisor_graph():
    """Returns the V1 supervisor graph."""
    return build_supervisor_graph()
