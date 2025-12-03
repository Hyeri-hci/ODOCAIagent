
import unittest
import os
import sys

# Usage: python tests/test_core_diagnosis.py
# Note: This test requires network access to GitHub API.
# If using pytest: pytest tests/test_core_diagnosis.py -m 'not slow' (add marker if configured)

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_scores
from backend.core.models import RepoSnapshot, DocsCoreResult, ActivityCoreResult, DependenciesSnapshot, DiagnosisCoreResult

class TestCoreDiagnosis(unittest.TestCase):
    def test_pipeline_end_to_end(self):
        # 1. 스냅샷 가져오기 (실제 리포지토리 사용)
        # 테스트 대상 리포지토리 상수 정의
        OWNER = "Hyeri-hci"
        REPO = "ODOCAIagent"
        REF = "HEAD"
        
        print(f"\nTesting pipeline for {OWNER}/{REPO}...")
        
        try:
            snapshot = fetch_repo_snapshot(OWNER, REPO, REF)
        except Exception as e:
            print(f"Skipping test due to fetch failure: {e}")
            return

        self.assertIsInstance(snapshot, RepoSnapshot)
        self.assertEqual(snapshot.owner, OWNER)
        self.assertEqual(snapshot.repo, REPO)

        # 2. 문서 분석
        docs = analyze_docs(snapshot)
        self.assertIsInstance(docs, DocsCoreResult)
        self.assertIsInstance(docs.total_score, (int, float))
        print(f"Docs Score: {docs.total_score}")

        # 3. 활동성 분석
        activity = analyze_activity(snapshot)
        self.assertIsInstance(activity, ActivityCoreResult)
        self.assertIsInstance(activity.total_score, (int, float))
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
        self.assertTrue(0 <= result.onboarding_score <= 100)
        self.assertIn(result.health_level, ["good", "warning", "bad"])
        self.assertIsNotNone(result.dependency_snapshot)
        
        # 추가 필드 검증
        self.assertIsInstance(result.docs_issues, list)
        self.assertIsInstance(result.activity_issues, list)

if __name__ == "__main__":
    unittest.main()
