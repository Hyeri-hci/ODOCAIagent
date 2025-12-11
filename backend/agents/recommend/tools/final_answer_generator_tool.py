import json
from typing import Dict, Any, List
from langchain.tools import tool
from core.recommendation.final_answer_generator import generate_final_report

@tool
async def final_answer_generator_tool(user_query: str, candidates: List[Dict[str, Any]]) -> str:
    """
    [Final Recommendation Generator]
    검색된 최종 후보 목록과 사용자 쿼리를 바탕으로, 각 프로젝트의 추천 이유를 생성하고 
    최종 결과 보고서(JSON)를 반환합니다. (로직은 core에 위임)
    """
    
    # Core 로직을 호출하고 결과를 반환
    return await generate_final_report(user_query, candidates)