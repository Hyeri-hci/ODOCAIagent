
import unittest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.diagnosis.graph import get_diagnosis_agent
from backend.agents.supervisor.state import SupervisorState

class TestDiagnosisAgent(unittest.TestCase):
    def test_diagnosis_graph_execution(self):
        # 1. 그래프 생성
        graph = get_diagnosis_agent()
        
        # 2. 초기 상태 설정
        initial_state = {
            "owner": "Hyeri-hci",
            "repo": "ODOCAIagent",
            "repo_ref": "HEAD",
            "task_type": "diagnosis",
            "messages": [],
        }
        
        # 3. 그래프 실행
        print(f"\nRunning DiagnosisAgent graph for {initial_state['owner']}/{initial_state['repo']}...")
        result = graph.invoke(initial_state)
        
        # 4. 결과 검증
        # - repo_snapshot 존재 여부
        self.assertIsNotNone(result.get("repo_snapshot"))
        self.assertEqual(result["repo_snapshot"].owner, "Hyeri-hci")
        
        # - diagnosis_result 존재 여부
        diag = result.get("diagnosis_result")
        self.assertIsNotNone(diag)
        print(f"Diagnosis Result: Health={diag.health_score}, Level={diag.health_level}")
        
        # - messages에 요약 메시지 추가 여부
        messages = result.get("messages", [])
        self.assertTrue(len(messages) > 0)
        last_msg = messages[-1]
        print(f"Last Message Content:\n{last_msg.content}")
        
        self.assertIn("진단 결과", last_msg.content)
        self.assertEqual(result.get("last_answer_kind"), "diagnosis")

if __name__ == "__main__":
    unittest.main()
