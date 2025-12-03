import unittest
import sys
import os
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.activity_core import (
    _compute_commit_metrics,
    _compute_issue_metrics,
    _compute_pr_metrics,
    score_commit_activity,
    score_issue_activity,
    score_pr_activity,
    aggregate_activity_score,
    activity_score_to_100,
)

class TestActivityScoring(unittest.TestCase):
    """이 테스트는 activity_core 점수 로직의 엣지케이스를 검증합니다."""

    def setUp(self):
        self.owner = "test-owner"
        self.repo = "test-repo"
        self.days = 90
        self.now = datetime.now(timezone.utc)

    def test_dead_repo(self):
        """(1) 이슈/PR/커밋이 거의 없는 'dead repo' 케이스"""
        commits = []
        issues = []
        prs = []

        # Metrics calculation
        c_metrics = _compute_commit_metrics(commits, self.owner, self.repo, self.days)
        i_metrics = _compute_issue_metrics(issues, self.owner, self.repo, self.days)
        p_metrics = _compute_pr_metrics(prs, self.owner, self.repo, self.days)

        # Score calculation
        c_score = score_commit_activity(c_metrics)
        i_score = score_issue_activity(i_metrics)
        p_score = score_pr_activity(p_metrics)
        
        breakdown = aggregate_activity_score(c_metrics, i_metrics, p_metrics)
        total_score = activity_score_to_100(breakdown)

        # Assertions
        self.assertEqual(c_score, 0.0)
        # Issues/PRs being empty might default to 0.5 or similar neutral score in current logic, 
        # or 0.0 depending on implementation. 
        # Looking at logic: if opened_issues_in_window == 0 -> return 0.5
        self.assertEqual(i_score, 0.5) 
        self.assertEqual(p_score, 0.5)
        
        # Overall score shouldn't be high, but not necessarily 0 due to neutral defaults
        self.assertLess(total_score, 60) 

    def test_commit_heavy_repo(self):
        """(2) 커밋은 많지만 이슈/PR이 거의 없는 repo"""
        commits = []
        for i in range(100):
            dt = self.now - timedelta(days=i)
            commits.append({
                "commit": {
                    "author": {"date": dt.isoformat(), "name": f"author{i%5}"},
                    "committer": {"date": dt.isoformat()}
                },
                "author": {"login": f"user{i%5}"}
            })

        issues = [] # Empty issues
        prs = []    # Empty PRs

        c_metrics = _compute_commit_metrics(commits, self.owner, self.repo, self.days)
        i_metrics = _compute_issue_metrics(issues, self.owner, self.repo, self.days)
        p_metrics = _compute_pr_metrics(prs, self.owner, self.repo, self.days)

        c_score = score_commit_activity(c_metrics)
        
        # Commit score should be high (freq=1.0, recency=1.0, diversity=1.0) -> ~1.0
        self.assertGreater(c_score, 0.8)
        
        breakdown = aggregate_activity_score(c_metrics, i_metrics, p_metrics)
        total_score = activity_score_to_100(breakdown)
        
        # Should be decent but not perfect
        self.assertGreater(total_score, 40)
        self.assertLess(total_score, 90)

    def test_issue_pr_heavy_repo(self):
        """(3) 이슈/PR은 활발하지만 커밋이 거의 없는 repo"""
        commits = []
        
        issues = []
        for i in range(10):
            created = self.now - timedelta(days=10+i)
            closed = self.now - timedelta(days=5+i)
            issues.append({
                "state": "CLOSED",
                "createdAt": created.isoformat(),
                "closedAt": closed.isoformat()
            })
            
        prs = []
        for i in range(10):
            created = self.now - timedelta(days=10+i)
            merged = self.now - timedelta(days=5+i)
            prs.append({
                "state": "MERGED",
                "createdAt": created.isoformat(),
                "mergedAt": merged.isoformat()
            })

        c_metrics = _compute_commit_metrics(commits, self.owner, self.repo, self.days)
        i_metrics = _compute_issue_metrics(issues, self.owner, self.repo, self.days)
        p_metrics = _compute_pr_metrics(prs, self.owner, self.repo, self.days)

        c_score = score_commit_activity(c_metrics)
        i_score = score_issue_activity(i_metrics)
        p_score = score_pr_activity(p_metrics)

        self.assertEqual(c_score, 0.0)
        self.assertGreater(i_score, 0.5)
        self.assertGreater(p_score, 0.5)

        breakdown = aggregate_activity_score(c_metrics, i_metrics, p_metrics)
        total_score = activity_score_to_100(breakdown)
        
        self.assertGreater(total_score, 30)

    def test_edge_cases(self):
        """(4) time-to-close / time-to-merge 계산 엣지케이스"""
        
        # Case 1: CreatedAt > ClosedAt (Should be handled safely)
        issues = [{
            "state": "CLOSED",
            "createdAt": self.now.isoformat(),
            "closedAt": (self.now - timedelta(days=1)).isoformat() # Closed before created
        }]
        i_metrics = _compute_issue_metrics(issues, self.owner, self.repo, self.days)
        # Duration should be 0.0, not negative
        self.assertEqual(i_metrics.median_time_to_close_days, 0.0)

        # Case 2: PR merged but no mergedAt (Should be ignored for merge duration)
        prs = [{
            "state": "MERGED",
            "createdAt": self.now.isoformat(),
            "mergedAt": None
        }]
        p_metrics = _compute_pr_metrics(prs, self.owner, self.repo, self.days)
        self.assertIsNone(p_metrics.median_time_to_merge_days)
        self.assertEqual(p_metrics.merged_in_window, 0)

        # Case 3: Invalid Date Strings (Should be ignored)
        commits = [{
            "commit": {
                "author": {"date": "invalid-date"},
            }
        }]
        c_metrics = _compute_commit_metrics(commits, self.owner, self.repo, self.days)
        self.assertEqual(c_metrics.total_commits, 1) # Counted
        self.assertIsNone(c_metrics.last_commit_date) # Date parsing failed

if __name__ == "__main__":
    unittest.main()
