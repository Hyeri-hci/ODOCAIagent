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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
