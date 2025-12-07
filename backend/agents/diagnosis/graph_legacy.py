"""Diagnosis Agent Subgraph (Legacy).
# NOTE: 현재 v1에서는 사용하지 않는 실험용/레거시 그래프입니다.
# 메인 실행 경로는 Supervisor -> run_diagnosis_node (DTO 기반 서비스) 입니다.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_scores
from backend.core.models import RepoSnapshot

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


def fetch_repo_data_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 1: GitHub 데이터 fetch → state['repo_snapshot']에 저장."""
    owner = state.owner
    repo = state.repo
    repo_ref = "HEAD" # state에 repo_ref가 없으므로 기본값 사용 or user_context 확인

    if not owner or not repo:
        return {"error_message": "owner/repo가 필요합니다."}

    try:
        snapshot = fetch_repo_snapshot(owner, repo, repo_ref)
        return {"repo_snapshot": snapshot}
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return {"error_message": str(e)}


def run_diagnosis_core_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 2: Core 레이어 진단 실행."""
    snapshot: Optional[RepoSnapshot] = state.user_context.get("repo_snapshot")
    
    # NOTE: repo_snapshot is stored in user_context because it's not part of the SupervisorState model in this legacy graph.
    snapshot = state.user_context.get("repo_snapshot")
    project_rules = state.user_context.get("project_rules")

    if not snapshot:
        return {"error_message": "저장소 스냅샷이 없습니다."}

    try:
        # 1. 의존성 분석
        deps = parse_dependencies(snapshot)
        
        # 2. 문서 분석
        docs_result = analyze_docs(snapshot)
        
        # 3. 활동성 분석
        activity_result = analyze_activity(snapshot)
        
        # 4. 종합 점수 계산
        diagnosis = compute_scores(docs_result, activity_result, deps)
        
        return {
            "dependency_snapshot": deps,
            "docs_result": docs_result,
            "activity_result": activity_result,
            "diagnosis_result": diagnosis,
        }
    except Exception as e:
        logger.error(f"Diagnosis core failed: {e}")
        return {"error_message": str(e)}


def summarize_diagnosis_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 3: 진단 결과 요약 (Simple Text)."""
    diagnosis = state.diagnosis_result
    docs_result = state.user_context.get("docs_result")

    if not diagnosis:
        return {
            "messages": [AIMessage(content="진단 결과가 없습니다.")],
            "last_answer_kind": "none"
        }

    # 1. Fallback Summary
    fallback_summary = (
        f"### {diagnosis.repo_id} 진단 결과\n\n"
        f"- **건강 점수**: {diagnosis.health_score}점 ({diagnosis.health_level})\n"
        f"- **문서 품질**: {diagnosis.documentation_quality}점\n"
        f"- **활동성**: {diagnosis.activity_maintainability}점\n"
        f"- **온보딩**: {diagnosis.onboarding_score}점 ({diagnosis.onboarding_level})\n\n"
        f"**주요 이슈**:\n"
        f"- 문서: {', '.join(diagnosis.docs_issues) or '없음'}\n"
        f"- 활동성: {', '.join(diagnosis.activity_issues) or '없음'}"
    )

    # 2. Check No-LLM Mode
    if not state.user_context.get("use_llm_summary", True):
        # LLM 사용 안 함 -> 바로 Fallback 반환 (로그 없음)
        return {
            "messages": [AIMessage(content=fallback_summary)],
            "last_answer_kind": "report"
        }

    # 3. LLM Summary (Optional)
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME

        client = fetch_llm_client()
        
        system_prompt = (
            "You are an expert software engineering consultant. "
            "Analyze the provided repository diagnosis data and provide a concise, professional summary in Korean. "
            "Highlight key strengths, critical issues, and actionable recommendations. "
            "Use markdown formatting with the following sections:\n"
            "1. **Summary**: Overall assessment.\n"
            "2. **Key Issues**: Critical problems found.\n"
            "3. **Recommendations**: Actionable steps to improve."
        )
        
        docs_detail = ""
        if docs_result:
            missing = ", ".join(docs_result.missing_sections) or "None"
            marketing = f"{docs_result.marketing_ratio:.2f}"
            docs_detail = (
                f"Missing Sections: {missing}\n"
                f"Marketing Ratio: {marketing}\n"
            )
        
        user_prompt = (
            f"Repository: {diagnosis.repo_id}\n"
            f"Health Score: {diagnosis.health_score} ({diagnosis.health_level})\n"
            f"Docs Quality: {diagnosis.documentation_quality}\n"
            f"Activity Score: {diagnosis.activity_maintainability}\n"
            f"Onboarding Score: {diagnosis.onboarding_score} ({diagnosis.onboarding_level})\n"
            f"Docs Issues: {', '.join(diagnosis.docs_issues)}\n"
            f"Activity Issues: {', '.join(diagnosis.activity_issues)}\n"
            f"Dependency Complexity: {diagnosis.dependency_complexity_score} (Flags: {', '.join(diagnosis.dependency_flags) or 'None'})\n"
            f"{docs_detail}\n"
            "Please summarize this diagnosis."
        )

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.2,
        )
        
        response = client.chat(request, timeout=10)
        return {
            "messages": [AIMessage(content=response.content)],
            "last_answer_kind": "report"
        }

    except Exception as e:
        logger.debug(f"LLM summary full traceback: {e}", exc_info=True)
        logger.warning(f"LLM summary failed (using fallback): {e}")
        return {
            "messages": [AIMessage(content=fallback_summary)],
            "last_answer_kind": "report"
        }


def route_after_fetch(state: SupervisorState) -> Literal["run_diagnosis_core", "__end__"]:
    """Fetch 실패 시 조기 종료."""
    if state.error:
        return "__end__"
    return "run_diagnosis_core"


def route_after_core(state: SupervisorState) -> Literal["summarize_diagnosis", "__end__"]:
    """Core 진단 실패 시 조기 종료."""
    if state.error:
        return "__end__"
    return "summarize_diagnosis"


def build_diagnosis_graph() -> StateGraph:
    """Diagnosis 서브그래프 빌드."""
    graph = StateGraph(SupervisorState)

    graph.add_node("fetch_repo_data", fetch_repo_data_node)
    graph.add_node("run_diagnosis_core", run_diagnosis_core_node)
    graph.add_node("summarize_diagnosis", summarize_diagnosis_node)

    graph.set_entry_point("fetch_repo_data")

    graph.add_conditional_edges(
        "fetch_repo_data",
        route_after_fetch,
        {
            "run_diagnosis_core": "run_diagnosis_core",
            "__end__": END,
        }
    )

    graph.add_conditional_edges(
        "run_diagnosis_core",
        route_after_core,
        {
            "summarize_diagnosis": "summarize_diagnosis",
            "__end__": END,
        }
    )

    graph.add_edge("summarize_diagnosis", END)

    return graph


def get_diagnosis_agent():
    """컴파일된 Diagnosis 서브그래프 반환."""
    return build_diagnosis_graph().compile()
