"""
Shared types for all agents.

이 모듈은 Diagnosis, Security, Recommend Agent 간 공유되는 타입을 정의합니다.
"""
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AgentResult:
    """모든 Agent의 표준 결과 타입."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    agent_name: str = ""


@dataclass  
class AgentError:
    """Agent 실행 중 발생한 에러."""
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# 공통 점수 타입
ScoreValue = float | int | None

# Agent 종류
AgentType = Literal["diagnosis", "security", "recommend", "supervisor"]
