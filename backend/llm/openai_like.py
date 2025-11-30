from __future__ import annotations

import time
import logging
from typing import Any, Dict, List
import requests

from backend.common.config import LLM_API_BASE, LLM_MODEL_NAME, LLM_API_KEY
from .base import LLMClient, ChatRequest, ChatResponse, ChatMessage

logger = logging.getLogger(__name__)


class OpenAILikeClient(LLMClient):
    """
      OpenAI / llama.cpp / 로컬 Kanana 프록시 등
      'OpenAI Chat Completions' API 호환 End-point LLM 클라이언트
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

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _convert_messages(
        self, messages: List[ChatMessage]
    ) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def chat(self, request: ChatRequest, timeout: int = 60) -> ChatResponse:
        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": request.model or self.default_model,
            "messages": self._convert_messages(request.messages),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    url,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=timeout,
                )
                resp.raise_for_status()
                
                data = resp.json()

                # OpenAI 호환 응답 처리: choices[0].message.content 사용
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError) as e:
                    raise ValueError(f"Invalid response format from LLM: {data}") from e
                
                return ChatResponse(content=content, raw=data)
                
            except requests.exceptions.Timeout:
                last_error = TimeoutError(f"LLM request timed out after {timeout}s")
                logger.warning(f"[LLM] Timeout (attempt {attempt + 1}/{self.max_retries})")
            except requests.exceptions.RequestException as e:
                last_error = ConnectionError(f"LLM request failed: {e}")
                logger.warning(f"[LLM] Connection error (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # 마지막 시도가 아니면 대기 후 재시도
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)  # exponential backoff
                logger.info(f"[LLM] Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        # 모든 재시도 실패
        raise last_error or ConnectionError("LLM request failed after all retries")