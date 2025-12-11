from typing import TypedDict, Optional, List, Dict, Any, Literal

class AgentState(TypedDict, total=False):
    """LangGraph의 상태 객체 정의: 그래프를 통해 전달되는 데이터 바구니"""
    user_query: str
    
    # 라우팅 결과
    category: Literal["search", "rag", "url", "trend"]
    
    # 중간 데이터들
    search_queries: List[Dict]       # API 쿼리 파라미터 (search_gen)
    rag_queries: List[Dict]          # 벡터 검색 쿼리/필터 (rag_gen)
    analyzed_data: Dict              # URL 분석 결과 (url_exec)
    
    # 검색 후보군
    raw_candidates: List[Dict]
    filtered_candidates: List[Dict] 
    
    # 💡 [핵심 추가] 필터링 필요 여부
    needs_filter: bool               # search_exec 노드에서 'other' 조건 유무에 따라 True/False 설정
    
    # 상태 추적 및 최종 결과
    last_status: Optional[Literal["success", "empty", "fail"]]
    final_result: Any