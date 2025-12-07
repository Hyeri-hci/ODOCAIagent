"""Supervisor Graph - Agentic 오케스트레이터."""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.diagnosis_nodes import run_diagnosis_node
from backend.agents.supervisor.nodes.onboarding_nodes import (
    fetch_issues_node,
    plan_onboarding_node,
    summarize_onboarding_plan_node
)
from backend.agents.supervisor.nodes.routing_nodes import (
    intent_analysis_node,
    decision_node,
    quality_check_node,
    use_cached_result_node,
    route_after_decision,
    route_after_cached_result,
    route_after_quality_check,
)
from backend.agents.supervisor.nodes.comparison_nodes import (
    batch_diagnosis_node,
    compare_results_node,
)
from backend.agents.supervisor.nodes.chat_nodes import chat_response_node

logger = logging.getLogger(__name__)


def build_supervisor_graph() -> StateGraph:
    """Supervisor 그래프 빌드."""
    graph = StateGraph(SupervisorState)

    # 노드 등록 - 기존 노드
    graph.add_node("intent_analysis_node", intent_analysis_node)
    graph.add_node("decision_node", decision_node)
    graph.add_node("run_diagnosis_node", run_diagnosis_node)
    graph.add_node("quality_check_node", quality_check_node)
    graph.add_node("fetch_issues_node", fetch_issues_node)
    graph.add_node("plan_onboarding_node", plan_onboarding_node)
    graph.add_node("summarize_onboarding_plan_node", summarize_onboarding_plan_node)
    
    # 노드 등록 - 캐시 및 비교 노드
    graph.add_node("use_cached_result_node", use_cached_result_node)
    graph.add_node("batch_diagnosis_node", batch_diagnosis_node)
    graph.add_node("compare_results_node", compare_results_node)
    
    # 노드 등록 - 채팅 노드
    graph.add_node("chat_response_node", chat_response_node)

    # Entry Point
    graph.set_entry_point("intent_analysis_node")

    # intent_analysis_node -> decision_node
    graph.add_edge("intent_analysis_node", "decision_node")

    # decision_node -> conditional routing (캐시, 진단, 비교, 채팅 분기)
    graph.add_conditional_edges(
        "decision_node",
        route_after_decision,
        {
            "run_diagnosis_node": "run_diagnosis_node",
            "use_cached_result_node": "use_cached_result_node",
            "batch_diagnosis_node": "batch_diagnosis_node",
            "chat_response_node": "chat_response_node",
            "__end__": END,
        }
    )

    # use_cached_result_node -> conditional routing
    def _route_after_cached(state: SupervisorState) -> Literal[
        "run_diagnosis_node", "quality_check_node", "fetch_issues_node", "compare_results_node"
    ]:
        return route_after_cached_result(state)

    graph.add_conditional_edges(
        "use_cached_result_node",
        _route_after_cached,
        {
            "run_diagnosis_node": "run_diagnosis_node",
            "quality_check_node": "quality_check_node",
            "fetch_issues_node": "fetch_issues_node",
            "compare_results_node": "compare_results_node",
        }
    )

    # run_diagnosis_node -> quality_check_node
    graph.add_edge("run_diagnosis_node", "quality_check_node")

    # quality_check_node -> conditional routing
    def _route_after_quality(state: SupervisorState) -> Literal[
        "run_diagnosis_node", "fetch_issues_node", "compare_results_node", "__end__"
    ]:
        if state.error:
            return "__end__"
        return route_after_quality_check(state)

    graph.add_conditional_edges(
        "quality_check_node",
        _route_after_quality,
        {
            "run_diagnosis_node": "run_diagnosis_node",
            "fetch_issues_node": "fetch_issues_node",
            "compare_results_node": "compare_results_node",
            "__end__": END,
        }
    )

    # Onboarding Flow
    graph.add_edge("fetch_issues_node", "plan_onboarding_node")
    graph.add_edge("plan_onboarding_node", "summarize_onboarding_plan_node")
    graph.add_edge("summarize_onboarding_plan_node", END)

    # Comparison Flow
    graph.add_edge("batch_diagnosis_node", "compare_results_node")
    graph.add_edge("compare_results_node", END)

    # Chat Flow
    graph.add_edge("chat_response_node", END)

    return graph


def get_supervisor_graph():
    """컴파일된 Supervisor 그래프 반환 (Checkpointer 포함)."""
    graph = build_supervisor_graph()
    
    # Checkpointer 설정
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        
        # SqliteSaver는 sqlite3.Connection 객체를 직접 받음
        conn = sqlite3.connect("odo_state.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        logger.info("Using SqliteSaver for state persistence.")
    except ImportError:
        logger.warning("SqliteSaver not found. Using MemorySaver.")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    except Exception as e:
        logger.warning(f"Failed to create SqliteSaver: {e}. Using MemorySaver instead.")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
