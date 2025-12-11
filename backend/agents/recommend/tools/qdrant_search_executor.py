# tools/qdrant_search_executor.py
import json
import numpy as np
from langchain.tools import tool
from typing import Dict, Any, List, Optional
# [핵심] vector_search_engine과 타입 변환 헬퍼를 import 해야 합니다.
# (convert_to_standard_types 함수는 vector_search.py에 있다고 가정하고 import)
from core.search.vector_search import vector_search_engine, convert_to_standard_types 

# -------------------------------------------------------------------
# RAG 툴 실행 함수
# -------------------------------------------------------------------

@tool
def qdrant_search_executor(
    query: str, 
    keywords: Optional[List[str]] = None, 
    filters: Optional[Dict[str, Any]] = None
) -> str:
    """
    [Core Search Execution Tool]
    Executes RAG search in Qdrant DB using the processed query, keywords, and filters.
    """
    
    # 1. 핵심 검색 로직 실행
    result_dict = vector_search_engine.search(
        query=query, 
        filters=filters, 
        keywords=keywords
    )
    
    # 2. 🌟 [핵심 수정] 반환 직전 float32 -> float 타입 변환 적용
    # JSON 직렬화 오류(float32 is not JSON serializable) 방지
    standardized_result = convert_to_standard_types(result_dict)
    
    # 3. JSON 문자열로 반환
    return json.dumps(standardized_result, ensure_ascii=False, indent=2)