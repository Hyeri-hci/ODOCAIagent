import pytest
import logging
from core.trend.get_trend import TrendService

# 로그를 화면에 찍기 위해 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_real_github_trend_integration():
    """
    [통합 테스트]
    Mock을 사용하지 않습니다.
    실제 OpenAI API와 GitHub(또는 크롤링)에 접속합니다.
    """
    # 1. 실제 서비스 객체 생성 (Mocking 없이!)
    service = TrendService()
    
    # 2. 실제 쿼리 날리기
    query = "요즘 뜨는 파이썬 라이브러리 알려줘"
    logger.info(f"🚀 실제 요청 보냄: {query}")
    
    try:
        results = await service.search_trending_repos(query)
        
        # 3. 눈으로 결과 확인
        print("\n" + "="*50)
        print(f"📊 검색 결과 개수: {len(results)}개")
        
        for idx, repo in enumerate(results[:3]): # 상위 3개만 출력
            print(f"\n[{idx+1}위] {repo.owner}/{repo.name}")
            print(f" - 설명: {repo.description}")
            print(f" - 스타: {repo.stars_since} (기간 내)")
            print(f" - 언어: {repo.language}")
            print(f" - URL: {repo.url}")
        print("="*50 + "\n")

        # 4. 최소한의 검증 (데이터가 비어있지 않은지)
        assert len(results) > 0
        assert results[0].name is not None

    except Exception as e:
        pytest.fail(f"❌ 실제 연동 실패: {e}")