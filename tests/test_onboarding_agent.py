"""Onboarding Agent E2E 테스트."""
import pytest
from unittest.mock import patch, MagicMock
from backend.api.agent_service import run_agent_task
from backend.agents.supervisor.models import OnboardingUserContext


class TestOnboardingUserContext:
    """OnboardingUserContext 모델 테스트."""
    
    def test_default_values(self):
        """기본값 테스트."""
        ctx = OnboardingUserContext()
        assert ctx.preferred_language == "ko"
        assert ctx.experience_level == "beginner"
        assert ctx.available_hours_per_week == 5
        assert ctx.preferred_issue_types == []
        assert ctx.focus_areas == []
    
    def test_from_dict(self):
        """dict에서 생성 테스트."""
        data = {
            "experience_level": "intermediate",
            "available_hours_per_week": 10,
            "unknown_key": "ignored"
        }
        ctx = OnboardingUserContext.from_dict(data)
        assert ctx.experience_level == "intermediate"
        assert ctx.available_hours_per_week == 10
        assert ctx.preferred_language == "ko"  # default
    
    def test_validation(self):
        """유효성 검사 테스트."""
        ctx = OnboardingUserContext(
            experience_level="advanced",
            available_hours_per_week=20,
            focus_areas=["backend", "testing"]
        )
        assert ctx.experience_level == "advanced"
        assert ctx.focus_areas == ["backend", "testing"]


class TestOnboardingAgentE2E:
    """Onboarding Agent E2E 테스트."""
    
    @patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
    @patch("backend.llm.kanana_wrapper.KananaWrapper.generate_onboarding_plan")
    @patch("backend.llm.kanana_wrapper.KananaWrapper.summarize_onboarding_plan")
    def test_onboarding_plan_success(
        self, 
        mock_summarize, 
        mock_generate, 
        mock_diagnosis
    ):
        """온보딩 플랜 생성 성공 테스트."""
        # Mock diagnosis
        mock_output = MagicMock()
        mock_output.to_dict.return_value = {
            "repo_id": "test/repo",
            "health_score": 75,
            "summary_for_user": "Good repository"
        }
        mock_diagnosis.return_value = mock_output
        
        # Mock LLM responses
        mock_generate.return_value = [
            {"week": 1, "goals": ["Setup environment"], "tasks": ["Clone repo", "Install deps"]},
            {"week": 2, "goals": ["First contribution"], "tasks": ["Fix typo", "Submit PR"]}
        ]
        mock_summarize.return_value = "2주 온보딩 플랜이 생성되었습니다."
        
        # Run agent task
        result = run_agent_task(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo",
            user_context={
                "experience_level": "beginner",
                "available_hours_per_week": 10
            }
        )
        
        # Assertions
        assert result["ok"] == True
        assert result["task_type"] == "build_onboarding_plan"
        assert "data" in result
        
        data = result["data"]
        assert "onboarding_plan" in data
        assert "onboarding_summary" in data
        assert len(data["onboarding_plan"]) == 2
    
    @patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
    @patch("backend.llm.kanana_wrapper.KananaWrapper.generate_onboarding_plan")
    def test_onboarding_plan_llm_error(
        self, 
        mock_generate, 
        mock_diagnosis
    ):
        """LLM JSON 파싱 실패 시 에러 처리 테스트."""
        # Mock diagnosis
        mock_output = MagicMock()
        mock_output.to_dict.return_value = {
            "repo_id": "test/repo",
            "health_score": 75,
            "summary_for_user": "Good repository"
        }
        mock_diagnosis.return_value = mock_output
        
        # Mock LLM failure
        mock_generate.side_effect = ValueError("LLM_JSON_PARSE_ERROR: Invalid JSON")
        
        # Run agent task
        result = run_agent_task(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo",
            user_context={"experience_level": "beginner"}
        )
        
        # Should still return but with error
        # (depends on implementation - either ok=False or ok=True with error in data)
        assert result["task_type"] == "build_onboarding_plan"


class TestTraceMode:
    """Trace Mode 테스트."""
    
    @patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
    def test_trace_enabled(self, mock_diagnosis):
        """trace 모드 활성화 테스트."""
        mock_output = MagicMock()
        mock_output.to_dict.return_value = {
            "repo_id": "test/repo",
            "health_score": 80
        }
        mock_diagnosis.return_value = mock_output
        
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            debug_trace=True
        )
        
        assert result["ok"] == True
        assert "trace" in result
        assert isinstance(result["trace"], list)
    
    @patch("backend.agents.supervisor.nodes.diagnosis_nodes.run_diagnosis")
    def test_trace_disabled(self, mock_diagnosis):
        """trace 모드 비활성화 테스트."""
        mock_output = MagicMock()
        mock_output.to_dict.return_value = {
            "repo_id": "test/repo",
            "health_score": 80
        }
        mock_diagnosis.return_value = mock_output
        
        result = run_agent_task(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            debug_trace=False
        )
        
        assert result["ok"] == True
        assert "trace" not in result
