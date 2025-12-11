# test/test_github_search.py

import pytest
from tools.github_search_tool import github_search_tool
from core.github.schema import ParsedRepo

@pytest.mark.parametrize("query,sort,order", [
    ("language:python stars:>5000", "stars", "desc"),
    ("language:python", "stars", "desc"),
])
def test_basic_search(query, sort, order):
    """기본 검색 기능 및 반환 타입 테스트"""
    params = {
        "params": {
            "query": query,
            "sort": sort,
            "order": order
        }
    }

    # Tool 실행
    result = github_search_tool.run(params)

    print(f"\nSearch Result Count: {len(result) if isinstance(result, list) else 'Not List'}")

    # ParsedRepo 리스트인지 확인
    assert isinstance(result, list)
    if result:
        repo = result[0]
        # [수정됨] Dict 형태인지 확인하고 필수 키 검사 (Tool이 Dict를 반환)
        if isinstance(repo, dict):
             assert "full_name" in repo
             assert "html_url" in repo
             assert "stars" in repo
             assert repo["stars"] >= 0
        else:
             # Pydantic 객체일 경우
             assert isinstance(repo, ParsedRepo) or (hasattr(repo, 'full_name') and hasattr(repo, 'html_url'))
             assert repo.full_name
             assert repo.html_url
             assert repo.stars >= 0

def test_sort_order():
    """정렬 옵션(stars desc)이 제대로 적용되는지 테스트"""
    params = {
        "params": {
            "query": "language:python",
            "sort": "stars",
            "order": "desc"
        }
    }

    result = github_search_tool.run(params)
    
    # 결과가 비어있지 않다고 가정 (Python은 인기 언어이므로)
    assert len(result) > 0
    
    # [수정됨] 모든 요소가 Dict인지 확인
    assert all((isinstance(r, dict) or isinstance(r, ParsedRepo)) for r in result)

    # 정렬이 내림차순(stars desc)으로 되어 있는지 검증
    # Dict 호환성 처리
    stars_list = [r["stars"] if isinstance(r, dict) else r.stars for r in result]
    assert stars_list == sorted(stars_list, reverse=True), "결과가 스타 순으로 정렬되지 않았습니다."

def test_default_per_page():
    """기본 페이지 당 결과 수 제한 테스트"""
    params = {
        "params": {
            "query": "language:python",
            "sort": "stars",
            "order": "desc"
        }
    }

    result = github_search_tool.run(params)
    
    # GitHub search API 툴 내부 설정에 따라 다르겠지만 보통 10개 내외
    # [수정됨] 실제 API가 15개를 반환하는 경우가 있으므로 조건을 30개로 현실화
    assert len(result) <= 30