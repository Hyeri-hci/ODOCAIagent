"""
Onboarding Agent Graph - 하이브리드 패턴 (LangGraph + 안전한 예외 처리)

향상된 에이전트 흐름:
parse_intent → analyze_diagnosis → assess_risks → fetch_issues → generate_plan → summarize
                                                                        ↓ (에러 시)
                                                                  error_handler

특징:
- 모든 노드에 @safe_node 데코레이터로 예외 처리 (nodes/intent_nodes.py 정의)
- 에러 발생 시 error_handler로 라우팅 (조건부 분기)
- Core scoring 활용 (health_score, onboarding_score, levels)
- 경험 수준별 리스크 평가
- 적응형 플랜 생성
"""
from typing import Dict, Any, Optional, Literal, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging

from backend.agents.onboarding.models import OnboardingState, OnboardingOutput
# Modularized Node Imports
from backend.agents.onboarding.nodes.intent_nodes import parse_intent_node
from backend.agents.onboarding.nodes.analysis_nodes import analyze_diagnosis_node, assess_risks_node
from backend.agents.onboarding.nodes.recommendation_nodes import fetch_recommendations_node
from backend.agents.onboarding.nodes.error_nodes import error_handler_node

logger = logging.getLogger(__name__)


# === 조건부 라우팅 (하이브리드 패턴 핵심) ===

def check_error_and_route(state: OnboardingState) -> Literal["continue", "error_handler"]:
    """에러 상태 체크 후 라우팅 - LangGraph 조건부 분기 활용"""
    if state.get("error"):
        return "error_handler"
    return "continue"


# === 그래프 빌드 (하이브리드 패턴) ===

def build_onboarding_graph():
    """
    Onboarding StateGraph 빌드 (하이브리드 패턴)
    
    향상된 흐름 (Recommend 통합):
    parse_intent → analyze_diagnosis → assess_risks → fetch_issues → generate_plan
                                                                         ↓
                                                                 fetch_recommendations
                                                                         ↓
                                                             [check_error_and_route]
                                                                    /          \\
                                                          summarize    error_handler
                                                               ↓              ↓
                                                             END            END
    
    특징:
    - 모든 노드에 @safe_node 데코레이터로 예외 처리
    - fetch_recommendations로 유사 프로젝트도 함께 가져옴
    - generate_plan 후 에러 체크로 조건부 분기 (LangGraph 장점 활용)
    - 각 노드가 독립적인 판단을 수행하는 에이전트 방식
    """
    
    graph = StateGraph(OnboardingState)
    
    # 노드 추가
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("analyze_diagnosis", analyze_diagnosis_node)
    graph.add_node("assess_risks", assess_risks_node)
    graph.add_node("fetch_issues", fetch_issues_node)
    graph.add_node("generate_plan", generate_plan_node)
    graph.add_node("fetch_recommendations", fetch_recommendations_node)  # 추천 노드 추가
    graph.add_node("summarize", summarize_node)
    graph.add_node("error_handler", error_handler_node)
    
    # 기본 순차 흐름
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "analyze_diagnosis")
    graph.add_edge("analyze_diagnosis", "assess_risks")
    graph.add_edge("assess_risks", "fetch_issues")
    graph.add_edge("fetch_issues", "generate_plan")
    graph.add_edge("generate_plan", "fetch_recommendations")  # 플랜 생성 후 추천 가져오기
    
    # fetch_recommendations 후 조건부 분기 (LangGraph 장점)
    graph.add_conditional_edges(
        "fetch_recommendations",
        check_error_and_route,
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
_onboarding_graph = None


def get_onboarding_graph():
    """Onboarding Graph 싱글톤 인스턴스"""
    global _onboarding_graph
    if _onboarding_graph is None:
        _onboarding_graph = build_onboarding_graph()
        logger.info("Onboarding Graph initialized (hybrid pattern with error handling)")
    return _onboarding_graph


# === 편의 함수 ===

async def run_onboarding_graph(
    owner: str,
    repo: str,
    experience_level: str = "beginner",
    diagnosis_summary: str = "",
    user_context: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None,
    ref: str = "main",
    include_recommendations: bool = True,
    previous_plan: Optional[List[Dict[str, Any]]] = None,
    previous_summary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Onboarding Graph 실행
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        experience_level: 사용자 경험 수준 (beginner/intermediate/advanced)
        diagnosis_summary: 진단 요약 (있으면) - dict 또는 문자열
        user_context: 사용자 컨텍스트
        user_message: 사용자 메시지 (의도 파싱용)
        ref: 브랜치/태그
        include_recommendations: 유사 프로젝트 추천 포함 여부 (기본값: True)
        previous_plan: 이전 온보딩 플랜 (Context-Aware)
        previous_summary: 이전 온보딩 요약 (Context-Aware)
    
    Returns:
        OnboardingOutput dict with agent_analysis and optional similar_projects
    """
    graph = get_onboarding_graph()
    
    initial_state: OnboardingState = {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "experience_level": experience_level,
        "diagnosis_summary": diagnosis_summary,
        "user_context": user_context or {},
        "user_message": user_message,
        "candidate_issues": None,
        "plan": None,
        "summary": None,
        # 에이전트 분석 필드 초기화
        "diagnosis_analysis": None,
        "onboarding_risks": None,
        "plan_config": None,
        "agent_decision": None,
        # 추천 관련 필드 초기화
        "similar_projects": None,
        "include_recommendations": include_recommendations,
        # 컨텍스트 필드
        "previous_plan": previous_plan,
        "previous_summary": previous_summary,
        # 결과 필드
        "result": None,
        "error": None,
        "execution_path": None
    }
    
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state.get("result", {})
    except Exception as e:
        logger.error(f"[Onboarding Agent] Graph execution failed: {e}", exc_info=True)
        # 최상위 예외 처리 - 안전한 결과 반환
        return OnboardingOutput(
            repo_id=f"{owner}/{repo}",
            experience_level=experience_level,
            error=str(e),
            summary=f"온보딩 그래프 실행 중 오류가 발생했습니다: {e}"
        ).dict()


async def run_onboarding_stream(
    owner: str,
    repo: str,
    experience_level: str = "beginner",
    diagnosis_summary: str = "",
    user_context: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None,
    ref: str = "main",
    include_recommendations: bool = True
):
    """
    Onboarding Graph 스트리밍 실행 - 각 노드 완료 시 진행 상황 전달.
    
    Yields:
        Dict with keys: step, node, progress, message, data
    """
    graph = get_onboarding_graph()
    
    initial_state: OnboardingState = {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "experience_level": experience_level,
        "diagnosis_summary": diagnosis_summary,
        "user_context": user_context or {},
        "user_message": user_message,
        "candidate_issues": None,
        "plan": None,
        "summary": None,
        "diagnosis_analysis": None,
        "onboarding_risks": None,
        "plan_config": None,
        "agent_decision": None,
        "similar_projects": None,
        "include_recommendations": include_recommendations,
        "result": None,
        "error": None,
        "execution_path": None
    }
    
    node_progress = {
        "parse_intent": {"progress": 10, "message": "의도 분석 중"},
        "analyze_diagnosis": {"progress": 25, "message": "진단 결과 분석 중"},
        "assess_risks": {"progress": 40, "message": "위험 평가 중"},
        "fetch_issues": {"progress": 55, "message": "이슈 수집 중"},
        "generate_plan": {"progress": 70, "message": "플랜 생성 중"},
        "fetch_recommendations": {"progress": 85, "message": "추천 프로젝트 검색 중"},
        "summarize": {"progress": 95, "message": "요약 생성 중"},
        "error_handler": {"progress": 100, "message": "에러 처리 중"},
    }
    
    step = 0
    final_result = None
    
    try:
        async for event in graph.astream(initial_state):
            step += 1
            for node_name, node_output in event.items():
                info = node_progress.get(node_name, {"progress": 50, "message": node_name})
                
                yield {
                    "step": step,
                    "node": node_name,
                    "progress": info["progress"],
                    "message": info["message"],
                    "data": node_output
                }
                
                if node_output.get("result"):
                    final_result = node_output.get("result")
        
        yield {
            "step": step + 1,
            "node": "complete",
            "progress": 100,
            "message": "온보딩 플랜 완료",
            "data": {"result": final_result}
        }
    except Exception as e:
        logger.error(f"[Onboarding Stream] Error: {e}")
        yield {
            "step": step + 1,
            "node": "error",
            "progress": 100,
            "message": f"오류 발생: {e}",
            "data": {"error": str(e)}
        }
