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
    DEFAULT_TIMEOUT = 60
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    @abstractmethod
    def chat(self, request: ChatRequest, timeout: int = 60) -> ChatResponse:
        """Handles a chat request."""
        raise NotImplementedError
    
    def stream_chat(
        self, 
        request: ChatRequest, 
        timeout: int = 60
    ) -> Generator[StreamChunk, None, None]:
        response = self.chat(request, timeout)
        yield StreamChunk(
            content=response.content,
            is_final=True,
            raw=response.raw,
        )
    
    def chat_with_retry(
        self,
        request: ChatRequest,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> ChatResponse:
        import time
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return self.chat(request, timeout)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise last_error
