"""
Supervisor Graph - 세션 기반 메타 에이전트
"""

from typing import Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
import logging

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.intent_parser import SupervisorIntentParserV2
from backend.agents.diagnosis.graph import run_diagnosis
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


async def parse_intent_node(state: SupervisorState) -> Dict[str, Any]:
    """의도 파싱 (Supervisor Intent Parser V2)"""
    logger.info("Parsing supervisor intent")
    
    user_message = state["user_message"]
    conversation_history = state.get("conversation_history", [])
    accumulated_context = state.get("accumulated_context", {})
    
    # === 명확한 요청 패턴 바로 라우팅 (LLM 파싱 스킵) ===
    # 저장소가 이미 지정되어 있으므로, 명확한 키워드만 있으면 바로 진행
    msg_lower = user_message.lower()
    
    # === 저장소 감지 (메시지에서 owner/repo 또는 프로젝트명 추출) ===
    import re
    from backend.common.github_client import search_repositories
    
    detected_owner = None
    detected_repo = None
    search_results = None  # GitHub 검색 결과
    
    # owner/repo 패턴 (예: facebook/react, Hyeri-hci/OSSDoctor)
    repo_pattern = r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
    repo_match = re.search(repo_pattern, user_message)
    if repo_match:
        detected_owner = repo_match.group(1)
        detected_repo = repo_match.group(2)
        logger.info(f"Detected repo from message: {detected_owner}/{detected_repo}")
    
    # 단독 프로젝트명 패턴 (예: "react 분석해줘", "OSSDoctor 진단해줘")
    if not detected_repo:
        # 진단/분석 키워드를 제외하고 프로젝트명 추출 시도
        exclude_keywords = [
            "분석", "진단", "해줘", "해주세요", "찾아", "알려", 
            "보여", "전체", "건강도", "온보딩", "보안", "취약점",
            "이", "저장소", "프로젝트", "라는", "를", "을", "좀"
        ]
        
        # 메시지에서 키워드 제거 후 남은 단어 추출
        words = user_message.split()
        potential_project = None
        
        for word in words:
            word_clean = word.strip().lower()
            # 영문자로 시작하고 2자 이상
            if len(word_clean) >= 2 and word_clean[0].isalpha():
                if word_clean not in exclude_keywords:
                    potential_project = word_clean
                    break
        
        # 프로젝트명이 발견되면 GitHub에서 검색
        if potential_project and len(potential_project) >= 2:
            logger.info(f"Searching for project: {potential_project}")
            try:
                search_results = search_repositories(potential_project, max_results=5)
                
                if search_results:
                    # 1순위: 저장소 이름이 정확히 일치하는 것
                    exact_match = None
                    for r in search_results:
                        if r["repo"].lower() == potential_project:
                            exact_match = r
                            break
                    
                    if exact_match:
                        detected_owner = exact_match["owner"]
                        detected_repo = exact_match["repo"]
                        logger.info(f"Exact match found: {detected_owner}/{detected_repo}")
                    elif search_results[0]["stars"] >= 10000:
                        # 2순위: 명확한 1위 (10000 스타 이상이고 이름에 검색어 포함)
                        top = search_results[0]
                        if potential_project in top["repo"].lower():
                            detected_owner = top["owner"]
                            detected_repo = top["repo"]
                            logger.info(f"Top popular match: {detected_owner}/{detected_repo}")
                    # 그 외: clarification으로 선택지 제공
            except Exception as e:
                logger.warning(f"GitHub search failed: {e}")
    
    # 진단/분석 명확한 요청
    diagnosis_keywords = [
        "분석해줘", "분석해주세요", "분석 해줘",
        "진단해줘", "진단해주세요", "진단 해줘",
        "건강도", "건강 점수", "health score", "health",
        "전체 진단", "전체 분석", "full diagnosis",
        "저장소 분석", "저장소 진단", "repo 분석",
        "이 저장소", "이 레포", "this repo"
    ]
    
    is_diagnosis_request = any(kw in msg_lower for kw in diagnosis_keywords)
    
    # "분석", "진단" 단독 사용도 허용
    if not is_diagnosis_request:
        simple_diag_keywords = ["분석", "진단", "diagnose", "analyze"]
        for kw in simple_diag_keywords:
            if kw in msg_lower and len(user_message) < 50:  # 짧은 메시지
                is_diagnosis_request = True
                break
    
    if is_diagnosis_request:
        # 검색 결과가 여러 개이고 명확하지 않으면 clarification 요청
        if search_results and len(search_results) > 1 and not detected_owner:
            # 상위 3개 결과 표시
            options = []
            for i, r in enumerate(search_results[:3], 1):
                stars_str = f"{r['stars']:,}" if r['stars'] >= 1000 else str(r['stars'])
                options.append(f"{i}. {r['full_name']} (스타: {stars_str})")
            
            question = f"다음 중 어떤 저장소를 진단할까요?\n" + "\n".join(options)
            
            # 검색 결과를 컨텍스트에 저장
            new_context = dict(accumulated_context)
            new_context["pending_search_results"] = search_results[:3]
            
            return {
                "supervisor_intent": {
                    "task_type": "diagnosis",
                    "target_agent": "diagnosis",
                    "needs_clarification": True,
                    "confidence": 0.7,
                    "reasoning": "여러 저장소 검색 결과 중 선택 필요"
                },
                "needs_clarification": True,
                "clarification_questions": [question],
                "target_agent": None,
                "accumulated_context": new_context
            }
        
        # 감지된 저장소가 있으면 state 업데이트
        result = {
            "supervisor_intent": {
                "task_type": "diagnosis",
                "target_agent": "diagnosis",
                "needs_clarification": False,
                "confidence": 0.95,
                "reasoning": f"명확한 진단 요청 키워드 감지"
            },
            "needs_clarification": False,
            "clarification_questions": [],
            "target_agent": "diagnosis"
        }
        
        if detected_owner and detected_repo:
            result["owner"] = detected_owner
            result["repo"] = detected_repo
            logger.info(f"Updating target repo to: {detected_owner}/{detected_repo}")
        
        logger.info(f"Direct diagnosis request detected: '{user_message}'")
        return result
    
    # 온보딩 명확한 요청 (경험 수준 포함 시)
    onboarding_keywords = ["온보딩", "기여", "contribute", "참여", "가이드"]
    from backend.common.intent_utils import extract_experience_level
    
    is_onboarding_request = any(kw in msg_lower for kw in onboarding_keywords)
    experience_level = extract_experience_level(user_message)
    
    if is_onboarding_request and experience_level:
        logger.info(f"Direct onboarding request with level: '{experience_level}'")
        new_context = dict(accumulated_context)
        user_profile = new_context.get("user_profile", {})
        user_profile["experience_level"] = experience_level
        new_context["user_profile"] = user_profile
        
        return {
            "supervisor_intent": {
                "task_type": "onboarding",
                "target_agent": "onboarding",
                "needs_clarification": False,
                "confidence": 0.95,
                "reasoning": f"온보딩 요청 + 경험 수준 '{experience_level}' 감지"
            },
            "needs_clarification": False,
            "clarification_questions": [],
            "target_agent": "onboarding",
            "accumulated_context": new_context
        }
    
    # 보안 명확한 요청
    security_keywords = ["보안", "취약점", "security", "cve", "vulnerability"]
    if any(kw in msg_lower for kw in security_keywords):
        logger.info(f"Direct security request detected: '{user_message}'")
        return {
            "supervisor_intent": {
                "task_type": "security",
                "target_agent": "security",
                "needs_clarification": False,
                "confidence": 0.95,
                "reasoning": "명확한 보안 요청 키워드 감지"
            },
            "needs_clarification": False,
            "clarification_questions": [],
            "target_agent": "security"
        }
    
    # === Clarification 응답 처리 (루프 방지) ===
    # 이전 턴이 clarification 요청이었으면, 현재 메시지는 그에 대한 응답
    if conversation_history:
        last_turn = conversation_history[-1] if conversation_history else None
        if last_turn:
            last_response = last_turn.get("agent_response", "")
            last_intent = last_turn.get("resolved_intent", {})
            
            # 이전에 저장소 선택을 물었던 경우 (pending_search_results 확인)
            pending_results = accumulated_context.get("pending_search_results", [])
            if pending_results and ("어떤 저장소를 진단" in last_response):
                msg_stripped = user_message.strip()
                selected_idx = None
                
                # 숫자로 선택
                if msg_stripped == "1":
                    selected_idx = 0
                elif msg_stripped == "2":
                    selected_idx = 1
                elif msg_stripped == "3":
                    selected_idx = 2
                
                if selected_idx is not None and selected_idx < len(pending_results):
                    selected = pending_results[selected_idx]
                    logger.info(f"User selected repo: {selected['full_name']}")
                    
                    # pending 결과 제거
                    new_context = dict(accumulated_context)
                    if "pending_search_results" in new_context:
                        del new_context["pending_search_results"]
                    
                    return {
                        "supervisor_intent": {
                            "task_type": "diagnosis",
                            "target_agent": "diagnosis",
                            "needs_clarification": False,
                            "confidence": 0.95,
                            "reasoning": f"사용자가 {selected['full_name']} 선택"
                        },
                        "needs_clarification": False,
                        "clarification_questions": [],
                        "target_agent": "diagnosis",
                        "owner": selected["owner"],
                        "repo": selected["repo"],
                        "accumulated_context": new_context
                    }
            
            # 이전에 경험 수준을 물었던 경우
            if "경험 수준을 알려주세요" in last_response or last_intent.get("needs_clarification"):
                experience_level = extract_experience_level(user_message)
                
                # 숫자 응답도 처리 (1, 2, 3)
                if not experience_level:
                    msg_stripped = user_message.strip()
                    if msg_stripped == "1" or "1" in msg_stripped:
                        experience_level = "beginner"
                    elif msg_stripped == "2" or "2" in msg_stripped:
                        experience_level = "intermediate"
                    elif msg_stripped == "3" or "3" in msg_stripped:
                        experience_level = "advanced"
                
                if experience_level:
                    logger.info(f"Clarification response detected: experience_level={experience_level}")
                    
                    # accumulated_context에 사용자 프로필 저장
                    new_context = dict(accumulated_context)
                    user_profile = new_context.get("user_profile", {})
                    user_profile["experience_level"] = experience_level
                    new_context["user_profile"] = user_profile
                    
                    # 온보딩으로 바로 라우팅 (재파싱 없이)
                    return {
                        "supervisor_intent": {
                            "task_type": "onboarding",
                            "target_agent": "onboarding",
                            "needs_clarification": False,
                            "confidence": 0.95,
                            "reasoning": f"Clarification 응답에서 경험 수준 '{experience_level}' 감지"
                        },
                        "needs_clarification": False,
                        "clarification_questions": [],
                        "target_agent": "onboarding",
                        "accumulated_context": new_context
                    }
    
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


def check_clarification_node(state: SupervisorState) -> Literal["clarification_response", "route_to_agent"]:
    """Clarification 필요 여부 체크"""
    if state.get("needs_clarification", False):
        return "clarification_response"
    return "route_to_agent"


async def clarification_response_node(state: SupervisorState) -> Dict[str, Any]:
    """명확화 질문 응답"""
    questions = state.get("clarification_questions", [])
    
    response = "다음 정보가 필요합니다:\n"
    for i, q in enumerate(questions, 1):
        response += f"{i}. {q}\n"
    
    return {
        "final_answer": response,
        "awaiting_clarification": True
    }


async def run_diagnosis_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """진단 Agent 실행"""
    logger.info("Running Diagnosis Agent V2")
    
    result = await run_diagnosis(
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


async def run_onboarding_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """온보딩 Agent 실행 - run_onboarding_graph 사용"""
    logger.info("Running Onboarding Agent via graph")
    
    from backend.agents.onboarding.graph import run_onboarding_graph
    
    # 진단 결과가 필요
    accumulated_context = state.get("accumulated_context", {})
    diagnosis_result = accumulated_context.get("diagnosis_result")
    
    if not diagnosis_result:
        logger.warning("Diagnosis result not found, running diagnosis first")
        # Diagnosis 먼저 실행
        diagnosis_result = await run_diagnosis(
            owner=state["owner"],
            repo=state["repo"],
            ref=state.get("ref", "main")
        )
    
    # 사용자 레벨 결정 (세션 컨텍스트나 의도에서 추출)
    session_profile = accumulated_context.get("user_profile", {})
    user_level = session_profile.get("experience_level", "beginner")
    
    # 온보딩 그래프 실행
    try:
        onboarding_result = await run_onboarding_graph(
            owner=state["owner"],
            repo=state["repo"],
            experience_level=user_level,
            diagnosis_summary=diagnosis_result,
            user_context=accumulated_context.get("user_context", {}),
            user_message=state.get("user_message"),
            ref=state.get("ref", "main")
        )
        
        plan = onboarding_result.get("plan", [])
        summary = onboarding_result.get("summary", "")
        
        result = {
            "type": "onboarding_plan",
            "plan": plan,
            "summary": summary or f"{len(plan)}주차 온보딩 가이드가 생성되었습니다.",
            "agent_analysis": onboarding_result.get("agent_analysis", {})
        }
        
        logger.info(f"Onboarding plan created via graph: {len(plan)} weeks")
        
    except Exception as e:
        logger.error(f"Onboarding graph execution failed: {e}", exc_info=True)
        result = {
            "type": "onboarding_plan",
            "error": str(e),
            "message": "온보딩 플랜 생성 중 오류가 발생했습니다."
        }
    
    return {
        "agent_result": result,
        "iteration": state.get("iteration", 0) + 1
    }


async def run_security_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """보안 Agent 실행"""
    logger.info("Running Security Agent")
    
    # Security Agent는 별도 모듈에서 구현
    # 현재는 placeholder 제공
    result = {
        "type": "security_scan",
        "message": "보안 스캔 기능은 security 모듈에서 제공됩니다.",
        "status": "not_implemented"
    }
    
    return {
        "agent_result": result,
        "iteration": state.get("iteration", 0) + 1
    }


async def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
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


async def finalize_answer_node(state: SupervisorState) -> Dict[str, Any]:
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
        owner = agent_result.get("owner", state.get("owner", ""))
        repo = agent_result.get("repo", state.get("repo", ""))
        health_score = agent_result.get("health_score", 0)
        onboarding_score = agent_result.get("onboarding_score", 0)
        health_level = agent_result.get("health_level", "")
        docs_score = agent_result.get("docs_score", 0)
        activity_score = agent_result.get("activity_score", 0)
        
        # 요약 (llm_summary가 있으면 사용, 없으면 구성)
        summary = agent_result.get("llm_summary", "")
        if not summary:
            # llm_summary가 없으면 직접 구성
            warnings = agent_result.get("warnings", [])
            recommendations = agent_result.get("recommendations", [])
            
            summary_parts = []
            if health_score >= 80:
                summary_parts.append(f"전반적으로 건강한 저장소입니다.")
            elif health_score >= 60:
                summary_parts.append(f"보통 수준의 건강도를 보입니다.")
            else:
                summary_parts.append(f"개선이 필요한 상태입니다.")
            
            if warnings:
                summary_parts.append(f"주의사항: {', '.join(warnings[:2])}")
            
            summary = " ".join(summary_parts)
        
        # 주요 발견사항
        key_findings = agent_result.get("key_findings", [])
        findings_text = ""
        if key_findings:
            for finding in key_findings[:3]:
                title = finding.get('title', '')
                desc = finding.get('description', '')
                if title and desc:
                    findings_text += f"- **{title}**: {desc}\n"
                elif title:
                    findings_text += f"- {title}\n"
        else:
            # key_findings가 없으면 recommendations 사용
            recommendations = agent_result.get("recommendations", [])
            if recommendations:
                for rec in recommendations[:3]:
                    findings_text += f"- {rec}\n"
        
        answer = f"""## {owner}/{repo} 진단 결과

**건강도:** {health_score}/100
**온보딩 점수:** {onboarding_score}/100
**문서화 점수:** {docs_score}/100
**활동성 점수:** {activity_score}/100

{summary}

**주요 발견사항:**
{findings_text if findings_text else "- 특이사항 없음"}
"""
        
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
            # plan이 리스트인 경우 (주차별 플랜)
            if isinstance(plan, list):
                steps_preview = "\n".join([
                    f"{i+1}. {step.get('title', step.get('week', f'Week {i+1}'))}" 
                    for i, step in enumerate(plan[:5]) if isinstance(step, dict)
                ])
                more_steps = "\n... (더 보기)" if len(plan) > 5 else ""
                prereqs = ""
                difficulty = "normal"
            else:
                # plan이 dict인 경우
                steps_preview = "\n".join([
                    f"{i+1}. {step.get('title', '')}" 
                    for i, step in enumerate(plan.get('steps', [])[:5]) if isinstance(step, dict)
                ])
                more_steps = "\n... (더 보기)" if len(plan.get('steps', [])) > 5 else ""
                prereqs = ', '.join(plan.get('prerequisites', [])[:3])
                difficulty = plan.get('difficulty', 'normal')
            
            answer = f"""**온보딩 플랜 생성 완료**

{summary}

**주요 단계:**
{steps_preview if steps_preview else "- 상세 단계는 플랜을 참조하세요"}{more_steps}

**난이도:** {difficulty}
{"**필요 사전지식:** " + prereqs if prereqs else ""}
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
        execution_time_ms=0  # TraceManager 연동 시 측정 가능
    )
    
    session_store.update_session(session)
    logger.info(f"Session updated: {session_id}")
    
    return {}


# === 라우팅 함수 ===

def route_to_agent_node(state: SupervisorState) -> Literal[
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

def build_supervisor_graph():
    """Supervisor Graph 빌드"""
    
    graph = StateGraph(SupervisorState)
    
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
    def combined_routing(state: SupervisorState) -> Literal[
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
_supervisor_graph = None

def get_supervisor_graph():
    """Supervisor Graph 싱글톤 인스턴스"""
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = build_supervisor_graph()
        logger.info("Supervisor Graph initialized")
    return _supervisor_graph


# === 편의 함수 ===

async def run_supervisor(
    owner: str,
    repo: str,
    user_message: str,
    session_id: Optional[str] = None,
    ref: str = "main"
) -> Dict[str, Any]:
    """
    Supervisor 실행
    
    Returns:
        {
            "session_id": "uuid",
            "final_answer": "...",
            "suggested_actions": [...],
            "awaiting_clarification": False
        }
    """
    
    graph = get_supervisor_graph()
    
    from typing import cast
    initial_state: SupervisorState = cast(SupervisorState, {
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
