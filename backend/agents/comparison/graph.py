"""
Comparison Agent Graph - 하이브리드 패턴 (LangGraph + 안전한 예외 처리)
"""
from typing import Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
import logging

from backend.agents.comparison.models import ComparisonState, ComparisonOutput
# Modularized Node Imports
from backend.agents.comparison.nodes.validation_nodes import validate_input_node
from backend.agents.comparison.nodes.compare_nodes import compare_node
from backend.agents.comparison.nodes.error_nodes import error_handler_node

logger = logging.getLogger(__name__)

# === 조건부 라우팅 (하이브리드 패턴 핵심) ===

def check_error_after_validate(state: ComparisonState) -> Literal["continue", "error_handler"]:
    """validate_input 후 에러 체크"""
    if state.get("error"):
        return "error_handler"
    return "continue"


def check_error_after_batch(state: ComparisonState) -> Literal["continue", "error_handler"]:
    """batch_diagnosis 후 에러 체크"""
    if state.get("error"):
        return "error_handler"
    return "continue"


def check_error_after_compare(state: ComparisonState) -> Literal["continue", "error_handler"]:
    """compare 후 에러 체크"""
    if state.get("error"):
        return "error_handler"
    return "continue"


# === 그래프 빌드 (하이브리드 패턴) ===

def build_comparison_graph():
    """
    Comparison StateGraph 빌드 (하이브리드 패턴)
    
    흐름: 
    validate_input → [check] → batch_diagnosis → [check] → compare → [check] → summarize
         ↓ (에러)              ↓ (에러)               ↓ (에러)
    error_handler ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    
    특징:
    - 모든 노드에 @safe_node 데코레이터로 예외 처리
    - 각 주요 노드 후 에러 체크 → 빠른 종료 (LangGraph 장점 활용)
    - compare 노드가 Core scoring을 활용하여 독립적인 분석 및 추천 수행
    """
    
    graph = StateGraph(ComparisonState)
    
    # 노드 추가
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("batch_diagnosis", batch_diagnosis_node)
    graph.add_node("compare", compare_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("error_handler", error_handler_node)  # 에러 핸들러 추가
    
    # 엔트리 포인트
    graph.set_entry_point("validate_input")
    
    # validate_input 후 조건부 분기
    graph.add_conditional_edges(
        "validate_input",
        check_error_after_validate,
        {
            "continue": "batch_diagnosis",
            "error_handler": "error_handler"
        }
    )
    
    # batch_diagnosis 후 조건부 분기
    graph.add_conditional_edges(
        "batch_diagnosis",
        check_error_after_batch,
        {
            "continue": "compare",
            "error_handler": "error_handler"
        }
    )
    
    # compare 후 조건부 분기
    graph.add_conditional_edges(
        "compare",
        check_error_after_compare,
        {
            "continue": "summarize",
            "error_handler": "error_handler"
        }
    )
    
    # 종료 엣지
    graph.add_edge("summarize", END)
    graph.add_edge("error_handler", END)
    
    return graph.compile()


# === 싱글톤 그래프 ===
_comparison_graph = None


def get_comparison_graph():
    """Comparison Graph 싱글톤 인스턴스"""
    global _comparison_graph
    if _comparison_graph is None:
        _comparison_graph = build_comparison_graph()
        logger.info("Comparison Graph initialized (hybrid pattern with error handling)")
    return _comparison_graph


# === 편의 함수 ===

async def run_comparison_graph(
    repos: list,
    ref: str = "main",
    use_cache: bool = True,
    user_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Comparison Graph 실행
    
    Args:
        repos: 비교할 저장소 목록 ["owner/repo", ...]
        ref: 분석할 브랜치/태그
        use_cache: 캐시 사용 여부
        user_message: 사용자 메시지 (있으면)
    
    Returns:
        ComparisonOutput dict with agent_analysis
    """
    graph = get_comparison_graph()
    
    initial_state: ComparisonState = {
        "repos": repos,
        "ref": ref,
        "use_cache": use_cache,
        "user_message": user_message,
        "validated_repos": None,
        "batch_results": None,
        "comparison_data": None,
        # 에이전트 분석 필드 초기화
        "agent_analysis": None,
        # 캐시 관련
        "cache_hits": None,
        "cache_misses": None,
        "warnings": None,
        # 결과 필드
        "comparison_summary": None,
        "result": None,
        "error": None,
        "execution_path": None
    }
    
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state.get("result", {})
    except Exception as e:
        logger.error(f"[Comparison Agent] Graph execution failed: {e}", exc_info=True)
        # 최상위 예외 처리 - 안전한 결과 반환
        return ComparisonOutput(
            results={},
            comparison_summary=f"비교 그래프 실행 중 오류가 발생했습니다: {e}",
            warnings=[str(e)]
        ).dict()
