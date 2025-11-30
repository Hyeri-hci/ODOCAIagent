from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import StateGraph, END

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
from backend.agents.supervisor.nodes.task_mapping import map_task_types_node
from backend.agents.supervisor.nodes.run_diagnosis import run_diagnosis_node
from backend.agents.supervisor.nodes.summarize_node import summarize_node
from backend.agents.supervisor.nodes.refine_tasks import refine_tasks_node
from backend.agents.supervisor.intent_config import (
    needs_diagnosis, 
    is_intent_ready, 
    is_refine_intent,
    requires_previous_context,
)


def route_after_mapping(state: SupervisorState) -> str:
    """
    mapping 이후 어떤 Agent 노드로 갈지 결정.
    
    INTENT_CONFIG의 needs_diagnosis 값을 기반으로 분기합니다.
    미지원 Intent는 바로 summarize로 보내서 안내 메시지를 표시합니다.
    
    멀티턴 처리:
    - refine_onboarding_tasks: refine_tasks 노드로 분기
    - is_followup + 이전 컨텍스트 필요: refine_tasks 또는 summarize로 분기
    """
    task_type = state.get("task_type", "diagnose_repo_health")
    is_followup = state.get("is_followup", False)
    followup_type = state.get("followup_type")

    # 미지원 Intent는 바로 summarize로 (안내 메시지 표시)
    if not is_intent_ready(task_type):
        return "summarize"
    
    # refine_onboarding_tasks는 refine_tasks 노드로
    if is_refine_intent(task_type):
        return "refine_tasks"
    
    # Follow-up이면서 이전 컨텍스트가 필요한 경우
    if is_followup and requires_previous_context(task_type, followup_type):
        # 이전 Task 목록이 있으면 refine, 없으면 새로 diagnosis
        if state.get("last_task_list") or state.get("diagnosis_result"):
            return "refine_tasks"
        # 이전 결과가 없으면 새로 diagnosis 실행
    
    # INTENT_CONFIG 기반 라우팅
    if needs_diagnosis(task_type):
        return "run_diagnosis"
    
    return "summarize"


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    # 노드 등록
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("map_task_types", map_task_types_node)
    graph.add_node("run_diagnosis", run_diagnosis_node)
    graph.add_node("refine_tasks", refine_tasks_node)
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
            "refine_tasks": "refine_tasks",
            "summarize": "summarize",
        },
    )

    # 3) Diagnosis → 요약
    graph.add_edge("run_diagnosis", "summarize")
    
    # 4) Refine Tasks → 요약
    graph.add_edge("refine_tasks", "summarize")

    # 5) 요약 → 종료
    graph.add_edge("summarize", END)

    return graph.compile()
