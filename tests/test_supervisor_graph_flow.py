import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from backend.agents.supervisor.graph import run_supervisor

# 통합 테스트 마커 (실제 그래프 실행)
pytestmark = pytest.mark.slow


@pytest.mark.asyncio
@patch("backend.agents.diagnosis.graph.run_diagnosis")
async def test_diagnose_repo_flow(mock_run_diagnosis):
    """진단 요청 플로우 테스트 (새 아키텍처)."""
    # Mock Diagnosis Output
    mock_run_diagnosis.return_value = {
        "type": "full_diagnosis",
        "repo_id": "test/repo",
        "health_score": 80,
        "health_level": "good",
        "onboarding_score": 70,
        "onboarding_level": "normal",
        "llm_summary": "Good job"
    }

    # Run Supervisor with proper user_message
    result = await run_supervisor(
        owner="test",
        repo="repo",
        user_message="이 저장소를 분석해주세요. 건강도와 온보딩 점수를 알려주세요."
    )
    
    # Verify (새 아키텍처 응답 형식)
    assert "session_id" in result
    assert "final_answer" in result
    # clarification 또는 실제 답변이 있어야 함
    assert result.get("final_answer") is not None or result.get("awaiting_clarification") == True


@pytest.mark.asyncio
@patch("backend.agents.diagnosis.graph.run_diagnosis")
@patch("backend.agents.onboarding.graph.run_onboarding_graph")
async def test_build_onboarding_plan_flow(mock_onboarding, mock_diagnosis):
    """온보딩 플랜 생성 플로우 테스트 (새 아키텍처)."""
    # Mock Diagnosis Output
    mock_diagnosis.return_value = {
        "type": "full_diagnosis",
        "repo_id": "test/repo",
        "health_score": 80,
        "health_level": "good",
        "onboarding_score": 70,
        "onboarding_level": "normal"
    }
    
    # Mock Onboarding Output
    mock_onboarding.return_value = {
        "repo_id": "test/repo",
        "experience_level": "beginner",
        "plan": [
            {"week": 1, "title": "환경 설정", "tasks": ["Clone repo"]},
            {"week": 2, "title": "첫 기여", "tasks": ["Fix bug"]}
        ],
        "summary": "2주 온보딩 플랜이 생성되었습니다."
    }

    # Run Supervisor with proper user_message
    result = await run_supervisor(
        owner="test",
        repo="repo",
        user_message="초보자용 온보딩 가이드를 만들어주세요"
    )
    
    # Verify (새 아키텍처 응답 형식)
    assert "session_id" in result
    assert "final_answer" in result
    # clarification 또는 실제 답변이 있어야 함
    assert result.get("final_answer") is not None or result.get("awaiting_clarification") == True
