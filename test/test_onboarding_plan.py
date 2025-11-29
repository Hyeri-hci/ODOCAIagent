"""
Tests for onboarding_plan.py
"""
import pytest
from backend.agents.diagnosis.tools.onboarding_plan import (
    OnboardingPlan,
    create_onboarding_plan_v0,
    create_onboarding_plan,
    _compute_difficulty,
    _compute_recommended,
    _generate_first_steps_rule_based,
    _generate_risks_rule_based,
    _estimate_setup_time,
)


class TestComputeDifficulty:
    def test_easy(self):
        assert _compute_difficulty(75) == "easy"
        assert _compute_difficulty(90) == "easy"
        assert _compute_difficulty(100) == "easy"

    def test_normal(self):
        assert _compute_difficulty(55) == "normal"
        assert _compute_difficulty(65) == "normal"
        assert _compute_difficulty(74) == "normal"

    def test_hard(self):
        assert _compute_difficulty(0) == "hard"
        assert _compute_difficulty(40) == "hard"
        assert _compute_difficulty(54) == "hard"


class TestComputeRecommended:
    def test_recommended(self):
        assert _compute_recommended(70, True) is True
        assert _compute_recommended(80, True) is True
        assert _compute_recommended(100, True) is True

    def test_not_recommended_low_score(self):
        assert _compute_recommended(60, True) is False
        assert _compute_recommended(69, True) is False

    def test_not_recommended_unhealthy(self):
        assert _compute_recommended(80, False) is False
        assert _compute_recommended(100, False) is False


class TestGenerateFirstSteps:
    def test_with_all_docs(self):
        steps = _generate_first_steps_rule_based(
            difficulty="easy",
            docs_issues=[],
        )
        assert len(steps) == 5
        assert "README" in steps[0]
        assert "Quick Start" in steps[1] or "Installation" in steps[1]
        assert "CONTRIBUTING" in steps[2]
        assert "good-first-issue" in steps[3]

    def test_with_missing_docs(self):
        steps = _generate_first_steps_rule_based(
            difficulty="hard",
            docs_issues=["missing_what", "missing_how", "missing_contributing"],
        )
        assert len(steps) == 5
        assert "Description" in steps[0]  # fallback for missing_what
        assert "package.json" in steps[1] or "requirements.txt" in steps[1]  # fallback for missing_how
        assert "기존 PR" in steps[2]  # fallback for missing_contributing
        assert "코드베이스를 충분히 탐색" in steps[3]  # hard difficulty


class TestGenerateRisks:
    def test_healthy_no_issues(self):
        risks = _generate_risks_rule_based(
            is_healthy=True,
            docs_issues=[],
            activity_issues=[],
        )
        assert len(risks) == 0

    def test_unhealthy(self):
        risks = _generate_risks_rule_based(
            is_healthy=False,
            docs_issues=[],
            activity_issues=[],
        )
        assert any("유지보수되지 않습니다" in r for r in risks)

    def test_activity_issues(self):
        risks = _generate_risks_rule_based(
            is_healthy=True,
            docs_issues=[],
            activity_issues=["no_recent_commits", "low_issue_closure", "slow_pr_merge"],
        )
        assert any("커밋이 없어" in r for r in risks)
        assert any("이슈 해결 속도" in r for r in risks)
        assert any("PR 머지" in r for r in risks)

    def test_inactive_project(self):
        risks = _generate_risks_rule_based(
            is_healthy=False,
            docs_issues=[],
            activity_issues=["inactive_project"],
        )
        assert any("비활성 상태" in r for r in risks)

    def test_docs_issues(self):
        risks = _generate_risks_rule_based(
            is_healthy=True,
            docs_issues=["weak_documentation", "missing_contributing", "missing_how"],
            activity_issues=[],
        )
        assert any("문서가 부족" in r for r in risks)
        assert any("기여 가이드" in r for r in risks)


class TestEstimateSetupTime:
    def test_easy_no_issues(self):
        assert _estimate_setup_time("easy", []) == "30분 이내"

    def test_easy_with_issues(self):
        assert _estimate_setup_time("easy", ["missing_how"]) == "30분 ~ 1시간"

    def test_normal(self):
        assert _estimate_setup_time("normal", []) == "1 ~ 2시간"

    def test_hard(self):
        assert _estimate_setup_time("hard", []) == "2시간 이상"


class TestCreateOnboardingPlanV0:
    def test_healthy_easy_project(self):
        plan = create_onboarding_plan_v0(
            onboarding_score=85,
            is_healthy=True,
            docs_issues=[],
            activity_issues=[],
        )
        assert plan.recommended_for_beginner is True
        assert plan.difficulty == "easy"
        assert len(plan.first_steps) == 5
        assert len(plan.risks) == 0
        assert plan.estimated_setup_time == "30분 이내"

    def test_unhealthy_project(self):
        plan = create_onboarding_plan_v0(
            onboarding_score=50,
            is_healthy=False,
            docs_issues=["missing_contributing"],
            activity_issues=["no_recent_commits"],
        )
        assert plan.recommended_for_beginner is False
        assert plan.difficulty == "hard"
        assert len(plan.risks) >= 2

    def test_to_dict(self):
        plan = create_onboarding_plan_v0(
            onboarding_score=70,
            is_healthy=True,
            docs_issues=[],
            activity_issues=[],
        )
        d = plan.to_dict()
        assert "recommended_for_beginner" in d
        assert "difficulty" in d
        assert "first_steps" in d
        assert "risks" in d
        assert "estimated_setup_time" in d


class TestCreateOnboardingPlan:
    def test_v0_interface(self):
        """통합 인터페이스로 v0 호출"""
        plan = create_onboarding_plan(
            scores={"onboarding_score": 80, "is_healthy": True},
            labels={"docs_issues": [], "activity_issues": []},
            use_llm=False,
        )
        assert plan.recommended_for_beginner is True
        assert plan.difficulty == "easy"
        assert len(plan.first_steps) == 5
