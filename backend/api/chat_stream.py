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
    """Supervisor를 경유하여 채팅 응답 생성."""
    from concurrent.futures import ThreadPoolExecutor
    
    def send_event(event_type: str, content: str = "", is_fallback: bool = False) -> str:
        event = StreamEvent(type=event_type, content=content, is_fallback=is_fallback)
        return f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"
    
    try:
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(
                executor,
                lambda: _invoke_supervisor_chat(message, repo_url, analysis_context)
            )
        
        if response:
            words = response.split(' ')
            for i, word in enumerate(words):
                yield send_event("token", word + (' ' if i < len(words) - 1 else ''))
                await asyncio.sleep(0.02)
            yield send_event("done")
        else:
            yield send_event("error", "응답 생성 실패")
            
    except Exception as e:
        logger.exception(f"Chat stream failed: {e}")
        yield send_event("error", str(e))


def _invoke_supervisor_chat(
    message: str,
    repo_url: Optional[str],
    analysis_context: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Supervisor Graph를 통해 채팅 처리."""
    from backend.agents.supervisor.graph import get_supervisor_graph
    from backend.agents.supervisor.models import SupervisorState
    
    owner, repo = "", ""
    if repo_url:
        parts = repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            owner, repo = parts[-2], parts[-1]
    
    initial_state = SupervisorState(
        task_type="diagnose_repo",
        owner=owner or "unknown",
        repo=repo or "unknown",
        chat_message=message,
        chat_context=analysis_context or {},
        user_context={"message": message},
    )
    
    graph = get_supervisor_graph()
    config = {"configurable": {"thread_id": f"chat_{owner}_{repo}"}}
    
    try:
        result = graph.invoke(initial_state, config=config)
        return result.get("chat_response")
    except Exception as e:
        logger.error(f"Supervisor chat failed: {e}")
        return None


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
