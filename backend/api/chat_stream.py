"""
SSE 기반 채팅 스트리밍 API.

AI 응답을 실시간으로 클라이언트에 전달합니다.
타이핑 효과를 위한 토큰 단위 스트리밍을 지원합니다.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional, Any, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.llm.base import Role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat-stream"])


class ChatStreamMessage(BaseModel):
    """채팅 메시지."""
    role: str = "user"
    content: str


class ChatStreamRequest(BaseModel):
    """스트리밍 채팅 요청."""
    message: str = Field(..., description="사용자 메시지")
    repo_url: Optional[str] = Field(default=None, description="분석 중인 저장소 URL")
    analysis_context: Optional[Dict[str, Any]] = Field(default=None, description="분석 결과 컨텍스트")
    conversation_history: List[ChatStreamMessage] = Field(default_factory=list, description="이전 대화 기록")


class StreamEvent(BaseModel):
    """스트리밍 이벤트."""
    type: str  # "token", "done", "error"
    content: str = ""
    is_fallback: bool = False


async def generate_chat_stream(
    message: str,
    repo_url: Optional[str],
    analysis_context: Optional[Dict[str, Any]],
    conversation_history: List[ChatStreamMessage],
) -> AsyncGenerator[str, None]:
    """
    채팅 응답을 SSE 이벤트로 스트리밍.
    
    토큰 단위로 응답을 전송하여 타이핑 효과를 구현합니다.
    """
    from concurrent.futures import ThreadPoolExecutor
    from backend.api.chat_service import get_chat_service, ChatServiceRequest, ChatMessage
    from backend.llm.base import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage
    
    def send_event(event_type: str, content: str = "", is_fallback: bool = False) -> str:
        event = StreamEvent(type=event_type, content=content, is_fallback=is_fallback)
        return f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"
    
    try:
        service = get_chat_service()
        
        # 시스템 프롬프트 구성
        system_prompt = service.build_system_prompt(repo_url, analysis_context)
        
        # LLM 메시지 구성
        messages = [LLMChatMessage(role="system", content=system_prompt)]
        for msg in conversation_history:
            role = cast(Role, msg.role) if msg.role in ("system", "user", "assistant") else "user"
            messages.append(LLMChatMessage(role=role, content=msg.content))
        messages.append(LLMChatMessage(role="user", content=message))
        
        # LLM 스트리밍 호출
        llm_request = LLMChatRequest(
            messages=messages,
            model=service.model_name,
            temperature=0.7,
            stream=True,
        )
        
        loop = asyncio.get_event_loop()
        
        try:
            # 스트리밍 응답 처리
            with ThreadPoolExecutor() as executor:
                # stream_chat 호출
                def get_stream():
                    return list(service.llm_client.stream_chat(llm_request, timeout=60))
                
                chunks = await loop.run_in_executor(executor, get_stream)
            
            # 청크 단위로 전송 (타이핑 효과)
            for chunk in chunks:
                if chunk.content:
                    # 긴 청크는 분할하여 타이핑 효과 강화
                    content = chunk.content
                    if len(content) > 10 and not chunk.is_final:
                        # 단어 단위로 분할
                        words = content.split(' ')
                        for i, word in enumerate(words):
                            yield send_event("token", word + (' ' if i < len(words) - 1 else ''))
                            await asyncio.sleep(0.03)  # 타이핑 딜레이
                    else:
                        yield send_event("token", content)
                        if not chunk.is_final:
                            await asyncio.sleep(0.02)
            
            yield send_event("done")
            
        except Exception as e:
            logger.warning(f"LLM streaming failed, using fallback: {e}")
            
            # Fallback 응답
            fallback = service.generate_fallback_response(message, analysis_context)
            
            # Fallback도 타이핑 효과 적용
            words = fallback.split(' ')
            for i, word in enumerate(words):
                yield send_event("token", word + (' ' if i < len(words) - 1 else ''), is_fallback=True)
                await asyncio.sleep(0.02)
            
            yield send_event("done", is_fallback=True)
            
    except Exception as e:
        logger.exception(f"Chat stream failed: {e}")
        yield send_event("error", str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """
    AI 어시스턴트와 스트리밍 채팅.
    
    SSE를 통해 토큰 단위로 응답을 전송합니다.
    타이핑 효과를 위해 약간의 딜레이가 추가됩니다.
    
    이벤트 형식:
    - type: "token" | "done" | "error"
    - content: 토큰 내용
    - is_fallback: LLM 실패 시 fallback 응답 여부
    
    예시:
    ```
    data: {"type": "token", "content": "안녕", "is_fallback": false}
    data: {"type": "token", "content": "하세요", "is_fallback": false}
    data: {"type": "done", "content": "", "is_fallback": false}
    ```
    """
    return StreamingResponse(
        generate_chat_stream(
            message=request.message,
            repo_url=request.repo_url,
            analysis_context=request.analysis_context,
            conversation_history=request.conversation_history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/chat/stream")
async def chat_stream_get(
    message: str,
    repo_url: Optional[str] = None,
):
    """
    GET 방식 스트리밍 채팅 (EventSource 호환).
    
    프론트엔드에서 EventSource API를 사용할 때 사용합니다.
    """
    return StreamingResponse(
        generate_chat_stream(
            message=message,
            repo_url=repo_url,
            analysis_context=None,
            conversation_history=[],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
