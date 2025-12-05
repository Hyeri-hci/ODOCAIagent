import sys
import os
from unittest.mock import MagicMock, patch

# Add current directory to sys.path
sys.path.append(os.getcwd())

from backend.agents.supervisor.models import SupervisorInput
from backend.agents.supervisor.service import init_state_from_input
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.core.models import DiagnosisCoreResult

def verify_scenarios():
    print("Verifying Scenarios...")

    # Mock Diagnosis Output to avoid actual API calls
    mock_diagnosis_output = MagicMock()
    mock_diagnosis_output.to_dict.return_value = {
        "repo_id": "test/repo",
        "health_score": 80,
        "structure": {"has_tests": True}, # Check structure
        "summary_for_user": "Good job"
    }

    with patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis") as mock_run:
        mock_run.return_value = mock_diagnosis_output

        # 1. diagnose_repo
        print("\n1. Testing diagnose_repo...")
        inp = SupervisorInput(task_type="diagnose_repo", owner="test", repo="repo")
        state = init_state_from_input(inp)
        graph = get_supervisor_graph()
        result = graph.invoke(state, config={"configurable": {"thread_id": "test1"}})
        
        if "structure" in result["diagnosis_result"]:
            print("  [PASS] diagnosis_result.structure exists")
        else:
            print("  [FAIL] diagnosis_result.structure MISSING")

        # 2. build_onboarding_plan
        print("\n2. Testing build_onboarding_plan...")
        inp = SupervisorInput(
            task_type="build_onboarding_plan", 
            owner="test", 
            repo="repo",
            user_context={"experience_days": 10}
        )
        state = init_state_from_input(inp)
        result = graph.invoke(state, config={"configurable": {"thread_id": "test2"}})

        if result.get("onboarding_plan"):
            print("  [PASS] onboarding_plan exists")
        else:
            print("  [FAIL] onboarding_plan MISSING")
            
        if result.get("onboarding_summary"):
            print("  [PASS] onboarding_summary exists")
            print(f"  Summary Preview: {result['onboarding_summary'][:50]}...")
        else:
            print("  [FAIL] onboarding_summary MISSING")

if __name__ == "__main__":
    verify_scenarios()
