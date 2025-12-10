from langgraph.graph import StateGraph, END
# agent.nodes 파일에 새로운 함수들이 정의되어야 합니다.
from agent.state import AgentState
from agent.router import route_query
from agent.nodes import (
    search_gen_node,
    search_exec_node,
    filter_exec_node,
    rag_gen_node,
    qdrant_exec_node,
    trend_exec_node,
    url_analysis_node,
    final_recommendation_node
)

# 🚦 Decision Node (Fallback Logic)
def check_rag_result(state: AgentState):
    """RAG 검색 결과 확인 후 대체 경로 결정"""
    status = state.get("last_status")
    
    if status == "empty" or status == "fail":
        print("🚨 RAG 검색 실패. API Search (search_gen)로 대체 경로 설정.")
        return "fallback_to_api" 
    
    return "finalize"

# 🚦 [NEW] Decision Node for Optional Filter
def check_filter_needed(state: AgentState):
    """search_exec 결과에 따라 필터 노드 실행 여부를 결정합니다."""
    if state.get("needs_filter", False):
        print("⚙️ [Filter Check] 'other' condition detected. Proceeding to filter_exec.")
        return "to_filter"
    else:
        print("⚙️ [Filter Check] No 'other' condition. Skipping filter_exec.")
        return "to_final_rec"


# 1. 그래프 생성
workflow = StateGraph(AgentState)

# 2. 노드 추가 (이전과 동일)
workflow.add_node("router", route_query)
workflow.add_node("search_gen", search_gen_node)
workflow.add_node("search_exec", search_exec_node)
workflow.add_node("filter_exec", filter_exec_node)
workflow.add_node("rag_gen", rag_gen_node)
workflow.add_node("qdrant_exec", qdrant_exec_node)
workflow.add_node("trend_exec", trend_exec_node)
workflow.add_node("url_exec", url_analysis_node)
workflow.add_node("final_rec", final_recommendation_node)

# 3. 시작점 설정 (이전과 동일)
workflow.set_entry_point("router")

# 4. 조건부 엣지 설정 (Router)
def get_next_node(state: AgentState):
    category = state["category"]
    if category == "trend": return "trend_exec"
    elif category == "search": return "search_gen"
    elif category == "url": return "url_exec"
    else: return "rag_gen"

workflow.add_conditional_edges("router", get_next_node, {
    "trend_exec": "trend_exec",
    "search_gen": "search_gen",
    "url_exec": "url_exec",
    "rag_gen": "rag_gen",
})

# 5. 직렬 엣지 (Sequential Edges) 설정
# Case C: API Search Path
workflow.add_edge("search_gen", "search_exec")

# 💡 [핵심 수정] search_exec 뒤에 필터 필요 여부 확인 엣지 추가
workflow.add_conditional_edges(
    "search_exec",
    check_filter_needed,
    {
        "to_filter": "filter_exec",     # 필터가 필요하면 filter_exec으로 이동
        "to_final_rec": "final_rec"     # 필터가 불필요하면 final_rec으로 바로 이동
    }
)

# filter_exec가 실행된 후에는 무조건 final_rec으로 이동
workflow.add_edge("filter_exec", "final_rec") 

# Case B: RAG Search Path (Primary + Fallback)
workflow.add_edge("rag_gen", "qdrant_exec")
workflow.add_conditional_edges(
    "qdrant_exec",
    check_rag_result,
    {
        "fallback_to_api": "search_gen", 
        "finalize": "final_rec"         
    }
)

# Case A: URL Analysis Path
workflow.add_edge("url_exec", "rag_gen") 

# 6. 단일 종료 엣지 및 최종 연결 (이전과 동일)
workflow.add_edge("trend_exec", "final_rec") 
workflow.add_edge("final_rec", END)         

# 7. 컴파일
app = workflow.compile()
print("✅ LangGraph Workflow Compiled. Conditional filtering added.")