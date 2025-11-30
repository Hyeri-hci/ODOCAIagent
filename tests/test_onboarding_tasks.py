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
    generate_reason_tags,
    generate_fallback_reason,
    create_tasks_from_issues,
    create_meta_tasks_from_labels,
    compute_onboarding_tasks,
    filter_tasks_by_user_level,
    filter_tasks_for_user,
    compute_task_score,
    HEALTHY_PROJECT_META_TASKS,
    STUDY_META_TASKS,
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
# 추천 이유 태그 생성 테스트
# ============================================================

class TestGenerateReasonTags:
    """추천 이유 태그 생성 테스트."""
    
    def test_good_first_issue_tag(self):
        labels = ["good first issue"]
        tags = generate_reason_tags(labels, "beginner")
        assert "good_first_issue" in tags
    
    def test_help_wanted_tag(self):
        labels = ["help wanted"]
        tags = generate_reason_tags(labels, "intermediate")
        assert "help_wanted" in tags
    
    def test_docs_tag(self):
        labels = ["documentation"]
        tags = generate_reason_tags(labels, "intermediate")
        assert "docs_issue" in tags
    
    def test_multiple_tags(self):
        labels = ["good first issue", "documentation", "hacktoberfest"]
        tags = generate_reason_tags(labels, "beginner")
        assert "good_first_issue" in tags
        assert "docs_issue" in tags
        assert "hacktoberfest" in tags
    
    def test_default_difficulty_tag(self):
        labels = ["question"]
        tags = generate_reason_tags(labels, "beginner")
        assert "difficulty_beginner" in tags


class TestGenerateFallbackReason:
    """Fallback 이유 생성 테스트."""
    
    def test_good_first_issue_fallback(self):
        reason = generate_fallback_reason("beginner", ["good_first_issue"])
        assert "메인테이너" in reason or "초보자" in reason
    
    def test_docs_fallback(self):
        reason = generate_fallback_reason("intermediate", ["docs_issue"])
        assert "코드" in reason
    
    def test_default_beginner_fallback(self):
        reason = generate_fallback_reason("beginner", ["difficulty_beginner"])
        assert "초보자" in reason
    
    def test_default_advanced_fallback(self):
        reason = generate_fallback_reason("advanced", ["difficulty_advanced"])
        assert "경험자" in reason or "도전" in reason


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
        # 새 필드 검증
        assert "good_first_issue" in task.reason_tags
        assert "docs_issue" in task.reason_tags
        assert task.fallback_reason is not None
    
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
        assert "bug_fix" in task.reason_tags


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
        # 새 필드 검증
        assert "missing_contributing" in tasks[0].meta_flags
        assert "docs_issue" in tasks[0].reason_tags
        assert tasks[0].fallback_reason is not None
    
    def test_missing_what(self):
        docs_issues = ["missing_what"]
        tasks = create_meta_tasks_from_labels(
            docs_issues=docs_issues,
            activity_issues=[],
            health_level="good",
            repo_url="",
        )
        
        task = next(t for t in tasks if t.id == "meta:improve_readme_what")
        assert "missing_what" in task.meta_flags
        assert "quick_win" in task.reason_tags
    
    def test_inactive_project(self):
        activity_issues = ["inactive_project"]
        tasks = create_meta_tasks_from_labels(
            docs_issues=[],
            activity_issues=activity_issues,
            health_level="warning",
            repo_url="",
        )
        
        task = next(t for t in tasks if t.id == "meta:check_maintainer_status")
        assert task.difficulty == "advanced"
        assert "inactive_project" in task.meta_flags
        assert "caution_needed" in task.reason_tags
        assert "주의" in task.fallback_reason
    
    def test_bad_health(self):
        tasks = create_meta_tasks_from_labels(
            docs_issues=[],
            activity_issues=[],
            health_level="bad",
            repo_url="",
        )
        
        task = next(t for t in tasks if t.id == "meta:evaluate_project_health")
        assert "unhealthy_project" in task.meta_flags
    
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
            reason_tags=["good_first_issue"],
            meta_flags=[],
            fallback_reason="테스트 이유",
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
        assert d["beginner"][0]["reason_tags"] == ["good_first_issue"]
        assert d["beginner"][0]["fallback_reason"] == "테스트 이유"
        assert d["meta"]["total_count"] == 1


# ============================================================
# 통합 테스트 (모킹)
# ============================================================

class TestComputeOnboardingTasks:
    """compute_onboarding_tasks 통합 테스트."""
    
    @patch("backend.agents.diagnosis.tools.onboarding_tasks.fetch_open_issues_for_tasks")
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


# ============================================================
# Task Score 계산 테스트
# ============================================================

class TestComputeTaskScore:
    """Task score 계산 테스트."""
    
    def test_good_first_issue_high_score(self):
        """good-first-issue 라벨은 높은 점수."""
        score = compute_task_score("beginner", ["good first issue"], comment_count=1, recency_days=5)
        assert score >= 80  # label 40 + recency 30 + complexity 30
    
    def test_old_issue_low_score(self):
        """오래된 이슈는 낮은 점수."""
        score = compute_task_score("beginner", ["good first issue"], comment_count=1, recency_days=200)
        assert score <= 75  # label 40 + recency 0 + complexity 30
    
    def test_complex_issue_lower_score(self):
        """댓글 많은 이슈는 복잡도 점수가 낮음."""
        score_simple = compute_task_score("beginner", ["bug"], comment_count=1, recency_days=5)
        score_complex = compute_task_score("beginner", ["bug"], comment_count=15, recency_days=5)
        assert score_simple > score_complex
    
    def test_recent_issue_higher_score(self):
        """최근 이슈는 높은 점수."""
        score_recent = compute_task_score("beginner", ["bug"], comment_count=1, recency_days=3)
        score_old = compute_task_score("beginner", ["bug"], comment_count=1, recency_days=100)
        assert score_recent > score_old


# ============================================================
# Intent/Task Score 필드 테스트
# ============================================================

class TestTaskIntent:
    """Intent 필드 테스트."""
    
    def test_task_suggestion_has_intent(self):
        """TaskSuggestion에 intent 필드가 있어야 함."""
        task = TaskSuggestion(
            id="test#1",
            title="Test Task",
            kind="issue",
            difficulty="beginner",
            level=1,
            intent="contribute",
        )
        assert task.intent == "contribute"
    
    def test_task_suggestion_has_task_score(self):
        """TaskSuggestion에 task_score 필드가 있어야 함."""
        task = TaskSuggestion(
            id="test#1",
            title="Test Task",
            kind="issue",
            difficulty="beginner",
            level=1,
            task_score=85,
        )
        assert task.task_score == 85
    
    def test_default_intent_is_contribute(self):
        """기본 intent는 contribute."""
        task = TaskSuggestion(
            id="test#1",
            title="Test Task",
            kind="issue",
            difficulty="beginner",
            level=1,
        )
        assert task.intent == "contribute"


# ============================================================
# 최소 Task 보장 정책 테스트
# ============================================================

class TestMinimumTaskGuarantee:
    """최소 Task 보장 정책 테스트."""
    
    def test_healthy_project_gets_meta_tasks(self):
        """건강한 프로젝트도 최소 메타 Task를 받아야 함."""
        assert len(HEALTHY_PROJECT_META_TASKS) >= 3
        for task in HEALTHY_PROJECT_META_TASKS:
            assert task.intent == "contribute"
    
    def test_study_meta_tasks_exist(self):
        """학습용 메타 Task가 존재해야 함."""
        assert len(STUDY_META_TASKS) >= 2
        for task in STUDY_META_TASKS:
            assert task.intent in ["study", "evaluate"]


# ============================================================
# 사용자 컨텍스트 필터링 테스트
# ============================================================

class TestFilterTasksForUser:
    """사용자 컨텍스트 기반 필터링 테스트."""
    
    def test_filter_by_kind(self):
        """kind로 필터링."""
        docs_task = TaskSuggestion(kind="docs", difficulty="beginner", level=1, id="d1", title="Docs")
        code_task = TaskSuggestion(kind="issue", difficulty="beginner", level=1, id="c1", title="Code")
        
        tasks = OnboardingTasks(
            beginner=[docs_task, code_task],
            intermediate=[],
            advanced=[],
        )
        
        filtered = filter_tasks_for_user(tasks, preferred_kinds=["docs"])
        assert any(t.id == "d1" for t in filtered)
    
    def test_filter_by_intent(self):
        """intent로 필터링."""
        contribute_task = TaskSuggestion(
            kind="issue", difficulty="beginner", level=1, 
            id="c1", title="Contribute", intent="contribute"
        )
        study_task = TaskSuggestion(
            kind="issue", difficulty="beginner", level=1, 
            id="s1", title="Study", intent="study"
        )
        
        tasks = OnboardingTasks(
            beginner=[contribute_task, study_task],
            intermediate=[],
            advanced=[],
        )
        
        filtered = filter_tasks_for_user(tasks, intent_filter="study")
        assert all(t.intent == "study" for t in filtered if t.intent)
    
    def test_sorted_by_task_score(self):
        """task_score로 정렬되어야 함."""
        low_score = TaskSuggestion(
            kind="issue", difficulty="beginner", level=1, 
            id="l1", title="Low", task_score=30
        )
        high_score = TaskSuggestion(
            kind="issue", difficulty="beginner", level=1, 
            id="h1", title="High", task_score=90
        )
        
        tasks = OnboardingTasks(
            beginner=[low_score, high_score],
            intermediate=[],
            advanced=[],
        )
        
        filtered = filter_tasks_for_user(tasks)
        assert filtered[0].id == "h1"  # 높은 점수가 먼저
    
    def test_beginner_level_filters_advanced(self):
        """beginner 레벨은 advanced Task 제외."""
        beginner_task = TaskSuggestion(kind="issue", difficulty="beginner", level=1, id="b1", title="B")
        advanced_task = TaskSuggestion(kind="issue", difficulty="advanced", level=5, id="a1", title="A")
        
        tasks = OnboardingTasks(
            beginner=[beginner_task],
            intermediate=[],
            advanced=[advanced_task],
        )
        
        filtered = filter_tasks_for_user(tasks, user_level="beginner")
        assert not any(t.id == "a1" for t in filtered)
