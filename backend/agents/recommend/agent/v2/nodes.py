import json
import re
import ast
import asyncio
import logging
from typing import Dict, Any, List
from .state import AgentState 

# [핵심] 툴 임포트 (경로는 프로젝트 구조에 맞게 조정 필요)
# 주의: 실제 환경에 맞게 툴의 경로를 수정해야 합니다.
from tools.search_query_generator_tool import github_search_query_generator as github_search_query_generator
from tools.github_search_tool import github_search_tool
from tools.github_filter_tool import github_filter_tool
from tools.rag_query_generator_tool import generate_rag_query_and_filters as rag_query_generator
from tools.qdrant_search_executor import qdrant_search_executor
from tools.github_ingest_tool import github_ingest_tool
from tools.github_trend_search_tool import github_trend_search_tool
from tools.final_answer_generator_tool import final_answer_generator_tool


logger = logging.getLogger(__name__)

# --- 헬퍼 함수 (툴 실행 담당) ---
async def _execute_tool(tool_func, inputs: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    """비동기/동기 툴 실행 및 JSON 파싱을 처리하는 헬퍼 (최종 방어 로직)"""
    try:
        result_obj = None
        
        # 1. LangChain Tool Wrapper 호출
        if hasattr(tool_func, "ainvoke"):
            result_obj = await tool_func.ainvoke(inputs)
        else:
            # 2. Custom Tool Functions 호출
            if asyncio.iscoroutinefunction(tool_func):
                result_obj = await tool_func(**inputs) 
            else:
                result_obj = tool_func(**inputs)
                
        # 3. [최종 방어] 반환된 객체가 await 되지 않은 코루틴인 경우, 여기서 await 합니다.
        if asyncio.iscoroutine(result_obj):
             result_str = await result_obj
        else:
             result_str = result_obj
             
        if not isinstance(result_str, str):
            result_str = str(result_str)

        # 4. JSON 파싱
        try:
            result_data = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            result_data = result_str
            
        return {"result": result_data, "success": True}

    except Exception as e:
        logger.error(f"❌ Tool Execution Failed ({tool_name}): {e}")
        return {"result": {"error": str(e)}, "success": False}
    
# =================================================================
# 1. API Search Path Nodes
# =================================================================

async def search_gen_node(state: AgentState) -> Dict[str, Any]:
    """Node: (1/3) 자연어 질문을 API 파라미터로 변환"""
    print("   [Node] 1. API Query Generation...")
    result = await _execute_tool(
        github_search_query_generator, 
        {"user_input": state['user_query']}, "github_search_query_generator"
    )
    
    if result["success"] and isinstance(result["result"], dict):
         tool_result = result["result"]
         other_condition = tool_result.get("other")
         
         return {
             "search_queries": [tool_result],
             # 👈 [유실 방지 1] 최상위 State에 'other' 키 명시적 저장
             "other": other_condition if other_condition else None
         }
    else:
         return {"search_queries": []}


async def search_exec_node(state: AgentState) -> Dict[str, Any]:
    """Node: (2/3) GitHub API 검색 실행"""
    print("   [Node] 2. GitHub API Execution...")
    queries = state.get("search_queries", [])
    
    if not queries: return {"raw_candidates": [], "last_status": "fail"}
        
    params = queries[-1] 
    result = await _execute_tool(
        github_search_tool, 
        {"params": params}, "github_search_tool"
    )
    
    recommendations = result["result"] if result["success"] else []
    
    status = "success" if recommendations and len(recommendations) > 0 else "empty"
    
    # needs_filter 로직: search_gen이 반환한 쿼리 파라미터 내부의 'other' 값을 사용
    needs_filter = params.get("other") is not None
    
    return {
        "raw_candidates": recommendations, 
        "last_status": status,
        "needs_filter": needs_filter, 
        # 🌟 [유실 방지 2] 이전 State에서 받은 'other' 값을 유지하여 다음 노드에 전달
        "other": state.get("other")
    }


async def filter_exec_node(state: AgentState) -> Dict[str, Any]:
    """Node: (3/3) 검색 결과에 대한 필터링 및 점수 정렬 실행"""
    print("   [Node] 3. Filtering & Scoring Execution...")
    
    # filter_tool은 State를 통째로 받아 'raw_candidates'와 'other'를 사용해야 합니다.
    result = await _execute_tool(
        github_filter_tool, 
        {"state": state}, "github_filter_tool"
    )
    
    if result["success"] and isinstance(result["result"], dict):
        # 🌟 [핵심] 여기서 반환하는 'filtered_candidates'에는 
        # 'github_filter_tool' 내부에서 계산된 'recent_commits' 같은 활동성 지표가 
        # 반드시 통합(Merge)되어 있어야 합니다.
        filtered_list = result["result"].get("filtered_candidates", [])
        print(f"   [Filter Node] 최종 필터링된 후보 개수: {len(filtered_list)}")
        return {"filtered_candidates": filtered_list}
    else:
        print("   [Filter Node] 필터링 도구 실행 실패 또는 결과 형식 오류.")
        return {"filtered_candidates": []}


# =================================================================
# 2. RAG Path Nodes
# =================================================================
async def rag_gen_node(state: AgentState) -> Dict[str, Any]:
    """Node: (1/2) 벡터 검색용 쿼리 및 필터 생성"""
    print("   [Node] 4. RAG Query Generation...")
    
    analyzed_data = state.get("analyzed_data", None)
    
    # 툴 실행 (LLM 호출을 통해 쿼리/필터 JSON 생성)
    result = await _execute_tool(
        rag_query_generator,
        {
            "user_request": state['user_query'],
            "category": "semantic_search", 
            "analyzed_data": analyzed_data 
        }, 
        "rag_query_generator"
    )
    
    parsed_result = None
    if result["success"]:
        raw_output = result.get("result")
        
        # 🌟 [핵심 수정: 파싱 로직 추가]
        if isinstance(raw_output, str):
            try:
                # LLM이 생성한 문자열을 딕셔너리로 변환 (안전한 ast.literal_eval 사용)
                parsed_result = ast.literal_eval(raw_output)
                print(f"   [RAG Query Gen DEBUG] Successfully parsed string to dict.")
            except Exception as e:
                print(f"   [RAG Query Gen PARSING ERROR] Failed to parse string: {e}")
        elif isinstance(raw_output, dict):
            # 이미 딕셔너리인 경우 (이상적인 경우)
            parsed_result = raw_output

    # 최종 결과가 유효한 딕셔너리인지 확인하여 State 업데이트
    if parsed_result and isinstance(parsed_result, dict):
         return {"rag_queries": [parsed_result]}
    else:
         # 파싱 실패 또는 툴 실행 실패 (이 경로를 타면 안 됩니다.)
         print(f"   [RAG Query Gen] Failed or invalid result format. Success: {result['success']}")
         return {"rag_queries": []}


async def qdrant_exec_node(state: AgentState) -> Dict[str, Any]:
    """Node: (2/2) Qdrant 벡터 검색 실행 (Fallback 상태 업데이트 포함)"""
    print("   [Node] 5. Qdrant Search Execution...")
    
    rag_queries = state.get("rag_queries", [])
    
    if not rag_queries: 

        print(f"================rag_queries:{rag_queries}=====================")
        return {"raw_candidates": [], "last_status": "fail"}
        
    rag_params = rag_queries[-1]
    result = await _execute_tool(
        qdrant_search_executor,
        {
            "query": rag_params.get("query"),
            "keywords": rag_params.get("keywords"),
            "filters": rag_params.get("filters")
        }, "qdrant_search_executor"
    )
    
    recommendations = result["result"].get("final_recommendations", []) if result["success"] else []
    
    status = "success" if recommendations and len(recommendations) > 0 else "empty"
    
    return {"raw_candidates": recommendations, "last_status": status}


# =================================================================
# 3. Trend Path Node
# =================================================================

async def trend_exec_node(state: AgentState) -> Dict[str, Any]:
    """Node: (1/1) GitHub Trending API 검색 실행"""
    print("   [Node] 6. Trend Search Execution...")
    result = await _execute_tool(
        github_trend_search_tool,
        {"query": state['user_query']}, "github_trend_search_tool"
    )
    return {"final_result": result["result"] if result["success"] else []}


# =================================================================
# 4. URL Path Node
# =================================================================

async def url_analysis_node(state: AgentState) -> Dict[str, Any]:
    """Node: (1/1) URL 분석 실행 (Ingest)"""
    print("   [Node] 7. URL Analysis (Ingest) Start...")
    
    url_match = re.search(r'(https?://[^\s]+)', state['user_query'])
    target_url = url_match.group(1) if url_match else state.get("target_repo_url")
    
    if not target_url: return {"analyzed_data": {"error": "URL not found"}}

    result = await _execute_tool(
        github_ingest_tool,
        {"repo_url": target_url}, "github_ingest_tool"
    )
    return {"analyzed_data": result["result"] if result["success"] else {}}


# =================================================================
# 5. Final Recommendation Node
# =================================================================

async def final_recommendation_node(state: AgentState) -> Dict[str, Any]:
    """Node: 8. 최종 후보 목록을 기반으로 추천 이유와 함께 최종 답변을 생성"""
    print("   [Node] 8. Final Recommendation Generation...")

    # 필터링된 결과(활동성 지표 포함)를 우선 사용하고, 없다면 원본 후보를 사용합니다.
    candidates = state.get("filtered_candidates", []) or state.get("raw_candidates", [])
    
    if not candidates:
        return {"final_result": "검색 결과가 없거나, 후보를 찾지 못했습니다."}
    
    other_conditions = state.get("other") 

    result = await _execute_tool(
        final_answer_generator_tool,
        {
            "user_query": state['user_query'], 
            "candidates": candidates,
            "other_conditions": other_conditions
        },
        "final_answer_generator_tool"
    )

    return {"final_result": result["result"] if result["success"] else "최종 답변 생성에 실패했습니다."}