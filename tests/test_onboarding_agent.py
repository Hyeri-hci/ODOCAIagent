"""온보딩 에이전트 E2E 테스트 (hybrid pattern + 예외 처리)"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.onboarding.graph import (
    get_onboarding_graph,
    build_onboarding_graph,
    safe_node,
    error_handler_node,
    run_onboarding_graph,
)
from backend.agents.onboarding.models import OnboardingState, OnboardingOutput


# ─────────────────────────────────────────────────────────────────────────────
# 공통 Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_state() -> OnboardingState:
    """샘플 OnboardingState (TypedDict로 구성)"""
    return {
        "owner": "microsoft",
        "repo": "vscode",
        "ref": "main",
        "experience_level": "beginner",
        "diagnosis_summary": "",
        "user_context": {},
        "user_message": None,
        "candidate_issues": None,
        "plan": None,
        "summary": None,
        "diagnosis_analysis": None,
        "onboarding_risks": None,
        "plan_config": None,
        "agent_decision": None,
        "result": None,
        "error": None,
        "execution_path": None,
    }


@pytest.fixture
def state_with_user_context() -> OnboardingState:
    """사용자 컨텍스트가 포함된 OnboardingState"""
    return {
        "owner": "facebook",
        "repo": "react",
        "ref": "main",
        "experience_level": "intermediate",
        "diagnosis_summary": "",
        "user_context": {
            "role": "frontend",
            "interests": ["hooks", "concurrent"]
        },
        "user_message": None,
        "candidate_issues": None,
        "plan": None,
        "summary": None,
        "diagnosis_analysis": None,
        "onboarding_risks": None,
        "plan_config": None,
        "agent_decision": None,
        "result": None,
        "error": None,
        "execution_path": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TestOnboardingUserContext: 사용자 컨텍스트 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingUserContext:
    """사용자 컨텍스트(역할, 관심사) 기반 온보딩 커스터마이징 테스트"""

    def test_state_user_context_included(self, state_with_user_context):
        """State에 사용자 컨텍스트가 포함되는지 확인"""
        state = state_with_user_context
        assert state["user_context"] is not None
        assert state["user_context"].get("role") == "frontend"
        assert "hooks" in state["user_context"].get("interests", [])

    def test_state_preserves_user_context(self, state_with_user_context):
        """State가 user_context를 유지하는지 확인"""
        state = state_with_user_context
        assert state["user_context"] is not None
        assert state["user_context"].get("role") == "frontend"

    def test_default_user_context_is_empty(self, sample_state):
        """기본 State에는 user_context가 빈 dict인지 확인"""
        assert sample_state["user_context"] == {}


# ─────────────────────────────────────────────────────────────────────────────
# TestOnboardingGraph: 그래프 생성 및 노드 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingGraph:
    """온보딩 그래프 구조 테스트"""

    def test_graph_creation(self):
        """그래프가 성공적으로 생성되는지 확인"""
        graph = build_onboarding_graph()
        assert graph is not None

    def test_singleton_graph(self):
        """싱글톤 그래프가 동일한 인스턴스를 반환하는지 확인"""
        graph1 = get_onboarding_graph()
        graph2 = get_onboarding_graph()
        assert graph1 is graph2

    @pytest.mark.asyncio
    async def test_error_handler_node_exists(self, sample_state):
        """error_handler 노드가 존재하고 동작하는지 확인"""
        # 에러 상태 설정
        sample_state["error"] = "Test error message"
        
        result = await error_handler_node(sample_state)
        assert "result" in result
        assert result["result"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# TestSafeNodeDecorator: @safe_node 데코레이터 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeNodeDecorator:
    """@safe_node 데코레이터 동작 테스트"""

    @pytest.mark.asyncio
    async def test_safe_node_success(self):
        """정상 동작 시 safe_node가 결과를 그대로 반환"""
        
        @safe_node({"test_field": "default_value"})
        async def success_func(state):
            return {"test_field": "success_value"}
        
        result = await success_func({})
        assert result["test_field"] == "success_value"

    @pytest.mark.asyncio
    async def test_safe_node_error_handling(self):
        """예외 발생 시 safe_node가 기본값을 반환"""
        
        @safe_node({"test_field": "fallback_value"})
        async def failing_func(state):
            raise ValueError("Test error")
        
        result = await failing_func({"execution_path": ""})
        assert result["test_field"] == "fallback_value"
        assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# TestOnboardingE2E: 엔드투엔드 통합 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingE2E:
    """온보딩 에이전트 E2E 테스트"""

    @pytest.mark.asyncio
    @patch("backend.agents.onboarding.nodes.fetch_issues")
    @patch("backend.agents.onboarding.nodes.generate_plan")
    @patch("backend.agents.onboarding.nodes.summarize_plan")
    async def test_full_onboarding_flow(
        self,
        mock_summarize,
        mock_generate_plan,
        mock_fetch_issues,
        sample_state
    ):
        """전체 온보딩 플로우 테스트 (mock된 외부 의존성)"""
        # Mock 설정
        mock_fetch_issues.return_value = [
            {"number": 1, "title": "Good first issue", "url": "http://test.com/1"}
        ]
        mock_generate_plan.return_value = {
            "plan": [
                {"week": 1, "title": "Getting Started", "tasks": ["Setup"]}
            ],
            "summary": "Great project for beginners"
        }
        mock_summarize.return_value = "온보딩 요약입니다."
        
        # run_onboarding_graph 실행
        result = await run_onboarding_graph(
            owner="microsoft",
            repo="vscode",
            experience_level="beginner",
        )
        
        # 결과 검증 - OnboardingOutput 형태여야 함
        assert result is not None
        # 에러가 있어도 결과가 반환되어야 함 (graceful degradation)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_graceful_error_handling(self, sample_state):
        """에러 발생 시 graceful 처리 테스트"""
        
        # 존재하지 않는 레포로 테스트 (외부 호출 mock 없이)
        # safe_node 덕분에 에러가 발생해도 크래시하지 않아야 함
        result = await run_onboarding_graph(
            owner="nonexistent-owner-12345",
            repo="fake-repo-12345",
            experience_level="beginner",
        )
        
        # 에러가 발생해도 결과가 반환되어야 함
        assert result is not None
        assert isinstance(result, dict)


# ─────────────────────────────────────────────────────────────────────────────
# TestConditionalRouting: 조건부 라우팅 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestConditionalRouting:
    """조건부 라우팅 테스트 (에러 발생 시 error_handler로 이동)"""

    def test_check_error_routing_function(self):
        """에러 체크 라우팅 함수가 올바르게 동작하는지 확인"""
        from backend.agents.onboarding.graph import check_error_and_route
        
        # 정상 상태 - 에러 없음
        normal_state = {"error": None}
        assert check_error_and_route(normal_state) == "continue"
        
        # 빈 에러 문자열도 정상 상태
        empty_error_state = {"error": ""}
        assert check_error_and_route(empty_error_state) == "continue"
        
        # 에러 상태
        error_state = {"error": "Some error occurred"}
        assert check_error_and_route(error_state) == "error_handler"
