# core/search/llm_query_generator.py

import json
import asyncio
import logging
from typing import Dict, List
from adapters.llm_client.llm_client import ChatMessage, llm_chat
from utils.date import DateUtilsUTC

logger = logging.getLogger(__name__)

class QueryParseError(Exception):
    """LLM 출력이 JSON 형식이 아닌 경우 발생"""

async def generate_github_query(user_input: str) -> Dict:
    """
    사용자의 자연어 입력을 기반으로 GitHub 검색용 JSON 쿼리 생성 (비동기)
    LLMClient 인스턴스는 내부에서 llm_chat()가 싱글톤으로 가져옴
    """
    print(f"⚙️ [LLMQueryGen] Analyzing user request: '{user_input}'")
    
    # 1. DateUtilsUTC를 사용하여 오늘 날짜 가져오기
    today_date = DateUtilsUTC.today_str()

    # 1. system 메시지: 역할과 규칙 (프롬프트 내용은 유지)
    system_prompt = f"""
# Role
GitHub 검색 쿼리 변환기입니다. 사용자 요청을 분석하여 정확한 JSON을 반환하세요.

# Context
**기준 날짜**: {today_date}

# ⛔ 절대 금지 사항 (CRITICAL)
1. **검색어 보존(KEYWORD PRESERVATION)**
    - `topic:`, `language:` 등으로 변환되지 않는 일반 명사(예: "library", "tool", "framework", "dashboard")는 **반드시 `q` 필드에 텍스트 그대로 포함**시켜야 합니다.
    - (X) "Python Library" -> `q: "language:python"` (정보 손실!)
    - (O) "Python Library" -> `q: "library language:python"` (성공)
    - (O) "Django Framework" -> `topic:django` (성공)

2. **임의 필터 창조 금지**:
    - 사용자가 숫자를 명시하지 않았다면 `stars`, `forks`, `pushed` 조건을 스스로 추가하지 마세요. (Clean Search)

3. **토큰 분리**: `many_issues` 같은 추상적 조건은 `q`에 넣지 말고 `other`로 빼세요.

4. **구분자 준수**: `q` 내부의 모든 조건은 반드시 **공백(Space)**으로 구분하세요.

# 규칙 (Rules)

1. **`q` 필드 작성 규칙 (White-list)**:
    - 형식: `{{General Keywords}} {{Filters}}` - 꼭 준수하세요.
    - **Filters**: `topic:`, `language:`, `stars:`, `forks:`, `created:`, `pushed:`, `license:`, `good-first-issues:`
    - **Keywords**: 필터가 아닌 일반 텍스트 검색어
      **[따옴표 규칙 (Quoting Rules)]**
        - **공백이 있는 경우**: 반드시 쌍따옴표(`""`)로 감싸야 하며, JSON 문자열 내부이므로 **이스케이프(`\\"`)** 해야 합니다.
        - 예: `topic:\\"machine learning\\"`, `\\"state management\\"`
        - **공백이 없는 경우**: 따옴표를 쓰지 않는 것을 권장합니다.
        - 예: `topic:python`, `dashboard`
    - **필수 토픽 추가**: "Library"->`topic:library`, "Framework"->`topic:framework`. "API" -> `topic:api`
    - **단순화**: "Django Framework" -> `topic:"django"`.
    - **초보자**: "초보자", "beginner" -> `good-first-issues:>5`.
    - 아무런 언급이 없는 경우는 공백을 넣으세요 (이슈가 많은 레포 -> `q: ''`)
    - (Note: `-topic:` 같은 부정 연산자도 허용됨)
    - 영어로 작성하세요.

2. **지표 및 날짜 (`q`) - 우선순위 준수**:
    - **1순위 (구체적 기간)**: "1년 내", "지난달", "최근 3개월" 등 **수치**가 있으면 해당 기간을 계산하세요. (기준일: {today_date})
      - 업데이트(pushed), 생성일(created)만 q 항목에 추가하세요. 나머지(prs, issues, commits)는 other에 적용시키세요.
    - **2순위 (단순 최근)**: 수치 없이 그냥 "최근(recent)"이라고만 하면 **6개월 전** 날짜를 적용하세요.
    - **범위 연산자**: 이상(>=), 이하(<=), 초과(>), 미만(<), 특정 범위(..)

3. **`other` 필드 작성 규칙 (Filter Tool용)**:
    - 검색 API(`q`)로 해결되지 않는 **이슈, PR, 커밋, 활동성** 관련 조건은 여기서 처리합니다.
    - **형식**: `{{action}}_{{target}}_{{duration/number}}` (Snake Case)
    
    **[사용 가능한 키워드 조합]**
    - **Target**: `issues`, `prs`, `commits`
    - **Action**: 
      - `many`: 약 50개 이상 (활발한 프로젝트)
      - `few`: 5개 이하 (안정적/적은 버그)
      - `has`: 1개 이상 (존재 여부)
    - **Suffix (선택)**:
      - `_recently`: 최근 6개월 기준
      - `_recently_1y`: 최근 1년 기준
      - `_recently_3m`: 최근 3개월 기준
      - `_{{숫자}}`: 구체적인 숫자 (예: `_30` -> 30개 이상)

    **[매핑 예시 테이블]**
    - "이슈 많은" -> `many_issues`
    - "PR이 활발한" -> `many_prs`
    - "커밋이 많은" -> `many_commits`
    - "최근(1년) 커밋이 많은" -> `many_commits_recently_1y`
    - "최근 활동이 있는" -> `has_commits_recently`
    - "PR이 30개 이상인" -> `has_prs_30`
    - "버그(이슈)가 적은" -> `few_issues`

    - 여러 개일 경우 **공백**으로 연결 (예: `"few_issues many_commits"`).
    - 없는 경우는 무조건 `null`.

4. **정렬 (`sort`, `order`) - [상세 가이드]**:
    - **사용자의 의도가 명확할 때만 설정하세요.** (모호하면 `null` -> 정확도순 정렬)
    - **인기순 (`stars`)**: "인기있는", "유명한", "스타 많은", "Best", "Top", "추천"
      -> `sort: "stars"`, `order: "desc"`
    - **최신순 (`updated`)**: "최근", "최신", "새로운", "업데이트된"
      -> `sort: "updated"`, `order: "desc"`
    - **포크순 (`forks`)**: "포크 많은", "많이 사용되는"
      -> `sort: "forks"`, `order: "desc"`
    - **기여 관련 (`help-wanted-issues`)**: "도움이 필요한", "기여하기 좋은"
      -> `sort: "help-wanted-issues"`, `order: "desc"`

# 정답 예시 (Few-shot Examples) - 이 패턴을 반드시 따르세요.

**Case 1: 키워드 검색 (가장 중요 - 이스케이프 주의)**
Input: "React state management 라이브러리"
Output:
```json
{{
  "q": "topic:\\"state management\\" topic:library topic:react",
  "sort": null,
  "order": null,
  "other": null
}}

**Case 2: 초보자 + 기간 + 커밋 복합**
Input: "초보자가 하기 좋고 최근 1년 내 커밋이 활발한 Python 프로젝트"
Output:
```json
{{
  "q": "language:python good-first-issues:>5",
  "sort": null,
  "order": null,
  "other": "many_commits_recently_1y"
}}

**Case 3: 구체적 숫자 및 정렬**
Input: "PR이 100개 넘게 쌓여있는 Django 프로젝트, 최신순으로"
Output:
```json
{{
  "q": "topic:django",
  "sort": "updated",
  "order": "desc",
  "other": "has_prs_100"
}}

**Case 4: 정렬 및 기간**
Input: "최근 한 달 내에 업데이트된 인기있는 Go 툴"
Output:
```json
{{
  "q": "topic:tool language:go pushed:>{today_date[:-3]}-01", 
  "sort": "stars",
  "order": "desc",
  "other": null
}}

**Case 5: 특정 조건 없이 메타데이터만 요구 (중요)**
Input: "PR이 10개 이상 쌓여있는 프로젝트"
Output:
```json
{{
  "q": "",
  "sort": null,
  "order": null,
  "other": "has_prs_10"
}}
"""
    
    # 2. user 메시지: 실제 사용자 입력
    user_prompt = f"User request: {user_input}"

    messages: List[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt)
    ]

    # 3. LLM 호출
    try:
        # 💡 [핵심 수정] 비동기 환경을 위해 asyncio.to_thread로 감싸 호출
        response = await asyncio.to_thread(
            llm_chat,
            messages=messages,
            model=None # 클라이언트 내부 default model 사용
        )
        
    except Exception as e:
        logger.error(f"[GitHubQueryGen] LLM Call Failed: {e}")
        # LLM 통신 실패 시 최소한의 쿼리만 반환하여 파이프라인 유지
        return {"q": "", "sort": None, "order": None, "other": None}


    # 4. 응답 문자열에서 JSON 추출 및 파싱
    content = response.content.strip()
    
    # 💡 [로그 추가] LLM 원본 응답 로그
    print("\n--- 🤖 LLM Raw Response Log (GitHub Query Gen) ---")
    print(content)
    print("--------------------------------------------------\n")
    
    # 코드 블록 제거 (```json ... ```)
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:-1])

    try:
        query_dict = json.loads(content)
        
        # 💡 [로그 추가] 파싱 성공 확인
        print(f"✅ [GitHubQueryGen] JSON Parsing Successful. q: {query_dict.get('q')}")
        return query_dict
        
    except json.JSONDecodeError as e:
        logger.error(f"[GitHubQueryGen] LLM Output is not valid JSON: {e}. Content:\n{content}")
        # JSON 파싱 실패 시 최소한의 쿼리만 반환하여 파이프라인 유지
        return {"q": "", "sort": None, "order": None, "other": None}
    
async def correct_github_query(original_request: str, failed_content: str, error_message: str) -> Dict:
    """
    LLM 출력이 JSON 파싱에 실패했을 때, 오류 내용을 기반으로 LLM에게 수정을 요청 (비동기).
    """
    print(f"\n--- 🤖 LLM Correction Request ---")
    print(f"⚙️ [LLMQueryCorrec] Requesting correction based on error: {error_message}")
    
    correction_prompt = f"""
    # Role
    당신은 GitHub 검색 쿼리 JSON 교정기입니다. 주어진 사용자 요청과 이전에 생성된 잘못된 JSON 결과, 그리고 발생한 오류 메시지를 바탕으로 **올바른 JSON 객체**를 다시 생성하세요.

    # Context
    **원래 사용자 요청**: "{original_request}"
    **이전 LLM이 생성한 잘못된 JSON**:
    {failed_content}
    **발생한 파싱/문법 오류**: {error_message}

    # 규칙 (Rules)
    1. **문법 수정**: 이전 응답에서 JSON 파싱 오류(따옴표, 이스케이프 오류 등)를 **반드시** 수정하세요.
    2. **의미 수정 (Semantic Correction)**: 이전 쿼리(`q` 필드)에 **핵심 키워드 필터(`topic:`, `language:`, `stars:`)**가 누락되었거나 일반 텍스트로 잘못 변환되었다면, **원래 사용자 요청의 의도**에 맞게 이들을 **`topic:` 필터로 복원**하세요.
       - 예시: 'topic:"machine learning" library'로 나와야 할 것이 'machine learning library'처럼 일반 키워드로만 남지 않도록 주의.
    3. 모든 규칙(q 필드 작성 규칙, other 필드 등)은 원본 시스템 프롬프트를 따릅니다.
    4. JSON 객체만 반환하세요. 다른 설명은 절대 포함하지 마세요.
    """
    
    messages: List[ChatMessage] = [
        ChatMessage(role="system", content=correction_prompt),
        ChatMessage(role="user", content="올바른 JSON 쿼리를 다시 생성해 주세요.")
    ]

    try:
        response = await asyncio.to_thread(
            llm_chat,
            messages=messages,
            model=None 
        )
    except Exception as e:
        logger.error(f"[GitHubQueryCorrec] LLM Call Failed during correction: {e}")
        return {"q": "", "sort": None, "order": None, "other": None} # 실패 시 최소 쿼리

    content = response.content.strip()
    
    print("\n--- 🤖 LLM Raw Response Log (Correction) ---")
    print(content)
    print("------------------------------------------\n")
    
    # 코드 블록 제거 및 파싱 로직 (generate_github_query와 동일)
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:-1])

    try:
        query_dict = json.loads(content)
        print(f"✅ [GitHubQueryCorrec] Correction successful. q: {query_dict.get('q')}")
        return query_dict
    except json.JSONDecodeError as e:
        logger.error(f"[GitHubQueryCorrec] Correction failed to produce valid JSON: {e}")
        return {"q": "", "sort": None, "order": None, "other": None}