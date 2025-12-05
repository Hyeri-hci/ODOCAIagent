import sys
import os
from unittest.mock import MagicMock, patch

# Add current directory to sys.path
sys.path.append(os.getcwd())

from backend.api.diagnosis_service import generate_onboarding_plan

def verify_api():
    print("Verifying API...")

    # Mock Supervisor Output
    mock_output = {
        "diagnosis_result": {"repo_id": "test/repo"},
        "onboarding_plan": [{"week": 1}],
        "onboarding_summary": "Summary text",
        "candidate_issues": [],
        "error": None
    }

    with patch("backend.agents.supervisor.service.get_supervisor_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.compile.return_value.invoke.return_value = mock_output
        mock_get_graph.return_value = mock_graph.compile.return_value # Mock the compiled graph directly or the factory?
        # get_supervisor_graph returns graph.compile()
        # So mock_get_graph.return_value should be the compiled graph object which has invoke method.
        mock_get_graph.return_value.invoke.return_value = mock_output

        result = generate_onboarding_plan(
            owner="test", 
            repo="repo", 
            user_context={"experience_days": 10}
        )
        
        print(f"Result OK: {result['ok']}")
        if result['ok']:
            data = result['data']
            print(f"  onboarding_summary present: {'onboarding_summary' in data}")
            print(f"  onboarding_plan present: {'onboarding_plan' in data}")
        else:
            print(f"  Error: {result.get('error')}")

if __name__ == "__main__":
    verify_api()
