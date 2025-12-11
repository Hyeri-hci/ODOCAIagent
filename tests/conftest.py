"""
pytest 설정 및 공통 fixture.

사용법:
    # 빠른 테스트만 실행 (개발 시)
    pytest --skip-slow
    
    # 전체 테스트 실행 (CI/CD)
    pytest
"""
import pytest
from typing import Any, Dict
from unittest.mock import MagicMock, AsyncMock


def pytest_addoption(parser):
    """느린 테스트 제외 옵션 추가."""
    parser.addoption(
        "--skip-slow",
        action="store_true",
        default=False,
        help="느린 테스트(실제 API 호출) 건너뛰기"
    )


def pytest_configure(config):
    """마커 등록."""
    config.addinivalue_line(
        "markers", "slow: 실제 API 호출이 필요한 느린 테스트"
    )
    config.addinivalue_line(
        "markers", "integration: 통합 테스트"
    )
    config.addinivalue_line(
        "markers", "unit: 단위 테스트"
    )


def pytest_collection_modifyitems(config, items):
    """--skip-slow 옵션 시 slow 마커 테스트 건너뛰기."""
    if not config.getoption("--skip-slow"):
        return
    
    skip_slow = pytest.mark.skip(reason="--skip-slow 옵션으로 건너뜀")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


# === 공통 Fixture ===

@pytest.fixture
def sample_repo_info() -> Dict[str, str]:
    """테스트용 저장소 정보."""
    return {
        "owner": "test-owner",
        "repo": "test-repo",
        "ref": "main"
    }


@pytest.fixture
def sample_supervisor_intent() -> Dict[str, Any]:
    """테스트용 Supervisor Intent."""
    return {
        "task_type": "diagnosis",
        "confidence": 0.95,
        "requires_repo": True,
        "extracted_repo": "test-owner/test-repo",
        "sub_intent": "full_analysis",
        "parameters": {
            "analysis_depth": 2,
            "focus": "all"
        },
        "clarification_needed": False,
        "clarification_question": None
    }


@pytest.fixture
def sample_diagnosis_result() -> Dict[str, Any]:
    """테스트용 Diagnosis 결과."""
    return {
        "ok": True,
        "health_score": 75,
        "onboarding_score": 65,
        "docs_result": {
            "score": 80,
            "has_readme": True,
            "has_contributing": False
        },
        "activity_result": {
            "score": 70,
            "days_since_last_commit": 5,
            "total_commits_30d": 15
        },
        "structure_result": {
            "score": 75,
            "file_count": 50
        },
        "deps_result": {
            "score": 80,
            "dependency_count": 10
        },
        "llm_summary": "테스트 프로젝트입니다."
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM Client."""
    mock = MagicMock()
    mock.chat = MagicMock(return_value=MagicMock(
        content="테스트 응답입니다."
    ))
    mock.chat_with_retry = MagicMock(return_value=MagicMock(
        content="테스트 응답입니다."
    ))
    return mock


@pytest.fixture
def mock_github_client():
    """Mock GitHub Client."""
    mock = AsyncMock()
    mock.get_repo_info = AsyncMock(return_value={
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "description": "Test repository",
        "stargazers_count": 100,
        "forks_count": 10
    })
    mock.get_readme = AsyncMock(return_value="# Test Repo\n\nThis is a test.")
    mock.get_commits = AsyncMock(return_value=[
        {"sha": "abc123", "message": "Initial commit"}
    ])
    return mock
