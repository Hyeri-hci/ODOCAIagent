# core/search/search_query_generator.py

from typing import Dict, Tuple, Optional
# 💡 [핵심] LLM 호출 함수는 비동기 함수임을 명시적으로 가정하고 임포트합니다.
from core.search.llm_query_generator import generate_github_query 
from core.search.llm_query_parser import parse_github_query

async def search_query_generator(user_input: str) -> Dict:
    """
    사용자 입력 → 최종 GitHub Search API 쿼리 파라미터 생성 (2단계 파이프라인)
    """
    print(f"🔄 [Query Pipe] Starting 2-step generation for: {user_input}")

    # 1. LLM에게 JSON 생성 요청
    # 💡 [필수 수정] 비동기 함수 호출이므로 await을 추가합니다.
    query_json = await generate_github_query(user_input) 

    print(f"   [Step 1/2] LLM JSON generated.")

    # 2. JSON → API 파라미터 변환 + 최소 품질 적용
    # parse_github_query는 동기 함수이므로 await이 필요 없습니다.
    q, sort, order, other = parse_github_query(query_json)

    print(f"   [Step 2/2] Final API query constructed: q='{q[:30]}...'")

    return {
        "q": q,
        "sort": sort,
        "order": order,
        "other": other
    }