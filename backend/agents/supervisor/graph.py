"""Supervisor Graph - 메인 오케스트레이터 (Hero Scenarios)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END
from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.diagnosis_nodes import run_diagnosis_node
from backend.agents.supervisor.nodes.onboarding_nodes import (
    fetch_issues_node,
    plan_onboarding_node,
    summarize_onboarding_plan_node
)

logger = logging.getLogger(__name__)


def router_start_node(state: SupervisorState) -> Dict[str, Any]:
    """라우팅 결정 노드."""
    task_type = state.task_type
    logger.info(f"Router: Starting task {task_type}")
    return {}


def route_after_start(state: SupervisorState) -> Literal["run_diagnosis_node", "__end__"]:
    """시작 후 라우팅."""
    task_type = state.task_type
    
    if task_type == "diagnose_repo":
        return "run_diagnosis_node"
    elif task_type == "build_onboarding_plan":
        # 진단 -> 이슈 수집 -> 플랜 생성 -> 요약
        return "run_diagnosis_node"
    
    logger.warning(f"Unknown task_type: {task_type}")
    return "__end__"


def build_supervisor_graph() -> StateGraph:
    """Supervisor 그래프 빌드."""
    graph = StateGraph(SupervisorState)

    graph.add_node("router_start_node", router_start_node)
    graph.add_node("run_diagnosis_node", run_diagnosis_node)
    graph.add_node("fetch_issues_node", fetch_issues_node)
    graph.add_node("plan_onboarding_node", plan_onboarding_node)
    graph.add_node("summarize_onboarding_plan_node", summarize_onboarding_plan_node)

    graph.set_entry_point("router_start_node")

    graph.add_conditional_edges(
        "router_start_node",
        route_after_start,
        {
            "run_diagnosis_node": "run_diagnosis_node",
            "__end__": END,
        }
    )

    # run_diagnosis_node 이후 분기
    def route_after_diagnosis(state: SupervisorState) -> Literal["fetch_issues_node", "__end__"]:
        # 진단 실패 시 온보딩 플로우로 넘어가지 않도록 조기 종료
        if state.error:
            return "__end__"
            
        if state.task_type == "build_onboarding_plan":
            return "fetch_issues_node"
        return "__end__"

    graph.add_conditional_edges(
        "run_diagnosis_node",
        route_after_diagnosis,
        {
            "fetch_issues_node": "fetch_issues_node",
            "__end__": END,
        }
    )

    # Onboarding Flow 연결
    graph.add_edge("fetch_issues_node", "plan_onboarding_node")
    graph.add_edge("plan_onboarding_node", "summarize_onboarding_plan_node")
    graph.add_edge("summarize_onboarding_plan_node", END)

    return graph


def get_supervisor_graph():
    """컴파일된 Supervisor 그래프 반환 (Checkpointer 포함)."""
    graph = build_supervisor_graph()
    
    # Checkpointer 설정
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        checkpointer = SqliteSaver.from_conn_string("sqlite:///odo_state.db")
    except ImportError:
        logger.warning("SqliteSaver not found. Using MemorySaver.")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    except Exception as e:
        logger.warning(f"Failed to create SqliteSaver: {e}. Using MemorySaver instead.")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
