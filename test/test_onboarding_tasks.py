"""
Onboarding Tasks 단위 테스트

난이도/레벨 결정, 메타 Task 생성, 통합 로직 테스트.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.agents.diagnosis.tools.onboarding_tasks import (
    TaskSuggestion,
    OnboardingTasks,
    determine_difficulty_from_labels,
    determine_level,
    determine_kind_from_labels,
    generate_issue_reasons,
    create_tasks_from_issues,
    create_meta_tasks_from_labels,
    compute_onboarding_tasks,
    filter_tasks_by_user_level,
)


# ============================================================
# 난이도 결정 테스트
# ============================================================

class TestDetermineDifficulty:
    """난이도 결정 테스트."""
    
    def test_good_first_issue(self):
        labels = ["good first issue", "enhancement"]
        assert determine_difficulty_from_labels(labels) == "beginner"
    
    def test_good_first_issue_hyphen(self):
        labels = ["good-first-issue"]
        assert determine_difficulty_from_labels(labels) == "beginner"
    
    def test_beginner_friendly(self):
        labels = ["beginner-friendly", "documentation"]
        assert determine_difficulty_from_labels(labels) == "beginner"
    
    def test_help_wanted(self):
        labels = ["help wanted"]
        assert determine_difficulty_from_labels(labels) == "intermediate"
    
    def test_documentation(self):
        labels = ["documentation"]
        assert determine_difficulty_from_labels(labels) == "intermediate"
    
    def test_bug(self):
        labels = ["bug"]
        assert determine_difficulty_from_labels(labels) == "advanced"
    
    def test_security(self):
        labels = ["security", "critical"]
        assert determine_difficulty_from_labels(labels) == "advanced"
    
    def test_no_matching_labels(self):
        labels = ["question", "wontfix"]
        assert determine_difficulty_from_labels(labels) == "intermediate"
    
    def test_case_insensitive(self):
        labels = ["Good First Issue", "ENHANCEMENT"]
        assert determine_difficulty_from_labels(labels) == "beginner"


class TestDetermineLevel:
    """레벨 결정 테스트."""
    
    def test_beginner_good_first_issue(self):
        labels = ["good first issue"]
        level = determine_level("beginner", labels)
        assert level == 1
    
    def test_beginner_other(self):
        labels = ["beginner-friendly"]
        level = determine_level("beginner", labels)
        assert level == 2
    
    def test_intermediate_docs(self):
        labels = ["documentation"]
        level = determine_level("intermediate", labels)
        assert level == 3
    
    def test_intermediate_other(self):
        labels = ["help wanted"]
        level = determine_level("intermediate", labels)
        assert level == 4
    
    def test_advanced_few_comments(self):
        labels = ["bug"]
        level = determine_level("advanced", labels, comment_count=5)
        assert level == 5
    
    def test_advanced_many_comments(self):
        labels = ["bug"]
        level = determine_level("advanced", labels, comment_count=15)
        assert level == 6


class TestDetermineKind:
    """Task 종류 결정 테스트."""
    
    def test_documentation(self):
        labels = ["documentation", "good first issue"]
        assert determine_kind_from_labels(labels) == "doc"
    
    def test_tests(self):
        labels = ["tests", "help wanted"]
        assert determine_kind_from_labels(labels) == "test"
    
    def test_refactor(self):
        labels = ["refactor", "enhancement"]
        assert determine_kind_from_labels(labels) == "refactor"
    
    def test_issue(self):
        labels = ["bug", "enhancement"]
        assert determine_kind_from_labels(labels) == "issue"


# ============================================================
# 추천 이유 생성 테스트
# ============================================================

class TestGenerateIssueReasons:
    """추천 이유 생성 테스트."""
    
    def test_good_first_issue_reason(self):
        labels = ["good first issue"]
        reasons = generate_issue_reasons(labels, "beginner")
        assert any("good-first-issue" in r for r in reasons)
    
    def test_help_wanted_reason(self):
        labels = ["help wanted"]
        reasons = generate_issue_reasons(labels, "intermediate")
        assert any("help-wanted" in r for r in reasons)
    
    def test_docs_reason(self):
        labels = ["documentation"]
        reasons = generate_issue_reasons(labels, "intermediate")
        assert any("문서" in r for r in reasons)
    
    def test_default_reason(self):
        labels = ["question"]
        reasons = generate_issue_reasons(labels, "beginner")
        assert len(reasons) > 0


# ============================================================
# 이슈 기반 Task 생성 테스트
# ============================================================

class TestCreateTasksFromIssues:
    """이슈에서 Task 생성 테스트."""
    
    def test_rest_api_format(self):
        issues = [
            {
                "number": 123,
                "title": "Add documentation",
                "html_url": "https://github.com/owner/repo/issues/123",
                "labels": [{"name": "good first issue"}, {"name": "documentation"}],
                "comments": 3,
            }
        ]
        tasks = create_tasks_from_issues(issues, "https://github.com/owner/repo")
        
        assert len(tasks) == 1
        task = tasks[0]
        assert task.id == "issue#123"
        assert task.difficulty == "beginner"
        assert task.level == 1
        assert task.kind == "doc"
        assert "good first issue" in task.labels
    
    def test_graphql_format(self):
        issues = [
            {
                "number": 456,
                "title": "Fix bug",
                "url": "https://github.com/owner/repo/issues/456",
                "labels": {"nodes": [{"name": "bug"}]},
                "comments": {"totalCount": 5},
            }
        ]
        tasks = create_tasks_from_issues(issues, "https://github.com/owner/repo")
        
        assert len(tasks) == 1
        task = tasks[0]
        assert task.id == "issue#456"
        assert task.difficulty == "advanced"
        assert task.kind == "issue"


# ============================================================
# 메타 Task 생성 테스트
# ============================================================

class TestCreateMetaTasks:
    """메타 Task 생성 테스트."""
    
    def test_missing_contributing(self):
        docs_issues = ["missing_contributing"]
        tasks = create_meta_tasks_from_labels(
            docs_issues=docs_issues,
            activity_issues=[],
            health_level="good",
            repo_url="https://github.com/owner/repo",
        )
        
        assert len(tasks) == 1
        assert tasks[0].id == "meta:create_contributing"
        assert tasks[0].kind == "meta"
        assert tasks[0].difficulty == "beginner"
    
    def test_missing_what(self):
        docs_issues = ["missing_what"]
        tasks = create_meta_tasks_from_labels(
            docs_issues=docs_issues,
            activity_issues=[],
            health_level="good",
            repo_url="",
        )
        
        assert any(t.id == "meta:improve_readme_what" for t in tasks)
    
    def test_inactive_project(self):
        activity_issues = ["inactive_project"]
        tasks = create_meta_tasks_from_labels(
            docs_issues=[],
            activity_issues=activity_issues,
            health_level="warning",
            repo_url="",
        )
        
        assert any(t.id == "meta:check_maintainer_status" for t in tasks)
        task = next(t for t in tasks if t.id == "meta:check_maintainer_status")
        assert task.difficulty == "advanced"
        assert any("[주의]" in r for r in task.reasons)
    
    def test_bad_health(self):
        tasks = create_meta_tasks_from_labels(
            docs_issues=[],
            activity_issues=[],
            health_level="bad",
            repo_url="",
        )
        
        assert any(t.id == "meta:evaluate_project_health" for t in tasks)
    
    def test_multiple_issues(self):
        docs_issues = ["missing_what", "missing_how", "weak_documentation"]
        activity_issues = ["low_issue_closure"]
        
        tasks = create_meta_tasks_from_labels(
            docs_issues=docs_issues,
            activity_issues=activity_issues,
            health_level="warning",
            repo_url="",
        )
        
        assert len(tasks) >= 4


# ============================================================
# OnboardingTasks 모델 테스트
# ============================================================

class TestOnboardingTasks:
    """OnboardingTasks 모델 테스트."""
    
    def test_to_dict(self):
        task = TaskSuggestion(
            kind="issue",
            difficulty="beginner",
            level=1,
            id="issue#1",
            title="Test",
            labels=["test"],
            reasons=["reason1"],
        )
        tasks = OnboardingTasks(
            beginner=[task],
            intermediate=[],
            advanced=[],
            total_count=1,
            issue_count=1,
            meta_count=0,
        )
        
        d = tasks.to_dict()
        assert len(d["beginner"]) == 1
        assert d["beginner"][0]["id"] == "issue#1"
        assert d["meta"]["total_count"] == 1


# ============================================================
# 통합 테스트 (모킹)
# ============================================================

class TestComputeOnboardingTasks:
    """compute_onboarding_tasks 통합 테스트."""
    
    @patch("backend.agents.diagnosis.tools.onboarding_tasks.fetch_open_issues_for_tasks_rest")
    def test_with_mocked_issues(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "number": 1,
                "title": "Easy issue",
                "html_url": "https://github.com/owner/repo/issues/1",
                "labels": [{"name": "good first issue"}],
                "comments": 0,
            },
            {
                "number": 2,
                "title": "Medium issue",
                "html_url": "https://github.com/owner/repo/issues/2",
                "labels": [{"name": "help wanted"}],
                "comments": 5,
            },
            {
                "number": 3,
                "title": "Hard issue",
                "html_url": "https://github.com/owner/repo/issues/3",
                "labels": [{"name": "bug"}, {"name": "critical"}],
                "comments": 20,
            },
        ]
        
        labels = {
            "health_level": "good",
            "onboarding_level": "easy",
            "docs_issues": ["missing_contributing"],
            "activity_issues": [],
        }
        
        result = compute_onboarding_tasks(
            owner="owner",
            repo="repo",
            labels=labels,
        )
        
        # beginner: issue#1 + meta:create_contributing
        assert len(result.beginner) >= 1
        # intermediate: issue#2
        assert len(result.intermediate) >= 1
        # advanced: issue#3
        assert len(result.advanced) >= 1
        
        assert result.issue_count == 3
        assert result.meta_count == 1


class TestFilterTasksByUserLevel:
    """사용자 레벨 기반 필터링 테스트."""
    
    def test_beginner_filter(self):
        beginner_task = TaskSuggestion(kind="issue", difficulty="beginner", level=1, id="b1", title="B1")
        intermediate_task = TaskSuggestion(kind="issue", difficulty="intermediate", level=3, id="i1", title="I1")
        advanced_task = TaskSuggestion(kind="issue", difficulty="advanced", level=5, id="a1", title="A1")
        
        tasks = OnboardingTasks(
            beginner=[beginner_task],
            intermediate=[intermediate_task],
            advanced=[advanced_task],
        )
        
        filtered = filter_tasks_by_user_level(tasks, "beginner")
        
        # beginner 전체 + intermediate 일부
        assert any(t.id == "b1" for t in filtered)
        assert any(t.id == "i1" for t in filtered)
        # advanced는 포함 안됨
        assert not any(t.id == "a1" for t in filtered)
    
    def test_advanced_filter(self):
        beginner_task = TaskSuggestion(kind="issue", difficulty="beginner", level=1, id="b1", title="B1")
        intermediate_task = TaskSuggestion(kind="issue", difficulty="intermediate", level=3, id="i1", title="I1")
        advanced_task = TaskSuggestion(kind="issue", difficulty="advanced", level=5, id="a1", title="A1")
        
        tasks = OnboardingTasks(
            beginner=[beginner_task],
            intermediate=[intermediate_task],
            advanced=[advanced_task],
        )
        
        filtered = filter_tasks_by_user_level(tasks, "advanced")
        
        # 모든 난이도 포함
        assert any(t.id == "a1" for t in filtered)
