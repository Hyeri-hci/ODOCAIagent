"""Supervisor V1 테스트: 기본 라우팅 및 응답 생성 검증."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

import pytest


class TestIntentConfig:
    """Intent 설정 테스트."""
    
    def test_v1_supported_intents(self):
        """V1 지원 Intent 검증."""
        from backend.agents.supervisor.intent_config import is_v1_supported
        
        # V1 지원
        assert is_v1_supported("analyze", "health")
        assert is_v1_supported("analyze", "onboarding")
        assert is_v1_supported("followup", "explain")
        assert is_v1_supported("general_qa", "chat")
        assert is_v1_supported("smalltalk", "greeting")
        
        # V1 미지원
        assert not is_v1_supported("analyze", "compare")
        assert not is_v1_supported("followup", "refine")
    
    def test_intent_meta(self):
        """Intent 메타데이터 검증."""
        from backend.agents.supervisor.intent_config import get_intent_meta
        
        # analyze/health: repo 필수, diagnosis 실행
        meta = get_intent_meta("analyze", "health")
        assert meta["requires_repo"] is True
        assert meta["runs_diagnosis"] is True
        
        # general_qa/chat: repo 불필요, diagnosis 불필요
        meta = get_intent_meta("general_qa", "chat")
        assert meta["requires_repo"] is False
        assert meta["runs_diagnosis"] is False
    
    def test_validate_intent(self):
        """Intent 유효성 검사."""
        from backend.agents.supervisor.intent_config import validate_intent, validate_sub_intent
        
        assert validate_intent("analyze") == "analyze"
        assert validate_intent("invalid") == "analyze"  # default
        assert validate_intent(None) == "analyze"
        
        assert validate_sub_intent("health") == "health"
        assert validate_sub_intent("invalid") == "health"  # default


class TestIntentClassifier:
    """Intent 분류 노드 테스트."""
    
    def test_greeting_classification(self):
        """인사 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify
        
        result = _fast_classify("안녕")
        assert result is not None
        assert result[0] == "smalltalk"
        assert result[1] == "greeting"
    
    def test_help_classification(self):
        """도움말 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify
        
        result = _fast_classify("뭘 할 수 있어?")
        assert result is not None
        assert result[0] == "help"
    
    def test_repo_extraction(self):
        """저장소 추출."""
        from backend.agents.supervisor.nodes.intent_classifier import _extract_repo
        
        # URL 형식
        repo = _extract_repo("https://github.com/facebook/react 분석해줘")
        assert repo is not None
        assert repo["owner"] == "facebook"
        assert repo["name"] == "react"
        
        # owner/repo 형식
        repo = _extract_repo("vuejs/vue 분석해줘")
        assert repo is not None
        assert repo["owner"] == "vuejs"
        assert repo["name"] == "vue"


class TestGraph:
    """Graph 라우팅 테스트."""
    
    def test_should_run_diagnosis(self):
        """진단 실행 조건 테스트."""
        from backend.agents.supervisor.graph import should_run_diagnosis
        
        # analyze + repo → diagnosis
        state = {
            "intent": "analyze",
            "sub_intent": "health",
            "repo": {"owner": "test", "name": "repo", "url": ""},
        }
        assert should_run_diagnosis(state) == "diagnosis"
        
        # general_qa → summarize
        state = {
            "intent": "general_qa",
            "sub_intent": "chat",
        }
        assert should_run_diagnosis(state) == "summarize"
        
        # error_message 있음 → summarize
        state = {
            "intent": "analyze",
            "sub_intent": "health",
            "error_message": "오류 발생",
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_graph_invocation_greeting(self):
        """Graph 실행: 인사."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("안녕!")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        assert result.get("intent") == "smalltalk"
        assert result.get("answer_kind") == "greeting"
        assert "안녕" in result.get("llm_summary", "").lower() or "ODOC" in result.get("llm_summary", "")
    
    def test_graph_invocation_general_qa(self):
        """Graph 실행: 일반 QA."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("Health Score가 뭐야?")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        assert result.get("intent") == "general_qa"
        assert result.get("answer_kind") == "chat"
        assert result.get("llm_summary")


class TestSummarizeNode:
    """Summarize 노드 테스트."""
    
    def test_extract_target_metrics(self):
        """지표 추출 테스트."""
        from backend.agents.supervisor.nodes.summarize_node import _extract_target_metrics
        
        metrics = _extract_target_metrics("health score가 뭐야?")
        assert "health_score" in metrics
        
        metrics = _extract_target_metrics("온보딩 점수 설명해줘")
        assert "onboarding_score" in metrics
    
    def test_generate_last_brief(self):
        """요약 생성 테스트."""
        from backend.agents.supervisor.nodes.summarize_node import _generate_last_brief
        
        summary = "# 분석 결과\n\n이 저장소는 건강합니다."
        brief = _generate_last_brief(summary, "facebook/react")
        
        assert len(brief) <= 200
        assert "저장소" in brief or "건강" in brief


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
