"""
세션 관련 노드
"""

from typing import Dict, Any
import logging
from datetime import datetime

from backend.agents.supervisor.models import SupervisorState
from backend.common.session import get_session_store

logger = logging.getLogger(__name__)


async def load_or_create_session_node(state: SupervisorState) -> Dict[str, Any]:
    """세션 로드 또는 생성"""
    session_store = get_session_store()
    
    session_id = state.get("session_id")
    
    if session_id:
        # 기존 세션 로드
        session = session_store.get_session(session_id)
        if session:
            logger.info(f"Session loaded: {session_id}")
            return {
                "is_new_session": False,
                "conversation_history": session.conversation_history,
                "accumulated_context": dict(session.accumulated_context)
            }
        else:
            logger.warning(f"Session not found or expired: {session_id}")
    
    # 새 세션 생성
    session = session_store.create_session(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main")
    )
    
    logger.info(f"New session created: {session.session_id}")
    
    return {
        "session_id": session.session_id,
        "is_new_session": True,
        "conversation_history": [],
        "accumulated_context": {}
    }


async def update_session_node(state: SupervisorState) -> Dict[str, Any]:
    """세션 업데이트"""
    session_id = state.get("session_id")
    if not session_id:
        return {}
    
    session_store = get_session_store()
    session = session_store.get_session(session_id)
    
    if not session:
        logger.warning(f"Session not found for update: {session_id}")
        return {}
    
    # 턴 추가
    data_generated = []
    agent_result = state.get("agent_result")
    target_agent = state.get("target_agent")
    
    result_updates = {}  # 최종 state에 반환할 값들
    
    if agent_result and isinstance(agent_result, dict):
        result_type = agent_result.get("type")
        
        # Diagnosis 결과 저장
        if result_type == "full_diagnosis" or target_agent == "diagnosis":
            data_generated.append("diagnosis_result")
            session.update_context("diagnosis_result", agent_result)
            session.update_context("last_topic", "diagnosis")
            result_updates["diagnosis_result"] = agent_result  # state에도 반환
            
            # 분석된 저장소 목록에 추가
            repo_info = {
                "owner": agent_result.get("owner", session.owner),
                "repo": agent_result.get("repo", session.repo),
                "health_score": agent_result.get("health_score", 0),
                "analyzed_at": datetime.now().isoformat()
            }
            session.add_analyzed_repo(repo_info)
            logger.info(f"Stored diagnosis_result and added to analyzed_repos: {repo_info['owner']}/{repo_info['repo']}")
        
        # Onboarding 결과 저장
        elif result_type == "onboarding_plan" or target_agent == "onboarding":
            data_generated.append("onboarding_plan")
            session.update_context("onboarding_plan", agent_result)
            session.update_context("last_topic", "onboarding")
            result_updates["onboarding_result"] = agent_result
            logger.info("Stored onboarding_plan in session context")
        
        # Security 결과 저장
        elif result_type == "security_scan" or target_agent == "security":
            data_generated.append("security_scan")
            session.update_context("security_scan", agent_result)
            session.update_context("last_topic", "security")
            result_updates["security_result"] = agent_result
            logger.info("Stored security_scan in session context")
        
        # Contributor 결과 저장
        elif result_type == "contributor" or target_agent == "contributor":
            data_generated.append("contributor_guide")
            session.update_context("contributor_guide", agent_result)
            session.update_context("last_topic", "contributor")
            result_updates["contributor_result"] = agent_result
            logger.info("Stored contributor_guide in session context")
        
        # Chat 결과도 저장 (참조 가능하도록)
        elif result_type == "chat" or target_agent == "chat":
            session.update_context("last_chat_response", agent_result)
            session.update_context("last_topic", "chat")
            logger.info("Stored chat response in session context")
    
    session.add_turn(
        user_message=state["user_message"],
        resolved_intent=state.get("supervisor_intent") or {},
        execution_path=state.get("target_agent") or "unknown",
        agent_response=state.get("final_answer") or "",
        data_generated=data_generated,
        execution_time_ms=0  # TraceManager 연동 시 측정 가능
    )
    
    # multi_agent_results에서 추가 에이전트 결과 저장 (병렬 실행된 결과)
    multi_agent_results = state.get("multi_agent_results", {})
    if multi_agent_results:
        # Security 결과 저장
        security_from_multi = multi_agent_results.get("security")
        if security_from_multi and isinstance(security_from_multi, dict):
            if "security_scan" not in data_generated:
                data_generated.append("security_scan")
            session.update_context("security_scan", security_from_multi)
            result_updates["security_result"] = security_from_multi
            logger.info("Stored security result from multi_agent_results in session context")
        
        # Onboarding 결과 저장
        onboarding_from_multi = multi_agent_results.get("onboarding")
        if onboarding_from_multi and isinstance(onboarding_from_multi, dict):
            if "onboarding_plan" not in data_generated:
                data_generated.append("onboarding_plan")
            session.update_context("onboarding_plan", onboarding_from_multi)
            result_updates["onboarding_result"] = onboarding_from_multi
            logger.info("Stored onboarding result from multi_agent_results in session context")
        
        # Diagnosis 결과 저장
        diagnosis_from_multi = multi_agent_results.get("diagnosis")
        if diagnosis_from_multi and isinstance(diagnosis_from_multi, dict):
            if "diagnosis_result" not in data_generated:
                data_generated.append("diagnosis_result")
            session.update_context("diagnosis_result", diagnosis_from_multi)
            result_updates["diagnosis_result"] = diagnosis_from_multi
            logger.info("Stored diagnosis result from multi_agent_results in session context")
    
    # accumulated_context의 last_mentioned_repo 등을 세션에 저장
    accumulated_ctx = state.get("accumulated_context", {})
    if accumulated_ctx:
        last_mentioned = accumulated_ctx.get("last_mentioned_repo")
        if last_mentioned:
            session.update_context("last_mentioned_repo", last_mentioned)
            logger.info(f"Stored last_mentioned_repo in session: {last_mentioned.get('full_name')}")
        
        # user_profile도 저장 (경험 수준 등)
        user_profile = accumulated_ctx.get("user_profile")
        if user_profile:
            session.update_context("user_profile", user_profile)
            logger.info(f"Stored user_profile in session: {user_profile}")
        
        # pending_request 저장 (clarification 응답 합치기용)
        pending_request = accumulated_ctx.get("pending_request")
        if pending_request:
            session.update_context("pending_request", pending_request)
            logger.info(f"Stored pending_request in session: {pending_request.get('original_message', '')[:50]}...")
    
    session_store.update_session(session)
    logger.info(f"Session updated: {session_id}")
    
    return result_updates
