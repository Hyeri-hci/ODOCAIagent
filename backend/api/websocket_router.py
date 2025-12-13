"""
WebSocket Router - 실시간 양방향 통신
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional
import json
import logging
import asyncio
from datetime import datetime

from backend.agents.supervisor.graph import run_supervisor
from backend.common.session import get_session_store

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_json(self, session_id: str, data: Dict[str, Any]):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(data)
            except Exception as e:
                logger.error(f"Failed to send message to {session_id}: {e}")


manager = ConnectionManager()


def safe_json_dumps(obj: Any) -> str:
    """datetime 등 JSON 직렬화 불가능한 객체 처리"""
    def default_serializer(o):
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
    return json.dumps(obj, default=default_serializer, ensure_ascii=False)


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 채팅 엔드포인트
    
    클라이언트 → 서버:
        { "type": "chat", "message": "...", "session_id": "...", "owner": "...", "repo": "..." }
        { "type": "cancel" }
    
    서버 → 클라이언트:
        { "type": "connected", "session_id": "..." }
        { "type": "processing", "agent": "...", "message": "..." }
        { "type": "agent_complete", "agent": "...", "result": {...} }
        { "type": "answer", "content": "...", "session_id": "..." }
        { "type": "error", "message": "..." }
    """
    session_id = None
    current_task: Optional[asyncio.Task] = None
    
    try:
        # WebSocket 연결 수락
        logger.info(f"WebSocket connection attempt from client")
        await websocket.accept()
        logger.info(f"WebSocket connection accepted")
        
        # 초기 연결 메시지 대기 (5초 타임아웃)
        try:
            initial_data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10.0
            )
            logger.info(f"Received initial data: {initial_data}")
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for initial message")
            await websocket.close(1008, "Timeout")
            return
        
        session_id = initial_data.get("session_id") or f"ws_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 연결 관리자에 등록
        manager.active_connections[session_id] = websocket
        
        # 연결 확인 메시지 전송
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "WebSocket 연결됨"
        })
        
        logger.info(f"WebSocket connected: {session_id}")
        
        # 메시지 루프
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type", "chat")
                
                if msg_type == "cancel":
                    # 현재 실행 중인 작업 취소
                    if current_task and not current_task.done():
                        current_task.cancel()
                        await websocket.send_json({
                            "type": "cancelled",
                            "message": "작업이 취소되었습니다."
                        })
                    continue
                
                if msg_type == "chat":
                    message = data.get("message", "")
                    owner = data.get("owner")
                    repo = data.get("repo")
                    
                    if not message.strip():
                        await websocket.send_json({
                            "type": "error",
                            "message": "메시지가 비어있습니다."
                        })
                        continue
                    
                    # owner/repo 정규화
                    if owner and owner.lower() == "unknown":
                        owner = None
                    if repo and repo.lower() == "unknown":
                        repo = None
                    
                    logger.info(f"WebSocket chat: message='{message[:50]}...', owner={owner}, repo={repo}")
                    
                    # 처리 시작 알림
                    await websocket.send_json({
                        "type": "processing",
                        "agent": "supervisor",
                        "message": "요청 분석 중..."
                    })
                    
                    # Supervisor 실행 (별도 태스크로)
                    current_task = asyncio.create_task(
                        process_chat_message(
                            websocket=websocket,
                            session_id=session_id,
                            message=message,
                            owner=owner,
                            repo=repo
                        )
                    )
                    
                    # 결과 대기
                    await current_task
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {session_id}")
                break
            except asyncio.CancelledError:
                logger.info(f"WebSocket task cancelled: {session_id}")
                break
            except json.JSONDecodeError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"잘못된 JSON 형식: {e}"
                })
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"처리 중 오류: {str(e)[:200]}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected during setup: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        if session_id:
            manager.disconnect(session_id)


async def process_chat_message(
    websocket: WebSocket,
    session_id: str,
    message: str,
    owner: Optional[str],
    repo: Optional[str]
):
    """채팅 메시지 처리 및 에이전트 결과 전송"""
    
    try:
        # Supervisor 실행
        result = await run_supervisor(
            user_message=message,
            session_id=session_id,
            owner=owner,
            repo=repo
        )
        
        # 결과에서 각 에이전트 결과 추출 및 전송
        
        # 1. Clarification 필요 여부
        if result.get("awaiting_clarification"):
            await websocket.send_json({
                "type": "clarification",
                "message": result.get("final_answer", ""),
                "session_id": result.get("session_id", session_id)
            })
            return
        
        # 2. 대용량 저장소 경고
        large_repo_warning = result.get("large_repo_warning")
        if large_repo_warning:
            await websocket.send_json({
                "type": "warning",
                "message": large_repo_warning
            })
        
        # 3. 각 에이전트 결과 전송
        target_agent = result.get("target_agent")
        agent_result = result.get("agent_result")
        
        if agent_result:
            await websocket.send_json({
                "type": "agent_complete",
                "agent": target_agent,
                "result": agent_result
            })
        
        # 4. 보안 결과 (멀티 에이전트)
        security_result = result.get("security_result") or result.get("multi_agent_results", {}).get("security")
        if security_result:
            await websocket.send_json({
                "type": "agent_complete",
                "agent": "security",
                "result": security_result
            })
        
        # 5. 온보딩 결과 (멀티 에이전트)
        onboarding_result = result.get("onboarding_result") or result.get("multi_agent_results", {}).get("onboarding")
        if onboarding_result:
            await websocket.send_json({
                "type": "agent_complete",
                "agent": "onboarding",
                "result": onboarding_result
            })
        
        # 6. 추천 결과
        recommend_result = result.get("recommend_result")
        if recommend_result:
            await websocket.send_json({
                "type": "agent_complete",
                "agent": "recommend",
                "result": recommend_result
            })
        
        # 7. 비교 분석 결과
        comparison_result = result.get("comparison_result") or result.get("multi_agent_results", {}).get("comparison")
        if comparison_result:
            await websocket.send_json({
                "type": "agent_complete",
                "agent": "comparison",
                "result": comparison_result
            })
        
        # 7. 최종 답변
        final_answer = result.get("final_answer", "")
        await websocket.send_json({
            "type": "answer",
            "content": final_answer,
            "session_id": result.get("session_id", session_id),
            "repo_info": {
                "owner": result.get("owner"),
                "repo": result.get("repo")
            },
            "suggestions": result.get("suggestions", [])
        })
        
        # 8. 완료 이벤트
        await websocket.send_json({
            "type": "done"
        })
        
    except asyncio.CancelledError:
        logger.info(f"Chat processing cancelled: {session_id}")
        raise
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": f"처리 중 오류 발생: {str(e)[:200]}"
        })
