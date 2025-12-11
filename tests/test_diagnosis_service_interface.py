from backend.agents.diagnosis.models import DiagnosisInput
from backend.agents.diagnosis.service import run_diagnosis
from unittest.mock import patch, AsyncMock
import pytest

@pytest.mark.asyncio
@patch("backend.agents.diagnosis.service.run_diagnosis_graph")
async def test_run_diagnosis_basic(mock_run_graph):
    """Test run_diagnosis wraps run_diagnosis_graph correctly (async)"""
    
    # Mock run_diagnosis_graph return value
    mock_result = {
        "repo_id": "Hyeri-hci/ODOCAIagent",
        "health_score": 75.0,
        "health_level": "Good",
        "onboarding_score": 80.0,
        "onboarding_level": "Easy",
        "docs": {"total_score": 80},
        "activity": {"total_score": 70},
        "structure": {"has_tests": True},
        "dependency_complexity_score": 20,
        "dependency_flags": [],
        "stars": 100,
        "forks": 50,
        "summary_for_user": "Test summary",
        "raw_metrics": {}
    }
    mock_run_graph.return_value = mock_result
    
    # Run (async 함수)
    input_ = DiagnosisInput(owner="Hyeri-hci", repo="ODOCAIagent", use_llm_summary=False)
    output = await run_diagnosis(input_)
    
    # Verify
    assert output.repo_id == "Hyeri-hci/ODOCAIagent"
    assert isinstance(output.health_score, float)
    assert isinstance(output.onboarding_score, float)
    assert isinstance(output.docs, dict)
    assert isinstance(output.activity, dict)
    assert isinstance(output.structure, dict)
    assert isinstance(output.summary_for_user, str)
    
    # Verify run_diagnosis_graph was called
    mock_run_graph.assert_called_once()
