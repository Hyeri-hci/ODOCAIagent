import logging
import json
from typing import List, Dict, Any
from pydantic import ValidationError

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from config.setting import settings
from adapters.trend_client import trend_client, TrendingPeriod
from core.github.schema import GitHubTrendInput, ParsedTrendingRepo

logger = logging.getLogger(__name__)

class TrendService:
    """
    사용자 입력을 분석하여 트렌드 정보를 조회하는 서비스
    - 호환성을 위해 JsonOutputParser(수동 파싱) 사용
    - 불완전한 데이터에 대한 방어 로직 포함
    """
    
    def __init__(self):
        # LLM 초기화
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0  # 정확한 추출을 위해 0 설정
        )
        
        # Pydantic 모델 기반의 JSON 파서 설정
        self.parser = JsonOutputParser(pydantic_object=GitHubTrendInput)

    async def search_trending_repos(self, user_query: str) -> List[ParsedTrendingRepo]:
        """
        [메인 함수] 사용자 쿼리를 받아 트렌드 검색 결과를 반환
        """
        # 1. LLM을 통해 필터(언어, 기간) 추출
        trend_input: GitHubTrendInput = await self._extract_search_filters(user_query)
        
        logger.info(f"🔍 Trend Search: Query='{user_query}' -> {trend_input.model_dump()}")

        # 2. 문자열 Period를 Client용 Enum으로 변환
        period_enum = self._map_period_string_to_enum(trend_input.since)
        
        # 3. TrendClient를 통해 데이터 조회 (API or Crawling)
        print(f"   [Trend Client] Fetching trending repos for Language: {trend_input.language}, Period: {trend_input.since}...")
        raw_results = await trend_client.get_trending_repos(
            language=trend_input.language,
            period=period_enum
        )
        print(f"   [Trend Client] Received {len(raw_results)} raw results.")
        
        # 4. 결과 변환 및 데이터 정제 (방어 로직 적용)
        parsed_results = []
        for item in raw_results:
            try:
                # [Data Fix] Owner가 없고 Name에 '/'가 있다면 쪼개기 (API 데이터 호환성)
                owner = item.get("owner")
                name = item.get("name")
                
                if (not owner or owner == "Unknown") and name and "/" in name:
                    parts = name.split("/", 1)
                    if len(parts) == 2:
                        item["owner"] = parts[0]
                        item["name"] = parts[1]
                        logger.debug(f"🔧 Fixed Repo Data: {name} -> {item['owner']} / {item['name']}")

                # Pydantic 모델 변환 시도
                repo = ParsedTrendingRepo(**item)
                parsed_results.append(repo)
                
            except ValidationError as e:
                # 특정 데이터가 불량이면 로그에 상세 정보 포함하여 건너뜀
                logger.warning(f"⚠️ Skipping invalid repo data: {item.get('name', 'Unknown')}. Validation Error: {e}")
                continue
        
        logger.info(f"✅ Successfully parsed {len(parsed_results)} repos.")
        return parsed_results

    async def _extract_search_filters(self, query: str) -> GitHubTrendInput:
        """
        사용자 발화에서 검색 조건(언어, 기간)을 추출 (안정성 강화 버전)
        """
        
        system_prompt = """
        You are a GitHub Trend Search Assistant.
        Analyze the user's query and extract `language` and `since` (period).

        ### Output Format (JSON ONLY)
        Please output strictly in the following JSON format, with no other text.
        {
            "language": "python" or null,
            "since": "daily" or "weekly" or "monthly"
        }

        ### Rules
        1. language: English name (e.g., "파이썬" -> "python"). If none, use null.
        2. since: 
            - "오늘" -> "daily"
            - "이번주/요즘" -> "weekly" (default)
            - "이번달" -> "monthly"
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{query}"),
        ])

        # 💡 [개선] LLM 호출과 파싱을 분리하여 원본 응답을 확인 가능하게 함
        llm_chain = prompt | self.llm 
        
        try:
            # 1. LLM 호출
            llm_response = await llm_chain.ainvoke({"query": query})
            response_content = llm_response.content
            
            logger.debug(f"🤖 LLM Raw Response for Trend Filters: {response_content}")

            # 2. JSON 파싱 시도
            result_dict = self.parser.parse(response_content) 
            
            # 3. Pydantic 모델로 변환 (Validation)
            result = GitHubTrendInput(**result_dict)
            
            logger.info(f"🤖 LLM Generated Query: {result.model_dump_json()}")
            
            # 필수 필드 기본값 처리
            if not result.since:
                result.since = "weekly"
                
            return result

        except Exception as e:
            # JsonOutputParser의 파싱 에러나 ValidationError가 발생했을 때 로그 기록
            logger.error(f"Failed to extract trend filters. Error: {e.__class__.__name__}. Using defaults.")
            
            # 실패 시 안전한 기본값 반환
            return GitHubTrendInput(since="weekly")

    def _map_period_string_to_enum(self, period_str: str) -> TrendingPeriod:
        """Pydantic 모델의 문자열 기간을 Client용 Enum으로 변환"""
        period_str = period_str.lower() if period_str else "weekly"
        
        mapping = {
            "daily": TrendingPeriod.DAILY,
            "weekly": TrendingPeriod.WEEKLY,
            "monthly": TrendingPeriod.MONTHLY,
        }
        return mapping.get(period_str, TrendingPeriod.WEEKLY)

# 싱글톤 인스턴스
trend_service = TrendService()