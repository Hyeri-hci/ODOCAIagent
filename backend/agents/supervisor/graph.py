"""Supervisor Graph - 메인 오케스트레이터 (Refactored)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.sqlite import SqliteSaver # Import inside function to avoid error if missing

from backend.agents.supervisor.state import SupervisorState
from backend.agents.diagnosis.graph import get_diagnosis_agent

logger = logging.getLogger(__name__)


def router_start_node(state: SupervisorState) -> Dict[str, Any]:
    """라우팅 결정 노드."""
    task_type = state.get("task_type", "diagnosis")
    logger.info(f"Router: Starting task {task_type}")
    # 여기서는 상태 변경 없이 로깅만 하고, 조건부 엣지에서 분기 처리
    return {}


def diagnosis_agent_entry(state: SupervisorState) -> Dict[str, Any]:
    """DiagnosisAgent 서브그래프 실행."""
    logger.info("Entering DiagnosisAgent...")
    diagnosis_agent = get_diagnosis_agent()
    result = diagnosis_agent.invoke(state)
    
    # 서브그래프 결과를 상위 상태에 병합
    return {
        "repo_snapshot": result.get("repo_snapshot"),
        "dependency_snapshot": result.get("dependency_snapshot"),
        "diagnosis_result": result.get("diagnosis_result"),
        "docs_result": result.get("docs_result"),
        "messages": result.get("messages"),
        "last_answer_kind": result.get("last_answer_kind"),
        "error_message": result.get("error_message"), # Propagate error
    }


def security_agent_entry(state: SupervisorState) -> Dict[str, Any]:
    """SecurityAgent 서브그래프 실행 (Placeholder)."""
    logger.info("Entering SecurityAgent (Placeholder)...")
    # 실제 구현은 생략됨 (요구사항)
    return {
        "security_result": {"status": "skipped", "reason": "Not implemented yet"},
        "last_answer_kind": "security",
    }


def route_after_start(state: SupervisorState) -> Literal["diagnosis_agent_entry", "security_agent_entry"]:
    """시작 후 라우팅."""
    task_type = state.get("task_type", "diagnosis")
    
    if task_type == "security":
        return "security_agent_entry"
    
    # diagnosis, diagnosis_and_security, explain 등은 diagnosis 먼저
    return "diagnosis_agent_entry"


def route_after_diagnosis(state: SupervisorState) -> Literal["security_agent_entry", "__end__"]:
    """진단 후 라우팅."""
    task_type = state.get("task_type", "diagnosis")
    
    if task_type == "diagnosis_and_security":
        return "security_agent_entry"
    
    return "__end__"


def build_supervisor_graph() -> StateGraph:
    """Supervisor 그래프 빌드."""
    graph = StateGraph(SupervisorState)

    graph.add_node("router_start_node", router_start_node)
    graph.add_node("diagnosis_agent_entry", diagnosis_agent_entry)
    graph.add_node("security_agent_entry", security_agent_entry)

    graph.set_entry_point("router_start_node")

    graph.add_conditional_edges(
        "router_start_node",
        route_after_start,
        {
            "diagnosis_agent_entry": "diagnosis_agent_entry",
            "security_agent_entry": "security_agent_entry",
        }
    )

    graph.add_conditional_edges(
        "diagnosis_agent_entry",
        route_after_diagnosis,
        {
            "security_agent_entry": "security_agent_entry",
            "__end__": END,
        }
    )

    graph.add_edge("security_agent_entry", END)

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
