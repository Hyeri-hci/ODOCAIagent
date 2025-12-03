from __future__ import annotations

from typing import Optional

from backend.common.config import LLM_PROVIDER
from .base import LLMClient
from .openai_like import OpenAILikeClient


class LLMClientProvider:
    """Singleton provider for LLM client with test reset support."""
    
    _instance: Optional[LLMClient] = None
    
    @classmethod
    def get(cls) -> LLMClient:
        """Returns the singleton LLM client instance."""
        if cls._instance is not None:
            return cls._instance

        provider = LLM_PROVIDER.lower()

        if provider == "openai_compatible":
            cls._instance = OpenAILikeClient()
        elif provider == "local_kanana":
            from .local_kanana import LocalKananaClient
            cls._instance = LocalKananaClient()
        else:
            cls._instance = OpenAILikeClient()

        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Resets the singleton instance (for testing)."""
        cls._instance = None
    
    @classmethod
    def set_instance(cls, client: LLMClient) -> None:
        """Sets a custom client instance (for testing/mocking)."""
        cls._instance = client


def fetch_llm_client() -> LLMClient:
    """Returns the singleton LLM client instance."""
    return LLMClientProvider.get()

