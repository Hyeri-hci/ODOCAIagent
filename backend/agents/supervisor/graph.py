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
    set_session_id,
    get_session_id,
)

logger = logging.getLogger(__name__)

# Agentic 모드 활성화 여부 (점진적 마이그레이션용)
AGENTIC_MODE = os.getenv("ODOC_AGENTIC_MODE", "false").lower() in ("1", "true")


# Agentic 노드들 (AGENTIC_MODE=true일 때 사용)
def infer_missing_node(state: SupervisorState) -> Dict[str, Any]:
    """Active Inference 노드 - 누락 정보 추론."""
    from backend.agents.supervisor.inference import (
        infer_missing,
        needs_disambiguation,
        build_disambiguation_message,
    )
    
    with span("infer_missing", actor="supervisor"):
        user_query = state.get("user_query", "")
        hints = infer_missing(user_query, state)
        
        # 저장소 정보 업데이트
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
        
        # disambiguation 필요 여부 체크
        if needs_disambiguation(hints):
            msg = build_disambiguation_message(hints)
            return {
                "error_message": msg,
                "_needs_disambiguation": True,
            }
        
        return {"_inference_hints": hints.model_dump()}


def build_plan_node(state: SupervisorState) -> Dict[str, Any]:
    """Plan 수립 노드."""
    from backend.agents.supervisor.nodes.planner import planner_node
    return planner_node(state)


def execute_plan_node(state: SupervisorState) -> Dict[str, Any]:
    """Plan 실행 노드."""
    from backend.agents.supervisor.executor import (
        execute_plan,
        create_default_agent_runners,
        PlanExecutionContext,
    )
    from backend.common.events import get_session_id
    
    with span("execute_plan", actor="supervisor"):
        plan_output = state.get("plan_output")
        if not plan_output or not plan_output.plan:
            # Plan이 없으면 기존 방식으로 진행
            return {}
        
        session_id = get_session_id() or generate_session_id()
        ctx = PlanExecutionContext(
            session_id=session_id,
            agent_runners=create_default_agent_runners(),
            state=state,
        )
        
        result = execute_plan(plan_output.plan, ctx)
        
        # 결과에서 diagnosis_result 추출
        diagnosis_result = None
        for step_id, step_result in result.get("results", {}).items():
            if "diagnosis" in step_id and step_result.get("result"):
                diagnosis_result = step_result["result"]
                break
        
        return {
            "_plan_execution_result": result,
            "_plan_status": result.get("status"),
            "diagnosis_result": diagnosis_result,
        }


# 라우팅 함수들
def route_after_mapping(state: SupervisorState) -> str:
    """INTENT_META 기반 라우팅 분기."""
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent") or DEFAULT_SUB_INTENT
    
    meta = get_intent_meta(intent, sub_intent)
    
    emit_event(
        EventType.SUPERVISOR_ROUTE_SELECTED,
        outputs={"intent": intent, "sub_intent": sub_intent, "meta": dict(meta)}
    )
    
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


def route_after_inference(state: SupervisorState) -> str:
    """Inference 후 라우팅 (Agentic 모드)."""
    # disambiguation 필요
    if state.get("_needs_disambiguation"):
        return "summarize"
    
    # 에러 있음
    if state.get("error_message"):
        return "summarize"
    
    return "build_plan"


def route_after_plan(state: SupervisorState) -> str:
    """Plan 수립 후 라우팅."""
    plan_output = state.get("plan_output")
    
    # Plan이 비어있으면 바로 요약
    if not plan_output or not plan_output.plan:
        return "summarize"
    
    # disambiguation 필요
    if plan_output.intent == "disambiguation":
        return "summarize"
    
    return "execute_plan"


# Graph Builders
def build_supervisor_graph():
    """기존 Supervisor Graph (하위 호환)."""
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


def build_agentic_supervisor_graph():
    """
    Agentic Supervisor Graph (v2).
    
    확장된 파이프라인:
    1. classify_intent: Intent/SubIntent 분류
    2. infer_missing: Active Inference (누락 정보 추론)
    3. build_plan: Plan 수립 (reasoning_trace 포함)
    4. execute_plan: Plan 실행 (에러 정책 기반)
    5. summarize: 최종 요약 (AnswerContract 검증)
    
    환경변수 ODOC_AGENTIC_MODE=true로 활성화
    """
    graph = StateGraph(SupervisorState)

    # 노드 등록
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("infer_missing", infer_missing_node)
    graph.add_node("build_plan", build_plan_node)
    graph.add_node("execute_plan", execute_plan_node)
    graph.add_node("summarize", summarize_node)

    # 시작 노드
    graph.set_entry_point("classify_intent")

    # 1) Intent 분류 → Active Inference
    graph.add_edge("classify_intent", "infer_missing")

    # 2) Inference 후 조건 분기
    graph.add_conditional_edges(
        "infer_missing",
        route_after_inference,
        {
            "build_plan": "build_plan",
            "summarize": "summarize",
        },
    )

    # 3) Plan 수립 후 조건 분기
    graph.add_conditional_edges(
        "build_plan",
        route_after_plan,
        {
            "execute_plan": "execute_plan",
            "summarize": "summarize",
        },
    )

    # 4) Plan 실행 → 요약
    graph.add_edge("execute_plan", "summarize")

    # 5) 요약 → 종료
    graph.add_edge("summarize", END)

    return graph.compile()


def get_supervisor_graph():
    """환경에 따라 적절한 Graph 반환."""
    if AGENTIC_MODE:
        logger.info("Using Agentic Supervisor Graph (v2)")
        return build_agentic_supervisor_graph()
    else:
        logger.info("Using Standard Supervisor Graph (v1)")
        return build_supervisor_graph()    # 5) 요약 → 종료
    graph.add_edge("summarize", END)

    return graph.compile()
