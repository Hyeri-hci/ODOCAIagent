from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import StateGraph, END

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
from backend.agents.supervisor.nodes.task_mapping import map_task_types_node
from backend.agents.supervisor.nodes.run_diagnosis import run_diagnosis_node
from backend.agents.supervisor.nodes.summarize_node import summarize_node


def route_after_mapping(state: SupervisorState) -> str:
    """
    mapping 이후 어떤 Agent 노드로 갈지 결정.
    - 전역 task_type + Agent별 task_type을 함께 보고 분기 가능.
    """
    task_type = state.get("task_type", "diagnose_repo_health")

    if task_type in ("diagnose_repo_health", "diagnose_repo_onboarding", "compare_two_repos"):
        return "run_diagnosis"

    if task_type in ("refine_onboarding_tasks", "explain_scores"):
        # 추후: 별도 노드 추가 가능
        return "summarize"

    return "summarize"


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    # 노드 등록
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("map_task_types", map_task_types_node)
    graph.add_node("run_diagnosis", run_diagnosis_node)
    graph.add_node("summarize", summarize_node)

    # 시작 노드
    graph.set_entry_point("classify_intent")

    # 1) Intent/전역 task_type 분류 후 → 매핑 노드로 고정
    graph.add_edge("classify_intent", "map_task_types")

    # 2) 매핑 노드 이후에는 조건 분기
    graph.add_conditional_edges(
        "map_task_types",
        route_after_mapping,
        {
            "run_diagnosis": "run_diagnosis",
            "summarize": "summarize",
        },
    )

    # 3) Diagnosis → 요약
    graph.add_edge("run_diagnosis", "summarize")

    # 4) 요약 → 종료
    graph.add_edge("summarize", END)

    return graph.compile()
