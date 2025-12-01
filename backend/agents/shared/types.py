"""
Shared types for all agents.

This module defines types shared between Diagnosis, Security, and Recommend Agents.
"""
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AgentResult:
    """Standard result type for all Agents."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    agent_name: str = ""


@dataclass  
class AgentError:
    """Error raised during Agent execution."""
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# Common score type
ScoreValue = float | int | None

# Agent types
AgentType = Literal["diagnosis", "security", "recommend", "supervisor"]
