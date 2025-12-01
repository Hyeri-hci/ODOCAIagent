"""
Supervisor Graph 정의.

새로운 3 Intent + SubIntent 구조:
- intent: analyze | followup | general_qa
- sub_intent: health | onboarding | compare | explain | refine | concept | chat

라우팅은 INTENT_META[intent, sub_intent]를 기반으로 합니다.
"""
from __future__ import annotations

from typing import Any, Dict

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
from backend.agents.supervisor.intent_config import (
    get_intent_meta,
    should_run_diagnosis,
    intent_requires_repo,
    intent_requires_previous_result,
    is_chat,
    is_concept_qa,
)


def route_after_mapping(state: SupervisorState) -> str:
    """
    mapping 이후 어떤 Agent 노드로 갈지 결정.
    
    INTENT_META[(intent, sub_intent)]를 기반으로 분기합니다.
    
    라우팅 우선순위 (단순화):
    1. error_message가 이미 있으면 → summarize (LLM 호출 없이 반환)
    2. requires_repo=True인데 repo 없음 → error_message 설정 후 summarize
    3. runs_diagnosis=True → run_diagnosis
    4. 기타 (general_qa 등) → summarize
    """
    # 현재 상태 추출
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent") or DEFAULT_SUB_INTENT
    
    # INTENT_META에서 메타 정보 조회
    meta = get_intent_meta(intent, sub_intent)
    
    # 1. 이미 error_message가 있으면 바로 summarize로
    if state.get("error_message"):
        return "summarize"
    
    # 2. repo 필수인데 없는 경우
    if meta["requires_repo"] and not state.get("repo"):
        state["error_message"] = "어떤 저장소를 기준으로 분석할지 알려주세요. 예: facebook/react 또는 GitHub URL"
        return "summarize"
    
    # 3. runs_diagnosis=True이면 run_diagnosis로
    if meta["runs_diagnosis"]:
        return "run_diagnosis"
    
    # 4. 그 외 (concept, chat 등) → summarize
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
