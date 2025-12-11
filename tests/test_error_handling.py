"""
통합 에러 처리 시스템 테스트.

Tests:
1. 각 에러 클래스가 올바르게 생성되는지
2. to_dict()가 올바른 형식으로 반환하는지
3. log() 메서드가 동작하는지
4. Fallback policy가 올바르게 조회되는지
5. FastAPI 에러 핸들러 통합 테스트
"""
import pytest
from backend.common.errors import (
    BaseError,
    ErrorKind,
    ErrorAction,
    GitHubError,
    RepoNotFoundError,
    RepoPrivateError,
    GitHubRateLimitError,
    LLMError,
    LLMTimeoutError,
    LLMParseError,
    LLMQuotaExceededError,
    AgentError,
    AgentTimeoutError,
    AgentInvalidInputError,
    DiagnosisError,
    DiagnosisPartialError,
    DiagnosisNoDataError,
    OnboardingError,
    OnboardingNoPlanError,
    CacheError,
    CacheMissError,
    SessionError,
    SessionNotFoundError,
    SessionExpiredError,
    ValidationError,
    get_fallback_policy,
)


class TestBaseError:
    """BaseError 기본 기능 테스트."""
    
    def test_base_error_creation(self):
        """BaseError 생성 테스트."""
        error = BaseError(
            message="Test error",
            kind=ErrorKind.UNKNOWN,
            http_status=500,
            fallback={"data": "test"},
            context={"info": "test"},
            suggested_action=ErrorAction.RETRY,
        )
        
        assert error.message == "Test error"
        assert error.kind == ErrorKind.UNKNOWN
        assert error.http_status == 500
        assert error.fallback == {"data": "test"}
        assert error.context == {"info": "test"}
        assert error.suggested_action == ErrorAction.RETRY
    
    def test_to_dict(self):
        """to_dict() 반환 형식 테스트."""
        error = BaseError(
            message="Test error",
            kind=ErrorKind.AGENT_EXECUTION_FAILED,
            fallback={"partial": "result"},
        )
        
        result = error.to_dict()
        
        assert result["error"] == "Test error"
        assert result["kind"] == "agent_execution_failed"
        assert result["suggested_action"] == "abort"
        assert result["fallback"] == {"partial": "result"}
    
    def test_log_method(self, caplog):
        """log() 메서드 테스트."""
        error = BaseError(
            message="Test logging",
            kind=ErrorKind.INTERNAL_ERROR,
            context={"test": "context"},
        )
        
        error.log(level="warning")
        
        assert "Test logging" in caplog.text
        assert "BaseError" in caplog.text


class TestGitHubErrors:
    """GitHub 관련 에러 테스트."""
    
    def test_repo_not_found_error(self):
        """RepoNotFoundError 테스트."""
        error = RepoNotFoundError(owner="test", repo="repo")
        
        assert error.owner == "test"
        assert error.repo == "repo"
        assert error.kind == ErrorKind.GITHUB_NOT_FOUND
        assert error.http_status == 404
        assert error.suggested_action == ErrorAction.USER_INPUT
        assert "test/repo" in error.message
    
    def test_repo_private_error(self):
        """RepoPrivateError 테스트."""
        error = RepoPrivateError(owner="test", repo="repo")
        
        assert error.owner == "test"
        assert error.repo == "repo"
        assert error.kind == ErrorKind.GITHUB_PRIVATE
        assert error.http_status == 403
        assert "private" in error.message.lower()
    
    def test_rate_limit_error(self):
        """GitHubRateLimitError 테스트."""
        error = GitHubRateLimitError(reset_at="2025-12-11T00:00:00Z")
        
        assert error.kind == ErrorKind.GITHUB_RATE_LIMIT
        assert error.http_status == 429
        assert error.suggested_action == ErrorAction.RETRY
        assert "2025-12-11" in error.message


class TestLLMErrors:
    """LLM 관련 에러 테스트."""
    
    def test_llm_timeout_error(self):
        """LLMTimeoutError 테스트."""
        error = LLMTimeoutError(model="gpt-4", timeout=30)
        
        assert error.kind == ErrorKind.LLM_TIMEOUT
        assert error.suggested_action == ErrorAction.RETRY
        assert error.model == "gpt-4"
        assert "30s" in error.message
    
    def test_llm_parse_error(self):
        """LLMParseError 테스트."""
        raw = "invalid json response" * 100
        error = LLMParseError(raw_response=raw, model="gpt-4")
        
        assert error.kind == ErrorKind.LLM_PARSE_ERROR
        assert error.model == "gpt-4"
        # 컨텍스트는 처음 500자만 저장
        assert len(error.context["raw_response"]) <= 500
    
    def test_llm_quota_exceeded_error(self):
        """LLMQuotaExceededError 테스트."""
        error = LLMQuotaExceededError(model="gpt-4")
        
        assert error.kind == ErrorKind.LLM_QUOTA_EXCEEDED
        assert error.http_status == 429
        assert error.suggested_action == ErrorAction.FALLBACK


class TestAgentErrors:
    """Agent 실행 에러 테스트."""
    
    def test_agent_timeout_error(self):
        """AgentTimeoutError 테스트."""
        error = AgentTimeoutError(agent_name="diagnosis", timeout=60)
        
        assert error.kind == ErrorKind.AGENT_TIMEOUT
        assert error.agent_name == "diagnosis"
        assert "60s" in error.message
        assert error.suggested_action == ErrorAction.FALLBACK
    
    def test_agent_invalid_input_error(self):
        """AgentInvalidInputError 테스트."""
        error = AgentInvalidInputError(
            agent_name="diagnosis",
            reason="Missing required field: repo"
        )
        
        assert error.kind == ErrorKind.AGENT_INVALID_INPUT
        assert error.http_status == 400
        assert error.suggested_action == ErrorAction.USER_INPUT
        assert "Missing required field" in error.message


class TestDiagnosisErrors:
    """Diagnosis 에러 테스트."""
    
    def test_diagnosis_partial_error(self):
        """DiagnosisPartialError 테스트."""
        error = DiagnosisPartialError(
            owner="test",
            repo="repo",
            completed_sections=["structure", "activity"],
            failed_sections=["dependencies"],
            partial_result={"structure": "ok"},
        )
        
        assert error.kind == ErrorKind.DIAGNOSIS_PARTIAL
        assert error.http_status == 206  # Partial Content
        assert error.suggested_action == ErrorAction.FALLBACK
        assert error.fallback == {"structure": "ok"}
        assert error.context["completed_sections"] == ["structure", "activity"]
        assert error.context["failed_sections"] == ["dependencies"]
    
    def test_diagnosis_no_data_error(self):
        """DiagnosisNoDataError 테스트."""
        error = DiagnosisNoDataError(
            owner="test",
            repo="repo",
            reason="Empty repository"
        )
        
        assert error.kind == ErrorKind.DIAGNOSIS_NO_DATA
        assert error.http_status == 404
        assert "Empty repository" in error.message


class TestOnboardingErrors:
    """Onboarding 에러 테스트."""
    
    def test_onboarding_no_plan_error(self):
        """OnboardingNoPlanError 테스트."""
        error = OnboardingNoPlanError(
            owner="test",
            repo="repo",
            reason="LLM timeout"
        )
        
        assert error.kind == ErrorKind.ONBOARDING_NO_PLAN
        assert error.suggested_action == ErrorAction.FALLBACK
        assert "LLM timeout" in error.message


class TestCacheErrors:
    """Cache 에러 테스트."""
    
    def test_cache_miss_error(self):
        """CacheMissError 테스트."""
        error = CacheMissError(key="test:key")
        
        assert error.kind == ErrorKind.CACHE_MISS
        assert error.context["key"] == "test:key"


class TestSessionErrors:
    """Session 에러 테스트."""
    
    def test_session_not_found_error(self):
        """SessionNotFoundError 테스트."""
        error = SessionNotFoundError(session_id="sess123")
        
        assert error.kind == ErrorKind.SESSION_NOT_FOUND
        assert error.http_status == 404
        assert "sess123" in error.message
    
    def test_session_expired_error(self):
        """SessionExpiredError 테스트."""
        error = SessionExpiredError(session_id="sess123")
        
        assert error.kind == ErrorKind.SESSION_EXPIRED
        assert error.http_status == 404


class TestValidationError:
    """Validation 에러 테스트."""
    
    def test_validation_error(self):
        """ValidationError 테스트."""
        error = ValidationError(
            message="Invalid email format",
            field="email",
        )
        
        assert error.kind == ErrorKind.INVALID_INPUT
        assert error.http_status == 400
        assert error.suggested_action == ErrorAction.USER_INPUT
        assert error.context["field"] == "email"


class TestFallbackPolicy:
    """Fallback Policy 테스트."""
    
    def test_get_fallback_policy_known(self):
        """알려진 에러 종류의 Fallback Policy 조회."""
        policy = get_fallback_policy(ErrorKind.GITHUB_RATE_LIMIT)
        
        assert policy["action"] == "캐시된 데이터 사용 또는 대기 후 재시도"
        assert policy["fallback"] == "cached_data"
    
    def test_get_fallback_policy_unknown(self):
        """알려지지 않은 에러 종류의 Fallback Policy 조회."""
        policy = get_fallback_policy(ErrorKind.UNKNOWN)
        
        assert policy["description"] == "Unknown error"
        assert policy["action"] == "Abort"
        assert policy["fallback"] is None


class TestErrorInheritance:
    """에러 클래스 상속 관계 테스트."""
    
    def test_all_errors_inherit_base_error(self):
        """모든 에러가 BaseError를 상속하는지 확인."""
        errors = [
            RepoNotFoundError("owner", "repo"),
            LLMTimeoutError(),
            AgentTimeoutError("agent", 60),
            DiagnosisNoDataError("owner", "repo", "reason"),
            OnboardingNoPlanError("owner", "repo", "reason"),
            CacheMissError("key"),
            SessionNotFoundError("sess123"),
            ValidationError("msg"),
        ]
        
        for error in errors:
            assert isinstance(error, BaseError)
            assert hasattr(error, "to_dict")
            assert hasattr(error, "log")
            assert hasattr(error, "kind")
            assert hasattr(error, "http_status")


# FastAPI 통합 테스트
class TestFastAPIErrorHandler:
    """FastAPI 에러 핸들러 통합 테스트."""
    
    def test_base_error_handler_registered(self):
        """BaseError 핸들러가 등록되어 있는지 확인."""
        from backend.main import app
        from backend.common.errors import BaseError
        
        # 에러 핸들러가 등록되어 있는지 확인
        assert BaseError in app.exception_handlers
    
    def test_global_exception_handler_registered(self):
        """전역 예외 핸들러가 등록되어 있는지 확인."""
        from backend.main import app
        
        # Exception 핸들러가 등록되어 있는지 확인
        assert Exception in app.exception_handlers
