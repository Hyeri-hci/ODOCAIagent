"""
Tests for diagnosis_labels.py
"""
import pytest
from backend.agents.diagnosis.tools.scoring.diagnosis_labels import (
    compute_health_level,
    compute_onboarding_level,
    compute_docs_issues,
    compute_activity_issues,
    create_diagnosis_labels,
)


class TestComputeHealthLevel:
    def test_good_level(self):
        assert compute_health_level(70) == "good"
        assert compute_health_level(80) == "good"
        assert compute_health_level(100) == "good"

    def test_warning_level(self):
        assert compute_health_level(50) == "warning"
        assert compute_health_level(60) == "warning"
        assert compute_health_level(69) == "warning"

    def test_bad_level(self):
        assert compute_health_level(0) == "bad"
        assert compute_health_level(30) == "bad"
        assert compute_health_level(49) == "bad"


class TestComputeOnboardingLevel:
    def test_easy_level(self):
        assert compute_onboarding_level(75) == "easy"
        assert compute_onboarding_level(90) == "easy"
        assert compute_onboarding_level(100) == "easy"

    def test_normal_level(self):
        assert compute_onboarding_level(55) == "normal"
        assert compute_onboarding_level(65) == "normal"
        assert compute_onboarding_level(74) == "normal"

    def test_hard_level(self):
        assert compute_onboarding_level(0) == "hard"
        assert compute_onboarding_level(40) == "hard"
        assert compute_onboarding_level(54) == "hard"


class TestComputeDocsIssues:
    def test_weak_documentation(self):
        issues = compute_docs_issues(doc_score=30)
        assert "weak_documentation" in issues

    def test_no_weak_documentation(self):
        issues = compute_docs_issues(doc_score=50)
        assert "weak_documentation" not in issues

    def test_missing_categories_dict_format(self):
        """CategoryInfo dict 형태 테스트"""
        readme_categories = {
            "WHAT": {"present": True, "raw_text": "Project description"},
            "WHY": {"present": False, "raw_text": ""},
            "HOW": {"present": True, "raw_text": "Installation steps"},
            "CONTRIBUTING": {"present": False, "raw_text": ""},
        }
        issues = compute_docs_issues(doc_score=60, readme_categories=readme_categories)
        assert "missing_what" not in issues
        assert "missing_why" in issues
        assert "missing_how" not in issues
        assert "missing_contributing" in issues

    def test_all_categories_present(self):
        readme_categories = {
            "WHAT": {"present": True, "raw_text": "What this is"},
            "WHY": {"present": True, "raw_text": "Why use this"},
            "HOW": {"present": True, "raw_text": "How to install"},
            "CONTRIBUTING": {"present": True, "raw_text": "How to contribute"},
        }
        issues = compute_docs_issues(doc_score=80, readme_categories=readme_categories)
        assert len(issues) == 0


class TestComputeActivityIssues:
    def test_inactive_project(self):
        issues = compute_activity_issues(activity_score=20)
        assert "inactive_project" in issues

    def test_no_inactive_project(self):
        issues = compute_activity_issues(activity_score=50)
        assert "inactive_project" not in issues

    def test_low_commit_score(self):
        activity_scores = {"commit_score": 0.1, "issue_score": 0.5, "pr_score": 0.5}
        issues = compute_activity_issues(activity_score=50, activity_scores=activity_scores)
        assert "no_recent_commits" in issues
        assert "low_issue_closure" not in issues
        assert "slow_pr_merge" not in issues

    def test_low_issue_closure(self):
        activity_scores = {"commit_score": 0.5, "issue_score": 0.2, "pr_score": 0.5}
        issues = compute_activity_issues(activity_score=50, activity_scores=activity_scores)
        assert "low_issue_closure" in issues

    def test_slow_pr_merge(self):
        activity_scores = {"commit_score": 0.5, "issue_score": 0.5, "pr_score": 0.3}
        issues = compute_activity_issues(activity_score=50, activity_scores=activity_scores)
        assert "slow_pr_merge" in issues

    def test_all_issues(self):
        activity_scores = {"commit_score": 0.1, "issue_score": 0.2, "pr_score": 0.3}
        issues = compute_activity_issues(activity_score=20, activity_scores=activity_scores)
        assert "inactive_project" in issues
        assert "no_recent_commits" in issues
        assert "low_issue_closure" in issues
        assert "slow_pr_merge" in issues


class TestCreateDiagnosisLabels:
    def test_healthy_project(self):
        labels = create_diagnosis_labels(
            health_score=80,
            onboarding_score=85,
            doc_score=90,
            activity_score=75,
        )
        assert labels.health_level == "good"
        assert labels.onboarding_level == "easy"
        assert len(labels.docs_issues) == 0
        assert len(labels.activity_issues) == 0

    def test_unhealthy_project(self):
        labels = create_diagnosis_labels(
            health_score=40,
            onboarding_score=50,
            doc_score=30,
            activity_score=20,
            activity_scores={"commit_score": 0.1, "issue_score": 0.2, "pr_score": 0.3},
        )
        assert labels.health_level == "bad"
        assert labels.onboarding_level == "hard"
        assert "weak_documentation" in labels.docs_issues
        assert "inactive_project" in labels.activity_issues

    def test_to_dict(self):
        labels = create_diagnosis_labels(
            health_score=70,
            onboarding_score=60,
            doc_score=50,
            activity_score=50,
        )
        d = labels.to_dict()
        assert "health_level" in d
        assert "onboarding_level" in d
        assert "docs_issues" in d
        assert "activity_issues" in d
        assert isinstance(d["docs_issues"], list)
        assert isinstance(d["activity_issues"], list)



