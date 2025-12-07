from __future__ import annotations

import time
import logging
from typing import Any, Dict, List
from openai import OpenAI

from backend.common.config import LLM_API_BASE, LLM_MODEL_NAME, LLM_API_KEY
from .base import LLMClient, ChatRequest, ChatResponse, ChatMessage

logger = logging.getLogger(__name__)


class OpenAILikeClient(LLMClient):
    """
    LLM client for endpoints compatible with the OpenAI Chat Completions API.
    (e.g., OpenAI, Kanana, local llama.cpp)
    Uses the official OpenAI SDK for better compatibility.
    """

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.api_base = api_base or LLM_API_BASE
        self.api_key = api_key or LLM_API_KEY
        self.default_model = default_model or LLM_MODEL_NAME
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # OpenAI SDK 클라이언트 초기화
        self._client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key or "dummy-key",
        )
        
        # 모델명이 없으면 API에서 가져오기
        if not self.default_model or self.default_model == "kanana-1.5-8b-instruct-2505":
            try:
                models = self._client.models.list()
                if models.data:
                    self.default_model = models.data[0].id
                    logger.info(f"[LLM] Auto-detected model: {self.default_model}")
            except Exception as e:
                logger.warning(f"[LLM] Could not fetch model list: {e}")
    
    def _convert_messages(
        self, messages: List[ChatMessage]
    ) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def chat(self, request: ChatRequest, timeout: int = 60) -> ChatResponse:
        model = request.model or self.default_model
        messages = self._convert_messages(request.messages)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    timeout=timeout,
                )
                
                content = response.choices[0].message.content
                raw = response.model_dump() if hasattr(response, 'model_dump') else {}
                
                return ChatResponse(content=content, raw=raw)
                
            except Exception as e:
                last_error = ConnectionError(f"LLM request failed: {e}")
                logger.warning(f"[LLM] Error (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # If not the last attempt, wait and retry
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)
                logger.info(f"[LLM] Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        # All retries failed
        raise last_error or ConnectionError("LLM request failed after all retries")