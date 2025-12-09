"""
Supervisor Graph V2 - 간소화 및 세션 기반
메타 에이전트 플로우 통합, 중복 제거
"""

from typing import Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
import logging

from backend.agents.supervisor.models_v2 import SupervisorStateV2
from backend.agents.supervisor.intent_parser_v2 import SupervisorIntentParserV2
from backend.agents.diagnosis.graph_v2 import run_diagnosis_v2
from backend.common.session import get_session_store, Session
from backend.common.trace_manager import get_trace_manager
from backend.common.pronoun_resolver import resolve_pronoun, detect_implicit_context

logger = logging.getLogger(__name__)


# === 헬퍼 함수 ===

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
        from backend.llm.base import ChatRequest, ChatMessage, Role
        import asyncio
        import json
        
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


# === 노드 함수들 ===

async def load_or_create_session_node(state: SupervisorStateV2) -> Dict[str, Any]:
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


async def parse_intent_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """의도 파싱 (Supervisor Intent Parser V2)"""
    logger.info("Parsing supervisor intent")
    
    user_message = state["user_message"]
    conversation_history = state.get("conversation_history", [])
    accumulated_context = state.get("accumulated_context", {})
    
    # 대명사 해결 시도
    resolved_message = user_message
    pronoun_detected = False
    
    try:
        # 타입 변환: Dict -> ConversationTurn, AccumulatedContext
        from backend.common.pronoun_resolver import resolve_pronoun
        from backend.common.session import ConversationTurn, AccumulatedContext
        from typing import List, cast
        
        # conversation_history가 이미 올바른 형식인지 확인
        if conversation_history and isinstance(conversation_history, list):
            # Dict를 ConversationTurn으로 변환
            typed_history: List[ConversationTurn] = []
            for turn in conversation_history:
                if isinstance(turn, dict):
                    typed_history.append(cast(ConversationTurn, turn))  # TypedDict이므로 dict 그대로 사용
            
            # accumulated_context도 마찬가지
            typed_context = cast(AccumulatedContext, accumulated_context if isinstance(accumulated_context, dict) else {})
            
            pronoun_result = resolve_pronoun(
                user_message=user_message,
                conversation_history=typed_history,
                accumulated_context=typed_context
            )
            
            if pronoun_result.get("resolved"):
                pronoun_detected = True
                logger.info(f"Pronoun resolved: {pronoun_result.get('pattern')} -> {pronoun_result.get('refers_to')}")
                
                # 대명사가 해결되면 세션 컨텍스트에 힌트 추가
                # 메시지 자체를 변경하지 않고, 컨텍스트에 정보를 추가
                if pronoun_result.get("refers_to"):
                    accumulated_context = dict(accumulated_context)
                    accumulated_context["last_pronoun_reference"] = pronoun_result
    except Exception as e:
        logger.warning(f"Pronoun resolution failed: {e}")
    
    # 세션 컨텍스트 구성
    session_context = {
        "owner": state["owner"],
        "repo": state["repo"],
        "ref": state.get("ref", "main"),
        "conversation_history": conversation_history,
        "accumulated_context": accumulated_context,
        "pronoun_detected": pronoun_detected
    }
    
    # Intent 파싱
    parser = SupervisorIntentParserV2()
    intent = await parser.parse(
        user_message=resolved_message,
        session_context=session_context
    )
    
    # Clarification 필요 여부
    needs_clarification = intent.needs_clarification
    clarification_questions = intent.clarification_questions
    
    if needs_clarification:
        logger.info(f"Clarification needed: {clarification_questions}")
    
    return {
        "supervisor_intent": intent.dict(),
        "needs_clarification": needs_clarification,
        "clarification_questions": clarification_questions,
        "target_agent": intent.target_agent
    }


def check_clarification_node(state: SupervisorStateV2) -> Literal["clarification_response", "route_to_agent"]:
    """Clarification 필요 여부 체크"""
    if state.get("needs_clarification", False):
        return "clarification_response"
    return "route_to_agent"


async def clarification_response_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """명확화 질문 응답"""
    questions = state.get("clarification_questions", [])
    
    response = "다음 정보가 필요합니다:\n"
    for i, q in enumerate(questions, 1):
        response += f"{i}. {q}\n"
    
    return {
        "final_answer": response,
        "awaiting_clarification": True
    }


async def run_diagnosis_agent_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """진단 Agent 실행"""
    logger.info("Running Diagnosis Agent V2")
    
    result = await run_diagnosis_v2(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main"),
        user_message=state["user_message"],
        supervisor_intent=state.get("supervisor_intent")
    )
    
    return {
        "agent_result": result,
        "iteration": state.get("iteration", 0) + 1
    }


async def run_onboarding_agent_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """온보딩 Agent 실행"""
    logger.info("Running Onboarding Agent")
    
    # 진단 결과가 필요
    accumulated_context = state.get("accumulated_context", {})
    diagnosis_result = accumulated_context.get("diagnosis_result")
    
    if not diagnosis_result:
        logger.warning("Diagnosis result not found, running diagnosis first")
        # Diagnosis 먼저 실행
        diagnosis_result = await run_diagnosis_v2(
            owner=state["owner"],
            repo=state["repo"],
            ref=state.get("ref", "main")
        )
    
    # 사용자 레벨 결정 (세션 컨텍스트나 의도에서 추출)
    supervisor_intent = state.get("supervisor_intent", {})
    user_level = "beginner"  # 기본값
    
    # TODO: 세션에서 사용자 프로필 가져오기
    # session_profile = accumulated_context.get("user_profile", {})
    # user_level = session_profile.get("experience_level", "beginner")
    
    # 온보딩 플랜 생성
    try:
        from backend.agents.recommend.onboarding_plan_generator import generate_onboarding_plan
        
        onboarding_plan = await generate_onboarding_plan(
            owner=state["owner"],
            repo=state["repo"],
            diagnosis_result=diagnosis_result,
            user_level=user_level,
            target_language="ko"
        )
        
        result = {
            "type": "onboarding_plan",
            "plan": onboarding_plan,
            "summary": f"{onboarding_plan.get('total_steps', 0)}단계의 온보딩 가이드가 생성되었습니다. 예상 소요 시간: {onboarding_plan.get('estimated_hours', 0)}시간"
        }
        
        logger.info(f"Onboarding plan created: {onboarding_plan.get('total_steps', 0)} steps")
        
    except Exception as e:
        logger.error(f"Onboarding plan generation failed: {e}", exc_info=True)
        result = {
            "type": "onboarding_plan",
            "error": str(e),
            "message": "온보딩 플랜 생성 중 오류가 발생했습니다."
        }
    
    return {
        "agent_result": result,
        "iteration": state.get("iteration", 0) + 1
    }


async def run_security_agent_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """보안 Agent 실행"""
    logger.info("Running Security Agent")
    
    # TODO: Security Agent 연동
    result = {
        "type": "security_scan",
        "message": "보안 스캔 (구현 예정)"
    }
    
    return {
        "agent_result": result,
        "iteration": state.get("iteration", 0) + 1
    }


async def chat_response_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """일반 채팅 응답"""
    logger.info("Generating chat response")
    
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        import asyncio
        
        llm = fetch_llm_client()
        loop = asyncio.get_event_loop()
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content=state["user_message"])
            ]
        )
        
        response = await loop.run_in_executor(None, llm.chat, request)
        answer = response.content
    except Exception as e:
        logger.warning(f"LLM call failed, using fallback: {e}")
        # Fallback 응답
        answer = f"질문을 받았습니다: {state['user_message']}\n\n저장소 정보가 필요한 경우 owner와 repo를 지정해주세요."
    
    return {
        "agent_result": {"type": "chat", "response": answer},
        "final_answer": answer
    }


async def finalize_answer_node(state: SupervisorStateV2) -> Dict[str, Any]:
    """최종 답변 생성 (대명사 해결 컨텍스트 포함)"""
    logger.info("Finalizing answer")
    
    agent_result = state.get("agent_result")
    
    if not agent_result:
        return {"final_answer": "결과를 생성할 수 없습니다.", "error": "No agent result"}
    
    # 대명사 해결 정보 가져오기
    accumulated_context = state.get("accumulated_context", {})
    pronoun_info = accumulated_context.get("last_pronoun_reference", {})
    user_message = state["user_message"]
    
    # 대명사 참조가 있는 경우 컨텍스트 데이터 가져오기
    referenced_data = None
    if pronoun_info.get("resolved") and pronoun_info.get("confidence", 0) > 0.5:
        refers_to = pronoun_info.get("refers_to")
        if refers_to and refers_to in accumulated_context:
            referenced_data = accumulated_context.get(refers_to)
            logger.info(f"Using referenced data from: {refers_to}")
    
    # 결과 타입에 따라 답변 포맷팅
    result_type = agent_result.get("type", "unknown")
    
    if result_type == "full_diagnosis":
        # 진단 결과 요약
        health_score = agent_result.get("health_score", 0)
        onboarding_score = agent_result.get("onboarding_score", 0)
        summary = agent_result.get("llm_summary", "")
        
        answer = f"""## 진단 결과

**건강도:** {health_score}/100
**온보딩 점수:** {onboarding_score}/100

{summary}

**주요 발견사항:**
"""
        for finding in agent_result.get("key_findings", [])[:3]:
            answer += f"- {finding.get('title', '')}: {finding.get('description', '')}\n"
        
        # 제안 액션
        suggested_actions = [
            {"action": "온보딩 가이드 만들기", "perspective": "beginner"},
            {"action": "다른 관점으로 보기", "perspective": "tech_lead"},
            {"action": "보안 스캔 실행", "type": "security"}
        ]
        
        return {
            "final_answer": answer,
            "suggested_actions": suggested_actions
        }
    
    elif result_type == "quick_query":
        # 빠른 조회 결과
        target = agent_result.get("target", "")
        data = agent_result.get("data", {})
        
        answer = f"## {target.upper()} 정보\n\n"
        
        if target == "readme":
            content = data.get("content", "")
            answer += content[:500] + "..." if len(content) > 500 else content
        else:
            answer += str(data)
        
        return {"final_answer": answer}
    
    elif result_type == "reinterpret":
        # 재해석 결과
        return {"final_answer": agent_result.get("reinterpreted_answer", "")}
    
    elif result_type == "onboarding_plan":
        # 온보딩 플랜 결과
        plan = agent_result.get("plan", {})
        summary = agent_result.get("summary", "")
        
        if plan:
            steps_preview = "\n".join([
                f"{i+1}. {step.get('title', '')}" 
                for i, step in enumerate(plan.get('steps', [])[:5])
            ])
            
            more_steps = "\n... (더 보기)" if len(plan.get('steps', [])) > 5 else ""
            prereqs = ', '.join(plan.get('prerequisites', [])[:3])
            
            answer = f"""**온보딩 플랜 생성 완료**

{summary}

**주요 단계:**
{steps_preview}{more_steps}

**난이도:** {plan.get('difficulty', 'normal')}
**필요 사전지식:** {prereqs}
"""
        else:
            answer = f"**온보딩 플랜**\n\n{agent_result.get('message', '온보딩 플랜이 생성되었습니다.')}"
        
        return {"final_answer": answer}
    
    else:
        # 기타 - 대명사 참조 처리
        answer = str(agent_result.get("message", agent_result.get("response", str(agent_result))))
        
        # 대명사 참조가 있고 referenced_data가 있으면 컨텍스트 추가
        if referenced_data and pronoun_info.get("action") in ["refine", "summarize", "view"]:
            try:
                # LLM으로 컨텍스트를 포함한 응답 생성
                answer = await _enhance_answer_with_context(
                    user_message=user_message,
                    base_answer=answer,
                    referenced_data=referenced_data,
                    action=pronoun_info.get("action"),
                    refers_to=pronoun_info.get("refers_to")
                )
            except Exception as e:
                logger.warning(f"Failed to enhance answer with context: {e}")
        
        return {"final_answer": answer}


async def update_session_node(state: SupervisorStateV2) -> Dict[str, Any]:
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
    
    if agent_result and isinstance(agent_result, dict):
        result_type = agent_result.get("type")
        
        # Diagnosis 결과 저장
        if result_type == "full_diagnosis" or target_agent == "diagnosis":
            data_generated.append("diagnosis_result")
            session.update_context("diagnosis_result", agent_result)
            session.update_context("last_topic", "diagnosis")
            logger.info("Stored diagnosis_result in session context")
        
        # Onboarding 결과 저장
        elif result_type == "onboarding_plan" or target_agent == "onboarding":
            data_generated.append("onboarding_plan")
            session.update_context("onboarding_plan", agent_result)
            session.update_context("last_topic", "onboarding")
            logger.info("Stored onboarding_plan in session context")
        
        # Security 결과 저장
        elif result_type == "security_scan" or target_agent == "security":
            data_generated.append("security_scan")
            session.update_context("security_scan", agent_result)
            session.update_context("last_topic", "security")
            logger.info("Stored security_scan in session context")
        
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
        execution_time_ms=0  # TODO: 실제 측정
    )
    
    session_store.update_session(session)
    logger.info(f"Session updated: {session_id}")
    
    return {}


# === 라우팅 함수 ===

def route_to_agent_node(state: SupervisorStateV2) -> Literal[
    "run_diagnosis_agent", "run_onboarding_agent", "run_security_agent", "chat_response"
]:
    """Target agent로 라우팅"""
    target = state.get("target_agent")
    
    if not target:
        return "chat_response"
    
    if target == "diagnosis":
        return "run_diagnosis_agent"
    elif target == "onboarding":
        return "run_onboarding_agent"
    elif target == "security":
        return "run_security_agent"
    else:
        return "chat_response"


# === 그래프 빌드 ===

def build_supervisor_graph_v2():
    """간소화된 Supervisor Graph V2"""
    
    graph = StateGraph(SupervisorStateV2)
    
    # 노드 추가
    graph.add_node("load_session", load_or_create_session_node)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("clarification_response", clarification_response_node)
    graph.add_node("run_diagnosis_agent", run_diagnosis_agent_node)
    graph.add_node("run_onboarding_agent", run_onboarding_agent_node)
    graph.add_node("run_security_agent", run_security_agent_node)
    graph.add_node("chat_response", chat_response_node)
    graph.add_node("finalize_answer", finalize_answer_node)
    graph.add_node("update_session", update_session_node)
    
    # 엣지 연결
    graph.set_entry_point("load_session")
    graph.add_edge("load_session", "parse_intent")
    
    # Clarification 체크 및 Agent 라우팅
    def combined_routing(state: SupervisorStateV2) -> Literal[
        "clarification_response", "run_diagnosis_agent", "run_onboarding_agent", 
        "run_security_agent", "chat_response"
    ]:
        """Clarification 체크 후 Agent 라우팅"""
        if state.get("needs_clarification", False):
            return "clarification_response"
        
        # Agent 라우팅
        target = state.get("target_agent")
        if not target:
            return "chat_response"
        
        if target == "diagnosis":
            return "run_diagnosis_agent"
        elif target == "onboarding":
            return "run_onboarding_agent"
        elif target == "security":
            return "run_security_agent"
        else:
            return "chat_response"
    
    graph.add_conditional_edges(
        "parse_intent",
        combined_routing,
        {
            "clarification_response": "clarification_response",
            "run_diagnosis_agent": "run_diagnosis_agent",
            "run_onboarding_agent": "run_onboarding_agent",
            "run_security_agent": "run_security_agent",
            "chat_response": "chat_response"
        }
    )
    
    # Clarification 응답 → 종료
    graph.add_edge("clarification_response", "update_session")
    
    # 모든 agent → finalize
    graph.add_edge("run_diagnosis_agent", "finalize_answer")
    graph.add_edge("run_onboarding_agent", "finalize_answer")
    graph.add_edge("run_security_agent", "finalize_answer")
    graph.add_edge("chat_response", "update_session")
    
    # finalize → update_session
    graph.add_edge("finalize_answer", "update_session")
    
    # update_session → END
    graph.add_edge("update_session", END)
    
    return graph.compile()


# === 싱글톤 그래프 ===
_supervisor_graph_v2 = None

def get_supervisor_graph_v2():
    """Supervisor Graph V2 싱글톤 인스턴스"""
    global _supervisor_graph_v2
    if _supervisor_graph_v2 is None:
        _supervisor_graph_v2 = build_supervisor_graph_v2()
        logger.info("Supervisor Graph V2 initialized")
    return _supervisor_graph_v2


# === 편의 함수 ===

async def run_supervisor_v2(
    owner: str,
    repo: str,
    user_message: str,
    session_id: Optional[str] = None,
    ref: str = "main"
) -> Dict[str, Any]:
    """
    Supervisor V2 실행
    
    Returns:
        {
            "session_id": "uuid",
            "final_answer": "...",
            "suggested_actions": [...],
            "awaiting_clarification": False
        }
    """
    
    graph = get_supervisor_graph_v2()
    
    from typing import cast
    initial_state: SupervisorStateV2 = cast(SupervisorStateV2, {
        "session_id": session_id,
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "user_message": user_message,
        "is_new_session": False,
        "supervisor_intent": None,
        "needs_clarification": False,
        "clarification_questions": [],
        "awaiting_clarification": False,
        "conversation_history": [],
        "accumulated_context": {},
        "target_agent": None,
        "agent_params": {},
        "agent_result": None,
        "final_answer": None,
        "suggested_actions": [],
        "iteration": 0,
        "max_iterations": 10,
        "next_node_override": None,
        "error": None,
        "trace_id": None
    })
    
    final_state = await graph.ainvoke(initial_state)
    
    return {
        "session_id": final_state.get("session_id"),
        "final_answer": final_state.get("final_answer"),
        "suggested_actions": final_state.get("suggested_actions", []),
        "awaiting_clarification": final_state.get("awaiting_clarification", False)
    }
