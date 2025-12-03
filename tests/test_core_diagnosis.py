
import unittest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_scores
from backend.core.models import RepoSnapshot, DocsCoreResult, ActivityCoreResult, DependenciesSnapshot, DiagnosisCoreResult

class TestCoreDiagnosis(unittest.TestCase):
    def test_pipeline(self):
        # 1. 스냅샷 가져오기 (실제 리포지토리 사용)
        owner = "Hyeri-hci"
        repo = "ODOCAIagent"
        
        print(f"\nTesting pipeline for {owner}/{repo}...")
        
        try:
            snapshot = fetch_repo_snapshot(owner, repo)
        except Exception as e:
            print(f"Skipping test due to fetch failure: {e}")
            return

        self.assertIsInstance(snapshot, RepoSnapshot)
        self.assertEqual(snapshot.owner, owner)
        self.assertEqual(snapshot.repo, repo)

        # 2. 문서 분석
        docs = analyze_docs(snapshot)
        self.assertIsInstance(docs, DocsCoreResult)
        print(f"Docs Score: {docs.total_score}")

        # 3. 활동성 분석
        activity = analyze_activity(snapshot)
        self.assertIsInstance(activity, ActivityCoreResult)
        print(f"Activity Score: {activity.total_score}")

        # 4. 의존성 파싱
        deps = parse_dependencies(snapshot)
        self.assertIsInstance(deps, DependenciesSnapshot)
        print(f"Dependencies Count: {deps.total_count}")

        # 5. 점수 계산
        result = compute_scores(docs, activity, deps)
        self.assertIsInstance(result, DiagnosisCoreResult)
        print(f"Health Score: {result.health_score}")
        print(f"Health Level: {result.health_level}")

        # 검증
        self.assertTrue(0 <= result.health_score <= 100)
        self.assertIn(result.health_level, ["good", "warning", "bad"])
        self.assertIsNotNone(result.dependency_snapshot)

if __name__ == "__main__":
    unittest.main()
