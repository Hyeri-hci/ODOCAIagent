# agent/intent_parser.py

"""
Intent Parser (Lightweight Version)
오직 실행 경로(Category)와 타겟 리소스(Repo/URL)만 식별하여 라우팅 결정
"""
import json
import re
import asyncio
from typing import Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config.setting import settings 
# TaskIntent는 state.py에서 정의된 구조를 따릅니다.
from agent.v1.state import TaskIntent

class IntentParser:
    """라우팅 전용 파서"""

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0
        )

        # 프롬프트: 상세 조건 추출 제거, 오직 카테고리 분류에 집중
        self.intent_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 GitHub 추천 에이전트의 **라우팅(Routing) 전문가**입니다.
            사용자의 요청을 분석하여 적절한 **실행 경로(Category)**를 결정하십시오.

            ### 카테고리 정의:
            1. **search_criteria**: '별점', '언어', '날짜' 등 **검색 조건**이 포함된 요청(키워드 기반 검색).
            2. **semantic_search**: 특정 **기능**이나 **목적**을 찾는 의미 기반 검색.
            3. **url_analysis**: **URL**이나 **특정 리포지토리(user/repo)**에 대한 분석/유사 추천 요청.
            4. **trend_analysis**: 인기 순위나 트렌드 요청.

            ### 분석 범위 (Scope):
            - **global**: 일반 검색
            - **similar_to_repo**: 특정 리포지토리 기반 (url_analysis일 때 선택)

            반드시 아래 **JSON 형식**으로만 응답하십시오 (키워드 추출 불필요):
            {{
                "category": "search_criteria" | "semantic_search" | "url_analysis" | "trend_analysis", 
                "scope": "global" | "similar_to_repo"
            }}
            """),
            ("user", "{user_request}")
        ])

    async def parse_intent(self, user_request: str) -> TaskIntent:
        """
        사용자 요청 -> 라우팅 정보(TaskIntent) 변환
        """
        print(f"\n🔍 [IntentParser] Analyzing Routing: {user_request}")

        try:
            # 1. 리포지토리 정보 강제 추출 (라우팅의 핵심 근거)
            owner, repo = self._extract_repository_info(user_request)
            target_repo = f"{owner}/{repo}" if owner and repo else None

            # 2. LLM 라우팅 결정
            chain = self.intent_prompt | self.llm
            response = await chain.ainvoke({"user_request": user_request})
            
            content = response.content
            intent_data = self._robust_json_parse(content)

            # 3. [강제 보정] Repo가 있으면 무조건 url_analysis
            category = intent_data.get("category", "semantic_search")
            scope = intent_data.get("scope", "global")

            if target_repo:
                if category != "url_analysis":
                    print(f"🚩 [Router Override] Repo detected -> Switching to 'url_analysis'")
                    category = "url_analysis"
                    scope = "similar_to_repo"

            # 4. 결과 반환
            intent: TaskIntent = {
                "category": category,
                "scope": scope,
                "target_repo": target_repo,
                "original_query": user_request # 뒷단 Tool들이 사용할 원본
            }
            
            print(f"✅ [IntentParser] Routed to: {category}")
            return intent

        except Exception as e:
            print(f"⚠️ [IntentParser] Error: {e}")
            # Fallback
            return {
                "category": "semantic_search",
                "scope": "global",
                "target_repo": None,
                "original_query": user_request
            }

    def _extract_repository_info(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """URL/Repo 패턴 정규식 추출 (이전과 동일)"""
        url_pattern = r'github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
        short_pattern = r'(?<!\w)([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?!\w)'
        
        url_match = re.search(url_pattern, text)
        if url_match: return url_match.group(1), url_match.group(2)

        short_match = re.search(short_pattern, text)
        if short_match:
            o, r = short_match.group(1), short_match.group(2)
            if o.lower() not in ['and', 'or', 'i'] and len(r) > 1:
                return o, r
        return None, None

    def _robust_json_parse(self, content: str) -> Dict[str, Any]:
        """JSON 파싱 헬퍼"""
        try:
            json_match = re.search(r'\{.*\}', content.strip(), re.DOTALL)
            if json_match: content = json_match.group(0)
            return json.loads(content)
        except:
            return {}

# --- TEST BLOCK ---
async def test_intent_parser():
    print("\n" + "="*60)
    print("🚀 INTENT PARSER TEST START")
    print("="*60)

    parser = IntentParser()

    test_cases = [
        # 1. API Search Case (명시적 조건)
        "파이썬으로 만들어진, 별점 1000개 이상인 웹 프레임워크 찾아줘.",
        
        # 2. Semantic Search Case (의미 기반)
        "RAG 파이프라인 구축을 쉽게 도와주는 라이브러리 추천해줄래?",
        
        # 3. URL Analysis Case (URL 포함)
        "https://github.com/tiangolo/fastapi 이 프로젝트랑 비슷한 거 찾아줘.",
        
        # 4. Repo Analysis Case (user/repo 포함)
        "facebook/react 분석해주고 비슷한 거 추천해줘.",
        
        # 5. Trend Analysis Case
        "요즘 깃허브에서 제일 핫한 프로젝트가 뭐야?"
    ]

    for i, req in enumerate(test_cases):
        print(f"\n[TEST CASE {i+1}] Request: {req}")
        result = await parser.parse_intent(req)
        
        print(f"👉 Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print("-" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(test_intent_parser())
    except NameError as e:
        print(f"FATAL ERROR: {e}. (Ensure config/setting.py and agent/state.py exist)")