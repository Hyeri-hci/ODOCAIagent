"""Explain v4 테스트: 3분기 파이프라인, 지표 유효성 검사, 타겟 분류"""
import pytest
from backend.agents.supervisor.models import (
    SupervisorState,
    ExplainTarget,
    decide_explain_target,
)
from backend.agents.supervisor.nodes.summarize_node import (
    _ensure_metrics_exist,
    METRIC_NOT_FOUND_MESSAGE,
    METRIC_NAME_KR,
)
from backend.agents.diagnosis.tools.scoring.reasoning_builder import (
    classify_explain_depth,
    build_warning_text,
)


class TestDecideExplainTarget:
    """decide_explain_target 함수 테스트"""

    def test_explain_after_report_returns_metric(self):
        """리포트 후 explain → metric 타겟"""
        state = {
            "last_answer_kind": "report",
            "diagnosis_result": {"scores": {"health_score": 70}},
        }
        assert decide_explain_target(state) == "metric"

    def test_explain_with_task_list_returns_task(self):
        """Task 목록 + onboarding sub_intent → task_recommendation 타겟"""
        state = {
            "last_sub_intent": "onboarding",
            "last_task_list": [{"title": "Fix README"}],
            "diagnosis_result": {},
        }
        assert decide_explain_target(state) == "task_recommendation"

    def test_explain_with_scores_returns_metric(self):
        """diagnosis_result에 scores 있으면 → metric"""
        state = {
            "diagnosis_result": {"scores": {"health_score": 70}},
        }
        assert decide_explain_target(state) == "metric"

    def test_no_data_returns_general(self):
        """데이터 없으면 → general 타겟"""
        state = {
            "diagnosis_result": {},
        }
        assert decide_explain_target(state) == "general"


class TestEnsureMetricsExist:
    """_ensure_metrics_exist 함수 테스트"""

    @pytest.fixture
    def sample_diagnosis(self):
        return {
            "scores": {
                "health_score": 72,
                "activity_maintainability": 65,
            },
            "reasoning_data": {
                "health_score": {"components": []},
            },
        }

    def test_existing_metric_passes(self, sample_diagnosis):
        """존재하는 지표 → 에러 없음"""
        state = {"diagnosis_result": sample_diagnosis}
        valid, error = _ensure_metrics_exist(state, ["health_score"])
        assert error is None
        assert "health_score" in valid

    def test_nonexistent_metric_returns_error(self, sample_diagnosis):
        """존재하지 않는 지표 → 에러 메시지"""
        state = {"diagnosis_result": sample_diagnosis}
        valid, error = _ensure_metrics_exist(state, ["fake_metric"])
        assert error is not None
        assert "fake_metric" in error

    def test_mixed_metrics_filters_valid(self, sample_diagnosis):
        """일부 없는 지표 → 유효한 것만 반환"""
        state = {"diagnosis_result": sample_diagnosis}
        valid, error = _ensure_metrics_exist(state, ["health_score", "nonexistent"])
        # health_score는 있으니 valid에 포함, error는 None
        assert "health_score" in valid

    def test_empty_diagnosis_returns_error(self):
        """diagnosis_result 없음 → 에러"""
        state = {"diagnosis_result": {}}
        valid, error = _ensure_metrics_exist(state, ["health_score"])
        assert error is not None


class TestClassifyExplainDepth:
    """classify_explain_depth 함수 테스트"""

    def test_short_query_returns_simple(self):
        """짧은 쿼리 → simple"""
        assert classify_explain_depth("점수 뭐야") == "simple"
        assert classify_explain_depth("이거 뭐임") == "simple"

    def test_why_keyword_returns_deep(self):
        """'왜' 키워드 → deep"""
        assert classify_explain_depth("왜 낮아?") == "deep"
        assert classify_explain_depth("이 점수 왜 이래") == "deep"

    def test_detail_keyword_returns_deep(self):
        """'구체', '자세' 키워드 → deep"""
        assert classify_explain_depth("구체적으로 설명해") == "deep"
        assert classify_explain_depth("자세히 알려줘") == "deep"

    def test_long_query_returns_deep(self):
        """긴 쿼리 → deep"""
        long_q = "이 저장소의 활동성 점수가 왜 이렇게 낮은지 자세하게 설명해 주세요"
        assert classify_explain_depth(long_q) == "deep"


class TestBuildWarningText:
    """build_warning_text 함수 테스트"""

    def test_low_health_returns_warning(self):
        """health_score < 50 → 경고"""
        scores = {"health_score": 45}
        warning = build_warning_text(scores)
        assert warning is not None
        assert "리스크" in warning or "50점" in warning

    def test_low_activity_returns_warning(self):
        """activity_maintainability < 50 → 경고"""
        scores = {"activity_maintainability": 35}
        warning = build_warning_text(scores)
        assert warning is not None

    def test_high_scores_no_warning(self):
        """점수 높으면 경고 없음"""
        scores = {
            "health_score": 80,
            "activity_maintainability": 70,
            "documentation_quality": 65,
        }
        warning = build_warning_text(scores)
        assert warning is None

    def test_empty_scores_no_warning(self):
        """빈 scores → 경고 없음"""
        assert build_warning_text({}) is None


class TestMetricNameKr:
    """METRIC_NAME_KR 매핑 테스트"""

    def test_health_score_mapping(self):
        assert METRIC_NAME_KR.get("health_score") == "전체 건강 점수"

    def test_activity_mapping(self):
        assert METRIC_NAME_KR.get("activity_maintainability") == "활동성/유지보수성"

    def test_onboarding_mapping(self):
        assert METRIC_NAME_KR.get("onboarding_score") == "온보딩 용이성"



