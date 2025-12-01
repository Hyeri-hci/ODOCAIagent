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


class TestRunnerOutputNormalization:
    """러너 출력 정규화 테스트."""
    
    def test_safe_get_none(self):
        """safe_get: None 처리."""
        from backend.agents.shared.contracts import safe_get
        
        assert safe_get(None, "key") is None
        assert safe_get(None, "key", "default") == "default"
    
    def test_safe_get_non_dict(self):
        """safe_get: dict가 아닌 값 처리."""
        from backend.agents.shared.contracts import safe_get
        
        assert safe_get("string", "key") is None
        assert safe_get(123, "key", "default") == "default"
        assert safe_get([], "key", "default") == "default"
    
    def test_safe_get_dict(self):
        """safe_get: 정상 dict 처리."""
        from backend.agents.shared.contracts import safe_get
        
        d = {"a": 1, "b": {"c": 2}}
        assert safe_get(d, "a") == 1
        assert safe_get(d, "b") == {"c": 2}
        assert safe_get(d, "missing") is None
        assert safe_get(d, "missing", "default") == "default"
    
    def test_safe_get_nested(self):
        """safe_get_nested: 중첩 접근."""
        from backend.agents.shared.contracts import safe_get_nested
        
        d = {"a": {"b": {"c": 3}}}
        assert safe_get_nested(d, "a", "b", "c") == 3
        assert safe_get_nested(d, "a", "b", "missing") is None
        assert safe_get_nested(d, "a", "b", "missing", default=0) == 0
        assert safe_get_nested(None, "a", "b") is None
    
    def test_normalize_none(self):
        """normalize_runner_output: None → 빈 성공."""
        from backend.agents.shared.contracts import normalize_runner_output, RunnerStatus
        
        output = normalize_runner_output(None)
        assert output.status == RunnerStatus.SUCCESS
        assert output.result == {}
    
    def test_normalize_dict(self):
        """normalize_runner_output: dict → RunnerOutput."""
        from backend.agents.shared.contracts import normalize_runner_output, RunnerStatus
        
        # 일반 dict
        output = normalize_runner_output({"scores": {"health": 80}})
        assert output.status == RunnerStatus.SUCCESS
        assert output.result == {"scores": {"health": 80}}
        
        # 에러 표시 dict
        output = normalize_runner_output({"error_message": "실패"})
        assert output.status == RunnerStatus.ERROR
        assert output.error_message == "실패"
    
    def test_normalize_runner_output_passthrough(self):
        """normalize_runner_output: RunnerOutput은 그대로 반환."""
        from backend.agents.shared.contracts import normalize_runner_output, RunnerOutput, RunnerStatus
        
        original = RunnerOutput.success(result={"test": 1})
        output = normalize_runner_output(original)
        assert output is original
    
    def test_normalize_exception(self):
        """normalize_runner_output: Exception → 에러."""
        from backend.agents.shared.contracts import normalize_runner_output, RunnerStatus
        
        output = normalize_runner_output(ValueError("테스트 에러"))
        assert output.status == RunnerStatus.ERROR
        assert "테스트 에러" in output.error_message
    
    def test_validate_runner_output(self):
        """validate_runner_output: 계약 검증."""
        from backend.agents.shared.contracts import (
            validate_runner_output, RunnerOutput, RunnerStatus, ContractViolation
        )
        
        # 유효한 출력
        valid = RunnerOutput.success(result={"data": 1})
        assert validate_runner_output(valid) is True
        
        # ERROR 상태인데 error_message 없음 (strict=False)
        invalid = RunnerOutput(status=RunnerStatus.ERROR, result={})
        assert validate_runner_output(invalid, strict=False) is False
        
        # ERROR 상태인데 error_message 없음 (strict=True)
        with pytest.raises(ContractViolation):
            validate_runner_output(invalid, strict=True)


class TestDegradeResponse:
    """디그레이드 응답 테스트."""
    
    def test_build_response_no_artifact_has_source(self):
        """아티팩트 없을 때도 sources != []."""
        from backend.agents.supervisor.nodes.summarize_node import (
            _build_response, DEGRADE_SOURCE_ID
        )
        
        state = {"intent": "analyze", "sub_intent": "health"}
        result = _build_response(state, "테스트 응답", "report", degraded=True)
        
        contract = result.get("answer_contract", {})
        assert contract.get("sources") != [], "sources는 빈 리스트가 아니어야 함"
        assert DEGRADE_SOURCE_ID in contract.get("sources", [])
    
    def test_build_response_normal_path_has_diagnosis_source(self):
        """정상 경로에서는 diagnosis source 포함."""
        from backend.agents.supervisor.nodes.summarize_node import _build_response
        
        state = {"repo": {"owner": "test", "name": "repo"}}
        diagnosis_result = {"scores": {"health_score": 80}}
        
        result = _build_response(state, "테스트 응답", "report", diagnosis_result)
        
        contract = result.get("answer_contract", {})
        assert contract.get("sources") != []
        assert "diagnosis_test_repo" in contract.get("sources", [])
    
    def test_llm_call_result_degraded_flag(self):
        """LLMCallResult의 degraded 플래그."""
        from backend.agents.supervisor.nodes.summarize_node import LLMCallResult
        
        # 정상
        normal = LLMCallResult("content", success=True)
        assert normal.degraded is False
        
        # 디그레이드
        degraded = LLMCallResult("fallback", success=False, degraded=True)
        assert degraded.degraded is True
    
    def test_greeting_response_has_source(self):
        """인사 응답도 source 포함."""
        from backend.agents.supervisor.nodes.summarize_node import _build_response
        
        state = {"intent": "smalltalk", "sub_intent": "greeting"}
        result = _build_response(state, "안녕하세요!", "greeting")
        
        contract = result.get("answer_contract", {})
        # 인사는 system_template source
        assert contract.get("sources") != []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
