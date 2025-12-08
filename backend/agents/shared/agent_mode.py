"""공통 에이전트 모드 타입."""
from enum import Enum
from typing import Literal


class AgentMode(str, Enum):
    """에이전트 실행 모드."""
    AUTO = "auto"
    FAST = "fast"
    FULL = "full"


AgentModeLiteral = Literal["auto", "fast", "full"]
