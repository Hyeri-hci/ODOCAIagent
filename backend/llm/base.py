from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Literal

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
    stream: bool = False  # 스트리밍 모드

@dataclass
class ChatResponse:
    content: str
    raw: Dict[str, Any]

@dataclass
class StreamChunk:
    """스트리밍 응답 청크."""
    content: str
    is_final: bool = False
    raw: Optional[Dict[str, Any]] = None

class LLMClient(ABC):
    """Abstract base class for an LLM client."""

    @abstractmethod
    def chat(self, request: ChatRequest, timeout: int = 60) -> ChatResponse:
        """Handles a chat request."""
        raise NotImplementedError
    
    def stream_chat(
        self, 
        request: ChatRequest, 
        timeout: int = 60
    ) -> Generator[StreamChunk, None, None]:
        """
        스트리밍 채팅 요청 처리.
        
        기본 구현: 전체 응답을 한 번에 반환 (fallback).
        서브클래스에서 실제 스트리밍 구현 가능.
        
        Args:
            request: 채팅 요청
            timeout: 타임아웃 (초)
        
        Yields:
            StreamChunk: 응답 청크
        """
        # 기본 구현: 전체 응답을 단일 청크로 반환
        response = self.chat(request, timeout)
        yield StreamChunk(
            content=response.content,
            is_final=True,
            raw=response.raw,
        )
