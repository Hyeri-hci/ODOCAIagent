import pytest
from unittest.mock import patch, MagicMock
from backend.api.agent_service import run_agent_task

@patch("backend.api.agent_service.run_supervisor_diagnosis")
def test_run_agent_task_diagnose_repo(mock_run_diagnosis):
    # Mock Success
    mock_result = MagicMock()
    mock_result.documentation_quality = 80
    mock_result.activity_maintainability = 70
    mock_result.health_score = 80
    mock_result.health_level = "good"
    mock_result.onboarding_score = 70
    mock_result.onboarding_level = "easy"
    mock_result.dependency_complexity_score = 20
    mock_result.dependency_flags = []
    mock_result.docs_issues = []
    mock_result.activity_issues = []
    
    mock_run_diagnosis.return_value = (
        mock_result, # result
        None # error
    )
    
    response = run_agent_task(
        task_type="diagnose_repo",
        owner="test",
        repo="repo"
    )
    
    assert response["ok"] is True
    assert response["task_type"] == "diagnose_repo"
    assert response["data"]["health_score"] == 80
    mock_run_diagnosis.assert_called_once()

@patch("backend.api.agent_service.run_supervisor_onboarding")
def test_run_agent_task_onboarding_plan(mock_run_onboarding):
    # Mock Success
    mock_run_onboarding.return_value = (
        {"onboarding_plan": []}, # result
        None # error
    )
    
    response = run_agent_task(
        task_type="build_onboarding_plan",
        owner="test",
        repo="repo",
        user_context={"experience_days": 10}
    )
    
    assert response["ok"] is True
    assert response["task_type"] == "build_onboarding_plan"
    assert "onboarding_plan" in response["data"]
    mock_run_onboarding.assert_called_once()

def test_run_agent_task_invalid_type():
    response = run_agent_task(
        task_type="unknown_task",
        owner="test",
        repo="repo"
    )
    
    assert response["ok"] is False
    assert "Unknown task_type" in response["error"]

@patch("backend.api.agent_service.run_supervisor_diagnosis")
def test_run_agent_task_diagnosis_failure(mock_run_diagnosis):
    # Mock Failure
    mock_run_diagnosis.return_value = (None, "Diagnosis failed")
    
    response = run_agent_task(
        task_type="diagnose_repo",
        owner="test",
        repo="repo"
    )
    
    assert response["ok"] is False
    assert response["error"] == "Diagnosis failed"
