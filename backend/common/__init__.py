"""
ODOCAIagent Common 모듈

공통 유틸리티, 설정, 에러 처리 등을 제공합니다.
"""

# 설정
from backend.common.config import (
    GITHUB_TOKEN,
    LLM_API_KEY,
    LLM_MODEL_NAME,
    LLM_PROVIDER,
)

# 에러 처리
from backend.common.errors import (
    ErrorKind,
    BaseError,
    DiagnosisError,
    GitHubError,
    LLMError,
)

# 로깅
from backend.common.logging_config import setup_logging

# 캐시
from backend.common.cache_manager import (
    CacheManager,
    github_cache,
    cached,
)

# GitHub 클라이언트 함수
from backend.common.github_client import (
    check_repo_access,
    fetch_repo_overview,
    fetch_repo,
    fetch_readme,
)

# 세션 관리
from backend.common.session import (
    Session,
    SessionStore,
    get_session_store,
)

# 메트릭 및 트레이스
from backend.common.metrics import (
    TaskMetrics,
    MetricsTracker,
    get_metrics_tracker,
    ExecutionTrace,
    TraceManager,
    get_trace_manager,
)

# 유틸리티
from backend.common.async_utils import (
    retry_with_backoff,
    async_with_fallback,
    gather_with_partial_results,
)

__all__ = [
    # Config
    "GITHUB_TOKEN",
    "LLM_API_KEY",
    "LLM_MODEL_NAME",
    "LLM_PROVIDER",
    # Errors
    "ErrorKind",
    "BaseError",
    "DiagnosisError",
    "GitHubError",
    "LLMError",
    # Logging
    "setup_logging",
    # Cache
    "CacheManager",
    "github_cache",
    "cached",
    # GitHub
    "check_repo_access",
    "fetch_repo_overview",
    "fetch_repo",
    "fetch_readme",
    # Session
    "Session",
    "SessionStore",
    "get_session_store",
    # Metrics & Trace
    "TaskMetrics",
    "MetricsTracker",
    "get_metrics_tracker",
    "ExecutionTrace",
    "TraceManager",
    "get_trace_manager",
    # Utils
    "retry_with_backoff",
    "async_with_fallback",
    "gather_with_partial_results",
]
