"""
Chat API Router - 세션 기반 멀티턴 대화 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
import asyncio
import json
from dataclasses import is_dataclass, asdict

from backend.agents.supervisor.graph import run_supervisor
from backend.common.session import get_session_store
from backend.common.async_utils import retry_with_backoff, GracefulDegradation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# === Custom JSON Encoder ===

class DataclassJSONEncoder(json.JSONEncoder):
    """Dataclass 객체를 JSON으로 직렬화하는 인코더"""
    def default(self, obj):
        if is_dataclass(obj) and not isinstance(obj, type):
            # dataclass 인스턴스면 to_dict() 있으면 사용, 없으면 asdict()
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            return asdict(obj)
        # set을 list로
        if isinstance(obj, set):
            return list(obj)
        # bytes를 str로
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        return super().default(obj)


def safe_json_dumps(obj: Any) -> str:
    """안전한 JSON 직렬화 (dataclass 지원)"""
    return json.dumps(obj, cls=DataclassJSONEncoder, ensure_ascii=False)


# === Request/Response Models ===

class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., description="사용자 메시지")
    session_id: Optional[str] = Field(None, description="세션 ID (없으면 새로 생성)")
    owner: Optional[str] = Field(None, description="저장소 소유자")
    repo: Optional[str] = Field(None, description="저장소 이름")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 메타데이터")


class ChatResponse(BaseModel):
    """채팅 응답"""
    session_id: str = Field(..., description="세션 ID")
    answer: str = Field(..., description="에이전트 응답")
    context: Dict[str, Any] = Field(default_factory=dict, description="컨텍스트 정보")
    suggestions: List[str] = Field(default_factory=list, description="추천 질문")
    trace: Optional[Dict[str, Any]] = Field(None, description="실행 추적 정보")


class SessionInfo(BaseModel):
    """세션 정보"""
    session_id: str
    created_at: str
    last_accessed: str
    turn_count: int
    accumulated_context: Dict[str, Any]


# === API Endpoints ===

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    채팅 메시지 처리
    
    - 세션 ID가 없으면 새로 생성
    - 기존 세션 ID가 있으면 대화 이어감
    - Supervisor V2를 통해 적절한 에이전트로 라우팅
    
    Example:
        ```json
        {
          "message": "django-oscar 프로젝트 분석해줘",
          "owner": "django-oscar",
          "repo": "django-oscar"
        }
        ```
    """
    
    try:
        # Supervisor V2 실행
        owner = request.owner or "unknown"
        repo = request.repo or "unknown"
        
        async def run_with_retry():
            try:
                return await run_supervisor(
                    user_message=request.message,
                    session_id=request.session_id,
                    owner=owner,
                    repo=repo
                )
            except Exception as e:
                logger.error(f"Supervisor execution failed: {e}", exc_info=True)
                # Fallback 응답
                return {
                    "session_id": request.session_id or "temp",
                    "final_answer": f"요청을 처리하는 중 오류가 발생했습니다: {str(e)[:100]}",
                    "suggested_actions": [],
                    "awaiting_clarification": False
                }
        
        result = await run_with_retry()
        
        # 응답 구성
        response = ChatResponse(
            session_id=result["session_id"],
            answer=result.get("final_answer", "죄송합니다. 응답을 생성할 수 없습니다."),
            context={
                "target_agent": result.get("target_agent"),
                "needs_clarification": result.get("needs_clarification", False),
                "agent_result_summary": _summarize_agent_result(result.get("agent_result")),
                "agent_result": result.get("agent_result")  # 전체 결과도 포함
            },
            suggestions=_generate_suggestions(result),
            trace=result.get("trace")
        )
        
        logger.info(f"Chat completed: session={response.session_id}, agent={result.get('target_agent')}")
        
        return response
    
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"채팅 처리 중 오류 발생: {str(e)}")


@router.get("/session/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """
    세션 정보 조회
    """
    
    session = get_session_store().get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return SessionInfo(
        session_id=session.session_id,
        created_at=session.created_at.isoformat(),
        last_accessed=getattr(session, 'last_accessed', session.created_at).isoformat(),
        turn_count=len(session.conversation_history),
        accumulated_context=dict(getattr(session.accumulated_context, '__dict__', session.accumulated_context))
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, Any]:
    """
    세션 삭제
    """
    try:
        session_store = get_session_store()
        
        # 세션 삭제 시도 (존재 여부와 무관하게 멱등성 보장)
        was_deleted = session_store.delete_session(session_id)
        
        if was_deleted:
            logger.info(f"Session {session_id} deleted successfully")
            return {"success": True, "message": f"Session {session_id} deleted"}
        else:
            # 이미 삭제됨 또는 존재하지 않음
            logger.info(f"Session {session_id} not found (already deleted or expired)")
            return {"success": True, "message": f"Session {session_id} already deleted or expired"}
    
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


@router.get("/sessions")
async def list_sessions() -> Dict[str, Any]:
    """
    활성 세션 목록 조회
    """
    
    session_store = get_session_store()
    all_sessions = [s for s in session_store._sessions.values()]
    
    return {
        "total": len(all_sessions),
        "sessions": [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "last_accessed": getattr(s, 'last_accessed', s.created_at).isoformat(),
                "turn_count": len(s.conversation_history)
            }
            for s in all_sessions
        ]
    }


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    스트리밍 채팅 (WebSocket 대신 SSE 사용)
    
    - 진행 상황을 실시간으로 전송
    - 최종 응답까지 스트리밍
    
    Note: 현재는 기본 구현만 제공. 추후 개선 필요.
    """
    
    async def event_generator():
        error_occurred = False
        try:
            # 시작 이벤트
            yield f"data: {json.dumps({'type': 'start', 'session_id': request.session_id or 'new'})}\n\n"
            
            # 입력 검증 및 로깅
            logger.info(f"Stream request: message='{request.message[:50] if request.message else None}...', owner={request.owner}, repo={request.repo}")
            
            if not request.message or not request.message.strip():
                error_msg = "메시지가 비어있습니다"
                logger.warning(f"Empty message in streaming request")
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                error_occurred = True
            else:
                # owner/repo가 unknown이어도 supervisor가 메시지에서 URL 감지 또는 clarification 처리
                owner = request.owner if request.owner and request.owner != "unknown" else ""
                repo = request.repo if request.repo and request.repo != "unknown" else ""
                
                # Supervisor 실행
                try:
                    logger.info(f"Starting streaming supervisor: message='{request.message[:50]}...', owner={owner or 'None'}, repo={repo or 'None'}")
                    
                    # 의도 분석 단계 이벤트
                    yield f"data: {json.dumps({'type': 'processing', 'step': 'parse_intent', 'message': '의도 분석 중...'})}\n\n"
                    
                    result = await run_supervisor(
                        user_message=request.message,
                        session_id=request.session_id,
                        owner=owner,
                        repo=repo
                    )
                    
                    # 진행 이벤트 (단계별)
                    if result.get("awaiting_clarification"):
                        yield f"data: {json.dumps({'type': 'clarification', 'message': result.get('final_answer', ''), 'session_id': result.get('session_id', '')})}\n\n"
                    else:
                        # target_agent에 따라 적절한 step 메시지 전송
                        target_agent = result.get("target_agent")
                        step_mapping = {
                            "diagnosis": ("run_diagnosis_agent", "프로젝트 진단 중..."),
                            "onboarding": ("run_onboarding_agent", "온보딩 플랜 생성 중..."),
                            "security": ("run_security_agent", "보안 취약점 분석 중..."),
                            "contributor": ("run_onboarding_agent", "기여 가이드 생성 중..."),  # contributor → onboarding
                            "recommend": ("run_recommend_agent", "추천 생성 중..."),
                        }
                        step_info = step_mapping.get(target_agent, ("finalize_answer", "응답 생성 중..."))
                        yield f"data: {json.dumps({'type': 'processing', 'step': step_info[0], 'message': step_info[1]})}\n\n"
                        
                        # 대용량 저장소 경고가 있으면 먼저 전송
                        large_repo_warning = result.get("large_repo_warning")
                        if large_repo_warning:
                            yield f"data: {json.dumps({'type': 'warning', 'message': large_repo_warning})}\n\n"
                        
                        # 최종 응답
                        # 진단 결과는 diagnosis_result 우선, 그 외는 agent_result
                        target_agent_for_result = result.get("target_agent")
                        if target_agent_for_result == "diagnosis":
                            main_agent_result = result.get("diagnosis_result") or result.get("agent_result")
                        else:
                            main_agent_result = result.get("agent_result")
                        
                        response_data = {
                            "type": "answer",
                            "session_id": result.get("session_id", "unknown"),
                            "answer": result.get("final_answer", ""),
                            "suggestions": _generate_suggestions(result),
                            # 저장소 정보 (프론트엔드 동기화용)
                            "repo_info": {
                                "owner": result.get("owner"),
                                "repo": result.get("repo"),
                            } if result.get("owner") and result.get("repo") else None,
                            # 기여 가이드 결과 (finalize_handler_node에서 반환)
                            "contributor_guide": result.get("contributor_guide"),
                            # 구조 시각화 결과 (최상위 레벨)
                            "structure_visualization": result.get("structure_visualization"),
                            "context": {
                                "target_agent": target_agent_for_result,
                                "agent_result_summary": _summarize_agent_result(main_agent_result),
                                "agent_result": main_agent_result,
                                # 멀티 에이전트 결과 (진단+보안 동시 실행 시)
                                "multi_agent_results": result.get("multi_agent_results", {}),
                                # 보안 분석 결과 (단독 필드)
                                "security_result": result.get("security_result") or result.get("multi_agent_results", {}).get("security"),
                                # 온보딩 결과 (단독 필드)
                                "onboarding_result": result.get("onboarding_result") or result.get("multi_agent_results", {}).get("onboarding"),
                                # 구조 시각화 결과
                                "structure_visualization": result.get("structure_visualization"),
                                # 대용량 저장소 경고
                                "large_repo_warning": large_repo_warning,
                            }
                        }
                        yield f"data: {safe_json_dumps(response_data)}\n\n"
                    
                except Exception as e:
                    logger.error(f"Supervisor execution failed in stream: {e}", exc_info=True)
                    error_msg = str(e) if str(e) else f"{type(e).__name__}"
                    if not error_msg or error_msg == "None":
                        error_msg = "알 수 없는 오류가 발생했습니다"
                    yield f"data: {json.dumps({'type': 'error', 'message': f'요청 처리 중 오류: {error_msg[:200]}'})}\n\n"
                    error_occurred = True
            
            # 완료 이벤트
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        except Exception as e:
            logger.error(f"Streaming generator error: {e}", exc_info=True)
            error_msg = str(e) if str(e) else f"{type(e).__name__}"
            if not error_msg or error_msg == "None":
                error_msg = "스트림 생성 중 알 수 없는 오류"
            
            if not error_occurred:
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# === Helper Functions ===

def _summarize_agent_result(agent_result: Optional[Any]) -> Optional[Dict[str, Any]]:
    """에이전트 결과 요약"""
    
    if not agent_result:
        return None
    
    if isinstance(agent_result, dict):
        # DiagnosisResult 요약
        if "health_score" in agent_result:
            return {
                "type": "diagnosis",
                "health_score": agent_result.get("health_score"),
                "onboarding_score": agent_result.get("onboarding_score"),
                "from_cache": agent_result.get("from_cache", False)
            }
        
        # OnboardingPlan 요약
        elif "steps" in agent_result:
            return {
                "type": "onboarding",
                "total_steps": len(agent_result.get("steps", [])),
                "estimated_days": agent_result.get("estimated_days", 0)
            }
        
        # SecurityScanResult 요약
        elif "vulnerabilities" in agent_result:
            vulns = agent_result.get("vulnerabilities", [])
            return {
                "type": "security",
                "total_vulnerabilities": len(vulns),
                "critical_count": sum(1 for v in vulns if v.get("severity") == "critical"),
                "high_count": sum(1 for v in vulns if v.get("severity") == "high")
            }
        
        # ContributorGuide 요약
        elif agent_result.get("type") == "contributor" or "features" in agent_result:
            features = agent_result.get("features", {})
            return {
                "type": "contributor",
                "has_guide": bool(features.get("first_contribution_guide")),
                "has_checklist": bool(features.get("contribution_checklist")),
                "has_community_analysis": bool(features.get("community_analysis")),
                "has_issue_matching": bool(features.get("issue_matching"))
            }
        
        # RecommendResult 요약
        elif agent_result.get("type") == "recommend" or "recommendations" in agent_result:
            recs = agent_result.get("recommendations", [])
            return {
                "type": "recommend",
                "total_recommendations": len(recs),
                "top_match": recs[0].get("full_name") if recs else None
            }
        
        # CompareResult 요약
        elif agent_result.get("type") == "compare" or "compare_results" in agent_result:
            return {
                "type": "compare",
                "repos_compared": len(agent_result.get("compare_repos", [])),
                "has_summary": bool(agent_result.get("compare_summary"))
            }
    
    return {"type": "unknown", "data": str(agent_result)[:100]}


def _generate_suggestions(result: Dict[str, Any]) -> List[str]:
    """추천 질문 생성"""
    
    try:
        # Clarification 요청 시
        if result.get("awaiting_clarification"):
            return []
        
        suggestions = []
        target_agent = result.get("target_agent")
        
        # 진단 결과는 diagnosis_result 우선 사용
        if target_agent == "diagnosis":
            agent_result = result.get("diagnosis_result") or result.get("agent_result")
        else:
            agent_result = result.get("agent_result")
        
        # Diagnosis 결과 기반 추천
        if target_agent == "diagnosis" and isinstance(agent_result, dict):
            health = agent_result.get("health_score", 0)
            
            if health < 50:
                suggestions.append("어떤 부분을 개선하면 좋을까?")
                suggestions.append("초보자 관점에서 다시 설명해줘")
            else:
                suggestions.append("온보딩 플랜 만들어줘")
                suggestions.append("기여 방법 알려줘")
        
        # Onboarding 결과 기반 추천
        elif target_agent == "onboarding":
            suggestions.append("첫 단계부터 자세히 설명해줘")
            suggestions.append("개발 환경 설정 방법은?")
        
        # Security 결과 기반 추천
        elif target_agent == "security":
            suggestions.append("심각한 취약점만 보여줘")
            suggestions.append("해결 방법 추천해줘")
        
        # Contributor 결과 기반 추천
        elif target_agent == "contributor":
            suggestions.append("Good First Issue 추천해줘")
            suggestions.append("커뮤니티 활동 분석해줘")
            suggestions.append("코드 구조 보여줘")
        
        # Recommend 결과 기반 추천
        elif target_agent == "recommend":
            suggestions.append("첫 번째 프로젝트 자세히 분석해줘")
            suggestions.append("다른 기준으로 추천해줘")
        
        # Compare 결과 기반 추천
        elif target_agent == "compare":
            suggestions.append("가장 적합한 프로젝트는?")
            suggestions.append("각 프로젝트 장단점 요약해줘")
        
        # 기본 추천
        if not suggestions:
            suggestions = [
                "더 자세히 설명해줘",
                "다른 관점에서 분석해줘",
                "요약해서 알려줘"
            ]
        
        return suggestions[:3]  # 최대 3개
    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        return ["더 자세히 설명해줘", "다른 관점에서 분석해줘", "요약해서 알려줘"]
