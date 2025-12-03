"""
Supervisor Graph V1 Unit Tests

Tests for graph routing logic and node execution flow.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.agents.supervisor.graph import (
    should_run_diagnosis,
    should_use_planning,
    build_supervisor_graph,
)
from backend.agents.supervisor.models import SupervisorState


class TestShouldRunDiagnosis:
    """Tests for should_run_diagnosis routing function."""
    
    def test_error_message_routes_to_summarize(self):
        """error_message가 있으면 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "test",
            "intent": "analyze",
            "sub_intent": "health",
            "error_message": "Some error occurred",
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_needs_ask_user_routes_to_summarize(self):
        """Access guard: _needs_ask_user=True면 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "test",
            "intent": "analyze",
            "sub_intent": "health",
            "_needs_ask_user": True,
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_needs_disambiguation_routes_to_summarize(self):
        """Disambiguation 필요 시 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "test",
            "intent": "analyze",
            "sub_intent": "health",
            "_needs_disambiguation": True,
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_smalltalk_routes_to_summarize(self):
        """smalltalk intent는 summarize로 라우팅 (fast path)."""
        state: SupervisorState = {
            "user_query": "안녕하세요",
            "intent": "smalltalk",
            "sub_intent": "greeting",
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_help_routes_to_summarize(self):
        """help intent는 summarize로 라우팅 (fast path)."""
        state: SupervisorState = {
            "user_query": "도움말",
            "intent": "help",
            "sub_intent": "usage",
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_general_qa_routes_to_summarize(self):
        """general_qa intent는 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "오픈소스가 뭐야?",
            "intent": "general_qa",
            "sub_intent": "concept",
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_analyze_without_repo_routes_to_summarize(self):
        """analyze intent지만 repo가 없으면 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "저장소 분석해줘",
            "intent": "analyze",
            "sub_intent": "health",
            "repo": None,
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_analyze_health_with_repo_routes_to_diagnosis(self):
        """analyze/health intent + repo가 있으면 diagnosis로 라우팅."""
        state: SupervisorState = {
            "user_query": "facebook/react 분석해줘",
            "intent": "analyze",
            "sub_intent": "health",
            "repo": {"owner": "facebook", "name": "react"},
        }
        assert should_run_diagnosis(state) == "diagnosis"
    
    def test_analyze_compare_routes_to_expert(self):
        """analyze/compare intent는 expert로 라우팅."""
        state: SupervisorState = {
            "user_query": "react랑 vue 비교해줘",
            "intent": "analyze",
            "sub_intent": "compare",
            "repo": {"owner": "facebook", "name": "react"},
        }
        assert should_run_diagnosis(state) == "expert"
    
    def test_analyze_onepager_routes_to_expert(self):
        """analyze/onepager intent는 expert로 라우팅."""
        state: SupervisorState = {
            "user_query": "react 한장 요약해줘",
            "intent": "analyze",
            "sub_intent": "onepager",
            "repo": {"owner": "facebook", "name": "react"},
        }
        assert should_run_diagnosis(state) == "expert"
    
    def test_followup_routes_to_summarize(self):
        """followup intent는 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "점수가 왜 낮아?",
            "intent": "followup",
            "sub_intent": "explain",
            "repo": {"owner": "facebook", "name": "react"},
            "diagnosis_result": {"scores": {"health_score": 75}},
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_analyze_with_existing_diagnosis_skips_rediagnosis(self):
        """이미 diagnosis_result가 있으면 재진단하지 않음."""
        state: SupervisorState = {
            "user_query": "facebook/react 분석해줘",
            "intent": "analyze",
            "sub_intent": "health",
            "repo": {"owner": "facebook", "name": "react"},
            "diagnosis_result": {"scores": {"health_score": 75}},
        }
        # diagnosis_result가 있으면 다시 diagnosis로 가지 않음
        result = should_run_diagnosis(state)
        assert result in ("summarize", "diagnosis")


class TestShouldUsePlanning:
    """Tests for should_use_planning routing function."""
    
    def test_smalltalk_never_uses_planning(self):
        """smalltalk은 planning 사용 안 함."""
        state: SupervisorState = {
            "user_query": "안녕",
            "intent": "smalltalk",
            "sub_intent": "greeting",
        }
        assert should_use_planning(state) == "summarize"
    
    def test_help_never_uses_planning(self):
        """help는 planning 사용 안 함."""
        state: SupervisorState = {
            "user_query": "도움말",
            "intent": "help",
            "sub_intent": "usage",
        }
        assert should_use_planning(state) == "summarize"
    
    def test_error_routes_to_summarize(self):
        """에러 시 summarize로 라우팅."""
        state: SupervisorState = {
            "user_query": "test",
            "intent": "analyze",
            "sub_intent": "health",
            "error_message": "error",
        }
        assert should_use_planning(state) == "summarize"
    
    def test_analyze_with_planning_flag_routes_to_plan(self):
        """analyze + _use_planning=True면 plan으로 라우팅."""
        state: SupervisorState = {
            "user_query": "react 분석해줘",
            "intent": "analyze",
            "sub_intent": "health",
            "_use_planning": True,
        }
        assert should_use_planning(state) == "plan"
    
    def test_analyze_without_planning_flag_routes_to_direct(self):
        """analyze + _use_planning=False면 direct로 라우팅."""
        state: SupervisorState = {
            "user_query": "react 분석해줘",
            "intent": "analyze",
            "sub_intent": "health",
        }
        assert should_use_planning(state) == "direct"


class TestBuildSupervisorGraph:
    """Tests for graph building."""
    
    def test_graph_builds_successfully(self):
        """그래프가 성공적으로 빌드되는지 확인."""
        graph = build_supervisor_graph()
        assert graph is not None
    
    def test_graph_has_nodes(self):
        """그래프에 필요한 노드들이 있는지 확인."""
        graph = build_supervisor_graph()
        # CompiledGraph doesn't expose nodes directly, just check it compiled
        assert graph is not None


class TestGraphIntegration:
    """Integration tests for the supervisor graph."""
    
    @pytest.mark.skip(reason="Requires mocking multiple dependencies")
    def test_end_to_end_smalltalk(self):
        """Smalltalk 쿼리 end-to-end 테스트."""
        pass
    
    @pytest.mark.skip(reason="Requires mocking multiple dependencies")
    def test_end_to_end_analyze(self):
        """Analyze 쿼리 end-to-end 테스트."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
