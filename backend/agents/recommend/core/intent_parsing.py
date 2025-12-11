# backend/core/intent_parsing.py

import asyncio
import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from backend.agents.recommend.agent.state import FocusedParsingResult, QuantitativeCondition
from backend.agents.recommend.config.setting import settings

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. 프롬프트 정의
# ==============================================================================

# (Focusing된 통합 파싱 프롬프트 사용)
FOCUSED_PARSING_PROMPT = """
당신은 GitHub 프로젝트 추천 시스템의 '핵심 의도 및 제약 조건 분석 AI'입니다.
주어진 사용자 요청을 분석하여, **의도 분류(Intent)**와 **정량적 필터 조건**만을 추출하여 구조화된 JSON 객체로 반환하십시오.

<사용자 요청>
{user_request}

---

### 🛑 지시사항 및 규칙 (반드시 준수)

1. **의도 분류 (user_intent) - 4가지 중 택일**: 요청이 다음 네 가지 중 어디에 해당하는지 가장 적절하게 분류하십시오.
   - 'url_analysis': 특정 URL 프로젝트와 유사한 것을 찾으려는 요청. (URL이 입력되면 이 의도로 분류)
   - 'semantic_search': 특정 기능이나 주제를 찾는 일반적인 내용 기반 검색 요청.
   - 'search_criteria': 특정 정량적 조건(예: "이슈가 많은")을 주 조건으로 검색하는 요청.
   - **'trend_analysis'**: **최근 경향, 인기 변화, 또는 특정 기간(예: 오늘, 이번 달, 2024년)의 인기 프로젝트**를 분석하거나 찾는 요청입니다. 

2. **정량적 필터 추출 (quantitative_filters) [핵심]**:
    - 요청에서 '수치나 활동성 관련된 요구사항만' 추출해야 하며, **의미적 내용(언어, 기술 이름 등)은 절대 포함하지 마십시오.**
    - 추출할 때 반드시 아래 **[Metric 정의 표]**에 있는 **MetricName**과 **OperatorName**만 사용하십시오.
    - **TREND\_LANGUAGE**와 **TREND\_SINCE**는 의도가 trend_analysis일때만 사용하십시오.
    - **TREND\_SINCE**의 Value는 반드시 'past\_24\_hours', 'past\_week', 'past\_month', 'past\_3\_months' 중 하나여야 합니다. 
      - 만약 사용자가 '1년' 또는 '2024년'과 같이 **허용되지 않는 긴 기간**을 요청하면, **'past\_3\_months'로 대체**하십시오.
      - '오늘'은 'past\_24\_hours', '이번 주'는 'past\_week'로 변환하십시오.
    - 정량적 요구사항이 없으면 빈 리스트 `[]`를 반환하십시오.

| MetricName | OperatorName | Value 형식 | 사용자 요청 예시 |
| :--- | :--- | :--- | :--- |
| **ISSUE_COUNT** | HIGH, LOW, GT, LT | 숫자 (예: '50') | '이슈가 적은', '이슈가 100개 이하인' |
| **COMMIT_ACTIVITY** | ACTIVE, INACTIVE, GT | 숫자/기간 (예: '30') | '개발이 활발한', '최근 1개월 내 30 커밋' |
| **STAR_COUNT** | HIGH, LOW, GT, LT | 숫자 (예: '1000') | '스타가 좀 되는', '10000 스타 초과' |
| **AGE\_DAYS** | LT, GT, TIME\_RANGE | 숫자/기간 (예: '90 days') | '오래되지 않은 프로젝트', '1년 이상 된' |
| **CONTRIBUTOR\_COUNT** | HIGH, LOW, GT, LT | 숫자 (예: '5') | '다수가 기여한 곳' |
| **PR\_VELOCITY** | HIGH, LOW | null | 'PR이 빠르게 머지되는' |
| **...** | **(나머지 Metric/Operator는 위에 준하여 명시하십시오.)** | | |
| **TREND\_LANGUAGE** (새 Metric) | EQ | 문자열 (예: 'python') | '파이썬 트렌드', 'Go 언어 요즘 인기' |
| **TREND\_SINCE** (새 Metric) | EQ | Literal ('past_24_hours', 'past_week', 'past_month', 'past_3_months') | '이번 주 트렌드', '오늘 인기' |

---

### 출력 형식 (JSON Only)
제공된 Pydantic 스키마를 완벽하게 준수하여 **순수 JSON 객체만을** 응답하십시오. 주석금지

{format_instructions}
"""

# ==============================================================================
# 2. Chain 정의 및 핵심 실행 함수
# ==============================================================================

def get_parsing_chain(llm_client):
    """
    LLM 클라이언트와 파싱 프롬프트를 연결하는 LangChain Expression Language (LCEL) 체인을 반환합니다.
    (Chain 정의)
    """
    parser = PydanticOutputParser(pydantic_object=FocusedParsingResult)
    prompt = ChatPromptTemplate.from_template(FOCUSED_PARSING_PROMPT)
    
    return (prompt | llm_client | parser), parser

async def extract_initial_metadata(llm_client, user_request: str, repo_url: Optional[str] = None) -> FocusedParsingResult:
    """
    핵심 로직: Chain을 실행하여 사용자 요청으로부터 의도와 정량적 제약 조건을 추출합니다.
    """
    logger.info(f"🔍 Core Logic: Starting metadata extraction for '{user_request}'")
    
    chain, parser = get_parsing_chain(llm_client)

    format_instructions = parser.get_format_instructions()
    
    # 요청에 URL 정보가 있으면 LLM에게 전달하여 'url_analysis'를 유도
    processed_request = user_request
    if repo_url:
        processed_request = f"[URL: {repo_url}] {user_request}"
    
    input_vars = {
        "user_request": processed_request,
        "format_instructions": format_instructions
    }
    
    try:
        # Chain 실행
        result: FocusedParsingResult = await chain.ainvoke(input_vars)
        return result
    except Exception as e:
        logger.error(f"❌ Core Logic Failed: {type(e).__name__} - {e}")
        # 실패 시 초기 상태로 폴백 (core 로직에서 폴백 처리)
        return FocusedParsingResult(
            user_intent="semantic_search",
            quantitative_filters=[],
        )
    