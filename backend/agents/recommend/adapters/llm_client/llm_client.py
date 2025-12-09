# adapters/llm_client/llm_client.py

from typing import Optional, List, Dict, Any
from .base import ChatMessage, ChatRequest, ChatResponse
from .factory import fetch_llm_client

def llm_chat(messages: List[ChatMessage], model: str = None, max_tokens: int = 1024) -> ChatResponse:
    """LLM에게 채팅 요청"""
    client = fetch_llm_client()
    request = ChatRequest(messages=messages, model=model, max_tokens=max_tokens)
    return client.chat(request)