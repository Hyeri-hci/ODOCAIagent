"""
Supervisor 헬퍼 함수
"""

from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


async def _enhance_answer_with_context(
    user_message: str,
    base_answer: str,
    referenced_data: Dict[str, Any],
    action: str,
    refers_to: str = "previous data"
) -> str:
    """대명사 참조 시 컨텍스트를 활용하여 답변 보강"""
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        import asyncio
        
        llm = fetch_llm_client()
        loop = asyncio.get_event_loop()
        
        # 컨텍스트 요약
        context_summary = json.dumps(referenced_data, ensure_ascii=False, indent=2)[:1000]
        
        action_instructions = {
            "refine": "더 자세하고 구체적으로",
            "summarize": "간단하고 핵심적으로",
            "view": "명확하게"
        }
        
        instruction = action_instructions.get(action, "명확하게")
        
        prompt = f"""사용자가 이전 대화에서 생성된 '{refers_to}' 데이터를 참조하여 질문하고 있습니다.

=== 사용자 질문 ===
{user_message}

=== 참조 데이터 ('{refers_to}') ===
{context_summary}

=== 지시사항 ===
사용자의 요청을 {instruction} 설명해주세요.
참조 데이터의 주요 내용을 기반으로 사용자가 원하는 답변을 제공하세요.

답변은 자연스러운 한국어로 작성하되, 참조 데이터의 구체적인 내용을 포함해주세요.
"""
        
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.7,
            max_tokens=1000
        )
        
        response = await loop.run_in_executor(None, llm.chat, request)
        enhanced_answer = response.content
        
        logger.info(f"Enhanced answer with context from '{refers_to}'")
        return enhanced_answer
    
    except Exception as e:
        logger.error(f"Failed to enhance answer: {e}", exc_info=True)
        return base_answer
