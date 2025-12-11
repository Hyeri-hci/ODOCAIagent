"""
통합 에러 처리 시스템.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorKind(str, Enum):
    """에러 종류 분류."""
    
    # GitHub API 관련
    GITHUB_NOT_FOUND = "github_not_found"
    GITHUB_PRIVATE = "github_private"
    GITHUB_RATE_LIMIT = "github_rate_limit"
    GITHUB_API_ERROR = "github_api_error"
    
    # LLM 관련
    LLM_TIMEOUT = "llm_timeout"
    LLM_PARSE_ERROR = "llm_parse_error"
    LLM_API_ERROR = "llm_api_error"
    LLM_QUOTA_EXCEEDED = "llm_quota_exceeded"
    
    # Agent 실행 관련
    AGENT_EXECUTION_FAILED = "agent_execution_failed"
    AGENT_TIMEOUT = "agent_timeout"
    AGENT_INVALID_INPUT = "agent_invalid_input"
    
    # 진단 관련
    DIAGNOSIS_FAILED = "diagnosis_failed"
    DIAGNOSIS_PARTIAL = "diagnosis_partial"
    DIAGNOSIS_NO_DATA = "diagnosis_no_data"
    
    # 온보딩 관련
    ONBOARDING_FAILED = "onboarding_failed"
    ONBOARDING_NO_PLAN = "onboarding_no_plan"
    
    # 캐시 관련
    CACHE_MISS = "cache_miss"
    CACHE_ERROR = "cache_error"
    
    # 세션 관련
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    
    # 입력 검증
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    
    # 기타
    UNKNOWN = "unknown"
    INTERNAL_ERROR = "internal_error"


class ErrorAction(str, Enum):
    """에러 발생 시 권장 액션."""
    RETRY = "retry"
    FALLBACK = "fallback"
    USER_INPUT = "user_input"
    ABORT = "abort"


class BaseError(Exception):
    """모든 ODOC Agent 에러의 베이스 클래스."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.UNKNOWN,
        http_status: int = 500,
        fallback: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        suggested_action: ErrorAction = ErrorAction.ABORT,
    ):
        """
        Args:
            message: 에러 메시지 (사용자에게 표시 가능)
            kind: 에러 종류
            http_status: HTTP 상태 코드 (API 응답 시 사용)
            fallback: Fallback 데이터 (선택적)
            context: 추가 컨텍스트 (로깅용, 사용자에게 노출 안 됨)
            suggested_action: 권장 액션
        """
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.http_status = http_status
        self.fallback = fallback or {}
        self.context = context or {}
        self.suggested_action = suggested_action
    
    def to_dict(self) -> Dict[str, Any]:
        """에러를 dict로 변환 (API 응답용)."""
        return {
            "error": self.message,
            "kind": self.kind.value,
            "suggested_action": self.suggested_action.value,
            "fallback": self.fallback,
        }
    
    def log(self, level: str = "error"):
        """에러를 로깅."""
        log_func = getattr(logger, level, logger.error)
        log_func(
            f"{self.__class__.__name__}: {self.message}",
            extra={
                "kind": self.kind.value,
                "http_status": self.http_status,
                "context": self.context,
            }
        )


# GitHub 관련 에러
class GitHubError(BaseError):
    """GitHub API 관련 에러."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.GITHUB_API_ERROR,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        # context를 kwargs에서 추출하거나 새로 생성
        context = kwargs.pop("context", {})
        context.update({
            "owner": owner,
            "repo": repo,
            "status_code": status_code,
        })
        super().__init__(
            message=message,
            kind=kind,
            http_status=status_code or 500,
            context=context,
            **kwargs
        )
        self.owner = owner
        self.repo = repo
        self.status_code = status_code


class RepoNotFoundError(GitHubError):
    """저장소를 찾을 수 없음 (404)."""
    
    def __init__(self, owner: str, repo: str):
        super().__init__(
            message=f"Repository {owner}/{repo} not found or not accessible",
            kind=ErrorKind.GITHUB_NOT_FOUND,
            owner=owner,
            repo=repo,
            status_code=404,
            suggested_action=ErrorAction.USER_INPUT,
        )


class RepoPrivateError(GitHubError):
    """Private 저장소에 접근 권한 없음 (403)."""
    
    def __init__(self, owner: str, repo: str):
        super().__init__(
            message=f"Repository {owner}/{repo} is private and requires authentication",
            kind=ErrorKind.GITHUB_PRIVATE,
            owner=owner,
            repo=repo,
            status_code=403,
            suggested_action=ErrorAction.USER_INPUT,
        )


class GitHubRateLimitError(GitHubError):
    """GitHub API Rate Limit 초과."""
    
    def __init__(self, reset_at: Optional[str] = None):
        message = "GitHub API rate limit exceeded"
        if reset_at:
            message += f". Resets at {reset_at}"
        
        super().__init__(
            message=message,
            kind=ErrorKind.GITHUB_RATE_LIMIT,
            status_code=429,
            suggested_action=ErrorAction.RETRY,
            context={"reset_at": reset_at},
        )


# LLM 관련 에러
class LLMError(BaseError):
    """LLM 관련 에러."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.LLM_API_ERROR,
        model: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({"model": model})
        super().__init__(
            message=message,
            kind=kind,
            context=context,
            **kwargs
        )
        self.model = model


class LLMTimeoutError(LLMError):
    """LLM 호출 타임아웃."""
    
    def __init__(self, model: Optional[str] = None, timeout: Optional[int] = None):
        message = f"LLM request timed out"
        if timeout:
            message += f" after {timeout}s"
        
        super().__init__(
            message=message,
            kind=ErrorKind.LLM_TIMEOUT,
            model=model,
            suggested_action=ErrorAction.RETRY,
            context={"timeout": timeout},
        )


class LLMParseError(LLMError):
    """LLM 응답 파싱 실패."""
    
    def __init__(self, raw_response: str, model: Optional[str] = None):
        super().__init__(
            message="Failed to parse LLM response",
            kind=ErrorKind.LLM_PARSE_ERROR,
            model=model,
            suggested_action=ErrorAction.RETRY,
            context={"raw_response": raw_response[:500]},  # 처음 500자만
        )


class LLMQuotaExceededError(LLMError):
    """LLM API 할당량 초과."""
    
    def __init__(self, model: Optional[str] = None):
        super().__init__(
            message="LLM API quota exceeded",
            kind=ErrorKind.LLM_QUOTA_EXCEEDED,
            model=model,
            http_status=429,
            suggested_action=ErrorAction.FALLBACK,
        )


# Agent 실행 에러
class AgentError(BaseError):
    """Agent 실행 중 에러."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.AGENT_EXECUTION_FAILED,
        agent_name: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({"agent_name": agent_name})
        super().__init__(
            message=message,
            kind=kind,
            context=context,
            **kwargs
        )
        self.agent_name = agent_name


class AgentTimeoutError(AgentError):
    """Agent 실행 타임아웃."""
    
    def __init__(self, agent_name: str, timeout: int):
        super().__init__(
            message=f"Agent '{agent_name}' timed out after {timeout}s",
            kind=ErrorKind.AGENT_TIMEOUT,
            agent_name=agent_name,
            suggested_action=ErrorAction.FALLBACK,
        )


class AgentInvalidInputError(AgentError):
    """Agent 입력이 유효하지 않음."""
    
    def __init__(self, agent_name: str, reason: str):
        super().__init__(
            message=f"Invalid input for agent '{agent_name}': {reason}",
            kind=ErrorKind.AGENT_INVALID_INPUT,
            agent_name=agent_name,
            http_status=400,
            suggested_action=ErrorAction.USER_INPUT,
        )


# Diagnosis 에러
class DiagnosisError(BaseError):
    """Diagnosis Agent 에러."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.DIAGNOSIS_FAILED,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({"owner": owner, "repo": repo})
        super().__init__(
            message=message,
            kind=kind,
            context=context,
            **kwargs
        )
        self.owner = owner
        self.repo = repo


class DiagnosisPartialError(DiagnosisError):
    """진단이 부분적으로만 완료됨."""
    
    def __init__(
        self,
        owner: str,
        repo: str,
        completed_sections: list[str],
        failed_sections: list[str],
        partial_result: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"Diagnosis partially completed for {owner}/{repo}",
            kind=ErrorKind.DIAGNOSIS_PARTIAL,
            owner=owner,
            repo=repo,
            http_status=206,  # Partial Content
            suggested_action=ErrorAction.FALLBACK,
            fallback=partial_result or {},
            context={
                "completed_sections": completed_sections,
                "failed_sections": failed_sections,
            }
        )


class DiagnosisNoDataError(DiagnosisError):
    """진단할 데이터가 없음."""
    
    def __init__(self, owner: str, repo: str, reason: str):
        super().__init__(
            message=f"No data available for diagnosis: {reason}",
            kind=ErrorKind.DIAGNOSIS_NO_DATA,
            owner=owner,
            repo=repo,
            http_status=404,
            suggested_action=ErrorAction.USER_INPUT,
        )


# Onboarding 에러
class OnboardingError(BaseError):
    """Onboarding Agent 에러."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.ONBOARDING_FAILED,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({"owner": owner, "repo": repo})
        super().__init__(
            message=message,
            kind=kind,
            context=context,
            **kwargs
        )


class OnboardingNoPlanError(OnboardingError):
    """온보딩 플랜 생성 실패."""
    
    def __init__(self, owner: str, repo: str, reason: str):
        super().__init__(
            message=f"Failed to generate onboarding plan: {reason}",
            kind=ErrorKind.ONBOARDING_NO_PLAN,
            owner=owner,
            repo=repo,
            suggested_action=ErrorAction.FALLBACK,
        )


# Cache 에러
class CacheError(BaseError):
    """Cache 관련 에러."""
    
    def __init__(self, message: str, kind: ErrorKind = ErrorKind.CACHE_ERROR, **kwargs):
        super().__init__(
            message=message,
            kind=kind,
            http_status=500,
            suggested_action=ErrorAction.FALLBACK,
            **kwargs
        )


class CacheMissError(CacheError):
    """캐시 미스 (정상적인 경우도 있으므로 warning)."""
    
    def __init__(self, key: str):
        super().__init__(
            message=f"Cache miss for key: {key}",
            kind=ErrorKind.CACHE_MISS,
            context={"key": key},
        )


# Session 에러
class SessionError(BaseError):
    """세션 관련 에러."""
    
    def __init__(
        self,
        message: str,
        kind: ErrorKind = ErrorKind.SESSION_NOT_FOUND,
        session_id: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({"session_id": session_id})
        super().__init__(
            message=message,
            kind=kind,
            http_status=404,
            context=context,
            **kwargs
        )


class SessionNotFoundError(SessionError):
    """세션을 찾을 수 없음."""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id}",
            kind=ErrorKind.SESSION_NOT_FOUND,
            session_id=session_id,
            suggested_action=ErrorAction.USER_INPUT,
        )


class SessionExpiredError(SessionError):
    """세션이 만료됨."""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session expired: {session_id}",
            kind=ErrorKind.SESSION_EXPIRED,
            session_id=session_id,
            suggested_action=ErrorAction.USER_INPUT,
        )


# Validation 에러
class ValidationError(BaseError):
    """입력 검증 에러."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        kind: ErrorKind = ErrorKind.INVALID_INPUT,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({"field": field})
        super().__init__(
            message=message,
            kind=kind,
            http_status=400,
            context=context,
            suggested_action=ErrorAction.USER_INPUT,
            **kwargs
        )


# Fallback Policy 문서화
FALLBACK_POLICIES = {
    ErrorKind.GITHUB_NOT_FOUND: {
        "description": "저장소를 찾을 수 없음",
        "action": "사용자에게 저장소 URL 재확인 요청",
        "fallback": None,
    },
    ErrorKind.GITHUB_RATE_LIMIT: {
        "description": "GitHub API Rate Limit 초과",
        "action": "캐시된 데이터 사용 또는 대기 후 재시도",
        "fallback": "cached_data",
    },
    ErrorKind.LLM_TIMEOUT: {
        "description": "LLM 호출 타임아웃",
        "action": "재시도 또는 규칙 기반 분석 사용",
        "fallback": "rule_based_analysis",
    },
    ErrorKind.LLM_PARSE_ERROR: {
        "description": "LLM 응답 파싱 실패",
        "action": "재시도 (최대 3회) 후 규칙 기반 분석",
        "fallback": "rule_based_analysis",
    },
    ErrorKind.DIAGNOSIS_PARTIAL: {
        "description": "진단이 부분적으로만 완료됨",
        "action": "부분 결과 반환",
        "fallback": "partial_result",
    },
    ErrorKind.CACHE_MISS: {
        "description": "캐시 미스",
        "action": "정상 플로우 (fresh fetch)",
        "fallback": None,
    },
}


def get_fallback_policy(kind: ErrorKind) -> Dict[str, Any]:
    """에러 종류에 따른 Fallback 정책 조회."""
    return FALLBACK_POLICIES.get(kind, {
        "description": "Unknown error",
        "action": "Abort",
        "fallback": None,
    })
