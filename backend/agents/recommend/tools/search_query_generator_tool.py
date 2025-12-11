# tools/search_query_generator.py (최종 수정 코드)

import json
import asyncio
from langchain.tools import tool
from core.search.search_query_generator import search_query_generator

@tool
async def github_search_query_generator(user_input: str) -> str:
    """
    Agent에서 호출 가능한 GitHub 검색 Tool (비동기 처리)
    """
    
    # 🌟 [필수 확인] 반드시 await이 있어야 합니다.
    result_dict = await search_query_generator(user_input)
    
    # 이제 result_dict는 딕셔너리입니다.
    return json.dumps(result_dict, ensure_ascii=False)