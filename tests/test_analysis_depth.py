"""동적 분석 깊이 및 스트리밍 진행 상황 테스트."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.routing_nodes import (
    determine_analysis_depth,
    intent_analysis_node,
    ANALYSIS_DEPTH_THRESHOLDS,
    DEPTH_KEYWORDS,
)
from backend.agents.diagnosis.models import DiagnosisInput


class TestDetermineAnalysisDepth:
    """분석 깊이 결정 테스트."""

    def test_default_is_standard(self):
        """기본값은 standard."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
        )
        depth = determine_analysis_depth(state)
        assert depth == "standard"

    def test_explicit_user_context_deep(self):
        """사용자가 명시적으로 deep을 요청한 경우."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            user_context={"analysis_depth": "deep"}
        )
        depth = determine_analysis_depth(state)
        assert depth == "deep"

    def test_explicit_user_context_quick(self):
        """사용자가 명시적으로 quick을 요청한 경우."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            user_context={"analysis_depth": "quick"}
        )
        depth = determine_analysis_depth(state)
        assert depth == "quick"

    def test_quick_scan_flag(self):
        """quick_scan 플래그가 설정된 경우."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            user_context={"quick_scan": True}
        )
        depth = determine_analysis_depth(state)
        assert depth == "quick"

    def test_keyword_deep_in_message(self):
        """메시지에 '자세히' 키워드가 있는 경우."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            chat_message="이 프로젝트를 자세히 분석해주세요"
        )
        depth = determine_analysis_depth(state)
        assert depth == "deep"

    def test_keyword_quick_in_message(self):
        """메시지에 '빠르게' 키워드가 있는 경우."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            chat_message="빠르게 스캔만 해주세요"
        )
        depth = determine_analysis_depth(state)
        assert depth == "quick"

    def test_existing_diagnosis_with_explain_intent(self):
        """이미 진단 결과가 있고 explain 의도인 경우 quick."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="explain",
            diagnosis_result={"health_score": 80}
        )
        depth = determine_analysis_depth(state)
        assert depth == "quick"

    def test_compare_with_many_repos(self):
        """비교 분석에서 3개 이상 저장소인 경우 quick."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="compare",
            compare_repos=["a/b", "c/d", "e/f"]
        )
        depth = determine_analysis_depth(state)
        assert depth == "quick"


class TestIntentAnalysisNodeWithDepth:
    """의도 분석 노드에서 분석 깊이 설정 테스트."""

    def test_sets_analysis_depth(self):
        """intent_analysis_node가 analysis_depth를 설정하는지 확인."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            user_context={"analysis_depth": "deep"}
        )
        result = intent_analysis_node(state)
        
        assert "analysis_depth" in result
        assert result["analysis_depth"] == "deep"

    def test_preserves_existing_depth(self):
        """이미 설정된 분석 깊이는 변경하지 않음."""
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            analysis_depth="deep",  # 이미 deep으로 설정됨
        )
        result = intent_analysis_node(state)
        
        # 이미 standard가 아닌 값이 설정되어 있으면 변경하지 않음
        # (현재 구현에서는 "standard"인 경우에만 재계산)
        assert "analysis_depth" not in result or result.get("analysis_depth") == "deep"


class TestDiagnosisInputModel:
    """DiagnosisInput 모델 테스트."""

    def test_default_analysis_depth(self):
        """기본 분석 깊이는 standard."""
        input_data = DiagnosisInput(owner="test", repo="repo")
        assert input_data.analysis_depth == "standard"

    def test_custom_analysis_depth(self):
        """커스텀 분석 깊이 설정."""
        input_data = DiagnosisInput(
            owner="test", 
            repo="repo", 
            analysis_depth="quick"
        )
        assert input_data.analysis_depth == "quick"

    def test_invalid_analysis_depth_raises_error(self):
        """잘못된 분석 깊이는 에러 발생."""
        with pytest.raises(Exception):
            DiagnosisInput(
                owner="test", 
                repo="repo", 
                analysis_depth="invalid"  # type: ignore
            )


class TestDepthConfigConstants:
    """분석 깊이 설정 상수 테스트."""

    def test_all_depths_defined(self):
        """모든 분석 깊이가 정의되어 있는지 확인."""
        assert "deep" in ANALYSIS_DEPTH_THRESHOLDS
        assert "standard" in ANALYSIS_DEPTH_THRESHOLDS
        assert "quick" in ANALYSIS_DEPTH_THRESHOLDS

    def test_depth_keywords_exist(self):
        """분석 깊이 키워드가 정의되어 있는지 확인."""
        assert "deep" in DEPTH_KEYWORDS
        assert "quick" in DEPTH_KEYWORDS
        
        # deep 키워드 확인
        assert "자세히" in DEPTH_KEYWORDS["deep"]
        assert "detailed" in DEPTH_KEYWORDS["deep"]
        
        # quick 키워드 확인
        assert "빠르게" in DEPTH_KEYWORDS["quick"]
        assert "quick" in DEPTH_KEYWORDS["quick"]
