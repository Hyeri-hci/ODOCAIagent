from langgraph.graph import StateGraph, END # END 임포트 추가
from backend.agents.recommend.agent.state import RecommendState
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

from backend.agents.recommend.agent.nodes import (
    parse_initial_request_node, fetch_snapshot_node, analyze_readme_summary_node, generate_api_search_query_node,
    generate_rag_search_query_node, github_search_node, vector_search_node, score_candidates_node, check_ingest_error_node, trend_search_node,
    route_after_analysis, route_after_api_query_gen, route_after_error_check, route_after_fetch, route_after_github_search,
    route_after_parsing, route_after_rag_query_gen, route_after_scoring, route_after_trend_search, route_after_vector_search,

)

def build_recommned_graph():
    workflow = StateGraph(RecommendState)
    
    # 1. 노드 등록
    workflow.add_node("parse_initial_request_node", parse_initial_request_node)
    workflow.add_node("fetch_snapshot_node", fetch_snapshot_node)
    workflow.add_node("analyze_readme_summary_node", analyze_readme_summary_node)
    
    # RAG 쿼리 노드와 API 쿼리 노드
    workflow.add_node("generate_rag_query_node", generate_rag_search_query_node)
    workflow.add_node("generate_api_search_query_node", generate_api_search_query_node) 
    
    # GitHub Search 노드
    workflow.add_node("github_search_node", github_search_node) 
    
    workflow.add_node("vector_search_node", vector_search_node)
    workflow.add_node("score_candidates_node", score_candidates_node)
    workflow.add_node("check_ingest_error_node", check_ingest_error_node)
    workflow.add_node("trend_search_node", trend_search_node)

    
    # 2. 진입점 설정
    workflow.set_entry_point("parse_initial_request_node")
    
    # 3. 엣지 연결 및 조건부 라우팅
    # 3.1. 초기 분기
    workflow.add_conditional_edges("parse_initial_request_node", route_after_parsing)
    
    # 3.2. URL 분석 흐름
    workflow.add_conditional_edges("fetch_snapshot_node", route_after_fetch)
    workflow.add_conditional_edges("analyze_readme_summary_node", route_after_analysis)
    
    # 3.3. 쿼리 생성 후 검색 흐름
    workflow.add_conditional_edges("generate_rag_query_node", route_after_rag_query_gen) 
    workflow.add_conditional_edges("generate_api_search_query_node", route_after_api_query_gen) 
    
    # 3.4. GitHub Search 후 Vector DB로 합류
    workflow.add_conditional_edges("github_search_node", route_after_github_search)
    
    # 3.5. Vector Search 후 Scoring
    workflow.add_conditional_edges("vector_search_node", route_after_vector_search)
    
    # 3.6. Trend Search 후 Scoring (ai_reason 생성을 위해)
    workflow.add_conditional_edges("trend_search_node", route_after_trend_search)
    
    # 3.7. Scoring 후 최종 요약 노드로 이동 (route_after_scoring이 generate_final_summary_node로 라우팅)
    workflow.add_conditional_edges("score_candidates_node", route_after_scoring) 
    
    # 3.9. 에러 복구 라우팅 (복구 후 해당 단계 재시도)
    # route_after_error_check는 END를 반환하거나 실패 단계로 돌아가도록 구성되어야 합니다.
    workflow.add_conditional_edges("check_ingest_error_node", route_after_error_check)
    
    return workflow.compile()

_recommend_graph = None

def get_recommend_graph():
    global _recommend_graph
    if _recommend_graph is None:
        _recommend_graph = build_recommned_graph()
        logger.info("Recommendation Graph initialized")
    return _recommend_graph


async def run_recommend(
    owner: str,
    repo: str,
    ref: str = "main",
    user_message: Optional[str] = None,
    skip_intent_parsing: bool = True,  # 기본적으로 Supervisor에서 이미 파싱됨
) -> Dict[str, Any]:
    """추천 에이전트 실행
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        ref: 브랜치/태그
        user_message: 사용자 메시지
        skip_intent_parsing: True면 내부 LLM intent parsing 건너뛰기
                           (Supervisor에서 이미 intent를 파싱한 경우)
    """
    graph = get_recommend_graph()
    initial_state: RecommendState = {
        "owner": owner,
        "repo": repo,
        "repo_url": f"{owner}/{repo}",
        "ref": ref,
        "user_request": user_message,
        "skip_intent_parsing": skip_intent_parsing,
        "user_intent": "semantic_search",  # 기본값 설정
    }
    
    final_state = await graph.ainvoke(initial_state)
    
    return final_state
