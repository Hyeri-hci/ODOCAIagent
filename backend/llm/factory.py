from __future__ import annotations

from typing import Optional

from backend.common.config import LLM_PROVIDER
from .base import LLMClient
from .openai_like import OpenAILikeClient

_client: Optional[LLMClient] = None

def fetch_llm_client() -> LLMClient:
    """싱글톤 LLM 클라이언트 인스턴스 반환"""
    global _client
    if _client is not None:
        return _client

    provider = LLM_PROVIDER.lower()

    if provider == "openai_compatible":
        _client = OpenAILikeClient()
    elif provider == "dummy":
        # 테스트용 더미 클라이언트 (원하면 추가 구현)
        from .dummy import DummyChatClient  # 존재한다고 가정
        _client = DummyChatClient()
    else:
        # 알 수 없는 값이면 기본값
        _client = OpenAILikeClient()

    return _client
