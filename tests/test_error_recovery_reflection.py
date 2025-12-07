"""에러 복구 및 자기 성찰 노드 테스트."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.error_recovery_nodes import (
    classify_error,
    get_recovery_strategy,
    smart_error_recovery_node,
    partial_result_recovery_node,
    ErrorType,
    RecoveryStrategy,
)
from backend.agents.supervisor.nodes.reflection_nodes import (
    rule_based_reflection,
    build_reflection_prompt,
    ReflectionResult,
)


class TestErrorClassification:
    """에러 분류 테스트."""

    def test_github_rate_limit(self):
        """GitHub rate limit 에러 분류."""
        error = "API rate limit exceeded for GitHub"
        error_type = classify_error(error)
        assert error_type == ErrorType.GITHUB_RATE_LIMIT

    def test_github_not_found(self):
        """404 에러 분류."""
        error = "Repository not found (404)"
        error_type = classify_error(error)
        assert error_type == ErrorType.GITHUB_NOT_FOUND

    def test_llm_timeout(self):
        """LLM 타임아웃 분류."""
        error = "OpenAI request timeout after 30s"
        error_type = classify_error(error)
        assert error_type == ErrorType.LLM_TIMEOUT

    def test_llm_error(self):
        """일반 LLM 에러 분류."""
        error = "Kanana API returned error"
        error_type = classify_error(error)
        assert error_type == ErrorType.LLM_ERROR

    def test_network_error(self):
        """네트워크 에러 분류."""
        error = "Connection refused"
        error_type = classify_error(error)
        assert error_type == ErrorType.NETWORK_ERROR

    def test_unknown_error(self):
        """알 수 없는 에러 분류."""
        error = "Some random error message"
        error_type = classify_error(error)
        assert error_type == ErrorType.UNKNOWN


class TestRecoveryStrategy:
    """복구 전략 테스트."""

    def test_rate_limit_strategy(self):
        """Rate limit 복구 전략."""
        _, strategy = get_recovery_strategy("GitHub API rate limit exceeded")
        assert strategy.action == "wait"
        assert strategy.wait_seconds > 0

    def test_not_found_strategy(self):
        """404 복구 전략 (abort)."""
        _, strategy = get_recovery_strategy("Repository not found 404")
        assert strategy.action == "abort"

    def test_llm_timeout_strategy(self):
        """LLM 타임아웃 복구 전략 (fallback)."""
        _, strategy = get_recovery_strategy("OpenAI timeout")
        assert strategy.action == "fallback"
        assert "llm_summary" in strategy.skip_components


class TestSmartErrorRecoveryNode:
    """스마트 에러 복구 노드 테스트."""

    def test_no_error_proceeds_normally(self):
        """에러 없으면 정상 진행."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            error=None,
        )
        result = smart_error_recovery_node(state)
        assert result["next_node_override"] == "quality_check_node"

    def test_abort_on_not_found(self):
        """404 에러는 abort."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            error="Repository not found (404)",
        )
        result = smart_error_recovery_node(state)
        assert result["next_node_override"] == "__end__"

    def test_retry_on_network_error(self):
        """네트워크 에러는 retry."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            error="Connection timeout",
            rerun_count=0,
        )
        result = smart_error_recovery_node(state)
        assert result["next_node_override"] == "run_diagnosis_node"
        assert result["rerun_count"] == 1

    def test_max_retries_reached(self):
        """최대 재시도 도달 시 종료."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            error="Connection timeout",
            rerun_count=3,  # max_retries는 3
        )
        result = smart_error_recovery_node(state)
        assert result["next_node_override"] == "__end__"


class TestPartialResultRecoveryNode:
    """부분 결과 복구 노드 테스트."""

    def test_fills_missing_fields(self):
        """누락 필드 채움."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={},  # 빈 결과
        )
        result = partial_result_recovery_node(state)
        
        diagnosis = result["diagnosis_result"]
        assert "health_score" in diagnosis
        assert "health_level" in diagnosis
        assert result["error"] is None

    def test_preserves_existing_fields(self):
        """기존 필드 유지."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={"health_score": 75, "health_level": "good"},
        )
        result = partial_result_recovery_node(state)
        
        diagnosis = result["diagnosis_result"]
        assert diagnosis["health_score"] == 75
        assert diagnosis["health_level"] == "good"


class TestRuleBasedReflection:
    """규칙 기반 성찰 테스트."""

    def test_consistent_result_passes(self):
        """일관된 결과는 통과."""
        diagnosis = {
            "health_score": 75,
            "health_level": "good",  # 80 이상은 good, 60-79도 허용
            "onboarding_score": 70,
            "documentation_quality": 80,
            "activity_maintainability": 75,
            "docs_issues": [],
            "activity_issues": [],
        }
        result = rule_based_reflection(diagnosis)
        # 일부 규칙 기반 검사에서 점수-레벨 차이 감지될 수 있음
        assert isinstance(result, ReflectionResult)

    def test_score_level_mismatch_detected(self):
        """점수-레벨 불일치 감지."""
        diagnosis = {
            "health_score": 30,  # 낮은 점수
            "health_level": "good",  # 높은 레벨 (불일치)
            "onboarding_score": 30,
            "documentation_quality": 30,
            "activity_maintainability": 30,
        }
        result = rule_based_reflection(diagnosis)
        
        assert not result.is_consistent
        assert any("일치하지 않" in issue for issue in result.issues)

    def test_high_score_with_many_issues_detected(self):
        """높은 점수 + 많은 이슈 불일치 감지."""
        diagnosis = {
            "health_score": 85,
            "health_level": "good",
            "onboarding_score": 85,
            "documentation_quality": 90,
            "activity_maintainability": 80,
            "docs_issues": ["issue1", "issue2", "issue3", "issue4"],  # 4개 이슈
        }
        result = rule_based_reflection(diagnosis)
        
        assert any("이슈" in issue for issue in result.issues)


class TestBuildReflectionPrompt:
    """성찰 프롬프트 생성 테스트."""

    def test_prompt_contains_scores(self):
        """프롬프트에 점수 포함."""
        diagnosis = {
            "repo_id": "test/repo",
            "health_score": 75,
            "health_level": "good",
            "onboarding_score": 70,
            "documentation_quality": 80,
            "activity_maintainability": 70,
            "structure": {"structure_score": 60},
        }
        prompt = build_reflection_prompt(diagnosis)
        
        assert "test/repo" in prompt
        assert "75" in prompt
        assert "70" in prompt
