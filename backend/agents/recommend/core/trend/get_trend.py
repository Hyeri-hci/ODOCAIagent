import logging
import json
from typing import List, Dict, Any
from pydantic import ValidationError

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from backend.agents.recommend.config.setting import settings
from backend.agents.recommend.adapters.trend_client import trend_client, TrendingPeriod
from backend.agents.recommend.core.github.schema import GitHubTrendInput, ParsedTrendingRepo
from backend.agents.recommend.agent.state import QuantitativeCondition

logger = logging.getLogger(__name__)

class TrendService:
    """
    LangGraph에서 추출된 QuantitativeCondition을 받아 트렌드 정보를 조회하는 서비스
    """
    
    def __init__(self):
        # 💡 LLM 초기화 로직 제거: 이 서비스는 LLM 호출 없이 필터 변환만 담당합니다.
        pass 

    def _extract_trend_filters(self, filters: List[QuantitativeCondition]) -> Dict[str, Any]:
        """QuantitativeCondition 리스트에서 TREND_LANGUAGE 및 TREND_SINCE 값을 추출합니다."""
        
        # TREND_SINCE의 기본값은 'weekly' (프롬프트 규칙에 따라)
        trend_filters = {"language": None, "since": "past_week"} 
        
        for condition in filters:
            if condition.metric == "TREND_LANGUAGE" and condition.value:
                # Value는 LLM에 의해 이미 영어 소문자 문자열로 추출되었을 것이라 가정
                trend_filters["language"] = condition.value
            elif condition.metric == "TREND_SINCE" and condition.value:
                # Value는 LLM에 의해 이미 유효한 Literal 값으로 변환되었을 것이라 가정
                trend_filters["since"] = condition.value
        
        return trend_filters

    async def search_trending_repos(self, filters: List[QuantitativeCondition]) -> List[ParsedTrendingRepo]:
        """
        [메인 함수] LangGraph 상태에서 추출된 필터(QuantitativeCondition)를 받아 트렌드 검색 결과를 반환
        """
        
        # 1. QuantitativeCondition 리스트에서 트렌드 필터 추출
        trend_input_dict = self._extract_trend_filters(filters)
        
        language = trend_input_dict["language"]
        since_str = trend_input_dict["since"]
        
        logger.info(f"🔍 Trend Search: Language='{language}', Period='{since_str}'")

        # 2. 문자열 Period를 Client용 Enum으로 변환 (Client의 요구사항에 맞게 매핑)
        period_enum = self._map_period_string_to_enum(since_str)
        
        # 3. TrendClient를 통해 데이터 조회 (기존 로직 유지)
        print(f"   [Trend Client] Fetching trending repos for Language: {language}, Period: {period_enum.value}...")
        
        # ⚠️ trend_client 인스턴스가 전역으로 정의되어 있어야 합니다.
        raw_results = await trend_client.get_trending_repos(
            language=language,
            period=period_enum
        )
        print(f"   [Trend Client] Received {len(raw_results)} raw results.")
        
        # 4. 결과 변환 및 데이터 정제 (기존 로직 유지)
        parsed_results = []
        for item in raw_results:
            try:
                # [Data Fix] Owner/Name 쪼개기 로직 (TrendService의 이전 로직에서 제거됨)
                # 이 로직은 TrendClient나 TrendService 내부에 있어야 하며, 여기서는 간략화합니다.
                
                # Pydantic 모델 변환 시도
                repo = ParsedTrendingRepo(**item)
                parsed_results.append(repo)
                
            except ValidationError as e:
                logger.warning(f"⚠️ Skipping invalid repo data: {item.get('name', 'Unknown')}. Validation Error: {e}")
                continue
        
        logger.info(f"✅ Successfully parsed {len(parsed_results)} repos.")
        return parsed_results

    def _map_period_string_to_enum(self, period_str: str) -> TrendingPeriod:
        """Pydantic 모델의 문자열 기간을 Client용 Enum으로 변환"""
        
        # LLM에게 지시한 Literal 값과 Client의 TrendingPeriod Enum을 매핑
        mapping = {
            "past_24_hours": TrendingPeriod.DAILY,
            "past_week": TrendingPeriod.WEEKLY,
            "past_month": TrendingPeriod.MONTHLY,
            "past_3_months": TrendingPeriod.MONTHLY, # 3개월이 없으므로 월별로 폴백
            # 추가: LLM이 실수로 출력할 수 있는 값에 대한 방어
            "daily": TrendingPeriod.DAILY, 
            "weekly": TrendingPeriod.WEEKLY,
            "monthly": TrendingPeriod.MONTHLY,
        }
        # 소문자 처리
        period_str = period_str.lower() if period_str else "past_week"
        
        # 매핑 실패 시 WEEKLY로 폴백
        return mapping.get(period_str, TrendingPeriod.WEEKLY)

# 싱글톤 인스턴스
trend_service = TrendService()