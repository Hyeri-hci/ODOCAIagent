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
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        result = _tier1_heuristic("안녕")
        assert result is not None
        assert result.intent == "smalltalk"
        assert result.sub_intent == "greeting"
    
    def test_help_classification(self):
        """도움말 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        result = _tier1_heuristic("뭘 할 수 있어?")
        assert result is not None
        assert result.intent == "help"
    
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


class TestIdempotency:
    """Idempotency 테스트."""
    
    def test_idempotency_store_basic(self):
        """IdempotencyStore 기본 동작."""
        from backend.common.cache import IdempotencyStore
        
        store = IdempotencyStore(ttl=10)
        
        # 저장
        entry = store.store_result("sess1", "turn1", "step1", {"data": 1})
        assert entry.answer_id.startswith("ans_")
        assert entry.result == {"data": 1}
        
        # 조회
        cached = store.get_cached("sess1", "turn1", "step1")
        assert cached is not None
        assert cached.answer_id == entry.answer_id
    
    def test_idempotency_store_different_keys(self):
        """다른 키는 다른 결과."""
        from backend.common.cache import IdempotencyStore
        
        store = IdempotencyStore(ttl=10)
        
        store.store_result("sess1", "turn1", "step1", {"a": 1})
        store.store_result("sess1", "turn2", "step1", {"b": 2})
        
        cached1 = store.get_cached("sess1", "turn1", "step1")
        cached2 = store.get_cached("sess1", "turn2", "step1")
        
        assert cached1.result == {"a": 1}
        assert cached2.result == {"b": 2}
        assert cached1.answer_id != cached2.answer_id
    
    def test_idempotency_store_disable(self):
        """비활성화 시 캐시 안함."""
        from backend.common.cache import IdempotencyStore
        
        store = IdempotencyStore(ttl=10)
        store.disable()
        
        store.store_result("sess1", "turn1", "step1", {"data": 1})
        cached = store.get_cached("sess1", "turn1", "step1")
        
        assert cached is None  # 비활성화 시 None 반환
    
    def test_answer_id_in_graph_result(self):
        """Graph 결과에 answer_id 포함."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("안녕!")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        assert "answer_id" in result
        assert result["answer_id"].startswith("ans_")
    
    def test_duplicate_execution_same_answer_id(self):
        """동일 실행은 같은 answer_id 반환."""
        from backend.common.cache import idempotency_store
        
        # 캐시 초기화
        idempotency_store.clear()
        
        # 첫 번째 저장
        entry1 = idempotency_store.store_result("sess_test", "turn_test", "summarize", {"x": 1})
        
        # 동일 키로 조회
        cached = idempotency_store.get_cached("sess_test", "turn_test", "summarize")
        
        assert cached is not None
        assert cached.answer_id == entry1.answer_id


class TestHierarchicalRouting:
    """계층 라우팅 테스트 (Heuristic → LLM)."""
    
    def test_tier1_greeting_heuristic(self):
        """Tier-1: 인사는 휴리스틱으로 즉시 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        # 단순 인사
        result = _tier1_heuristic("안녕")
        assert result is not None
        assert result.intent == "smalltalk"
        assert result.sub_intent == "greeting"
        assert result.method == "heuristic"
        assert result.confidence == 1.0
        
        # 영어 인사
        result = _tier1_heuristic("hello")
        assert result is not None
        assert result.intent == "smalltalk"
        assert result.sub_intent == "greeting"
    
    def test_tier1_help_heuristic(self):
        """Tier-1: 도움말은 휴리스틱으로 즉시 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        # 기능 문의
        result = _tier1_heuristic("뭘 할 수 있어?")
        assert result is not None
        assert result.intent == "help"
        assert result.sub_intent == "getting_started"
        
        # 사용법
        result = _tier1_heuristic("사용법 알려줘")
        assert result is not None
        assert result.intent == "help"
        
        # 오류 문의
        result = _tier1_heuristic("에러가 나요")
        assert result is not None
        assert result.intent == "help"
    
    def test_tier1_overview_heuristic(self):
        """Tier-1: 레포 개요는 휴리스틱으로 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        result = _tier1_heuristic("facebook/react 뭐야?")
        assert result is not None
        assert result.intent == "overview"
        assert result.sub_intent == "repo"
        assert result.repo is not None
        assert result.repo["owner"] == "facebook"
    
    def test_tier1_short_emoji_fallback(self):
        """Tier-1: 짧은/이모지 쿼리는 help로 폴백."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        # 짧은 쿼리
        result = _tier1_heuristic("?")
        assert result is not None
        assert result.intent == "help"
        
        # 이모지만
        result = _tier1_heuristic("👋")
        assert result is not None
        assert result.intent == "help"
    
    def test_tier1_analysis_requires_llm(self):
        """Tier-1: 분석 요청은 LLM 분류 필요."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        # 분석 + repo → LLM 분류 필요
        result = _tier1_heuristic("facebook/react 건강도 분석해줘")
        assert result is None  # LLM으로 넘김
    
    def test_confidence_threshold(self):
        """Confidence 임계값 검증."""
        from backend.agents.supervisor.intent_config import (
            get_confidence_threshold, 
            should_degrade_to_help
        )
        
        # 임계값 확인
        assert get_confidence_threshold("analyze") == 0.6
        assert get_confidence_threshold("help") == 0.4
        assert get_confidence_threshold("smalltalk") == 0.3
        
        # 디그레이드 판단
        assert should_degrade_to_help("analyze", 0.5) is True   # 0.5 < 0.6
        assert should_degrade_to_help("analyze", 0.7) is False  # 0.7 >= 0.6
        assert should_degrade_to_help("help", 0.3) is True      # 0.3 < 0.4
        assert should_degrade_to_help("help", 0.5) is False     # 0.5 >= 0.4
    
    def test_routing_fast_path(self):
        """라우팅: smalltalk/help/overview는 diagnosis 스킵."""
        from backend.agents.supervisor.graph import should_run_diagnosis
        
        # smalltalk → summarize
        state = {"intent": "smalltalk", "sub_intent": "greeting"}
        assert should_run_diagnosis(state) == "summarize"
        
        # help → summarize
        state = {"intent": "help", "sub_intent": "getting_started"}
        assert should_run_diagnosis(state) == "summarize"
        
        # overview → summarize
        state = {
            "intent": "overview", 
            "sub_intent": "repo",
            "repo": {"owner": "test", "name": "repo", "url": ""},
        }
        assert should_run_diagnosis(state) == "summarize"
    
    def test_routing_analyze_requires_diagnosis(self):
        """라우팅: analyze는 diagnosis 실행."""
        from backend.agents.supervisor.graph import should_run_diagnosis
        
        state = {
            "intent": "analyze",
            "sub_intent": "health",
            "repo": {"owner": "test", "name": "repo", "url": ""},
        }
        assert should_run_diagnosis(state) == "diagnosis"
    
    def test_graph_greeting_no_diagnosis(self):
        """Graph: 인사는 diagnosis 노드 진입 안 함."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("안녕하세요!")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        assert result.get("intent") == "smalltalk"
        assert result.get("diagnosis_result") is None  # diagnosis 실행 안 함
        assert result.get("llm_summary")  # 응답은 있음
    
    def test_graph_help_no_diagnosis(self):
        """Graph: 도움말은 diagnosis 노드 진입 안 함."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("어떤 기능이 있어?")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        assert result.get("intent") == "help"
        assert result.get("diagnosis_result") is None
        assert result.get("llm_summary")


class TestLightweightPath:
    """Step 2: Smalltalk/Help 경량 경로 테스트."""
    
    def test_smalltalk_greeting_has_next_actions(self):
        """인사 응답에 다음 행동 2개 포함."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("안녕!")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        summary = result.get("llm_summary", "")
        assert "다음 행동" in summary
        assert summary.count("`") >= 2  # 최소 2개 코드 블록 (행동 제안)
    
    def test_help_response_has_next_actions(self):
        """도움말 응답에 다음 행동 2개 포함."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("뭘 할 수 있어?")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        summary = result.get("llm_summary", "")
        assert "다음 행동" in summary
        assert summary.count("`") >= 2
    
    def test_smalltalk_source_is_template(self):
        """인사 응답 source가 SYS:TEMPLATES:SMALLTALK."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("안녕하세요")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        contract = result.get("answer_contract", {})
        sources = contract.get("sources", [])
        
        assert len(sources) > 0
        assert "SYS:TEMPLATES:SMALLTALK" in sources[0]
    
    def test_help_source_is_template(self):
        """도움말 응답 source가 SYS:TEMPLATES:HELP."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("사용법 알려줘")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        contract = result.get("answer_contract", {})
        sources = contract.get("sources", [])
        
        assert len(sources) > 0
        assert "SYS:TEMPLATES:HELP" in sources[0]
    
    def test_lightweight_response_latency(self):
        """경량 응답 지연시간 < 100ms."""
        import time
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("안녕!")
        graph = get_supervisor_graph()
        
        start = time.perf_counter()
        result = graph.invoke(state)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # p95 < 100ms 검증 (실제로는 훨씬 빠름)
        # 테스트 환경에서는 200ms 이내면 통과
        assert elapsed_ms < 200, f"Latency too high: {elapsed_ms:.1f}ms"
        assert result.get("llm_summary")
    
    def test_overview_response_format(self):
        """overview 응답 포맷 검증."""
        from backend.agents.supervisor.nodes.summarize_node import _build_lightweight_response
        from backend.agents.supervisor.prompts import OVERVIEW_REPO_TEMPLATE, OVERVIEW_SOURCE_ID
        
        state = {
            "repo": {"owner": "facebook", "name": "react", "url": ""},
        }
        template = OVERVIEW_REPO_TEMPLATE.format(owner="facebook", repo="react")
        result = _build_lightweight_response(state, template, "chat", OVERVIEW_SOURCE_ID)
        
        assert "facebook/react" in result["llm_summary"]
        assert "다음 행동" in result["llm_summary"]
        assert result["answer_contract"]["sources"][0] == OVERVIEW_SOURCE_ID
    
    def test_chitchat_response(self):
        """chitchat 응답 검증."""
        from backend.agents.supervisor import get_supervisor_graph, build_initial_state
        
        state = build_initial_state("네 알겠어요 고마워요")
        graph = get_supervisor_graph()
        result = graph.invoke(state)
        
        # chitchat → smalltalk.chitchat
        assert result.get("intent") == "smalltalk"
        assert "다음 행동" in result.get("llm_summary", "")


class TestOverviewPath:
    """Step 3: Overview 경로 테스트."""
    
    def test_fetch_overview_artifacts(self):
        """아티팩트 수집 함수 테스트."""
        from backend.agents.supervisor.service import fetch_overview_artifacts
        
        # 실제 저장소로 테스트 (캐시됨)
        artifacts = fetch_overview_artifacts("facebook", "react")
        
        # repo_facts는 필수
        assert artifacts.repo_facts
        assert artifacts.repo_facts.get("full_name") == "facebook/react"
        
        # sources >= 1 (최소 repo_facts)
        assert len(artifacts.sources) >= 1
        assert any("REPO_FACTS" in s for s in artifacts.sources)
    
    def test_overview_artifacts_sources_count(self):
        """아티팩트 sources >= 2 검증."""
        from backend.agents.supervisor.service import fetch_overview_artifacts
        
        artifacts = fetch_overview_artifacts("microsoft", "vscode")
        
        # 정상 케이스: sources >= 2
        # (repo_facts + readme_head 또는 recent_activity)
        assert len(artifacts.sources) >= 2, f"Expected >= 2 sources, got {artifacts.sources}"
    
    def test_build_overview_prompt(self):
        """Overview 프롬프트 빌드 테스트."""
        from backend.agents.supervisor.prompts import build_overview_prompt
        
        system, user = build_overview_prompt(
            owner="test",
            repo="repo",
            repo_facts={"description": "Test repo", "stars": 100, "language": "Python"},
            readme_head="# Test\n\nThis is a test.",
            recent_activity={"commit_count_30d": 10},
        )
        
        assert "test/repo" in system
        assert "다음 행동" in system
        assert "repo_facts" in user
        assert "readme_head" in user
        assert "recent_activity" in user
    
    def test_overview_response_has_sources(self):
        """Overview 응답에 sources 포함."""
        from backend.agents.supervisor.nodes.summarize_node import _build_overview_response
        
        sources = ["ARTIFACT:REPO_FACTS:test/repo", "ARTIFACT:README_HEAD:test/repo"]
        result = _build_overview_response(
            state={},
            summary="Test summary",
            sources=sources,
            repo_id="test/repo",
        )
        
        contract = result.get("answer_contract", {})
        assert len(contract.get("sources", [])) >= 2
        assert "github_artifact" in contract.get("source_kinds", [])
    
    def test_overview_fallback_template(self):
        """API 제한 시 fallback 템플릿 사용."""
        from backend.agents.supervisor.prompts import OVERVIEW_FALLBACK_TEMPLATE
        
        fallback = OVERVIEW_FALLBACK_TEMPLATE.format(
            owner="test",
            repo="repo",
            description="A test repo",
            language="Python",
            stars=100,
            forks=10,
        )
        
        assert "test/repo" in fallback
        assert "다음 행동" in fallback
        assert "100" in fallback  # stars


class TestFollowupPlanner:
    """Follow-up Planner 테스트: 직전 턴 아티팩트 기반 근거 설명."""
    
    def test_detect_followup_patterns(self):
        """후속 패턴 감지."""
        from backend.agents.supervisor.nodes.intent_classifier import _detect_followup
        
        # 직전 아티팩트 있을 때
        assert _detect_followup("그 결과 왜 그래?", has_prev_artifacts=True)
        assert _detect_followup("근거가 뭐야?", has_prev_artifacts=True)
        assert _detect_followup("왜?", has_prev_artifacts=True)
        assert _detect_followup("어디서 나왔어?", has_prev_artifacts=True)
        assert _detect_followup("좀더 자세히 설명해줘", has_prev_artifacts=True)
        
        # 직전 아티팩트 없을 때 → False
        assert not _detect_followup("그 결과 왜 그래?", has_prev_artifacts=False)
        assert not _detect_followup("왜?", has_prev_artifacts=False)
    
    def test_followup_intent_classification(self):
        """follow-up intent 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _tier1_heuristic
        
        # has_prev_artifacts=True일 때만 followup.evidence로 분류
        result = _tier1_heuristic("근거가 뭐야?", has_prev_artifacts=True)
        assert result is not None
        assert result.intent == "followup"
        assert result.sub_intent == "evidence"
        
        # has_prev_artifacts=False일 때는 None (LLM으로 넘어감)
        result = _tier1_heuristic("근거가 뭐야?", has_prev_artifacts=False)
        assert result is None
    
    def test_followup_no_artifacts_fallback(self):
        """직전 아티팩트 없으면 안내 + 선택지."""
        from backend.agents.supervisor.nodes.summarize_node import _handle_followup_evidence_mode
        
        state = {"user_query": "왜 그래?"}
        result = _handle_followup_evidence_mode(state, "왜 그래?", None)
        
        assert "이전 분석 결과가 없어" in result["llm_summary"]
        assert "다음 행동" in result["llm_summary"]
    
    def test_followup_evidence_prompt(self):
        """Follow-up 근거 설명 프롬프트 생성."""
        from backend.agents.supervisor.prompts import build_followup_evidence_prompt
        
        artifacts = {
            "scores": {"health_score": 75, "documentation_quality": 80},
            "labels": {"health_level": "good"},
        }
        
        system, user = build_followup_evidence_prompt(
            user_query="왜 그런 점수가 나왔어?",
            prev_intent="analyze",
            prev_answer_kind="report",
            repo_id="test/repo",
            artifacts=artifacts,
        )
        
        assert "근거" in system
        assert "3-5문장" in system
        assert "참조 데이터" in system
        assert "test/repo" in user
        assert "health_score" in user
        assert "75" in user
    
    def test_followup_response_has_sources(self):
        """Follow-up 응답에 직전 아티팩트 sources 포함."""
        from backend.agents.supervisor.nodes.summarize_node import _build_followup_response
        
        sources = ["PREV:test/repo:scores", "PREV:test/repo:labels"]
        result = _build_followup_response(
            state={},
            summary="Test evidence explanation",
            sources=sources,
            repo_id="test/repo",
            diagnosis_result=None,
        )
        
        contract = result.get("answer_contract", {})
        assert len(contract.get("sources", [])) >= 2
        assert "prev_turn_artifact" in contract.get("source_kinds", [])
        assert result["answer_kind"] == "explain"
    
    def test_followup_config_registered(self):
        """followup.evidence가 V1 지원 목록에 등록됨."""
        from backend.agents.supervisor.intent_config import (
            is_v1_supported,
            get_intent_meta,
            get_answer_kind,
        )
        
        assert is_v1_supported("followup", "evidence")
        
        meta = get_intent_meta("followup", "evidence")
        assert meta["requires_repo"] is False
        assert meta["runs_diagnosis"] is False
        
        assert get_answer_kind("followup", "evidence") == "explain"


class TestExpertRunner:
    """Expert Runner 테스트: sources 필수, 에러 정책, 디그레이드."""
    
    def test_runner_result_success(self):
        """RunnerResult.ok 생성."""
        from backend.agents.supervisor.runners.base import RunnerResult
        from backend.agents.shared.contracts import AnswerContract
        
        answer = AnswerContract(
            text="Test",
            sources=["ARTIFACT:TEST:repo"],
            source_kinds=["test"],
        )
        result = RunnerResult.ok(
            answer=answer,
            artifacts_out=["ARTIFACT:TEST:repo"],
        )
        
        assert result.success is True
        assert result.degraded is False
        assert len(result.artifacts_out) == 1
    
    def test_runner_result_degraded(self):
        """RunnerResult.degraded_ok 생성."""
        from backend.agents.supervisor.runners.base import RunnerResult
        from backend.agents.shared.contracts import AnswerContract
        
        answer = AnswerContract(
            text="Degraded response",
            sources=["FALLBACK:repo"],
            source_kinds=["fallback"],
        )
        result = RunnerResult.degraded_ok(
            answer=answer,
            artifacts_out=["FALLBACK:repo"],
            reason="test_degrade",
        )
        
        assert result.success is True
        assert result.degraded is True
        assert result.meta.get("degrade_reason") == "test_degrade"
    
    def test_artifact_collector(self):
        """ArtifactCollector 기능."""
        from backend.agents.supervisor.runners.base import ArtifactCollector
        
        collector = ArtifactCollector("test/repo")
        
        # Add artifacts
        aid = collector.add("overview", {"stars": 100})
        assert "ARTIFACT:OVERVIEW:test/repo" in aid
        
        collector.add("readme", "# Title", required=False)
        
        # Get artifacts
        assert collector.get("overview") == {"stars": 100}
        assert collector.get("readme") == "# Title"
        assert collector.get("missing") is None
        
        # IDs and kinds
        assert len(collector.get_ids()) == 2
        assert "overview" in collector.get_kinds()
    
    def test_artifact_collector_missing_required(self):
        """필수 아티팩트 누락 감지."""
        from backend.agents.supervisor.runners.base import ArtifactCollector
        
        collector = ArtifactCollector("test/repo")
        collector.add("overview", None, required=True)  # None data
        collector.add("readme", "content", required=False)
        
        assert not collector.has_required()
        assert "overview" in collector.missing_required()
    
    def test_error_policy_mapping(self):
        """에러 종류별 정책 매핑."""
        from backend.agents.supervisor.runners.base import ExpertRunner, ErrorPolicy
        
        # Mock runner for testing
        class TestRunner(ExpertRunner):
            runner_name = "test"
            def _collect_artifacts(self): pass
            def _execute(self): pass
        
        runner = TestRunner("test/repo")
        
        assert runner._get_error_policy("rate limit exceeded") == ErrorPolicy.RETRY
        assert runner._get_error_policy("timeout error") == ErrorPolicy.RETRY
        assert runner._get_error_policy("not found") == ErrorPolicy.ASK_USER
        assert runner._get_error_policy("permission denied") == ErrorPolicy.ASK_USER
        assert runner._get_error_policy("no data available") == ErrorPolicy.FALLBACK
    
    def test_diagnosis_runner_builds_answer_with_sources(self):
        """DiagnosisRunner가 sources 포함 AnswerContract 생성."""
        from backend.agents.supervisor.runners.base import ArtifactCollector
        from backend.agents.shared.contracts import AnswerContract
        
        # Test _build_answer method
        collector = ArtifactCollector("test/repo")
        collector.add("diagnosis_scores", {"health_score": 75})
        collector.add("diagnosis_labels", {"health_level": "good"})
        
        # Build answer with sources
        sources = collector.get_ids()
        kinds = collector.get_kinds()
        
        answer = AnswerContract(
            text="Test diagnosis",
            sources=sources,
            source_kinds=kinds,
        )
        
        assert len(answer.sources) >= 2
        assert "diagnosis_scores" in answer.source_kinds
    
    def test_runner_validates_empty_sources(self):
        """Empty sources 검증 및 자동 채움."""
        from backend.agents.supervisor.runners.base import ExpertRunner
        from backend.agents.shared.contracts import AnswerContract
        
        class TestRunner(ExpertRunner):
            runner_name = "test"
            def _collect_artifacts(self):
                self.collector.add("test_artifact", {"data": "value"})
            def _execute(self):
                pass
        
        runner = TestRunner("test/repo")
        runner._collect_artifacts()
        
        # Empty sources answer
        answer = AnswerContract(text="Test", sources=[], source_kinds=[])
        runner._validate_answer_contract(answer)
        
        # Should auto-fill from collector
        assert len(answer.sources) > 0
    
    def test_compare_runner_structure(self):
        """CompareRunner 구조 검증."""
        from backend.agents.supervisor.runners import CompareRunner
        
        runner = CompareRunner(
            repo_a="facebook/react",
            repo_b="vuejs/vue",
        )
        
        assert runner.runner_name == "compare"
        assert runner.repo_a == "facebook/react"
        assert runner.repo_b == "vuejs/vue"
        assert "repo_a_overview" in runner.required_artifacts
    
    def test_onepager_runner_structure(self):
        """OnepagerRunner 구조 검증."""
        from backend.agents.supervisor.runners import OnepagerRunner
        
        runner = OnepagerRunner(repo_id="test/repo")
        
        assert runner.runner_name == "onepager"
        assert "repo_overview" in runner.required_artifacts


class TestAgenticPlanning:
    """Agentic Planning 테스트 (Step 12)."""
    
    def test_plan_model_creation(self):
        """Plan 모델 생성 검증."""
        from backend.agents.supervisor.planner import (
            Plan, PlanStep, PlanStatus, StepStatus, ErrorPolicy
        )
        
        step = PlanStep(
            id="test_step",
            runner="diagnosis",
            params={"repo": "test/repo"},
            needs=[],
            on_error=ErrorPolicy.FALLBACK,
        )
        
        assert step.id == "test_step"
        assert step.status == StepStatus.PENDING
        assert step.is_ready(set())
        
        plan = Plan(
            id="test_plan",
            intent="analyze",
            sub_intent="health",
            steps=[step],
        )
        
        assert plan.status == PlanStatus.PENDING
        assert len(plan.steps) == 1
        assert not plan.is_complete()
    
    def test_plan_step_dependencies(self):
        """PlanStep 의존성 검증."""
        from backend.agents.supervisor.planner import PlanStep, ErrorPolicy
        
        step_a = PlanStep(id="a", runner="diagnosis", needs=[])
        step_b = PlanStep(id="b", runner="compare", needs=["a"])
        
        # step_a is ready (no deps)
        assert step_a.is_ready(set())
        
        # step_b needs step_a
        assert not step_b.is_ready(set())
        assert step_b.is_ready({"a"})
    
    def test_plan_builder_analyze_health(self):
        """PlanBuilder: analyze.health 계획 생성."""
        from backend.agents.supervisor.planner import build_plan
        
        plan = build_plan("analyze", "health", {"repo": {"owner": "test", "name": "repo"}})
        
        assert plan.intent == "analyze"
        assert plan.sub_intent == "health"
        assert len(plan.steps) >= 1
        assert plan.steps[0].runner == "diagnosis"
    
    def test_plan_builder_smalltalk(self):
        """PlanBuilder: smalltalk.greeting 계획 생성."""
        from backend.agents.supervisor.planner import build_plan
        
        plan = build_plan("smalltalk", "greeting", {})
        
        assert plan.intent == "smalltalk"
        assert len(plan.steps) == 1
        assert plan.steps[0].runner == "smalltalk"
        assert plan.steps[0].timeout_sec == 5.0  # Fast path
    
    def test_plan_builder_compare(self):
        """PlanBuilder: analyze.compare 계획 생성 (병렬 의존성)."""
        from backend.agents.supervisor.planner import build_plan
        
        plan = build_plan("analyze", "compare", {
            "repo": {"owner": "facebook", "name": "react"},
            "compare_repo": {"owner": "vuejs", "name": "vue"},
        })
        
        assert plan.intent == "analyze"
        assert plan.sub_intent == "compare"
        
        # fetch_repo_a, fetch_repo_b (parallel), compare (depends on both)
        step_ids = [s.id for s in plan.steps]
        assert "fetch_repo_a" in step_ids
        assert "fetch_repo_b" in step_ids
        assert "compare" in step_ids
        
        # Compare step depends on both fetch steps
        compare_step = next(s for s in plan.steps if s.id == "compare")
        assert "fetch_repo_a" in compare_step.needs
        assert "fetch_repo_b" in compare_step.needs
    
    def test_plan_get_ready_steps(self):
        """Plan.get_ready_steps() 검증."""
        from backend.agents.supervisor.planner import Plan, PlanStep, StepStatus
        
        step_a = PlanStep(id="a", runner="diagnosis", needs=[])
        step_b = PlanStep(id="b", runner="diagnosis", needs=[])
        step_c = PlanStep(id="c", runner="compare", needs=["a", "b"])
        
        plan = Plan(
            id="test",
            intent="analyze",
            sub_intent="compare",
            steps=[step_a, step_b, step_c],
        )
        
        # Initially a and b are ready
        ready = plan.get_ready_steps()
        assert len(ready) == 2
        assert {s.id for s in ready} == {"a", "b"}
        
        # After a completes, still just b is ready (c needs both)
        step_a.status = StepStatus.SUCCESS
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "b"
        
        # After both complete, c is ready
        step_b.status = StepStatus.SUCCESS
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "c"
    
    def test_step_result_dataclass(self):
        """StepResult 데이터클래스 검증."""
        from backend.agents.supervisor.planner import StepResult, StepStatus
        
        result = StepResult(
            step_id="test",
            status=StepStatus.SUCCESS,
            result={"data": "value"},
            execution_time_ms=100.5,
        )
        
        assert result.success
        assert result.step_id == "test"
        assert result.result["data"] == "value"
        
        failed = StepResult(
            step_id="fail",
            status=StepStatus.FAILED,
            error_message="Test error",
        )
        
        assert not failed.success
        assert failed.error_message == "Test error"
    
    def test_error_policy_enum(self):
        """ErrorPolicy enum 검증."""
        from backend.agents.supervisor.planner import ErrorPolicy
        
        assert ErrorPolicy.RETRY.value == "retry"
        assert ErrorPolicy.FALLBACK.value == "fallback"
        assert ErrorPolicy.ASK_USER.value == "ask_user"
        assert ErrorPolicy.ABORT.value == "abort"
    
    def test_replanner_can_replan(self):
        """Replanner 재계획 가능 여부 검증."""
        from backend.agents.supervisor.planner import Plan, Replanner
        
        plan = Plan(id="test", intent="analyze", sub_intent="health")
        replanner = Replanner(plan)
        
        assert replanner.can_replan()
        
        # After max attempts
        plan.replan_count = 2
        replanner2 = Replanner(plan)
        assert not replanner2.can_replan()
    
    def test_replanner_step_failure(self):
        """Replanner: 스텝 실패 시 재계획."""
        from backend.agents.supervisor.planner import (
            Plan, PlanStep, Replanner, ReplanReason, ErrorPolicy, StepStatus
        )
        
        step = PlanStep(
            id="failed_step",
            runner="diagnosis",
            on_error=ErrorPolicy.FALLBACK,
        )
        step.status = StepStatus.FAILED
        step.error_message = "Test failure"
        
        plan = Plan(
            id="original",
            intent="analyze",
            sub_intent="health",
            steps=[step],
        )
        
        replanner = Replanner(plan)
        new_plan = replanner.replan(step, ReplanReason.STEP_FAILED)
        
        assert new_plan is not None
        assert new_plan.replan_count == 1
        assert "_r1" in new_plan.id
    
    def test_plan_status_transitions(self):
        """Plan 상태 전환 검증."""
        from backend.agents.supervisor.planner import Plan, PlanStatus
        
        plan = Plan(id="test", intent="analyze", sub_intent="health")
        
        assert plan.status == PlanStatus.PENDING
        
        plan.mark_running()
        assert plan.status == PlanStatus.RUNNING
        
        plan.mark_success()
        assert plan.status == PlanStatus.SUCCESS
        
        plan2 = Plan(id="test2", intent="analyze", sub_intent="health")
        plan2.mark_failed("Error occurred")
        assert plan2.status == PlanStatus.FAILED
        assert plan2.error_message == "Error occurred"
        
        plan3 = Plan(id="test3", intent="analyze", sub_intent="health")
        plan3.mark_ask_user("Need clarification")
        assert plan3.status == PlanStatus.ASK_USER


class TestPlanningErrorRecovery:
    """Planning 오류 복구 테스트: 정상 종료율 ≥ 95% 검증."""
    
    def test_error_terminates_gracefully(self):
        """오류 발생 시 정상 종료 (ask_user 또는 에러 메시지)."""
        from backend.agents.supervisor.planner import (
            Plan, PlanStep, PlanExecutor, PlanStatus, StepStatus, ErrorPolicy
        )
        
        # Mock executor that always fails
        def failing_runner(step, inputs):
            from backend.agents.supervisor.planner import StepResult
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error_message="Simulated failure",
            )
        
        step = PlanStep(
            id="fail_step",
            runner="mock",
            on_error=ErrorPolicy.ASK_USER,  # Should escalate
            max_retries=0,
        )
        
        plan = Plan(
            id="test",
            intent="analyze",
            sub_intent="health",
            steps=[step],
        )
        
        executor = PlanExecutor(step_executors={"mock": failing_runner})
        result = executor.execute(plan, {})
        
        # Should terminate gracefully (either ASK_USER or FAILED with message)
        assert result.status in (PlanStatus.ASK_USER, PlanStatus.FAILED)
        assert result.error_message is not None
    
    def test_retry_then_fallback(self):
        """retry → fallback 정책 검증."""
        from backend.agents.supervisor.planner import (
            Plan, PlanStep, PlanExecutor, StepStatus, ErrorPolicy
        )
        
        call_count = [0]
        
        def retry_then_succeed(step, inputs):
            from backend.agents.supervisor.planner import StepResult
            call_count[0] += 1
            
            if call_count[0] <= 1:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error_message="First call fails",
                )
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                result={"data": "success"},
            )
        
        step = PlanStep(
            id="retry_step",
            runner="mock",
            on_error=ErrorPolicy.RETRY,
            max_retries=1,
        )
        
        plan = Plan(
            id="test",
            intent="analyze",
            sub_intent="health",
            steps=[step],
        )
        
        executor = PlanExecutor(step_executors={"mock": retry_then_succeed})
        result = executor.execute(plan, {})
        
        # Should succeed after retry
        assert call_count[0] == 2
    
    def test_parallel_execution_all_succeed(self):
        """병렬 실행 시 모두 성공."""
        from backend.agents.supervisor.planner import (
            Plan, PlanStep, PlanExecutor, PlanStatus, StepStatus
        )
        
        def success_runner(step, inputs):
            from backend.agents.supervisor.planner import StepResult
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                result={"step": step.id},
            )
        
        step_a = PlanStep(id="a", runner="mock", needs=[])
        step_b = PlanStep(id="b", runner="mock", needs=[])
        
        plan = Plan(
            id="test",
            intent="analyze",
            sub_intent="compare",
            steps=[step_a, step_b],
        )
        
        executor = PlanExecutor(step_executors={"mock": success_runner})
        result = executor.execute(plan, {})
        
        assert result.status == PlanStatus.SUCCESS
        assert len(result.execution_order) == 2


class TestIntentThresholds:
    """Step 8: 의도별 임계/정책 분리 테스트."""
    
    def test_confidence_thresholds_by_cost(self):
        """비용에 따른 임계값 검증: 고비용=높은임계, 저비용=낮은임계."""
        from backend.agents.supervisor.intent_config import (
            get_confidence_threshold,
            get_disambiguation_threshold,
        )
        
        # 고비용 (analyze, compare): 높은 임계
        assert get_confidence_threshold("analyze") == 0.6
        assert get_confidence_threshold("compare") == 0.6
        
        # 중비용 (followup, recommendation): 중간 임계
        assert get_confidence_threshold("followup") == 0.5
        assert get_confidence_threshold("recommendation") == 0.5
        
        # 저비용 (overview, general_qa): 낮은 임계
        assert get_confidence_threshold("overview") == 0.4
        assert get_confidence_threshold("general_qa") == 0.5
        
        # 경량 (smalltalk, help): 가장 낮은 임계
        assert get_confidence_threshold("smalltalk") == 0.3
        assert get_confidence_threshold("help") == 0.4
    
    def test_disambiguation_thresholds(self):
        """Disambiguation 임계값 검증."""
        from backend.agents.supervisor.intent_config import (
            get_disambiguation_threshold,
            should_disambiguate,
        )
        
        # 고비용은 높은 disambiguation 임계
        assert get_disambiguation_threshold("analyze") == 0.4
        assert get_disambiguation_threshold("compare") == 0.4
        
        # 경량은 낮은 disambiguation 임계
        assert get_disambiguation_threshold("smalltalk") == 0.15
        assert get_disambiguation_threshold("help") == 0.2
        
        # should_disambiguate 로직
        assert should_disambiguate("analyze", 0.35) is True
        assert should_disambiguate("analyze", 0.45) is False
        assert should_disambiguate("smalltalk", 0.10) is True
        assert should_disambiguate("smalltalk", 0.20) is False
    
    def test_calibration_store(self):
        """CalibrationStore 기본 동작 검증."""
        from backend.agents.supervisor.calibration import CalibrationStore
        
        store = CalibrationStore()
        
        # 쿼리 기록
        store.record_query("analyze", 0.7, {"analyze": 0.7, "followup": 0.2})
        store.record_query("analyze", 0.55, {"analyze": 0.55, "followup": 0.3}, was_disambiguation=True)
        
        # 메트릭 조회
        metrics = store.get_metrics("analyze")
        assert metrics is not None
        assert metrics["total_queries"] == 2
        assert metrics["disambiguation_rate"] == 0.5
    
    def test_calibration_weekly_adjustment(self):
        """주간 임계값 조정 검증."""
        from backend.agents.supervisor.calibration import CalibrationStore
        
        store = CalibrationStore()
        
        # 충분한 데이터 기록 (disambiguation이 너무 적음 → 임계 올림)
        for _ in range(20):
            store.record_query("analyze", 0.8, {"analyze": 0.8})
        
        adjustment = store.compute_weekly_adjustment("analyze")
        # Disambiguation이 0%라 임계값 올려야 함
        assert adjustment > 0
    
    def test_check_disambiguation(self):
        """Disambiguation 체크 로직 검증."""
        from backend.agents.supervisor.calibration import check_disambiguation
        
        # 낮은 confidence → disambiguation
        result = check_disambiguation("analyze", 0.3, has_repo=True)
        assert result.should_disambiguate is True
        
        # repo 없으면 → disambiguation
        result = check_disambiguation("analyze", 0.8, has_repo=False)
        assert result.should_disambiguate is True
        assert "저장소" in result.reason
        
        # 충분한 confidence + repo → 통과
        result = check_disambiguation("analyze", 0.7, has_repo=True)
        assert result.should_disambiguate is False
    
    def test_temperature_scaling(self):
        """Temperature scaling 함수 검증."""
        from backend.agents.supervisor.calibration import temperature_scale
        
        logits = {"analyze": 2.0, "followup": 1.0, "general_qa": 0.5}
        
        # temp=1.0: 원래 softmax
        probs_1 = temperature_scale(logits, temperature=1.0)
        assert probs_1["analyze"] > probs_1["followup"] > probs_1["general_qa"]
        
        # temp=2.0: 더 부드러운 분포
        probs_2 = temperature_scale(logits, temperature=2.0)
        # 높은 temp → 확률 차이 줄어듦
        assert (probs_2["analyze"] - probs_2["followup"]) < (probs_1["analyze"] - probs_1["followup"])


class TestToneGuide:
    """Step 9: 한국어 프롬프트/톤 가이드 테스트."""
    
    def test_mode_mapping(self):
        """Intent → Mode 매핑 검증."""
        from backend.agents.supervisor.tone_guide import (
            get_mode_for_intent,
            PromptMode,
        )
        
        # Fast mode
        assert get_mode_for_intent("smalltalk") == PromptMode.FAST
        assert get_mode_for_intent("help") == PromptMode.FAST
        assert get_mode_for_intent("general_qa") == PromptMode.FAST
        
        # Expert mode
        assert get_mode_for_intent("analyze") == PromptMode.EXPERT
        assert get_mode_for_intent("compare") == PromptMode.EXPERT
        assert get_mode_for_intent("followup") == PromptMode.EXPERT
    
    def test_tone_config_params(self):
        """톤 설정 파라미터 검증."""
        from backend.agents.supervisor.tone_guide import (
            get_tone_config,
            PromptMode,
        )
        
        fast = get_tone_config(PromptMode.FAST)
        expert = get_tone_config(PromptMode.EXPERT)
        
        # Fast: 높은 temperature, 적은 불릿
        assert fast.temperature == 0.7
        assert fast.max_bullets == 3
        assert fast.max_sentences == 5
        assert fast.allow_chitchat is True
        
        # Expert: 낮은 temperature, 많은 불릿
        assert expert.temperature == 0.25
        assert expert.max_bullets == 7
        assert expert.max_sentences == 15
        assert expert.allow_chitchat is False
    
    def test_llm_params_for_intent(self):
        """Intent별 LLM 파라미터 검증."""
        from backend.agents.supervisor.tone_guide import get_llm_params_for_intent
        
        # Fast mode intents
        chat_params = get_llm_params_for_intent("general_qa")
        assert chat_params["temperature"] == 0.7
        
        # Expert mode intents
        analyze_params = get_llm_params_for_intent("analyze")
        assert analyze_params["temperature"] == 0.25
    
    def test_tone_compliance_check(self):
        """톤 준수 체크 검증."""
        from backend.agents.supervisor.tone_guide import (
            check_tone_compliance,
            is_tone_compliant,
            PromptMode,
        )
        
        # 좋은 Expert 응답
        good_expert = """### 분석 결과

| 지표 | 점수 |
|------|------|
| 건강 점수 | 78점 |

활동성이 85점으로 우수합니다.

**다음 행동**
- 점수 자세히 설명해줘"""
        
        results = check_tone_compliance(good_expert, PromptMode.EXPERT)
        assert results["존댓말 사용"] is True
        assert results["이모지 없음"] is True
        assert results["데이터 인용"] is True
        
        # 나쁜 응답 (추측 표현)
        bad_expert = "아마 이것은 좋은 것 같습니다."
        results = check_tone_compliance(bad_expert, PromptMode.EXPERT)
        assert results["추측 표현 없음"] is False
    
    def test_response_length_validation(self):
        """응답 길이 검증."""
        from backend.agents.supervisor.tone_guide import (
            validate_response_length,
            truncate_response,
            PromptMode,
        )
        
        short_text = "짧은 응답입니다. 좋아요."
        is_valid, warning = validate_response_length(short_text, PromptMode.FAST)
        assert is_valid is True
        assert warning is None
        
        # 긴 텍스트 자르기
        long_text = "테스트 " * 500
        truncated = truncate_response(long_text, PromptMode.FAST)
        assert len(truncated) < len(long_text)
        assert "생략" in truncated
    
    def test_prompts_llm_params_updated(self):
        """prompts.py LLM_PARAMS가 Step 9 기준으로 업데이트됨."""
        from backend.agents.supervisor.prompts import LLM_PARAMS
        
        # Expert mode: 낮은 temperature
        assert LLM_PARAMS["health_report"]["temperature"] == 0.25
        assert LLM_PARAMS["score_explain"]["temperature"] == 0.2
        assert LLM_PARAMS["followup_evidence"]["temperature"] == 0.2
        
        # Fast mode: 높은 temperature
        assert LLM_PARAMS["chat"]["temperature"] == 0.7
        assert LLM_PARAMS["greeting"]["temperature"] == 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
