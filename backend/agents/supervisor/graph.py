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
from backend.agents.supervisor.nodes.error_recovery_nodes import (
    smart_error_recovery_node,
    partial_result_recovery_node,
)
from backend.agents.supervisor.nodes.reflection_nodes import (
    self_reflection_node,
)
from backend.agents.supervisor.nodes.meta_nodes import (
    parse_supervisor_intent,
    create_supervisor_plan,
    execute_supervisor_plan,
    reflect_supervisor,
    finalize_supervisor_answer,
)

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
    
    # 노드 등록 - 에러 복구 노드
    graph.add_node("smart_error_recovery_node", smart_error_recovery_node)
    graph.add_node("partial_result_recovery_node", partial_result_recovery_node)
    
    # 노드 등록 - 자기 성찰 노드
    graph.add_node("self_reflection_node", self_reflection_node)

    # 노드 등록 - 메타 에이전트 노드
    graph.add_node("parse_supervisor_intent", parse_supervisor_intent)
    graph.add_node("create_supervisor_plan", create_supervisor_plan)
    graph.add_node("execute_supervisor_plan", execute_supervisor_plan)
    graph.add_node("reflect_supervisor", reflect_supervisor)
    graph.add_node("finalize_supervisor_answer", finalize_supervisor_answer)

    # Entry Point Router
    def _entry_router(state: SupervisorState) -> Literal["parse_supervisor_intent", "intent_analysis_node"]:
        # chat_message도 확인하여 메타 에이전트로 라우팅 (API 입력 호환성)
        # task_type="diagnose_repo"도 메타 에이전트로 보내서 동적 계획 수립 (FAST/FULL 등)
        if state.task_type in ["general_inquiry", "diagnose_repo"] or state.user_message or state.chat_message or state.global_intent:
            return "parse_supervisor_intent"
        return "intent_analysis_node"

    graph.set_conditional_entry_point(
        _entry_router,
        {
            "parse_supervisor_intent": "parse_supervisor_intent",
            "intent_analysis_node": "intent_analysis_node",
        }
    )

    # 메타 에이전트 플로우
    graph.add_edge("parse_supervisor_intent", "create_supervisor_plan")
    graph.add_edge("create_supervisor_plan", "execute_supervisor_plan")
    graph.add_edge("execute_supervisor_plan", "reflect_supervisor")

    def _route_after_meta_reflection(state: SupervisorState) -> Literal["execute_supervisor_plan", "finalize_supervisor_answer"]:
        if state.next_node_override == "execute_supervisor_plan":
            return "execute_supervisor_plan"
        return "finalize_supervisor_answer"

    graph.add_conditional_edges(
        "reflect_supervisor",
        _route_after_meta_reflection,
        {
            "execute_supervisor_plan": "execute_supervisor_plan",
            "finalize_supervisor_answer": "finalize_supervisor_answer",
        }
    )
    graph.add_edge("finalize_supervisor_answer", END)

    # 기존 플로우 연결
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

    # run_diagnosis_node -> conditional routing (에러 복구 또는 품질 검사)
    def _route_after_diagnosis(state: SupervisorState) -> Literal[
        "smart_error_recovery_node", "quality_check_node"
    ]:
        if state.error:
            return "smart_error_recovery_node"
        return "quality_check_node"
    
    graph.add_conditional_edges(
        "run_diagnosis_node",
        _route_after_diagnosis,
        {
            "smart_error_recovery_node": "smart_error_recovery_node",
            "quality_check_node": "quality_check_node",
        }
    )

    # smart_error_recovery_node -> conditional routing
    def _route_after_error_recovery(state: SupervisorState) -> Literal[
        "run_diagnosis_node", "partial_result_recovery_node", "__end__"
    ]:
        next_node = state.next_node_override
        if next_node == "run_diagnosis_node":
            return "run_diagnosis_node"
        elif next_node == "__end__" or state.error:
            return "__end__"
        # fallback이나 skip인 경우
        return "partial_result_recovery_node"
    
    graph.add_conditional_edges(
        "smart_error_recovery_node",
        _route_after_error_recovery,
        {
            "run_diagnosis_node": "run_diagnosis_node",
            "partial_result_recovery_node": "partial_result_recovery_node",
            "__end__": END,
        }
    )
    
    # partial_result_recovery_node -> END
    graph.add_edge("partial_result_recovery_node", END)

    # quality_check_node -> conditional routing (성찰 또는 다음 단계)
    def _route_after_quality(state: SupervisorState) -> Literal[
        "run_diagnosis_node", "self_reflection_node", "fetch_issues_node", "compare_results_node", "__end__"
    ]:
        if state.error:
            return "__end__"
        
        # deep 분석이거나 reflection 활성화된 경우 성찰 노드로
        if state.analysis_depth == "deep" or state.user_context.get("enable_reflection"):
            return "self_reflection_node"
        
        return route_after_quality_check(state)

    graph.add_conditional_edges(
        "quality_check_node",
        _route_after_quality,
        {
            "run_diagnosis_node": "run_diagnosis_node",
            "self_reflection_node": "self_reflection_node",
            "fetch_issues_node": "fetch_issues_node",
            "compare_results_node": "compare_results_node",
            "__end__": END,
        }
    )
    
    # self_reflection_node -> conditional routing
    def _route_after_reflection(state: SupervisorState) -> Literal[
        "run_diagnosis_node", "fetch_issues_node", "compare_results_node", "__end__"
    ]:
        next_node = state.next_node_override
        if next_node == "run_diagnosis_node":
            return "run_diagnosis_node"
        elif next_node == "fetch_issues_node":
            return "fetch_issues_node"
        elif next_node == "compare_results_node":
            return "compare_results_node"
        return "__end__"
    
    graph.add_conditional_edges(
        "self_reflection_node",
        _route_after_reflection,
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
    
    # MemorySaver 사용 (SqliteSaver 대신 - sqlite 미사용)
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    logger.info("Using MemorySaver for state persistence.")

    return graph.compile(checkpointer=checkpointer)

