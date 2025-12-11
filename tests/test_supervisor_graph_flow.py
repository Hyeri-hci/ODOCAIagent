import pytest
from unittest.mock import patch, MagicMock
from backend.agents.supervisor.models import SupervisorInput, SupervisorState
from backend.agents.supervisor.service import init_state_from_input
from backend.agents.supervisor.graph import get_supervisor_graph

# 통합 테스트 마커 (실제 그래프 실행)
pytestmark = pytest.mark.slow

@pytest.mark.asyncio
@patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
async def test_diagnose_repo_flow(mock_run_diagnosis):
    # Mock Diagnosis Output
    mock_output = MagicMock()
    mock_output.to_dict.return_value = {
        "repo_id": "test/repo",
        "health_score": 80,
        "health_level": "good",
        "onboarding_score": 70,
        "onboarding_level": "medium",
        "summary_for_user": "Good job"
    }
    mock_run_diagnosis.return_value = mock_output

    # Input
    inp = SupervisorInput(
        task_type="diagnose_repo",
        owner="test",
        repo="repo"
    )
    state = init_state_from_input(inp)
    
    # Run Graph (async)
    graph = get_supervisor_graph()
    result = await graph.ainvoke(state, config={"configurable": {"thread_id": "test"}})
    
    # Verify
    assert result["task_type"] == "diagnose_repo"
    assert result["diagnosis_result"]["repo_id"] == "test/repo"
    assert result["last_answer_kind"] == "report" # run_diagnosis_node sets this

@pytest.mark.asyncio
@patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
async def test_build_onboarding_plan_flow(mock_run_diagnosis):
    # Mock Diagnosis Output
    mock_output = MagicMock()
    mock_output.to_dict.return_value = {
        "repo_id": "test/repo",
        "health_score": 80,
        "health_level": "good",
        "onboarding_score": 70,
        "onboarding_level": "medium",
        "summary_for_user": "Good job"
    }
    mock_run_diagnosis.return_value = mock_output

    # Input
    inp = SupervisorInput(
        task_type="build_onboarding_plan",
        owner="test",
        repo="repo",
        user_context={"experience_days": 10}
    )
    state = init_state_from_input(inp)
    
    # Run Graph (async)
    graph = get_supervisor_graph()
    result = await graph.ainvoke(state, config={"configurable": {"thread_id": "test2"}})
    
    # Verify
    assert result["task_type"] == "build_onboarding_plan"
    assert result["diagnosis_result"]["repo_id"] == "test/repo"
    
    # Verify Onboarding Flow
    assert "candidate_issues" in result
    assert len(result["candidate_issues"]) > 0
    assert "onboarding_plan" in result
    assert len(result["onboarding_plan"]) > 0
    assert result["last_answer_kind"] == "plan" # summarize_onboarding_plan_node sets this
