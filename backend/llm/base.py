from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal

Role = Literal["system", "user", "assistant"]

@dataclass
class ChatMessage:
    role: Role
    content: str

@dataclass
class ChatRequest:
    messages: List[ChatMessage]
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.2
    top_p: float = 0.9

@dataclass
class ChatResponse:
    content: str
    raw: Dict[str, Any]

class LLMClient(ABC):
    """
    LLM 클라이언트 추상 클래스
    """

    @abstractmethod
    def chat(self, request: ChatRequest, timeout: int = 60) -> ChatResponse:
        """
        채팅 요청 처리
        
        Args:
            request: 채팅 요청 데이터
            timeout: 요청 타임아웃 (초)
        
        Returns:
            ChatResponse: LLM 응답
        """
        raise NotImplementedError