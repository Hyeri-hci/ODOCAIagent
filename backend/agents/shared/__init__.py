"""
Shared module for cross-agent utilities and types.

향후 Security Agent, Recommend Agent 통합 시 공통 코드 위치.
"""

from .types import AgentResult, AgentError

__all__ = [
    "AgentResult",
    "AgentError",
]
