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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
