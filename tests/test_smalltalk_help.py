"""Smalltalk/Help 경량 경로 테스트."""
from __future__ import annotations

import pytest
import time
from typing import Dict, Any


class TestFastClassifySmallTalk:
    """경량 분류 함수 테스트."""
    
    def test_greeting_simple(self):
        """간단한 인사 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        result = _fast_classify_smalltalk("안녕")
        assert result == ("smalltalk", "greeting")
    
    def test_greeting_variations(self):
        """인사 변형 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        greetings = ["하이", "hi", "hello", "안뇽", "헬로", "반가워"]
        for g in greetings:
            result = _fast_classify_smalltalk(g)
            assert result == ("smalltalk", "greeting"), f"Failed for: {g}"
    
    def test_chitchat_simple(self):
        """잡담 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        result = _fast_classify_smalltalk("고마워")
        assert result == ("smalltalk", "chitchat")
    
    def test_chitchat_variations(self):
        """잡담 변형 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        chitchats = ["감사합니다", "좋아", "굿", "오케이", "알겠어"]
        for c in chitchats:
            result = _fast_classify_smalltalk(c)
            assert result == ("smalltalk", "chitchat"), f"Failed for: {c}"
    
    def test_help_simple(self):
        """도움말 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        result = _fast_classify_smalltalk("뭘 할 수 있어?")
        assert result == ("help", "getting_started")
    
    def test_help_variations(self):
        """도움말 변형 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        helps = ["도와줘", "help", "무엇을 할 수 있어?", "뭐 해줄 수 있어?"]
        for h in helps:
            result = _fast_classify_smalltalk(h)
            assert result == ("help", "getting_started"), f"Failed for: {h}"
    
    def test_overview_pattern(self):
        """개요 패턴 분류."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        overviews = [
            "facebook/react가 뭐야?",
            "vercel/next.js가 뭐야",
            "tensorflow/tensorflow 알려줘",
        ]
        for o in overviews:
            result = _fast_classify_smalltalk(o)
            assert result == ("overview", "repo"), f"Failed for: {o}"
    
    def test_not_smalltalk_repo_query(self):
        """저장소 분석 쿼리는 Expert 경로."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        result = _fast_classify_smalltalk("facebook/react 분석해줘")
        assert result is None  # Expert Tool 경로
    
    def test_not_smalltalk_long_query(self):
        """긴 쿼리는 일반 분류 필요."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        result = _fast_classify_smalltalk(
            "안녕 react라는 프로젝트에 기여하고 싶은데 어떤 이슈부터 시작하면 좋을까?"
        )
        assert result is None  # Expert Tool 경로


class TestSmalltalkRunner:
    """Smalltalk runner 테스트."""
    
    def test_greeting_response(self):
        """인사 응답 형식 확인."""
        from backend.agents.supervisor.executor import create_default_agent_runners
        from backend.agents.shared.contracts import AgentType
        
        runners = create_default_agent_runners()
        runner = runners[AgentType.SMALLTALK]
        
        result = runner({"style": "greeting"}, {}, {})
        
        assert "answer_contract" in result
        assert result["answer_contract"]["text"]
        assert result["answer_contract"]["sources"] == ["SYS:TEMPLATES:SMALLTALK"]
        assert result["answer_contract"]["source_kinds"] == ["system_template"]
    
    def test_chitchat_response(self):
        """잡담 응답 형식 확인."""
        from backend.agents.supervisor.executor import create_default_agent_runners
        from backend.agents.shared.contracts import AgentType
        
        runners = create_default_agent_runners()
        runner = runners[AgentType.SMALLTALK]
        
        result = runner({"style": "chitchat"}, {}, {})
        
        assert "answer_contract" in result
        assert result["answer_contract"]["text"]
        assert "SYS:TEMPLATES:SMALLTALK" in result["answer_contract"]["sources"]
    
    def test_greeting_contains_next_actions(self):
        """인사 응답에 다음 행동 예시 포함 확인."""
        from backend.agents.supervisor.executor import create_default_agent_runners
        from backend.agents.shared.contracts import AgentType
        
        runners = create_default_agent_runners()
        runner = runners[AgentType.SMALLTALK]
        
        result = runner({"style": "greeting"}, {}, {})
        text = result["answer_contract"]["text"]
        
        # 다음 행동 예시 키워드 확인
        assert any(kw in text for kw in ["개요", "진단", "비교"])


class TestHelpRunner:
    """Help runner 테스트."""
    
    def test_help_response_format(self):
        """도움말 응답 형식 확인."""
        from backend.agents.supervisor.executor import create_default_agent_runners
        from backend.agents.shared.contracts import AgentType
        
        runners = create_default_agent_runners()
        runner = runners[AgentType.HELP]
        
        result = runner({}, {}, {})
        
        assert "answer_contract" in result
        assert result["answer_contract"]["text"]
        assert result["answer_contract"]["sources"] == ["SYS:TEMPLATES:HELP"]
        assert result["answer_contract"]["source_kinds"] == ["system_template"]
    
    def test_help_contains_capabilities(self):
        """도움말에 기능 목록 포함 확인."""
        from backend.agents.supervisor.executor import create_default_agent_runners
        from backend.agents.shared.contracts import AgentType
        
        runners = create_default_agent_runners()
        runner = runners[AgentType.HELP]
        
        result = runner({}, {}, {})
        text = result["answer_contract"]["text"]
        
        # 주요 기능 키워드 확인
        assert "개요" in text or "레포" in text
        assert "진단" in text
        assert "비교" in text


class TestIntentConfig:
    """Intent 설정 테스트."""
    
    def test_smalltalk_meta_no_diagnosis(self):
        """smalltalk은 진단 실행 안 함."""
        from backend.agents.supervisor.intent_config import get_intent_meta
        
        meta = get_intent_meta("smalltalk", "greeting")
        assert meta["runs_diagnosis"] is False
        assert meta["requires_repo"] is False
        
        meta = get_intent_meta("smalltalk", "chitchat")
        assert meta["runs_diagnosis"] is False
    
    def test_help_meta_no_diagnosis(self):
        """help는 진단 실행 안 함."""
        from backend.agents.supervisor.intent_config import get_intent_meta
        
        meta = get_intent_meta("help", "getting_started")
        assert meta["runs_diagnosis"] is False
        assert meta["requires_repo"] is False
    
    def test_overview_meta_no_diagnosis(self):
        """overview는 진단 없이 facts+readme만."""
        from backend.agents.supervisor.intent_config import get_intent_meta
        
        meta = get_intent_meta("overview", "repo")
        assert meta["runs_diagnosis"] is False
        assert meta["requires_repo"] is True  # repo 필요하지만 진단은 안 함
    
    def test_answer_kind_mapping(self):
        """AnswerKind 매핑 확인."""
        from backend.agents.supervisor.intent_config import get_answer_kind
        
        assert get_answer_kind("smalltalk", "greeting") == "greeting"
        assert get_answer_kind("smalltalk", "chitchat") == "greeting"
        assert get_answer_kind("help", "getting_started") == "help"
        assert get_answer_kind("overview", "repo") == "overview"


class TestPlannerSmallTalk:
    """Planner smalltalk/help Plan 생성 테스트."""
    
    def test_smalltalk_plan_lightweight(self):
        """Smalltalk Plan은 1 스텝."""
        from backend.agents.supervisor.nodes.planner import build_plan
        
        state = {
            "intent": "smalltalk",
            "sub_intent": "greeting",
            "user_query": "안녕",
        }
        
        output = build_plan(state)
        
        assert len(output.plan) == 1
        assert output.plan[0].agent.value == "smalltalk"
        assert output.artifacts_required == []  # 외부 데이터 불필요
    
    def test_help_plan_lightweight(self):
        """Help Plan은 1 스텝."""
        from backend.agents.supervisor.nodes.planner import build_plan
        
        state = {
            "intent": "help",
            "sub_intent": "getting_started",
            "user_query": "뭘 할 수 있어?",
        }
        
        output = build_plan(state)
        
        assert len(output.plan) == 1
        assert output.plan[0].agent.value == "help"
        assert output.artifacts_required == []
    
    def test_overview_plan_lightweight(self):
        """Overview Plan은 1 스텝, 진단 없음."""
        from backend.agents.supervisor.nodes.planner import build_plan
        
        state = {
            "intent": "overview",
            "sub_intent": "repo",
            "user_query": "facebook/react가 뭐야?",
            "repo": {"owner": "facebook", "name": "react"},
        }
        
        output = build_plan(state)
        
        assert len(output.plan) == 1
        assert output.plan[0].agent.value == "overview"


class TestPerformance:
    """성능 테스트 (p95 < 100ms 목표)."""
    
    def test_fast_classify_performance(self):
        """경량 분류 성능 테스트."""
        from backend.agents.supervisor.nodes.intent_classifier import _fast_classify_smalltalk
        
        queries = ["안녕", "하이", "고마워", "도와줘", "뭘 할 수 있어?"]
        times = []
        
        for q in queries:
            start = time.perf_counter()
            _fast_classify_smalltalk(q)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 10, f"경량 분류 p95 = {p95:.2f}ms (목표: <10ms)"
    
    def test_runner_performance(self):
        """Runner 성능 테스트."""
        from backend.agents.supervisor.executor import create_default_agent_runners
        from backend.agents.shared.contracts import AgentType
        
        runners = create_default_agent_runners()
        smalltalk_runner = runners[AgentType.SMALLTALK]
        help_runner = runners[AgentType.HELP]
        
        times = []
        for _ in range(10):
            start = time.perf_counter()
            smalltalk_runner({"style": "greeting"}, {}, {})
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            
            start = time.perf_counter()
            help_runner({}, {}, {})
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 50, f"Runner p95 = {p95:.2f}ms (목표: <50ms)"


class TestNoDiagnosisInvocation:
    """진단 호출 금지 테스트."""
    
    def test_smalltalk_no_diagnosis_plan(self):
        """Smalltalk Plan에 Diagnosis 스텝 없음."""
        from backend.agents.supervisor.nodes.planner import build_plan
        from backend.agents.shared.contracts import AgentType
        
        state = {
            "intent": "smalltalk",
            "sub_intent": "greeting",
            "user_query": "안녕",
        }
        
        output = build_plan(state)
        
        for step in output.plan:
            assert step.agent != AgentType.DIAGNOSIS, "Smalltalk에서 Diagnosis 호출 금지"
    
    def test_help_no_diagnosis_plan(self):
        """Help Plan에 Diagnosis 스텝 없음."""
        from backend.agents.supervisor.nodes.planner import build_plan
        from backend.agents.shared.contracts import AgentType
        
        state = {
            "intent": "help",
            "sub_intent": "getting_started",
            "user_query": "도와줘",
        }
        
        output = build_plan(state)
        
        for step in output.plan:
            assert step.agent != AgentType.DIAGNOSIS, "Help에서 Diagnosis 호출 금지"
