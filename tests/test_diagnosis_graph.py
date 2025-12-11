"""Diagnosis LangGraph 테스트."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.agents.diagnosis.models import DiagnosisState, DiagnosisInput, DiagnosisOutput


class TestDiagnosisState:
    """DiagnosisState 모델 테스트."""

    def test_default_values(self):
        """기본값 테스트."""
        state = DiagnosisState(owner="test", repo="repo")
        
        assert state.ref == "main"
        assert state.analysis_depth == "standard"
        assert state.use_llm_summary == True
        assert state.step == 0
        assert state.error is None
        assert state.timings == {}

    def test_get_partial_result(self):
        """부분 결과 조회."""
        state = DiagnosisState(
            owner="test",
            repo="repo",
            docs_result={"documentation_quality": 80},
            activity_result={"activity_maintainability": 70},
            error="some error",
            failed_step="analyze_structure",
        )
        
        partial = state.get_partial_result()
        
        assert partial["owner"] == "test"
        assert partial["docs"] == {"documentation_quality": 80}
        assert partial["activity"] == {"activity_maintainability": 70}
        assert partial["error"] == "some error"
        assert partial["failed_step"] == "analyze_structure"


@pytest.mark.skip(reason="nodes.py deprecated - routing functions removed")
class TestDiagnosisRouting:
    """Diagnosis 그래프 라우팅 테스트."""

    def test_route_after_snapshot_normal(self):
        """스냅샷 후 정상 라우팅."""
        state = DiagnosisState(owner="test", repo="repo", error=None)
        next_node = route_after_snapshot(state)
        assert next_node == "analyze_docs_node"

    def test_route_after_snapshot_error(self):
        """스냅샷 에러 시 에러 체크로."""
        state = DiagnosisState(owner="test", repo="repo", error="fetch failed")
        next_node = route_after_snapshot(state)
        assert next_node == "check_error_node"

    def test_route_after_activity_quick_mode(self):
        """Quick 모드에서 구조 분석 스킵."""
        state = DiagnosisState(
            owner="test", 
            repo="repo", 
            analysis_depth="quick",
            error=None,
        )
        next_node = route_after_activity(state)
        assert next_node == "compute_scores_node"

    def test_route_after_activity_standard_mode(self):
        """Standard 모드에서 구조 분석 진행."""
        state = DiagnosisState(
            owner="test", 
            repo="repo", 
            analysis_depth="standard",
            error=None,
        )
        next_node = route_after_activity(state)
        assert next_node == "analyze_structure_node"

    def test_route_after_error_check_max_retry(self):
        """최대 재시도 시 출력 생성으로."""
        state = DiagnosisState(
            owner="test",
            repo="repo",
            error="some error",
            retry_count=3,
            max_retry=2,
        )
        next_node = route_after_error_check(state)
        assert next_node == "build_output_node"


@pytest.mark.skip(reason="nodes.py deprecated - _generate_fallback_summary removed")
class TestFallbackSummary:
    """Fallback 요약 생성 테스트."""

    def test_generates_summary(self):
        """요약 생성 테스트."""
        state = DiagnosisState(
            owner="test",
            repo="myrepo",
            scoring_result={
                "health_score": 75,
                "health_level": "good",
                "onboarding_score": 70,
            },
        )
        
        summary = _generate_fallback_summary(state)
        
        assert "test/myrepo" in summary
        assert "75" in summary
        assert "70" in summary

    def test_handles_missing_data(self):
        """데이터 없어도 동작."""
        state = DiagnosisState(
            owner="test",
            repo="repo",
            scoring_result=None,
        )
        
        summary = _generate_fallback_summary(state)
        
        assert "test/repo" in summary
        assert "50" in summary  # 기본값


class TestDiagnosisInputOutput:
    """DiagnosisInput/Output 모델 테스트."""

    def test_input_with_custom_depth(self):
        """커스텀 깊이로 입력 생성."""
        input_data = DiagnosisInput(
            owner="facebook",
            repo="react",
            analysis_depth="deep",
        )
        
        assert input_data.analysis_depth == "deep"
        assert input_data.use_llm_summary == True

    def test_output_to_dict(self):
        """출력 dict 변환."""
        output = DiagnosisOutput(
            repo_id="test/repo",
            health_score=80.0,
            health_level="good",
            onboarding_score=75.0,
            onboarding_level="easy",
            docs={"documentation_quality": 85},
            activity={"activity_maintainability": 80},
            structure={"structure_score": 70},
            dependency_complexity_score=20,
            dependency_flags=["many_deps"],
            stars=1000,
            forks=100,
            summary_for_user="Good project!",
        )
        
        d = output.to_dict()
        
        assert d["repo_id"] == "test/repo"
        assert d["health_score"] == 80.0
        assert d["dependency_flags"] == ["many_deps"]
