from __future__ import annotations

from typing import Optional

from backend.common.config import LLM_PROVIDER
from .base import LLMClient
from .openai_like import OpenAILikeClient

_client: Optional[LLMClient] = None

def fetch_llm_client() -> LLMClient:
    """Returns the singleton LLM client instance."""
    global _client
    if _client is not None:
        return _client

    provider = LLM_PROVIDER.lower()

    if provider == "openai_compatible":
        _client = OpenAILikeClient()
    elif provider == "local_kanana":
        # Dummy client for testing (can be implemented further if needed)
        from .local_kanana import LocalKananaClient
        _client = LocalKananaClient()
    else:
        # Default to OpenAILikeClient if the provider is unknown
        _client = OpenAILikeClient()

    return _client
