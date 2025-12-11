import json
import logging
import re
import asyncio
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate 
from backend.agents.recommend.config.setting import settings 

logger = logging.getLogger(__name__)

# LLM for reasoning (생성 품질 및 JSON 안정성을 위해 설정)
try:
    llm = ChatOpenAI(
        base_url=settings.llm.api_base,
        api_key=settings.llm.api_key,
        model=settings.llm.model_name,
        temperature=0.3 
    )
except Exception as e:
    logger.error(f"LLM Client Initialization Failed in Core: {e}")
    raise e 


SYSTEM_PROMPT = """
당신은 GitHub 프로젝트 추천 및 분석 전문가입니다.
주어진 사용자 요청, **분석된 활동 조건**, 그리고 검색된 프로젝트 후보 목록(JSON)을 바탕으로,
각 프로젝트가 왜 추천되는지 **가장 핵심적인 이유**를 명확하고 설득력 있게 **한국어로 한 문장**으로 작성해야 합니다.

### 역할
1. 각 후보 프로젝트의 장점을 분석하고, **사용자가 요구한 활동 조건**과 데이터(`recent_commits` 등)를 연결하여 추천 근거를 작성하십시오.
2. 만약 후보 데이터에 활동 지표가 포함되어 있다면 (예: recent_commits), 이를 근거로 제시해야 합니다.
3. 최종 결과는 반드시 아래의 **JSON 형식**으로만 출력해야 합니다. 다른 서론이나 설명은 절대 포함하지 마십시오.

### 출력 형식 (JSON ONLY)
{
    "summary_reasoning": "전체 추천에 대한 요약 문구 및 추천 이유 (한국어)",
    "top_candidates": [
        {
            "name": "프로젝트 이름",
            "url": "URL",
            "recommendation_reason": "여기에 핵심 추천 이유와 함께 사용자의 요청(예: 커밋 수)에 부합하는 근거를 작성하십시오."
        }
        // ... 최대 5개까지 반복 ...
    ]
}
"""

async def generate_final_report(
    user_query: str, 
    candidates: List[Dict[str, Any]],
    other_conditions: Optional[str] = None # 👈 [추가] 사용자가 요구한 활동 조건
) -> str:
    """
    [핵심 로직] 후보 목록을 받아 LLM을 호출하여 추천 이유를 생성하고 최종 보고서를 반환합니다.
    """
    if not candidates:
        return json.dumps({"summary_reasoning": "검색 결과가 없어 최종 보고서를 생성할 수 없습니다."}, ensure_ascii=False)

    print("✨ [Core Logic] Generating Final Recommendation Report...")
    
    # 후보 목록을 최대 5개로 제한 및 LLM이 읽기 쉽도록 데이터 간소화
    top_candidates = candidates[:5]
    simplified_candidates = []
    
    for cand in top_candidates:
        content_summary = cand.get('content', '')[:300] 
        
        # 💡 [핵심] 필터링 도구(filter_exec)에서 추가된 활동성 지표를 LLM에 주입
        simplified_candidates.append({
            "name": cand.get('name'),
            "stars": cand.get('stars', cand.get('stargazers_count', 0)),
            "language": cand.get('language', 'N/A'),
            "topics": cand.get('topics', []),
            "content_snippet": content_summary,
            "recent_commits": cand.get('recent_commits', 'N/A'), # filter_exec에서 추가된다고 가정
            "recent_issues": cand.get('recent_issues', 'N/A'),   # filter_exec에서 추가된다고 가정
            "score": cand.get('rerank_score', cand.get('score', 0))
        })

    # 💡 [핵심] LLM 메시지에 사용자 요청과 필터링 조건을 명시적으로 포함
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""
        [사용자 원본 요청]: {user_query}
        [분석된 활동 조건]: {other_conditions or '조건 없음'}
        [검색된 후보 데이터]: {json.dumps(simplified_candidates, indent=2, ensure_ascii=False)}
        
        위 요청, 활동 조건, 데이터를 분석하여, 각 프로젝트의 추천 이유를 담은 최종 JSON 보고서를 생성하십시오.
        """}
    ]
    
    try:
        # LLM 호출
        response = await llm.ainvoke(messages)
        content = response.content
        
        # 💡 [로그 추가] LLM이 생성한 원본 응답을 로그로 출력
        print("\n--- 🤖 LLM Raw Response Log (for Debug) ---")
        print(content)
        print("-------------------------------------------\n")
        
        # JSON 파싱 및 정리 (마크다운 블록 제거)
        content = content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match: content = json_match.group(0)

        json_data = json.loads(content)
        
        # LLM이 생성한 추천 이유를 원본 데이터에 다시 매핑
        final_list = []
        reason_map = {c.get('name'): c.get('recommendation_reason') for c in json_data.get('top_candidates', [])}
        
        for cand in top_candidates:
            reason = reason_map.get(cand.get('name'))
            cand_copy = cand.copy()
            
            # Note: 여기서는 final_list에 cand_copy의 모든 필드(예: recent_commits)가 포함되도록 합니다.
            # LLM이 생성한 reason을 최종 데이터에 덮어씁니다.
            if reason:
                cand_copy["recommendation_reason"] = reason
            else:
                cand_copy["recommendation_reason"] = "LLM이 추천 사유를 생성하지 못했습니다."

            final_list.append(cand_copy)
                
        # 최종 보고서 형태로 JSON 반환
        return json.dumps({
            "summary_reasoning": json_data.get('summary_reasoning', "요약 사유 생성에 실패했습니다."),
            "top_candidates": final_list
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"❌ Final Report Generation Failed in Core: {e}")
        return json.dumps({"error": f"Final Report Generation Failed: {e}"}, ensure_ascii=False)