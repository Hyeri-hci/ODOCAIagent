# test/test_github_ingest.py

import pytest
from tools.github_ingest_tool import github_ingest_tool

@pytest.mark.parametrize("repo_url", [
    "https://github.com/facebook/react",  # 풀 URL
    "facebook/react",                     # user/repo 형식
])
def test_github_ingest_tool(repo_url):
    """
    GitHubIngest Tool이 정상적으로 동작하는지 테스트
    - 풀 URL과 user/repo 형식 모두 지원
    """
    # Tool 실행 (invoke 사용 권장, run도 호환 가능)
    # 입력이 단일 문자열인 경우 invoke에 바로 전달하거나 dict로 전달
    try:
        result = github_ingest_tool.invoke(repo_url)
    except AttributeError:
        # invoke가 없는 구버전 LangChain 객체일 경우
        result = github_ingest_tool.run(repo_url)

    print(f"\nResult for {repo_url}: {result}")
    
    # 기본 검증: 반환값이 RepoSchema(또는 유사 객체) 형식이어야 함
    assert result is not None
    
    # [수정됨] Pydantic 객체가 아닌 Dict가 반환되므로 키 존재 여부로 확인
    if isinstance(result, dict):
        assert "repo_url" in result
        assert "name" in result
        assert "owner" in result
    else:
        # 만약 객체라면 기존 방식 유지
        assert hasattr(result, "repo_url")
        assert hasattr(result, "name")
        assert hasattr(result, "owner")

    # repo_url에 repo 이름이 포함되어 있는지 확인
    # "facebook/react" -> "react" 추출
    expected_name = repo_url.rstrip("/").split("/")[-1]
    
    # Dict 호환성 처리
    target_url = result.get("repo_url") if isinstance(result, dict) else result.repo_url
    assert expected_name in target_url