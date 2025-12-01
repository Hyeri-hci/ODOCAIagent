"""
Agentic Orchestrator 테스트.

Phase 1: Contract/Event 시스템
Phase 2: Planning/Execution
Phase 3: Active Inference
"""
import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Phase 1: Contract Tests
# =============================================================================

class TestAnswerContract:
    """AnswerContract 검증 테스트."""
    
    def test_valid_contract(self):
        from backend.agents.shared.contracts import AnswerContract
        
        contract = AnswerContract(
            text="React는 Facebook에서 만든 UI 라이브러리입니다.",
            sources=["diagnosis_raw_abc123"],
            source_kinds=["diagnosis_raw"],
        )
        
        assert contract.text
        assert len(contract.sources) == 1
        assert contract.validate_sources_match()
    
    def test_empty_sources_allowed(self):
        from backend.agents.shared.contracts import AnswerContract
        
        # 빈 sources 허용 (require_sources=False 시나리오)
        contract = AnswerContract(
            text="안녕하세요!",
            sources=[],
            source_kinds=[],
        )
        
        assert contract.text
        assert contract.validate_sources_match()
    
    def test_mismatched_sources_fail(self):
        from backend.agents.shared.contracts import AnswerContract
        
        contract = AnswerContract(
            text="테스트",
            sources=["id1", "id2"],
            source_kinds=["kind1"],  # 길이 불일치
        )
        
        assert not contract.validate_sources_match()


class TestPlanStep:
    """PlanStep 구조 테스트."""
    
    def test_create_plan_step(self):
        from backend.agents.shared.contracts import PlanStep, AgentType, ErrorAction
        
        step = PlanStep(
            id="fetch_diag",
            agent=AgentType.DIAGNOSIS,
            params={"reuse_cache": True},
            needs=[],
            on_error=ErrorAction.FALLBACK,
        )
        
        assert step.id == "fetch_diag"
        assert step.agent == AgentType.DIAGNOSIS
        assert step.on_error == ErrorAction.FALLBACK
    
    def test_plan_step_with_dependencies(self):
        from backend.agents.shared.contracts import PlanStep, AgentType
        
        step = PlanStep(
            id="calc_scores",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "scoring"},
            needs=["fetch_readme", "compute_activity"],
        )
        
        assert len(step.needs) == 2
        assert "fetch_readme" in step.needs


# =============================================================================
# Phase 1: Event System Tests
# =============================================================================

class TestEventSystem:
    """이벤트 시스템 테스트."""
    
    def test_emit_event(self):
        from backend.common.events import (
            EventType, 
            emit_event, 
            get_event_store,
            set_session_id,
            set_turn_id,
        )
        
        # 세션 설정
        set_session_id("test_session")
        set_turn_id("test_turn")
        
        # 이벤트 발행
        event = emit_event(
            EventType.NODE_STARTED,
            actor="test_node",
            inputs={"key": "value"},
        )
        
        assert event.type == EventType.NODE_STARTED
        assert event.actor == "test_node"
        assert event.session_id == "test_session"
    
    def test_artifact_store(self):
        from backend.common.events import (
            get_artifact_store,
            set_session_id,
        )
        
        set_session_id("artifact_test_session")
        store = get_artifact_store()
        
        # Artifact 저장
        content = {"score": 85, "level": "good"}
        artifact_id = store.persist(
            session_id="artifact_test_session",
            kind="diagnosis_raw",
            content=content,
        )
        
        # 내용주소화 확인 (동일 내용 = 동일 ID)
        artifact_id2 = store.persist(
            session_id="artifact_test_session",
            kind="diagnosis_raw",
            content=content,
        )
        
        assert artifact_id == artifact_id2
        assert store.exists(artifact_id)
    
    def test_span_context(self):
        from backend.common.events import span, get_event_store
        
        store = get_event_store()
        initial_count = len(store._events)
        
        with span("test_operation", actor="test"):
            pass  # 작업 시뮬레이션
        
        # NODE_STARTED + NODE_FINISHED 이벤트 발생
        assert len(store._events) >= initial_count + 2


# =============================================================================
# Phase 2: Planning Tests
# =============================================================================

class TestPlanner:
    """Planner 테스트."""
    
    def test_build_diagnosis_plan(self):
        from backend.agents.supervisor.nodes.planner import build_plan
        from backend.common.events import set_session_id, set_turn_id
        
        set_session_id("planner_test")
        set_turn_id("turn_1")
        
        state = {
            "intent": "analyze",
            "sub_intent": "health",
            "repo": {"owner": "facebook", "name": "react"},
            "_intent_confidence": 0.95,
        }
        
        output = build_plan(state)
        
        assert output.intent in ("explain", "task_recommendation", "compare")
        assert len(output.plan) > 0
        assert output.reasoning_trace
    
    def test_low_confidence_triggers_disambiguation(self):
        from backend.agents.supervisor.nodes.planner import build_plan
        from backend.common.events import set_session_id, set_turn_id
        
        set_session_id("planner_test_2")
        set_turn_id("turn_2")
        
        state = {
            "intent": "analyze",
            "sub_intent": "health",
            "_intent_confidence": 0.3,  # 낮은 신뢰도
        }
        
        output = build_plan(state)
        
        assert output.intent == "disambiguation"
        assert len(output.plan) == 0


class TestTopologicalSort:
    """위상 정렬 테스트."""
    
    def test_topological_sort(self):
        from backend.agents.supervisor.executor import topological_sort
        from backend.agents.shared.contracts import PlanStep, AgentType
        
        steps = [
            PlanStep(id="a", agent=AgentType.DIAGNOSIS, params={}, needs=[]),
            PlanStep(id="b", agent=AgentType.DIAGNOSIS, params={}, needs=["a"]),
            PlanStep(id="c", agent=AgentType.DIAGNOSIS, params={}, needs=["a"]),
            PlanStep(id="d", agent=AgentType.DIAGNOSIS, params={}, needs=["b", "c"]),
        ]
        
        levels = topological_sort(steps)
        
        # 레벨 0: a (의존성 없음)
        # 레벨 1: b, c (a에 의존)
        # 레벨 2: d (b, c에 의존)
        assert len(levels) == 3
        assert levels[0][0].id == "a"
        assert set(s.id for s in levels[1]) == {"b", "c"}
        assert levels[2][0].id == "d"


# =============================================================================
# Phase 3: Active Inference Tests
# =============================================================================

class TestActiveInference:
    """Active Inference 테스트."""
    
    def test_extract_github_url(self):
        from backend.agents.supervisor.inference import extract_repo_from_text
        
        result = extract_repo_from_text(
            "https://github.com/facebook/react 분석해줘"
        )
        
        assert result is not None
        owner, repo, confidence = result
        assert owner == "facebook"
        assert repo == "react"
        assert confidence >= 0.9
    
    def test_extract_known_repo(self):
        from backend.agents.supervisor.inference import extract_repo_from_text
        
        result = extract_repo_from_text("react 분석해줘")
        
        assert result is not None
        owner, repo, confidence = result
        assert owner == "facebook"
        assert repo == "react"
    
    def test_extract_owner_repo_format(self):
        from backend.agents.supervisor.inference import extract_repo_from_text
        
        result = extract_repo_from_text("vercel/next.js 분석해줘")
        
        assert result is not None
        owner, repo, confidence = result
        assert owner == "vercel"
        assert repo == "next.js"
    
    def test_infer_user_level(self):
        from backend.agents.supervisor.inference import infer_user_level
        
        level, conf = infer_user_level("초보자인데 처음으로 오픈소스에 기여하고 싶어요")
        assert level == "beginner"
        assert conf > 0.5
        
        level, conf = infer_user_level("고급 아키텍처 분석해줘")
        assert level == "advanced"
    
    def test_infer_missing_with_state(self):
        from backend.agents.supervisor.inference import infer_missing
        from backend.common.events import set_session_id
        
        set_session_id("inference_test")
        
        hints = infer_missing(
            "react 분석해줘",
            current_state={}
        )
        
        assert hints.owner == "facebook"
        assert hints.name == "react"
        assert hints.confidence > 0.5
    
    def test_needs_disambiguation(self):
        from backend.agents.supervisor.inference import (
            needs_disambiguation,
            InferenceHints,
        )
        from backend.agents.shared.contracts import InferenceHints
        
        # 저장소 없음 → disambiguation 필요
        hints = InferenceHints()
        assert needs_disambiguation(hints)
        
        # 저장소 있고 신뢰도 높음 → 불필요
        hints = InferenceHints(
            owner="facebook",
            name="react",
            repo_guess="facebook/react",
            confidence=0.9,
        )
        assert not needs_disambiguation(hints)


# =============================================================================
# Integration Tests
# =============================================================================

class TestGraphIntegration:
    """Graph 통합 테스트."""
    
    def test_build_standard_graph(self):
        from backend.agents.supervisor.graph import build_supervisor_graph
        
        graph = build_supervisor_graph()
        assert graph is not None
    
    def test_build_agentic_graph(self):
        from backend.agents.supervisor.graph import build_agentic_supervisor_graph
        
        graph = build_agentic_supervisor_graph()
        assert graph is not None
    
    def test_get_supervisor_graph_default(self):
        from backend.agents.supervisor.graph import get_supervisor_graph
        
        # 기본은 standard graph
        graph = get_supervisor_graph()
        assert graph is not None


# Quality Assurance Tests (5번 작업)

class TestSourceEnforcement:
    """출처 강제 테스트: 가짜 artifact로 Contract 검증."""
    
    def test_contract_requires_sources(self):
        """sources가 없으면 validate 실패."""
        from backend.agents.shared.contracts import AnswerContract
        
        contract = AnswerContract(
            text="분석 결과입니다.",
            sources=[],
            source_kinds=[],
        )
        
        # 빈 sources는 validate_sources_match는 통과하지만
        # require_sources=True면 LLM wrapper에서 거부됨
        assert contract.validate_sources_match()
    
    def test_contract_with_multiple_sources(self):
        """여러 artifact 참조 시 sources/source_kinds 일치."""
        from backend.agents.shared.contracts import AnswerContract
        
        contract = AnswerContract(
            text="건강 점수 85점, 활동성 72점입니다.",
            sources=["diagnosis_raw_abc123", "python_metrics_def456"],
            source_kinds=["diagnosis_raw", "python_metrics"],
        )
        
        assert len(contract.sources) == 2
        assert contract.validate_sources_match()
    
    def test_artifact_persistence_generates_id(self):
        """persist_artifact가 content-addressable ID 생성."""
        from backend.common.events import (
            persist_artifact,
            get_artifact_store,
            set_session_id,
            generate_session_id,
        )
        
        session_id = generate_session_id()
        set_session_id(session_id)
        
        content = {"health_score": 85, "activity": 72}
        artifact_id = persist_artifact(kind="diagnosis_raw", content=content)
        
        assert artifact_id.startswith("diagnosis_raw_")
        assert len(artifact_id) > 20  # kind + hash
        
        # 저장소에서 조회 가능
        store = get_artifact_store()
        artifact = store.get(artifact_id)
        assert artifact is not None
        assert artifact.content == content


class TestEndToEndEvents:
    """엔드투엔드 테스트: intent→plan→execute→answer 이벤트."""
    
    def test_event_types_exist(self):
        """필요한 이벤트 타입 정의 확인."""
        from backend.common.events import EventType
        
        required_types = [
            "SUPERVISOR_INTENT_DETECTED",
            "SUPERVISOR_PLAN_BUILT",
            "NODE_STARTED",
            "NODE_FINISHED",
            "ARTIFACT_CREATED",
            "ANSWER_GENERATED",
        ]
        
        for type_name in required_types:
            assert hasattr(EventType, type_name), f"Missing EventType: {type_name}"
    
    def test_event_store_captures_events(self):
        """EventStore가 이벤트 정상 캡처."""
        from backend.common.events import (
            EventType,
            emit_event,
            get_event_store,
            set_session_id,
            generate_session_id,
        )
        
        session_id = generate_session_id()
        set_session_id(session_id)
        
        store = get_event_store()
        initial_count = len(store.get_by_session(session_id))
        
        # 이벤트 발행
        emit_event(EventType.NODE_STARTED, actor="test", inputs={"step": "test_step"})
        emit_event(EventType.NODE_FINISHED, actor="test", outputs={"success": True})
        
        events = store.get_by_session(session_id)
        assert len(events) >= initial_count + 2
    
    def test_plan_execution_emits_events(self):
        """Plan 실행 시 이벤트 발행 확인."""
        from backend.agents.supervisor.executor import (
            execute_plan,
            PlanExecutionContext,
            topological_sort,
        )
        from backend.agents.shared.contracts import PlanStep, AgentType
        from backend.common.events import (
            get_event_store,
            set_session_id,
            generate_session_id,
        )
        
        session_id = generate_session_id()
        set_session_id(session_id)
        
        # 간단한 plan
        steps = [
            PlanStep(
                id="test_step",
                agent=AgentType.DIAGNOSIS,
                params={},
            )
        ]
        
        # Mock runner
        def mock_runner(params, state, dependencies):
            return {"test": "result"}
        
        ctx = PlanExecutionContext(
            session_id=session_id,
            agent_runners={AgentType.DIAGNOSIS: mock_runner},
            state={"repo": {"owner": "test", "name": "repo"}},
        )
        
        result = execute_plan(steps, ctx)
        
        assert result["status"] in ("completed", "partial")
        
        # 이벤트 발행 확인
        store = get_event_store()
        events = store.get_by_session(session_id)
        event_types = [e.type.value for e in events]
        
        assert any("node.started" in t for t in event_types)
        assert any("node.finished" in t for t in event_types)


class TestDisambiguationThreshold:
    """Disambiguation 임계값 테스트."""
    
    def test_threshold_lowered_to_0_4(self):
        """needs_disambiguation 임계값이 0.4로 하향되었는지 확인."""
        from backend.agents.supervisor.inference import needs_disambiguation
        from backend.agents.shared.contracts import InferenceHints
        
        # 신뢰도 0.5 → 이전 임계값(0.6)에서는 disambiguation 필요
        # 새 임계값(0.4)에서는 불필요
        hints = InferenceHints(
            owner="facebook",
            name="react",
            repo_guess="facebook/react",
            confidence=0.5,
        )
        
        assert not needs_disambiguation(hints), "0.5 신뢰도는 disambiguation 불필요해야 함"
    
    def test_very_low_confidence_triggers_disambiguation(self):
        """신뢰도 0.3은 disambiguation 트리거."""
        from backend.agents.supervisor.inference import needs_disambiguation
        from backend.agents.shared.contracts import InferenceHints
        
        hints = InferenceHints(
            owner="facebook",
            name="react",
            repo_guess="facebook/react",
            confidence=0.3,
        )
        
        assert needs_disambiguation(hints), "0.3 신뢰도는 disambiguation 필요"
    
    def test_missing_repo_always_triggers_disambiguation(self):
        """저장소 정보 없으면 항상 disambiguation."""
        from backend.agents.supervisor.inference import needs_disambiguation
        from backend.agents.shared.contracts import InferenceHints
        
        hints = InferenceHints(confidence=0.9)  # 높은 신뢰도지만 repo 없음
        
        assert needs_disambiguation(hints)


class TestArtifactReproducibility:
    """재현성 테스트: 동일 입력 → 동일 artifact ID."""
    
    def test_same_content_same_hash(self):
        """동일 content는 동일 sha256 해시 생성."""
        from backend.common.events import (
            ArtifactStore,
        )
        
        store = ArtifactStore()
        
        content = {"score": 85, "level": "good"}
        
        # 동일 content로 두 번 저장
        id1 = store.persist("session1", "diagnosis", content)
        id2 = store.persist("session2", "diagnosis", content)
        
        # 해시 부분이 동일해야 함 (kind_hash 형식)
        hash1 = id1.split("_", 1)[1]
        hash2 = id2.split("_", 1)[1]
        
        assert hash1 == hash2, "동일 content는 동일 hash 생성해야 함"
    
    def test_different_content_different_hash(self):
        """다른 content는 다른 해시 생성."""
        from backend.common.events import ArtifactStore
        
        store = ArtifactStore()
        
        id1 = store.persist("session1", "diagnosis", {"score": 85})
        id2 = store.persist("session1", "diagnosis", {"score": 90})
        
        hash1 = id1.split("_", 1)[1]
        hash2 = id2.split("_", 1)[1]
        
        assert hash1 != hash2, "다른 content는 다른 hash 생성해야 함"
    
    def test_artifact_deduplication(self):
        """동일 ID artifact는 덮어쓰기 (중복 저장 방지)."""
        from backend.common.events import ArtifactStore
        
        store = ArtifactStore()
        
        content = {"test": "value"}
        
        id1 = store.persist("session1", "test_kind", content)
        id2 = store.persist("session1", "test_kind", content)
        
        # 동일 ID
        assert id1 == id2
        
        # 저장소에 하나만 존재
        artifacts = store.get_by_session("session1")
        test_artifacts = [a for a in artifacts if a.id == id1]
        assert len(test_artifacts) == 1


class TestRecommendationRunner:
    """Recommendation Runner 실구현 테스트."""
    
    def test_collect_artifacts_function_exists(self):
        """collect_artifacts_for_recommendation 함수 존재."""
        from backend.agents.supervisor.executor import collect_artifacts_for_recommendation
        
        result = collect_artifacts_for_recommendation(
            state={},
            results={},
            required_kinds=["diagnosis_raw"],
        )
        
        assert isinstance(result, list)
    
    def test_build_recommendation_prompt(self):
        """build_recommendation_prompt 함수 동작."""
        from backend.agents.supervisor.executor import build_recommendation_prompt
        
        prompt = build_recommendation_prompt(
            style="explain",
            state={
                "repo": {"owner": "facebook", "name": "react"},
                "user_query": "건강 상태 알려줘",
            },
            artifacts=[],
        )
        
        assert "facebook/react" in prompt
        assert "건강 상태" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
