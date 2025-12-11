"""메타 에이전트 테스트."""
import pytest
from unittest.mock import MagicMock, patch

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.agents.supervisor.nodes.meta_nodes import (
    parse_supervisor_intent,
    create_supervisor_plan,
    execute_supervisor_plan,
    reflect_supervisor,
)


@pytest.fixture
def mock_predict():
    # _invoke_chain이 intent_parsing 모듈로 이동됨
    with patch("backend.agents.supervisor.nodes.intent_parsing._invoke_chain") as mock:
        yield mock


def test_meta_flow_chat_intent(mock_predict):
    """채팅 의도 테스트."""
    mock_predict.return_value = '{"task_type": "chat"}'
    
    state = SupervisorState(
        task_type="diagnose_repo",
        owner="test",
        repo="test",
        user_message="안녕",
    )
    
    # 1. Parse
    res1 = parse_supervisor_intent(state)
    assert res1["global_intent"] == "chat"
    state.global_intent = "chat"
    
    # 2. Plan
    res2 = create_supervisor_plan(state)
    plan = res2["task_plan"]
    assert len(plan) == 1
    assert plan[0]["agent"] == "chat"


def test_meta_flow_diagnose_conditional(mock_predict):
    """조건부 진단 테스트."""
    # 1. Parse Intent
    mock_predict.return_value = '{"task_type": "diagnose", "user_preferences": {"ignore": []}}'
    
    state = SupervisorState(
        task_type="diagnose_repo",
        owner="test", repo="test",
        user_message="진단해주고 안 좋으면 보안도 봐줘",
    )
    
    res1 = parse_supervisor_intent(state)
    assert res1["global_intent"] == "diagnose"
    state.global_intent = "diagnose"
    state.user_preferences = {"ignore": []}
    
    # 2. Create Plan
    res2 = create_supervisor_plan(state)
    plan = res2["task_plan"]
    state.task_plan = plan
    
    # 기본: diagnosis (Security, Recommend are disabled by default for now)
    assert len(plan) >= 1
    assert plan[0]["agent"] == "diagnosis"
    
    # Manually inject plan for execution test
    state.task_plan = [
        {"step": 1, "agent": "diagnosis", "mode": "AUTO", "condition": "always"},
        {"step": 2, "agent": "security", "mode": "FAST", "condition": "if diagnosis.health_score < 50"},
    ]
    
    # 3. Execute (Mocking interactions)
    with patch("backend.agents.diagnosis.service.run_diagnosis") as mock_diag:
        # Case A: Health Good -> Security Skip
        mock_diag.return_value = {"health_score": 80, "summary_for_user": "Good"}
        
        res3 = execute_supervisor_plan(state)
        results = res3["task_results"]
        
        assert "diagnosis" in results
        assert "security" not in results  # Skipped
        
        # Case B: Health Bad -> Security Run
        mock_diag.return_value = {"health_score": 20, "summary_for_user": "Bad"}
        # Reset results
        state.task_results = {}
        
        # Mock security
        with patch("backend.agents.security.service.analyze_repository") as mock_sec:
            mock_sec.return_value = {"total_dependencies": 5}
            
            res4 = execute_supervisor_plan(state)
            results4 = res4["task_results"]
            
            assert "diagnosis" in results4
            assert "security" in results4
