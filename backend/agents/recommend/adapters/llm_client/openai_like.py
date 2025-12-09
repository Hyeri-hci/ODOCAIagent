# adapters/llm_client/openai_like.py

from __future__ import annotations

from typing import Any, Dict, List
import requests

from config.setting import settings
from .base import LLMClient, ChatRequest, ChatResponse, ChatMessage

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
    ) -> None:
        self.api_base = api_base or settings.llm.api_base
        self.api_key = api_key or settings.llm.api_key
        self.default_model = default_model or settings.llm.model_name

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
    
    def chat(self, request: ChatRequest) -> ChatResponse:
        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": request.model or self.default_model,
            "messages": self._convert_messages(request.messages),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        resp = requests.post(
            url,
            headers=self._build_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        # OpenAI 호환 응답 처리: choices[0].message.content 사용
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError("Invalid response format from LLM") from e
        
        return ChatResponse(content=content, raw=data)