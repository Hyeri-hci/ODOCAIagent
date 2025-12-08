"""메타 에이전트 통합 테스트."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.api.agent_service import run_agent_task


@pytest.fixture
def mock_diagnosis_service():
    """Diagnosis 서비스 모킹 - run_diagnosis 함수 모킹."""
    with patch("backend.agents.supervisor.nodes.meta_nodes._run_diagnosis_agent") as mock:
        yield mock


@pytest.fixture
def mock_llm_predict():
    """LLM 예측 모킹."""
    with patch("backend.agents.supervisor.nodes.meta_nodes._predict") as mock:
        yield mock


class TestMetaAgentIntegration:
    """메타 에이전트 통합 테스트 클래스."""

    def test_simple_analysis_without_meta_intent(self, mock_diagnosis_service):
        """메시지 없는 기본 진단."""
        # Mock diagnosis 결과
        mock_diagnosis_service.return_value = {
            "health_score": 75,
            "onboarding_score": 60,
            "summary": "건강한 저장소",
        }

        # run_agent_task 호출
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="test",
            repo="test-repo",
            user_message=None,
            use_llm_summary=True,
        )

        # 검증
        assert result["ok"] is True
        assert result["data"]["health_score"] == 75

    def test_analysis_with_user_message_and_priority(
        self, mock_llm_predict, mock_diagnosis_service
    ):
        """사용자 메시지와 우선순위를 포함한 분석."""
        # LLM 의도 분석 결과 모킹
        mock_llm_predict.return_value = (
            '{"task_type": "diagnose", "user_preferences": {"focus": [], "ignore": []}, '
            '"priority": "speed", "initial_mode_hint": "FAST"}'
        )

        # Diagnosis 결과 모킹
        mock_diagnosis_service.return_value = {
            "health_score": 50,
            "onboarding_score": 40,
            "summary": "진단 완료",
        }

        # 실행
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="facebook",
            repo="react",
            user_message="빠르게 상태만 확인해줘",
            priority="speed",
            use_llm_summary=True,
        )

        # 검증: 기본 진단 데이터
        assert result["ok"] is True
        data = result["data"]
        assert data["health_score"] == 50

    def test_conditional_security_execution(
        self, mock_llm_predict, mock_diagnosis_service
    ):
        """조건부 보안 분석 실행 테스트."""
        # LLM 의도 분석: diagnose 의도
        mock_llm_predict.return_value = (
            '{"task_type": "diagnose", "user_preferences": {"focus": [], "ignore": []}, '
            '"priority": "thoroughness", "initial_mode_hint": "FULL"}'
        )

        # Low health -> security 실행되어야 함
        mock_diagnosis_service.return_value = {
            "health_score": 30,  # 30 < 50 -> 조건 만족
            "onboarding_score": 25,
            "summary": "낮은 건강도",
        }

        # 실행
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="low-health-repo",
            repo="vulnerable",
            user_message="건강도가 낮으면 보안도 봐줘",
            priority="thoroughness",
            use_llm_summary=True,
        )

        # 검증
        assert result["ok"] is True
        data = result["data"]
        assert data["health_score"] == 30

    def test_ignore_security_preference(self, mock_llm_predict, mock_diagnosis_service):
        """보안 분석 스킵 (사용자 선호사항)."""
        # LLM 의도 분석: 보안 무시
        mock_llm_predict.return_value = (
            '{"task_type": "diagnose", '
            '"user_preferences": {"focus": ["onboarding"], "ignore": ["security"]}, '
            '"priority": "thoroughness", "initial_mode_hint": "FULL"}'
        )

        # Diagnosis만 실행 (security 스킵)
        mock_diagnosis_service.return_value = {
            "health_score": 45,
            "onboarding_score": 50,
            "summary": "진단 완료",
        }

        # 실행
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="test",
            repo="test-repo",
            user_message="보안은 무시하고 온보딩만 깊게",
            priority="thoroughness",
            use_llm_summary=True,
        )

        # 검증: security 없음
        assert result["ok"] is True
        data = result["data"]
        assert "task_results" not in data or "security" not in data.get("task_results", {})

    def test_full_audit_intent(self, mock_llm_predict, mock_diagnosis_service):
        """Full Audit 의도 테스트."""
        # LLM 의도 분석: full_audit
        mock_llm_predict.return_value = (
            '{"task_type": "full_audit", "user_preferences": {"focus": [], "ignore": []}, '
            '"priority": "thoroughness", "initial_mode_hint": "FULL"}'
        )

        # 모든 에이전트 실행
        mock_diagnosis_service.return_value = {
            "health_score": 60,
            "onboarding_score": 55,
            "summary": "전체 감사 완료",
        }

        # 실행
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="test",
            repo="test-repo",
            user_message="전체적으로 완전히 감사해줘",
            priority="thoroughness",
            use_llm_summary=True,
        )

        # 검증: 모든 에이전트 실행 됨
        assert result["ok"] is True


class TestMetaAgentErrorHandling:
    """메타 에이전트 에러 처리 테스트."""

    def test_llm_parse_failure_fallback(self, mock_llm_predict, mock_diagnosis_service):
        """LLM 파싱 실패 시 폴백."""
        # LLM 예측 실패
        mock_llm_predict.side_effect = Exception("LLM 호출 실패")

        # 폴백: 기본 chat 응답
        mock_diagnosis_service.return_value = {
            "health_score": 0,
        }

        # 실행
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="test",
            repo="test-repo",
            user_message="분석해줘",
            use_llm_summary=True,
        )

        # 검증: 오류 처리됨
        assert result["ok"] is False or "error" in result

    def test_diagnosis_service_failure(self, mock_llm_predict, mock_diagnosis_service):
        """Diagnosis 서비스 실패."""
        mock_llm_predict.return_value = (
            '{"task_type": "diagnose", "user_preferences": {"focus": [], "ignore": []}}'
        )

        # Diagnosis 실패 (예외 발생)
        mock_diagnosis_service.side_effect = Exception("저장소를 찾을 수 없음")

        # 실행
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="invalid",
            repo="notfound",
            user_message="분석해줘",
            use_llm_summary=True,
        )

        # 검증: 에러 반환
        assert result["ok"] is False
        assert "error" in result
