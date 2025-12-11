# test/test_github_filter.py

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.github_filter_tool import github_filter_tool
from core.github.schema import ParsedRepo

# -----------------------------------------------------------------------------
# Part 1. Fixtures & Mock Data (단위 테스트용)
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_repos_dict():
    """Tool 입력용 Dict 리스트 (ParsedRepo 스키마 준수)"""
    return [
        {
            "full_name": "owner/active-repo",
            "owner": "owner",
            "name": "active-repo",
            "html_url": "https://github.com/owner/active-repo",
            "stars": 1000,
            "forks": 200,
            "open_issues": 50,
            "description": "Very Active Repo",
            "topics": ["python"],
            "last_update": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        },
        {
            "full_name": "owner/dead-repo",
            "owner": "owner",
            "name": "dead-repo",
            "html_url": "https://github.com/owner/dead-repo",
            "stars": 10,
            "forks": 2,
            "open_issues": 0,
            "description": "Inactive Repo",
            "topics": ["java"],
            "last_update": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z"
        }
    ]

# -----------------------------------------------------------------------------
# Part 2. Unit Tests (Mock 사용 - 로직 검증)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("other_condition, expected_count", [
    ("many_issues", 1),       # active-repo만 통과한다고 가정
    ("few_issues", 1),        # dead-repo만 통과한다고 가정
    ("has_prs_10", 1),
    ("many_commits_recently_1y", 1) 
])
@patch("tools.github_filter_tool.RepoFilter")
def test_mocked_logic(MockRepoFilter, sample_repos_dict, other_condition, expected_count):
    """
    [Logic Test] 실제 API 없이 필터링 로직이 호출되는지 확인
    """
    # Mock 설정: 필터가 항상 첫 번째 레포만 반환한다고 가정 (로직 흐름 확인용)
    mock_instance = MockRepoFilter.return_value
    # filter_repositories는 ParsedRepo 객체 리스트를 반환
    mock_instance.filter_repositories.return_value = [ParsedRepo(**sample_repos_dict[0])]

    query_result = {
        "q": "test",
        "other": other_condition
    }

    result = github_filter_tool.run({
        "repos": sample_repos_dict,
        "query_result": query_result
    })

    print(f"\n[Mock Test] Condition: {other_condition} -> Count: {len(result)}")
    
    # Tool은 다시 Dict 리스트를 반환해야 함
    assert isinstance(result, list)
    assert len(result) == expected_count
    # 내부 로직 호출 확인
    MockRepoFilter.assert_called_once()


# -----------------------------------------------------------------------------
# Part 3. Real Integration Tests (실제 GitHub API 호출)
# -----------------------------------------------------------------------------

# 실제 테스트에 사용할 리포지토리 데이터 생성 헬퍼
def create_real_repo_input(owner, name):
    return {
        "full_name": f"{owner}/{name}",
        "owner": owner,
        "name": name,
        "html_url": f"https://github.com/{owner}/{name}",
        "stars": 0, "forks": 0, "open_issues": 0, # 더미 데이터 (Filter는 API로 새로 긁어옴)
        "description": "Real Test Repo",
        "topics": [],
        "last_update": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

# 실제 API를 때리는 테스트 케이스 정의
REAL_WORLD_SCENARIOS = [
    # 1. Facebook React (초대형 활성 프로젝트)
    # -> 당연히 이슈, PR, 커밋이 많아야 함
    ("facebook", "react", "many_issues", True, "React는 이슈가 많아야 함"),
    ("facebook", "react", "many_commits_recently_1y", True, "React는 최근 1년 커밋이 활발해야 함"),
    ("facebook", "react", "few_commits", False, "React는 커밋이 적으면 안 됨 (탈락 예상)"),
    ("facebook", "react", "has_prs_10", True, "React는 PR이 10개 이상이어야 함"),

    # 2. 아주 오래된/죽은 프로젝트 예시 (직접 만든 더미가 없으므로 가상의 상황 가정)
    # 비교적 덜 활발한 레포 (예: requests는 안정적이지만 React만큼 미친듯이 커밋되진 않음 - 상황에 따라 다름)
    # 여기서는 확실한 검증을 위해 React 위주로 테스트합니다.
]

@pytest.mark.parametrize("owner, name, condition, should_pass, desc", REAL_WORLD_SCENARIOS)
def test_real_github_integration(owner, name, condition, should_pass, desc):
    """
    [Integration Test] 실제 GitHub API를 사용하여 필터링이 제대로 작동하는지 검증
    """
    print(f"\n{'='*60}")
    print(f"🌍 REAL API TEST: {owner}/{name}")
    print(f"👉 Condition: '{condition}'")
    print(f"👉 Expectation: {'PASS (Keep)' if should_pass else 'FAIL (Drop)'}")
    print(f"👉 Description: {desc}")
    print(f"{'-'*60}")

    # 1. 입력 데이터 준비
    real_input_repos = [create_real_repo_input(owner, name)]
    
    query_result = {
        "q": "test",
        "other": condition
    }

    # 2. 실제 툴 실행 (Mocking 없음!)
    try:
        result = github_filter_tool.run({
            "repos": real_input_repos,
            "query_result": query_result
        })
    except Exception as e:
        pytest.fail(f"API 호출 중 에러 발생: {e}")

    # 3. 결과 검증
    is_passed = len(result) > 0
    
    print(f"✅ Filter Result: {'PASSED' if is_passed else 'DROPPED'}")

    if should_pass:
        assert is_passed, f"Expected {owner}/{name} to PASS condition '{condition}', but it was dropped."
    else:
        assert not is_passed, f"Expected {owner}/{name} to FAIL condition '{condition}', but it passed."

# 직접 실행 시 pytest 호출
if __name__ == "__main__":
    pytest.main(["-s", __file__])