"""Diagnosis LangGraph 정의.

저장소 진단을 위한 독립적인 LangGraph.
각 분석 단계가 노드로 분리되어 부분 실패 복구가 가능

그래프 구조:
    fetch_snapshot_node
           ↓
    analyze_docs_node
           ↓
    analyze_activity_node
           ↓
    analyze_structure_node (quick 모드에서는 스킵)
           ↓
    parse_deps_node (quick 모드에서는 스킵)
           ↓
    compute_scores_node
           ↓
    generate_summary_node
           ↓
    build_output_node
           ↓
        END
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from backend.agents.diagnosis.models import DiagnosisState, DiagnosisInput, DiagnosisOutput
from backend.agents.diagnosis.nodes import (
    fetch_snapshot_node,
    analyze_docs_node,
    analyze_activity_node,
    analyze_structure_node,
    parse_deps_node,
    compute_scores_node,
    generate_summary_node,
    build_output_node,
    check_error_node,
    route_after_snapshot,
    route_after_docs,
    route_after_activity,
    route_after_structure,
    route_after_deps,
    route_after_scores,
    route_after_summary,
    route_after_error_check,
)

logger = logging.getLogger(__name__)

# 싱글톤 그래프 인스턴스
_diagnosis_graph = None


def build_diagnosis_graph() -> StateGraph:
    """Diagnosis LangGraph 빌드."""
    
    # 상태 그래프 생성
    graph = StateGraph(DiagnosisState)
    
    # 노드 등록
    graph.add_node("fetch_snapshot_node", fetch_snapshot_node)
    graph.add_node("analyze_docs_node", analyze_docs_node)
    graph.add_node("analyze_activity_node", analyze_activity_node)
    graph.add_node("analyze_structure_node", analyze_structure_node)
    graph.add_node("parse_deps_node", parse_deps_node)
    graph.add_node("compute_scores_node", compute_scores_node)
    graph.add_node("generate_summary_node", generate_summary_node)
    graph.add_node("build_output_node", build_output_node)
    graph.add_node("check_error_node", check_error_node)
    
    # 시작점 설정
    graph.set_entry_point("fetch_snapshot_node")
    
    # 조건부 엣지 설정
    graph.add_conditional_edges(
        "fetch_snapshot_node",
        route_after_snapshot,
        {
            "check_error_node": "check_error_node",
            "analyze_docs_node": "analyze_docs_node",
        }
    )
    
    graph.add_conditional_edges(
        "analyze_docs_node",
        route_after_docs,
        {
            "check_error_node": "check_error_node",
            "analyze_activity_node": "analyze_activity_node",
        }
    )
    
    graph.add_conditional_edges(
        "analyze_activity_node",
        route_after_activity,
        {
            "check_error_node": "check_error_node",
            "analyze_structure_node": "analyze_structure_node",
            "compute_scores_node": "compute_scores_node",  # quick 모드
        }
    )
    
    graph.add_conditional_edges(
        "analyze_structure_node",
        route_after_structure,
        {
            "check_error_node": "check_error_node",
            "parse_deps_node": "parse_deps_node",
        }
    )
    
    graph.add_conditional_edges(
        "parse_deps_node",
        route_after_deps,
        {
            "check_error_node": "check_error_node",
            "compute_scores_node": "compute_scores_node",
        }
    )
    
    graph.add_conditional_edges(
        "compute_scores_node",
        route_after_scores,
        {
            "check_error_node": "check_error_node",
            "generate_summary_node": "generate_summary_node",
        }
    )
    
    graph.add_conditional_edges(
        "generate_summary_node",
        route_after_summary,
        {
            "build_output_node": "build_output_node",
        }
    )
    
    graph.add_conditional_edges(
        "check_error_node",
        route_after_error_check,
        {
            "fetch_snapshot_node": "fetch_snapshot_node",
            "analyze_docs_node": "analyze_docs_node",
            "analyze_activity_node": "analyze_activity_node",
            "analyze_structure_node": "analyze_structure_node",
            "build_output_node": "build_output_node",
        }
    )
    
    # 종료 노드
    graph.add_edge("build_output_node", END)
    
    return graph


def get_diagnosis_graph():
    """컴파일된 Diagnosis 그래프 반환 (싱글톤)."""
    global _diagnosis_graph
    
    if _diagnosis_graph is None:
        graph = build_diagnosis_graph()
        _diagnosis_graph = graph.compile()
        logger.info("Diagnosis graph compiled")
    
    return _diagnosis_graph


def run_diagnosis_graph(input_data: DiagnosisInput) -> DiagnosisOutput:
    """
    Diagnosis 그래프 실행.
    """
    graph = get_diagnosis_graph()
    
    # 초기 상태 생성
    initial_state = DiagnosisState(
        owner=input_data.owner,
        repo=input_data.repo,
        ref=input_data.ref,
        analysis_depth=input_data.analysis_depth,
        use_llm_summary=input_data.use_llm_summary,
    )
    
    config = {
        "configurable": {
            "thread_id": f"diagnosis_{input_data.owner}/{input_data.repo}"
        }
    }
    
    logger.info(f"Running diagnosis graph for {input_data.owner}/{input_data.repo} "
                f"with depth={input_data.analysis_depth}")
    
    # 그래프 실행
    result = graph.invoke(initial_state, config=config)
    
    # 결과 추출
    if hasattr(result, "diagnosis_output"):
        output_dict = result.diagnosis_output
    elif isinstance(result, dict):
        output_dict = result.get("diagnosis_output", {})
    else:
        output_dict = {}
    
    if not output_dict:
        # 에러 또는 빈 결과 - 부분 결과로 생성
        logger.warning("Empty diagnosis output, using partial result")
        output_dict = {
            "repo_id": f"{input_data.owner}/{input_data.repo}",
            "health_score": 50,
            "health_level": "unknown",
            "onboarding_score": 50,
            "onboarding_level": "unknown",
            "docs": {},
            "activity": {},
            "structure": {},
            "dependency_complexity_score": 0,
            "dependency_flags": [],
            "stars": 0,
            "forks": 0,
            "summary_for_user": "분석 중 오류가 발생했습니다.",
            "raw_metrics": {},
        }
    
    # DiagnosisOutput으로 변환
    return DiagnosisOutput(
        repo_id=output_dict.get("repo_id", f"{input_data.owner}/{input_data.repo}"),
        health_score=float(output_dict.get("health_score", 50)),
        health_level=output_dict.get("health_level", "unknown"),
        onboarding_score=float(output_dict.get("onboarding_score", 50)),
        onboarding_level=output_dict.get("onboarding_level", "unknown"),
        docs=output_dict.get("docs", {}),
        activity=output_dict.get("activity", {}),
        structure=output_dict.get("structure", {}),
        dependency_complexity_score=output_dict.get("dependency_complexity_score", 0),
        dependency_flags=output_dict.get("dependency_flags", []),
        stars=output_dict.get("stars", 0),
        forks=output_dict.get("forks", 0),
        summary_for_user=output_dict.get("summary_for_user", ""),
        raw_metrics=output_dict.get("raw_metrics", {}),
    )
