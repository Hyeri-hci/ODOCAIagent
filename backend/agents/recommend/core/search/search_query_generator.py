# core/search/search_query_generator.py

import json
from typing import Dict, Tuple, Optional
from core.search.llm_query_generator import generate_github_query, correct_github_query
from core.search.llm_query_parser import parse_github_query

async def search_query_generator(user_input: str) -> Dict:
    """
    사용자 입력 → 최종 GitHub Search API 쿼리 파라미터 생성 (2단계 파이프라인 + LLM Correction Retry)
    """
    print(f"🔄 [Query Pipe] Starting 2-step generation for: {user_input}")

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        
        # 1. LLM에게 JSON 생성 요청 (첫 시도 또는 재시도)
        if attempt == 1:
            query_json = await generate_github_query(user_input) 
            source_content = None # 첫 시도에는 이전 내용 없음
        else:
            # 2차 시도는 이전 실패 내용을 기반으로 수정 요청
            query_json = await correct_github_query(user_input, source_content, error_message)
            
        print(f"   [Step 1/{max_attempts}] LLM JSON generated (Attempt {attempt}).")
        
        # LLM 응답이 최소한 딕셔너리 형태가 아니라면 바로 다음 시도로 넘어감 (혹은 파이프라인 중단)
        if not isinstance(query_json, dict) or not query_json.get("q"):
             if attempt == max_attempts:
                 print(f"❌ [Step 1 Fail] LLM failed to produce a valid dictionary after {max_attempts} attempts.")
                 break # 2차 시도까지 실패하면 종료

             # 다음 시도를 위해 원본 LLM 응답을 저장 (필요하다면)
             source_content = str(query_json) 
             error_message = "LLM response was not a valid dictionary or was empty."
             continue # 다음 시도로 넘어감


        # 2. JSON → API 파라미터 변환 + 최소 품질 적용
        try:
            q, sort, order, other = parse_github_query(query_json)
            
            # 파싱 및 검증 성공 -> 즉시 반환
            print(f"   [Step 2/{max_attempts}] Final API query constructed: q='{q[:30]}...'")
            return {
                "q": q,
                "sort": sort,
                "order": order,
                "other": other
            }
            
        except Exception as e:
            # parse_github_query에서 오류 발생 시
            if attempt < max_attempts:
                print(f"   ⚠️ Parsing failed (Attempt {attempt}). Retrying with LLM correction.")
                # 재시도를 위해 오류 정보 저장
                source_content = json.dumps(query_json, ensure_ascii=False)
                error_message = str(e)
                continue # 다음 시도로 넘어감
            else:
                print(f"❌ [Step 2 Fail] Final parsing failed after {max_attempts} attempts: {e}")
                break # 최종 실패

    # 모든 시도 실패 시 최종 반환
    return {"q": "", "sort": None, "order": None, "other": None}