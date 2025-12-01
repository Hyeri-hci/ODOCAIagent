"""
Shared module for cross-agent utilities and types.

This is the location for common code when integrating Security and Recommend Agents.
"""

from .types import AgentResult, AgentError

__all__ = [
    "AgentResult",
    "AgentError",
]
