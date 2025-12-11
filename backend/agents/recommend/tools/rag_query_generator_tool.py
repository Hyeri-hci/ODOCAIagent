# tools/rag_query_generator_tool.py

import json
from langchain.tools import tool
from typing import Dict, Any, Literal
# 코어 로직 임포트
from core.search.rag_query_generator import generate_rag_query_and_filters

@tool
async def rag_query_generator(
    user_request: str, 
    category: Literal["semantic_search", "url_analysis"],
    analyzed_data: Dict[str, Any] = None
) -> str:
    """
    [RAG 쿼리 및 필터 생성 Tool]
    semantic_search 또는 url_analysis 요청을 받아, Milvus 검색에 최적화된 쿼리(query)와 필터(filters)를 생성합니다.
    """
    
    # 💡 Core Logic 호출 (LLM 통신 및 파싱을 여기서 수행)
    result_dict = await generate_rag_query_and_filters(
        user_request=user_request,
        category=category,
        analyzed_data=analyzed_data
    )

    # Tool은 항상 JSON 문자열을 반환해야 함
    return json.dumps(result_dict, ensure_ascii=False)