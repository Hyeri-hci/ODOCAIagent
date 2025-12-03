"""Supervisor Graph V1: Simple 4-node workflow with idempotency."""
from __future__ import annotations

import logging
from typing import Any, Dict

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
from backend.agents.shared.contracts import safe_get
from backend.common.events import EventType, emit_event
from backend.common.cache import idempotency_store

# Import nodes from modular files
from backend.agents.supervisor.nodes.init_node import init_node
from backend.agents.supervisor.nodes.classify_node import classify_node
from backend.agents.supervisor.nodes.diagnosis_node import diagnosis_node
from backend.agents.supervisor.nodes.expert_node import expert_node
from backend.agents.supervisor.nodes.plan_nodes import plan_node, execute_plan_node

logger = logging.getLogger(__name__)


# Summarize Node Wrapper with idempotency
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


# Routing Functions
def should_run_diagnosis(state: SupervisorState) -> str:
    """Hierarchical routing: route to appropriate node based on intent."""
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent", DEFAULT_SUB_INTENT)
    
    # Check for errors first
    if state.get("error_message"):
        return "summarize"
    
    # Access Guard: repo inaccessible → ask_user (BLOCK diagnosis)
    if state.get("_needs_ask_user"):
        logger.debug(f"[route] Access guard: {intent}.{sub_intent} → summarize (ask_user)")
        return "summarize"
    
    # Disambiguation: repo 필요하지만 없음 → 전문가 노드 진입 금지
    if state.get("_needs_disambiguation"):
        logger.debug(f"[route] Disambiguation: {intent}.{sub_intent} → summarize")
        return "summarize"
    
    # Fast path: smalltalk/help/overview → never diagnosis
    if intent in ("smalltalk", "help", "overview", "general_qa"):
        logger.debug(f"[route] Fast path: {intent}.{sub_intent} → summarize")
        return "summarize"
    
    # Check V1 support
    if not is_v1_supported(intent, sub_intent):
        return "summarize"
    
    meta = get_intent_meta(intent, sub_intent)
    
    # Entity guard: repo 필요하지만 없음 → disambiguation 강제
    if meta["requires_repo"] and not state.get("repo"):
        logger.debug(f"[route] Entity guard: no repo → summarize")
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
        return "summarize"
    
    return "summarize"


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


# Graph Builders
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
