"""Chat Agent 서비스 레이어."""
from __future__ import annotations

import logging
from typing import Dict, Any

from backend.agents.chat.models import ChatInput, ChatOutput

logger = logging.getLogger(__name__)


def run_chat(input_data: ChatInput) -> ChatOutput:
    """
    채팅 응답 생성.
    
    Args:
        input_data: 채팅 입력 (메시지, 컨텍스트)
    
    Returns:
        ChatOutput: 생성된 응답
    """
    from backend.agents.chat.nodes import generate_response
    
    logger.info(f"Chat: intent={input_data.intent}, message={input_data.message[:50]}...")
    
    try:
        response = generate_response(
            message=input_data.message,
            intent=input_data.intent,
            diagnosis=input_data.diagnosis_result,
            chat_context=input_data.chat_context,
            candidate_issues=input_data.candidate_issues,
            owner=input_data.owner,
            repo=input_data.repo,
        )
        
        return ChatOutput(
            response=response,
            intent=input_data.intent,
        )
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return ChatOutput(
            response="요청을 처리하는 중 문제가 발생했습니다. 다시 시도해주세요.",
            intent=input_data.intent,
            error=str(e),
        )


async def run_chat_async(input_data: ChatInput) -> ChatOutput:
    """비동기 버전의 채팅."""
    import asyncio
    return await asyncio.to_thread(run_chat, input_data)
