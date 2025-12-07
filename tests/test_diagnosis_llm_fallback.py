
import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, patch
from backend.agents.diagnosis.graph import summarize_diagnosis_node
from backend.core.models import DiagnosisCoreResult
from backend.agents.supervisor.state import SupervisorState

class TestDiagnosisLLMFallback(unittest.TestCase):
    def test_summarize_diagnosis_fallback(self):
        # 1. Mock State with Diagnosis Result
        mock_diagnosis = DiagnosisCoreResult(
            repo_id="test/repo",
            health_score=80,
            health_level="good",
            documentation_quality=70,
            activity_maintainability=90,
            onboarding_score=80,
            onboarding_level="easy",
            is_healthy=True,
            docs_issues=["missing_readme"],
            activity_issues=[],
            dependency_snapshot=None
        )
        
        state: SupervisorState = {
            "diagnosis_result": mock_diagnosis,
            "messages": [],
            "task_type": "diagnosis"
        }
        
        # 2. Mock LLM Client to raise Exception
        with patch("backend.llm.factory.fetch_llm_client") as mock_fetch:
            mock_client = MagicMock()
            mock_client.chat.side_effect = Exception("LLM API Error")
            mock_fetch.return_value = mock_client
            
            # 3. Run Node
            result = summarize_diagnosis_node(state)
            
            # 4. Verify Fallback Output
            messages = result.get("messages")
            self.assertTrue(len(messages) > 0)
            content = messages[0].content
            
            # Check if fallback format is used
            self.assertIn("### test/repo 진단 결과", content)
            self.assertIn("건강 점수", content)
            self.assertIn("80점", content)
            
            print("\nFallback Summary Output:\n", content)

if __name__ == "__main__":
    unittest.main()
