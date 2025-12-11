import json
import logging
from langchain.tools import tool
from core.trend.get_trend import trend_service

logger = logging.getLogger(__name__)

@tool
async def github_trend_search_tool(query: str) -> str:
    """
    [GitHub Trend Search Tool]
    GitHub에서 현재 인기 있는(Trending) 리포지토리를 검색합니다.
    언어(예: Python, Java)나 기간(오늘, 이번주, 이번달)은 사용자의 질문에서 자동으로 추출됩니다.

    Args:
        query: 사용자의 자연어 질문 전체 (예: "요즘 뜨는 파이썬 라이브러리 보여줘", "오늘의 인기 프로젝트")

    Returns:
        JSON string containing a list of trending repositories (rank, name, stars, description, url).
    """
    try:
        # 1. 이미 생성된 싱글톤 서비스 호출 (비동기)
        # Service 내부에서 LLM이 언어/기간을 분석하고 API/크롤링을 수행합니다.
        results = await trend_service.search_trending_repos(query)
        
        if not results:
            return "검색 결과가 없습니다. (No trending repositories found)."

        # 2. Pydantic 모델 리스트 -> 딕셔너리 리스트 변환 -> JSON 직렬화
        # LLM이 읽기 편하게 JSON 문자열로 반환합니다.
        results_dict = [repo.model_dump() for repo in results]
        
        return json.dumps(results_dict, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"❌ Error in github_trend_search_tool: {e}")
        return f"Error searching trends: {str(e)}"