"""Kanana LLM 통합 테스트."""
import pytest
from unittest.mock import patch, MagicMock
from backend.agents.supervisor.nodes.onboarding_nodes import plan_onboarding_node, summarize_onboarding_plan_node
from backend.agents.supervisor.models import SupervisorState, SupervisorInput
from backend.agents.supervisor.service import init_state_from_input
from backend.agents.supervisor.graph import get_supervisor_graph

# 통합 테스트 마커
pytestmark = pytest.mark.slow

@patch("backend.agents.supervisor.nodes.onboarding_nodes.KananaWrapper")
def test_plan_onboarding_node(mock_wrapper_cls):
    # Mock Wrapper Instance
    mock_instance = mock_wrapper_cls.return_value
    mock_instance.generate_onboarding_plan.return_value = [{"week": 1, "goals": ["Test"]}]

    # State
    state = SupervisorState(
        task_type="build_onboarding_plan",
        owner="test",
        repo="repo",
        diagnosis_result={"summary_for_user": "Summary"},
        candidate_issues=[{"number": 1, "title": "Issue"}]
    )

    # Run Node
    result = plan_onboarding_node(state)

    # Verify
    assert "onboarding_plan" in result
    assert result["onboarding_plan"][0]["week"] == 1
    mock_instance.generate_onboarding_plan.assert_called_once()

@patch("backend.agents.supervisor.nodes.onboarding_nodes.KananaWrapper")
def test_summarize_onboarding_plan_node(mock_wrapper_cls):
    # Mock Wrapper Instance
    mock_instance = mock_wrapper_cls.return_value
    mock_instance.summarize_onboarding_plan.return_value = "Summary Text"

    # State
    state = SupervisorState(
        task_type="build_onboarding_plan",
        owner="test",
        repo="repo",
        onboarding_plan=[{"week": 1}]
    )

    # Run Node
    result = summarize_onboarding_plan_node(state)

    # Verify
    assert result["onboarding_summary"] == "Summary Text"
    assert result["last_answer_kind"] == "plan"
    mock_instance.summarize_onboarding_plan.assert_called_once()

@pytest.mark.asyncio
@patch("backend.agents.supervisor.nodes.onboarding_nodes.KananaWrapper")
@patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
async def test_build_onboarding_plan_integration(mock_run_diagnosis, mock_wrapper_cls):
    """
    Integration test: Run the full graph with mocked KananaWrapper.
    Verifies that the graph correctly routes to onboarding nodes and populates the state.
    """
    # 1. Mock Diagnosis
    mock_diagnosis_output = MagicMock()
    mock_diagnosis_output.to_dict.return_value = {
        "repo_id": "test/repo",
        "health_score": 80,
        "summary_for_user": "Diagnosis Summary"
    }
    mock_run_diagnosis.return_value = mock_diagnosis_output

    # 2. Mock Kanana Wrapper
    mock_instance = mock_wrapper_cls.return_value
    mock_instance.generate_onboarding_plan.return_value = [{"week": 1, "goals": ["Integration Test"]}]
    mock_instance.summarize_onboarding_plan.return_value = "Integration Summary"

    # 3. Input & State
    inp = SupervisorInput(
        task_type="build_onboarding_plan",
        owner="test",
        repo="repo",
        user_context={"experience_days": 10}
    )
    state = init_state_from_input(inp)
    
    # 4. Run Graph (async)
    graph = get_supervisor_graph()
    result = await graph.ainvoke(state, config={"configurable": {"thread_id": "test_integration"}})
    
    # 5. Verify
    assert result["task_type"] == "build_onboarding_plan"
    assert result["diagnosis_result"]["repo_id"] == "test/repo"
    
    # Verify Onboarding Plan (from Kanana)
    assert "onboarding_plan" in result
    assert result["onboarding_plan"][0]["goals"] == ["Integration Test"]
    
    # Verify Summary (from Kanana)
    assert result["onboarding_summary"] == "Integration Summary"
    assert result["last_answer_kind"] == "plan"
    
    # Verify Mock Calls
    mock_instance.generate_onboarding_plan.assert_called_once()
    mock_instance.summarize_onboarding_plan.assert_called_once()
