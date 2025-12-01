from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from backend.agents.supervisor.models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)
from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
from backend.agents.supervisor.nodes.task_mapping import map_task_types_node
from backend.agents.supervisor.nodes.run_diagnosis import run_diagnosis_node
from backend.agents.supervisor.nodes.summarize_node import summarize_node
from backend.agents.supervisor.nodes.refine_tasks import refine_tasks_node
from backend.agents.supervisor.nodes.profile_updater import update_profile_node
from backend.agents.supervisor.intent_config import (
    get_intent_meta,
    should_run_diagnosis,
    intent_requires_repo,
    intent_requires_previous_result,
    is_chat,
    is_concept_qa,
)
from backend.common.events import (
    EventType,
    emit_event,
    turn_context,
    span,
    generate_session_id,
    generate_turn_id,
    set_session_id,
    set_turn_id,
    get_session_id,
    get_turn_id,
)

logger = logging.getLogger(__name__)


def init_session_node(state: SupervisorState) -> Dict[str, Any]:
    """Initializes session context from LangGraph config (thread_id)."""
    # Set session_id from state or generate a new one
    existing_session_id = state.get("_session_id")
    if existing_session_id:
        set_session_id(existing_session_id)
    else:
        session_id = generate_session_id()
        set_session_id(session_id)
    
    # Generate new turn_id for each turn
    turn_id = generate_turn_id()
    set_turn_id(turn_id)
    
    emit_event(
        EventType.NODE_STARTED,
        actor="supervisor",
        inputs={"node_name": "init_session"},
        outputs={
            "session_id": get_session_id(),
            "turn_id": get_turn_id(),
        }
    )
    
    return {
        "_session_id": get_session_id(),
        "_turn_id": turn_id,
    }

# Whether to enable Agentic mode (default: true)
AGENTIC_MODE = os.getenv("ODOC_AGENTIC_MODE", "true").lower() in ("1", "true")


# Agentic nodes (used when AGENTIC_MODE=true)
def infer_missing_node(state: SupervisorState) -> Dict[str, Any]:
    """Active Inference: infers missing information from the query."""
    from backend.agents.supervisor.inference import (
        infer_missing,
        needs_disambiguation,
        build_disambiguation_message,
    )
    
    with span("infer_missing", actor="supervisor"):
        user_query = state.get("user_query", "")
        hints = infer_missing(user_query, state)
        
        # Update repo info
        if hints.owner and hints.name and not state.get("repo"):
            repo_info = {
                "owner": hints.owner,
                "name": hints.name,
                "url": f"https://github.com/{hints.owner}/{hints.name}",
            }
            
            emit_event(
                EventType.SUPERVISOR_INTENT_DETECTED,
                outputs={
                    "inferred_repo": f"{hints.owner}/{hints.name}",
                    "confidence": hints.confidence,
                }
            )
            
            return {
                "repo": repo_info,
                "_inference_hints": hints.model_dump(),
                "_inference_confidence": hints.confidence,
            }
        
        # Check if disambiguation is needed
        if needs_disambiguation(hints):
            msg = build_disambiguation_message(hints)
            return {
                "error_message": msg,
                "_needs_disambiguation": True,
            }
        
        return {"_inference_hints": hints.model_dump()}


def build_plan_node(state: SupervisorState) -> Dict[str, Any]:
    """Builds a plan for the supervisor to execute."""
    from backend.agents.supervisor.nodes.planner import planner_node
    return planner_node(state)


def execute_plan_node(state: SupervisorState) -> Dict[str, Any]:
    """Executes the supervisor's plan."""
    from backend.agents.supervisor.executor import (
        execute_plan,
        create_default_agent_runners,
        PlanExecutionContext,
    )
    from backend.common.events import get_session_id
    
    with span("execute_plan", actor="supervisor"):
        plan_output = state.get("plan_output")
        if not plan_output or not plan_output.plan:
            # Fallback to legacy mode if no plan exists
            return {}
        
        session_id = get_session_id() or generate_session_id()
        ctx = PlanExecutionContext(
            session_id=session_id,
            agent_runners=create_default_agent_runners(),
            state=state,
        )
        
        result = execute_plan(plan_output.plan, ctx)
        
        # Extract results by type
        diagnosis_result = None
        fast_chat_result = None  # for smalltalk/help/overview

        for step_id, step_result in result.get("results", {}).items():
            step_data = step_result.get("result", {})
            if not step_data:
                continue
            
            if "diagnosis" in step_id:
                diagnosis_result = step_data
            elif "answer_contract" in step_data:
                fast_chat_result = step_data
        
        return {
            "_plan_execution_result": result,
            "_plan_status": result.get("status"),
            "diagnosis_result": diagnosis_result,
            "_fast_chat_result": fast_chat_result,
        }


# Routing functions
def route_after_mapping(state: SupervisorState) -> str:
    """Routes after the task mapping node based on INTENT_META."""
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent") or DEFAULT_SUB_INTENT
    
    meta = get_intent_meta(intent, sub_intent)
    
    emit_event(
        EventType.SUPERVISOR_ROUTE_SELECTED,
        outputs={"intent": intent, "sub_intent": sub_intent, "meta": dict(meta)}
    )
    
    if state.get("error_message"):
        return "summarize"
    
    if meta["requires_repo"] and not state.get("repo"):
        state["error_message"] = "어떤 저장소를 기준으로 분석할지 알려주세요. 예: facebook/react 또는 GitHub URL"
        return "summarize"
    
    if meta["runs_diagnosis"]:
        return "run_diagnosis"
    
    # Fallback for concept, chat, etc.
    return "summarize"


def route_after_inference(state: SupervisorState) -> str:
    """Routes after the inference node (Agentic mode)."""
    if state.get("_needs_disambiguation"):
        return "summarize"
    
    if state.get("error_message"):
        return "summarize"
    
    return "build_plan"


def route_after_plan(state: SupervisorState) -> str:
    """Routes after the planning node."""
    plan_output = state.get("plan_output")
    
    if not plan_output or not plan_output.plan:
        return "summarize"
    
    if plan_output.intent == "disambiguation":
        return "summarize"
    
    return "execute_plan"


# Graph Builders
def build_supervisor_graph():
    """Builds the standard Supervisor Graph (v1)."""
    graph = StateGraph(SupervisorState)

    graph.add_node("init_session", init_session_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("map_task_types", map_task_types_node)
    graph.add_node("run_diagnosis", run_diagnosis_node)
    graph.add_node("refine_tasks", refine_tasks_node)
    graph.add_node("update_profile", update_profile_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("init_session")

    graph.add_edge("init_session", "classify_intent")
    graph.add_edge("classify_intent", "map_task_types")

    graph.add_conditional_edges(
        "map_task_types",
        route_after_mapping,
        {
            "run_diagnosis": "run_diagnosis",
            "refine_tasks": "refine_tasks",
            "summarize": "summarize",
        },
    )

    graph.add_edge("run_diagnosis", "update_profile")
    graph.add_edge("update_profile", "summarize")
    graph.add_edge("refine_tasks", "summarize")
    graph.add_edge("summarize", END)

    # Session state is managed externally (e.g., Streamlit session_state)
    return graph.compile()


def build_agentic_supervisor_graph():
    """Builds the Agentic Supervisor Graph (v2)."""
    graph = StateGraph(SupervisorState)

    graph.add_node("init_session", init_session_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("infer_missing", infer_missing_node)
    graph.add_node("build_plan", build_plan_node)
    graph.add_node("execute_plan", execute_plan_node)
    graph.add_node("update_profile", update_profile_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("init_session")

    graph.add_edge("init_session", "classify_intent")
    graph.add_edge("classify_intent", "infer_missing")

    graph.add_conditional_edges(
        "infer_missing",
        route_after_inference,
        {
            "build_plan": "build_plan",
            "summarize": "summarize",
        },
    )

    graph.add_conditional_edges(
        "build_plan",
        route_after_plan,
        {
            "execute_plan": "execute_plan",
            "summarize": "summarize",
        },
    )

    graph.add_edge("execute_plan", "update_profile")
    graph.add_edge("update_profile", "summarize")
    graph.add_edge("summarize", END)

    # Session state is managed externally (e.g., Streamlit session_state)
    return graph.compile()


def get_supervisor_graph():
    """Gets the appropriate supervisor graph based on the environment."""
    if AGENTIC_MODE:
        logger.info("Using Agentic Supervisor Graph (v2)")
        return build_agentic_supervisor_graph()
    else:
        logger.info("Using Standard Supervisor Graph (v1)")
        return build_supervisor_graph()
