"""
Supervisor Graph - 세션 기반 메타 에이전트
"""

from typing import Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.intent_parser import SupervisorIntentParserV2
from backend.agents.diagnosis.graph import run_diagnosis
from backend.common.session import get_session_store, Session
from backend.common.metrics import get_trace_manager
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
    """
    의도 파싱 (Supervisor Intent Parser V2)
    
    흐름:
    1. 대명사 해결 (맥락 추론)
    2. 저장소 감지 (owner/repo 패턴 + GitHub 검색)
    3. Clarification 응답 처리 (숫자 선택 등)
    4. 세션 컨텍스트 구성
    5. LLM 의도 파싱 (IntentParserV2)
    """
    import re
    from backend.common.github_client import search_repositories
    from backend.common.intent_utils import extract_experience_level
    
    logger.info("Parsing supervisor intent")
    
    user_message = state.get("user_message") or ""
    user_context = state.get("user_context", {}) or {}
    conversation_history = state.get("conversation_history", [])
    accumulated_context = dict(state.get("accumulated_context", {}))
    
    # === user_message가 없으면 기본 진단으로 라우팅 ===
    if not user_message.strip():
        logger.info("No user message provided, defaulting to diagnosis")
        return {
            "supervisor_intent": {
                "task_type": "diagnosis",
                "target_agent": "diagnosis",
                "needs_clarification": False,
                "confidence": 1.0,
                "reasoning": "No user message, defaulting to diagnosis"
            },
            "needs_clarification": False,
            "clarification_questions": [],
            "target_agent": "diagnosis",
            "detected_intent": "diagnose_repo",
            "intent_confidence": 1.0,
            "decision_reason": "No user message provided"
        }
    
    # === 0단계: force_diagnosis 체크 ===
    # /api/analyze/stream에서도 키워드 기반으로 적절한 에이전트 라우팅
    if user_context.get("force_diagnosis"):
        msg_lower_check = user_message.lower()
        
        # 보안 키워드 체크
        security_keywords = ["보안", "취약점", "security", "cve", "vulnerability", "의존성 취약"]
        if any(kw in msg_lower_check for kw in security_keywords):
            logger.info("force_diagnosis: routing to security agent based on keywords")
            return {
                "supervisor_intent": {
                    "task_type": "security",
                    "target_agent": "security",
                    "needs_clarification": False,
                    "confidence": 0.95,
                    "reasoning": "보안 관련 키워드 감지"
                },
                "needs_clarification": False,
                "clarification_questions": [],
                "target_agent": "security",
                "detected_intent": "security_scan",
                "intent_confidence": 0.95,
                "decision_reason": "security keywords detected"
            }
        
        # 온보딩 키워드 체크
        onboarding_keywords = ["온보딩", "기여", "contribute", "가이드", "참여", "시작하고 싶"]
        if any(kw in msg_lower_check for kw in onboarding_keywords):
            logger.info("force_diagnosis: routing to onboarding agent based on keywords")
            return {
                "supervisor_intent": {
                    "task_type": "onboarding",
                    "target_agent": "onboarding",
                    "needs_clarification": False,
                    "confidence": 0.95,
                    "reasoning": "온보딩 관련 키워드 감지"
                },
                "needs_clarification": False,
                "clarification_questions": [],
                "target_agent": "onboarding",
                "detected_intent": "build_onboarding_plan",
                "intent_confidence": 0.95,
                "decision_reason": "onboarding keywords detected"
            }
        
        # 키워드 매칭 실패 + 메시지가 있으면 LLM 의도 파싱
        if user_message.strip():
            logger.info("force_diagnosis: no keyword match, using LLM intent parsing")
            try:
                session_context = {
                    "owner": state.get("owner", ""),
                    "repo": state.get("repo", ""),
                    "accumulated_context": {},
                    "pronoun_detected": False
                }
                
                parser = SupervisorIntentParserV2()
                intent = await parser.parse(
                    user_message=user_message,
                    session_context=session_context
                )
                
                return {
                    "supervisor_intent": intent.dict(),
                    "needs_clarification": intent.needs_clarification,
                    "clarification_questions": intent.clarification_questions,
                    "target_agent": intent.target_agent,
                    "detected_intent": intent.task_type,
                    "intent_confidence": intent.confidence,
                    "decision_reason": f"LLM parsed: {intent.reasoning}"
                }
            except Exception as e:
                logger.warning(f"LLM intent parsing failed: {e}, defaulting to diagnosis")
        
        # 기본값: 진단 (메시지 없거나 LLM 실패)
        logger.info("force_diagnosis: defaulting to diagnosis agent")
        return {
            "supervisor_intent": {
                "task_type": "diagnosis",
                "target_agent": "diagnosis",
                "needs_clarification": False,
                "confidence": 1.0,
                "reasoning": "force_diagnosis flag set (default)"
            },
            "needs_clarification": False,
            "clarification_questions": [],
            "target_agent": "diagnosis",
            "detected_intent": "diagnose_repo",
            "intent_confidence": 1.0,
            "decision_reason": "force_diagnosis flag enabled (default)"
        }
    
    msg_lower = user_message.lower()
    
    # === 1단계: 대명사 해결 (맥락 추론) ===
    resolved_message = user_message
    pronoun_detected = False
    
    try:
        from backend.common.pronoun_resolver import resolve_pronoun
        from backend.common.session import ConversationTurn, AccumulatedContext
        from typing import List, cast
        
        if conversation_history and isinstance(conversation_history, list):
            typed_history: List[ConversationTurn] = []
            for turn in conversation_history:
                if isinstance(turn, dict):
                    typed_history.append(cast(ConversationTurn, turn))
            
            typed_context = cast(AccumulatedContext, accumulated_context)
            
            pronoun_result = resolve_pronoun(
                user_message=user_message,
                conversation_history=typed_history,
                accumulated_context=typed_context
            )
            
            if pronoun_result.get("resolved"):
                pronoun_detected = True
                logger.info(f"Pronoun resolved: {pronoun_result.get('pattern')} -> {pronoun_result.get('refers_to')}")
                accumulated_context["last_pronoun_reference"] = pronoun_result
    except Exception as e:
        logger.warning(f"Pronoun resolution failed: {e}")
    
    # === 2단계: 저장소 감지 ===
    detected_owner = None
    detected_repo = None
    search_results = None
    
    # 2-1. owner/repo 패턴 (예: facebook/react)
    repo_pattern = r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
    repo_match = re.search(repo_pattern, user_message)
    if repo_match:
        detected_owner = repo_match.group(1)
        detected_repo = repo_match.group(2)
        logger.info(f"Detected repo from message: {detected_owner}/{detected_repo}")
        accumulated_context["last_mentioned_repo"] = {
            "owner": detected_owner,
            "repo": detected_repo,
            "full_name": f"{detected_owner}/{detected_repo}"
        }
    
    # 2-2. 단독 프로젝트명 (예: "react 분석해줘")
    if not detected_repo:
        exclude_keywords = [
            "분석", "진단", "해줘", "해주세요", "찾아", "알려", 
            "보여", "전체", "건강도", "온보딩", "보안", "취약점",
            "이", "저장소", "프로젝트", "라는", "를", "을", "좀",
            "뭐야", "뭔가", "어때", "어떻게", "어떤"
        ]
        
        words = user_message.split()
        potential_project = None
        
        for word in words:
            word_clean = word.strip().rstrip("?!는란이가을를").lower()
            if len(word_clean) >= 2 and word_clean[0].isalpha():
                if word_clean not in exclude_keywords:
                    potential_project = word_clean
                    break
        
        if potential_project and len(potential_project) >= 2:
            logger.info(f"Searching for project: {potential_project}")
            try:
                search_results = search_repositories(potential_project, max_results=5)
                
                if search_results:
                    # 정확한 이름 매칭 우선
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
                        top = search_results[0]
                        if potential_project in top["repo"].lower():
                            detected_owner = top["owner"]
                            detected_repo = top["repo"]
                            logger.info(f"Top popular match: {detected_owner}/{detected_repo}")
                    
                    if detected_owner and detected_repo:
                        accumulated_context["last_mentioned_repo"] = {
                            "owner": detected_owner,
                            "repo": detected_repo,
                            "full_name": f"{detected_owner}/{detected_repo}"
                        }
            except Exception as e:
                logger.warning(f"GitHub search failed: {e}")
    
    # 2-3. last_mentioned_repo에서 복원
    if not detected_repo:
        last_mentioned = accumulated_context.get("last_mentioned_repo", {})
        if last_mentioned.get("owner") and last_mentioned.get("repo"):
            detected_owner = last_mentioned["owner"]
            detected_repo = last_mentioned["repo"]
            logger.info(f"Using last mentioned repo: {detected_owner}/{detected_repo}")
    
    # === 3단계: Clarification 응답 처리 (숫자 선택) ===
    # 이전 턴에서 clarification 요청했으면 응답 처리
    if conversation_history:
        last_turn = conversation_history[-1] if conversation_history else None
        if last_turn:
            last_response = last_turn.get("agent_response", "")
            last_intent = last_turn.get("resolved_intent", {})
            
            # 저장소 선택 응답 (pending_search_results)
            pending_results = accumulated_context.get("pending_search_results", [])
            if pending_results and ("어떤 저장소를" in last_response):
                try:
                    selection = int(user_message.strip()) - 1
                    if 0 <= selection < len(pending_results):
                        selected = pending_results[selection]
                        logger.info(f"User selected repo: {selected['full_name']}")
                        
                        new_context = dict(accumulated_context)
                        new_context.pop("pending_search_results", None)
                        new_context["last_mentioned_repo"] = {
                            "owner": selected["owner"],
                            "repo": selected["repo"],
                            "full_name": selected["full_name"]
                        }
                        
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
                except (ValueError, IndexError):
                    pass
            
            # 경험 수준 응답
            if "경험 수준을 알려주세요" in last_response or last_intent.get("needs_clarification"):
                experience_level = extract_experience_level(user_message)
                
                # 숫자 응답 처리
                if not experience_level:
                    msg_stripped = user_message.strip()
                    if msg_stripped == "1":
                        experience_level = "beginner"
                    elif msg_stripped == "2":
                        experience_level = "intermediate"
                    elif msg_stripped == "3":
                        experience_level = "advanced"
                
                if experience_level:
                    logger.info(f"Experience level from clarification: {experience_level}")
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
                            "reasoning": f"Clarification 응답에서 경험 수준 '{experience_level}' 감지"
                        },
                        "needs_clarification": False,
                        "clarification_questions": [],
                        "target_agent": "onboarding",
                        "accumulated_context": new_context
                    }
    
    # === 4단계: 검색 결과가 여러 개면 clarification 요청 ===
    if search_results and len(search_results) > 1 and not detected_owner:
        options = []
        for i, r in enumerate(search_results[:3], 1):
            stars_str = f"{r['stars']:,}" if r['stars'] >= 1000 else str(r['stars'])
            options.append(f"{i}. {r['full_name']} (스타: {stars_str})")
        
        question = f"다음 중 어떤 저장소를 분석할까요?\n" + "\n".join(options)
        
        new_context = dict(accumulated_context)
        new_context["pending_search_results"] = search_results[:3]
        
        return {
            "supervisor_intent": {
                "task_type": "clarification",
                "target_agent": None,
                "needs_clarification": True,
                "confidence": 0.7,
                "reasoning": "여러 저장소 검색 결과 중 선택 필요"
            },
            "needs_clarification": True,
            "clarification_questions": [question],
            "target_agent": None,
            "accumulated_context": new_context
        }
    
    # === 5단계: 세션 컨텍스트 구성 ===
    session_context = {
        "owner": state["owner"],
        "repo": state["repo"],
        "ref": state.get("ref", "main"),
        "conversation_history": conversation_history,
        "accumulated_context": accumulated_context,
        "pronoun_detected": pronoun_detected,
        "detected_repo": f"{detected_owner}/{detected_repo}" if detected_owner else None
    }
    
    # === 6단계: LLM 의도 파싱 ===
    parser = SupervisorIntentParserV2()
    intent = await parser.parse(
        user_message=resolved_message,
        session_context=session_context
    )
    
    needs_clarification = intent.needs_clarification
    clarification_questions = intent.clarification_questions
    
    if needs_clarification:
        logger.info(f"Clarification needed: {clarification_questions}")
    
    result = {
        "supervisor_intent": intent.dict(),
        "needs_clarification": needs_clarification,
        "clarification_questions": clarification_questions,
        "target_agent": intent.target_agent,
        "additional_agents": intent.additional_agents,  # 멀티 에이전트 협업
        "accumulated_context": accumulated_context
    }
    
    # LLM이 detected_repo를 반환했으면 세션 업데이트
    if intent.detected_repo:
        try:
            parts = intent.detected_repo.split("/")
            if len(parts) == 2:
                result["owner"] = parts[0]
                result["repo"] = parts[1]
                logger.info(f"LLM detected repo: {intent.detected_repo}")
                
                accumulated_context["last_mentioned_repo"] = {
                    "owner": parts[0],
                    "repo": parts[1],
                    "full_name": intent.detected_repo
                }
                result["accumulated_context"] = accumulated_context
        except Exception as e:
            logger.warning(f"Failed to parse detected_repo: {e}")
    
    # 규칙 기반 detected_owner/detected_repo 우선
    if detected_owner and detected_repo:
        result["owner"] = detected_owner
        result["repo"] = detected_repo
        logger.info(f"Using pre-detected repo: {detected_owner}/{detected_repo}")
    
    return result


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
    """보안 Agent 실행 (SecurityAgent 연결)"""
    import os
    logger.info("Running Security Agent")
    
    try:
        from backend.agents.security.agent.security_agent import SecurityAgent
        
        # SecurityAgent 초기화
        agent = SecurityAgent(
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "gpt-4"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            execution_mode="fast"  # supervisor에서는 빠른 모드 사용
        )
        
        # 분석 요청 구성
        user_message = state.get("user_message", "")
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        # SecurityAgent 실행
        result = await agent.analyze(
            user_request=user_message if user_message else f"{owner}/{repo} 보안 분석",
            owner=owner,
            repository=repo,
            github_token=os.getenv("GITHUB_TOKEN")
        )
        
        logger.info(f"Security analysis completed: success={result.get('success', False)}")
        
        # type 필드 추가 (finalize_answer_node에서 사용)
        result["type"] = "security_scan"
        
        return {
            "agent_result": result,
            "security_result": result,  # finalize에서 사용
            "iteration": state.get("iteration", 0) + 1
        }
        
    except ImportError as e:
        logger.warning(f"SecurityAgent import failed: {e}")
        return {
            "agent_result": {
                "type": "security_scan",
                "message": f"보안 에이전트 모듈 로드 실패: {e}",
                "status": "import_error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception as e:
        logger.error(f"Security analysis failed: {e}")
        return {
            "agent_result": {
                "type": "security_scan",
                "message": f"보안 분석 오류: {e}",
                "status": "error"
            },
            "iteration": state.get("iteration", 0) + 1
        }


async def run_contributor_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """신규 기여자 지원 에이전트 실행 (첫 기여 가이드, 이슈 매칭, 체크리스트 등)"""
    logger.info("Running Contributor Agent")
    
    try:
        from backend.common.contribution_guide import (
            generate_first_contribution_guide,
            format_guide_as_markdown,
            generate_contribution_checklist,
            format_checklist_as_markdown
        )
        from backend.common.issue_matcher import (
            match_issues_to_user,
            format_matched_issues_as_markdown
        )
        from backend.common.structure_visualizer import (
            generate_structure_visualization,
            format_structure_as_markdown
        )
        from backend.common.community_analyzer import (
            analyze_community_activity,
            format_community_analysis_as_markdown
        )
        
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        user_message = state.get("user_message", "").lower()
        
        result = {
            "type": "contributor",
            "owner": owner,
            "repo": repo,
            "features": {}
        }
        
        # 첫 기여 가이드 (기본 제공)
        guide = generate_first_contribution_guide(owner, repo)
        result["features"]["first_contribution_guide"] = guide
        
        # 기여 체크리스트 (기본 제공)
        checklist = generate_contribution_checklist(owner, repo)
        result["features"]["contribution_checklist"] = checklist
        
        # 요청에 따라 추가 기능 활성화
        if any(kw in user_message for kw in ["구조", "폴더", "structure"]):
            # 코드 구조 시각화 (파일 트리 필요 - accumulated_context에서 가져옴)
            accumulated_context = state.get("accumulated_context", {})
            file_tree = accumulated_context.get("file_tree", [])
            if file_tree:
                visualization = generate_structure_visualization(owner, repo, file_tree)
                result["features"]["structure_visualization"] = visualization
        
        if any(kw in user_message for kw in ["이슈", "issue", "good first"]):
            # Good First Issue 매칭 (accumulated_context에서 이슈 정보 가져옴)
            accumulated_context = state.get("accumulated_context", {})
            issues = accumulated_context.get("open_issues", [])
            if issues:
                matched = match_issues_to_user(issues, experience_level="beginner")
                result["features"]["issue_matching"] = matched
        
        if any(kw in user_message for kw in ["커뮤니티", "활동", "community"]):
            # 커뮤니티 활동 분석
            accumulated_context = state.get("accumulated_context", {})
            prs = accumulated_context.get("recent_prs", [])
            issues = accumulated_context.get("recent_issues", [])
            contributors = accumulated_context.get("contributors", [])
            
            community = analyze_community_activity(
                owner, repo, 
                recent_prs=prs, 
                recent_issues=issues, 
                contributors=contributors
            )
            result["features"]["community_analysis"] = community
        
        # 마크다운 요약 생성
        summary_md = f"# {owner}/{repo} 기여 가이드\n\n"
        summary_md += format_guide_as_markdown(guide)
        summary_md += "\n---\n"
        summary_md += format_checklist_as_markdown(checklist)
        result["summary_markdown"] = summary_md
        
        logger.info(f"Contributor agent completed: {list(result['features'].keys())}")
        
        return {
            "agent_result": result,
            "iteration": state.get("iteration", 0) + 1
        }
        
    except ImportError as e:
        logger.warning(f"Contributor agent import failed: {e}")
        return {
            "agent_result": {
                "type": "contributor",
                "message": f"기여자 지원 모듈 로드 실패: {e}",
                "status": "import_error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception as e:
        logger.error(f"Contributor agent failed: {e}")
        return {
            "agent_result": {
                "type": "contributor",
                "message": f"기여자 지원 실행 오류: {e}",
                "status": "error"
            },
            "iteration": state.get("iteration", 0) + 1
        }


async def run_recommend_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """추천 에이전트 실행 (onboarding 점수 기반 프로젝트 추천)"""
    logger.info("Running Recommend Agent")
    
    try:
        from backend.agents.recommend.agent.graph import run_recommend
        
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        user_message = state.get("user_message", "")
        
        # 추천 에이전트 실행
        result = await run_recommend(
            owner=owner,
            repo=repo,
            user_message=user_message
        )
        
        # 결과 포맷팅
        search_results = result.get("search_results", [])
        final_summary = result.get("final_summary", "")
        
        formatted_result = {
            "type": "recommend",
            "recommendations": [],
            "summary": final_summary
        }
        
        # onboarding 점수 기준 필터링 (70점 이상)
        for item in search_results:
            # RecommendSnapshot 객체인 경우 속성 접근
            if hasattr(item, "onboarding_score"):
                onboarding_score = item.onboarding_score or 0
                if onboarding_score >= 70:
                    formatted_result["recommendations"].append({
                        "name": getattr(item, "name", ""),
                        "full_name": getattr(item, "full_name", ""),
                        "description": getattr(item, "description", ""),
                        "stars": getattr(item, "stars", 0),
                        "onboarding_score": onboarding_score,
                        "ai_reason": getattr(item, "ai_reason", "")
                    })
            elif isinstance(item, dict):
                onboarding_score = item.get("onboarding_score", 0) or 0
                if onboarding_score >= 70:
                    formatted_result["recommendations"].append(item)
        
        logger.info(f"Recommend agent completed: {len(formatted_result['recommendations'])} projects")
        
        return {
            "agent_result": formatted_result,
            "iteration": state.get("iteration", 0) + 1
        }
        
    except ImportError as e:
        logger.warning(f"Recommend agent import failed: {e}")
        return {
            "agent_result": {
                "type": "recommend",
                "message": f"추천 에이전트 모듈 로드 실패: {e}",
                "status": "import_error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception as e:
        logger.error(f"Recommend agent failed: {e}")
        return {
            "agent_result": {
                "type": "recommend",
                "message": f"추천 실행 오류: {e}",
                "status": "error"
            },
            "iteration": state.get("iteration", 0) + 1
        }


async def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
    """일반 채팅 응답"""
    logger.info("Generating chat response")
    
    user_message = state.get("user_message") or ""
    
    # user_message가 비어있으면 기본 응답
    if not user_message.strip():
        answer = "안녕하세요! 저장소 분석이나 질문이 있으시면 말씀해주세요."
        return {
            "agent_result": {"type": "chat", "response": answer},
            "final_answer": answer
        }
    
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        import asyncio
        
        llm = fetch_llm_client()
        loop = asyncio.get_event_loop()
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content=user_message)
            ]
        )
        
        response = await loop.run_in_executor(None, llm.chat, request)
        answer = response.content
    except Exception as e:
        logger.warning(f"LLM call failed, using fallback: {e}")
        # Fallback 응답
        answer = f"질문을 받았습니다: {user_message}\n\n저장소 정보가 필요한 경우 owner와 repo를 지정해주세요."
    
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
        
        # 프로액티브 제안 (점수 기반 조건부 생성)
        suggested_actions = []
        
        # 건강도가 낮으면 보안 점검 추천
        if health_score < 50:
            suggested_actions.append({
                "action": "보안 취약점 점검 추천",
                "type": "security",
                "reason": f"건강도가 {health_score}점으로 낮습니다. 보안 점검을 권장합니다."
            })
        
        # 온보딩 점수가 높으면 기여 가이드 추천
        if onboarding_score >= 70:
            suggested_actions.append({
                "action": "기여 가이드 생성 가능",
                "type": "onboarding",
                "reason": f"온보딩 점수가 {onboarding_score}점으로 높습니다. 기여 가이드를 만들어 보세요."
            })
        
        # 기본 제안 추가
        suggested_actions.extend([
            {"action": "온보딩 가이드 만들기", "type": "onboarding"},
            {"action": "보안 스캔 실행", "type": "security"}
        ])
        
        # AI 판단 근거 (Agentic 요소 가시화)
        decision_reason = state.get("decision_reason", "")
        supervisor_intent = state.get("supervisor_intent", {})
        reasoning = supervisor_intent.get("reasoning", "") if isinstance(supervisor_intent, dict) else ""
        
        # 다음 단계 안내 (진단→온보딩 연결)
        next_steps = """
---
**다음 단계:**
이 저장소에 기여하고 싶다면 `온보딩 가이드 만들어줘`라고 말해보세요!
보안 취약점이 걱정된다면 `보안 분석해줘`라고 요청하세요.
"""
        
        # AI 판단 근거 섹션 (reasoning이 있으면 표시)
        ai_trace = ""
        if reasoning or decision_reason:
            ai_trace = f"""
---
**[AI 판단 과정]**
{reasoning or decision_reason}
"""
        
        answer = answer + ai_trace + next_steps
        
        return {
            "final_answer": answer,
            "suggested_actions": suggested_actions,
            "decision_trace": {
                "reasoning": reasoning,
                "decision_reason": decision_reason,
                "target_agent": state.get("target_agent"),
                "intent_confidence": state.get("intent_confidence", 0)
            }
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
    
    elif result_type == "security_scan":
        # 보안 분석 결과
        results = agent_result.get("results", {})
        security_score = results.get("security_score", agent_result.get("security_score"))
        security_grade = results.get("security_grade", agent_result.get("security_grade", "N/A"))
        risk_level = results.get("risk_level", agent_result.get("risk_level", "unknown"))
        vulnerabilities = results.get("vulnerabilities", {})
        vuln_total = vulnerabilities.get("total", 0)
        vuln_critical = vulnerabilities.get("critical", 0)
        vuln_high = vulnerabilities.get("high", 0)
        vuln_medium = vulnerabilities.get("medium", 0)
        vuln_low = vulnerabilities.get("low", 0)
        
        # 취약점 요약
        if vuln_total == 0:
            vuln_summary = "발견된 취약점이 없습니다."
        else:
            parts = []
            if vuln_critical > 0:
                parts.append(f"🔴 Critical: {vuln_critical}")
            if vuln_high > 0:
                parts.append(f"🟠 High: {vuln_high}")
            if vuln_medium > 0:
                parts.append(f"🟡 Medium: {vuln_medium}")
            if vuln_low > 0:
                parts.append(f"🟢 Low: {vuln_low}")
            vuln_summary = " | ".join(parts) if parts else f"총 {vuln_total}개의 취약점"
        
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        answer = f"""## {owner}/{repo} 보안 분석 결과

**보안 점수:** {security_score}/100 (등급: {security_grade})
**위험도:** {risk_level}

### 취약점 현황
{vuln_summary}

보안 분석이 완료되었습니다. 상세 정보는 우측 보고서의 "보안 분석" 섹션에서 확인하세요.
"""
        
        return {"final_answer": answer}
    
    elif result_type == "contributor":
        # 기여자 가이드 결과
        features = agent_result.get("features", {})
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        guide = features.get("first_contribution_guide", {})
        checklist = features.get("contribution_checklist", {})
        
        # 첫 기여 가이드 요약
        guide_summary = ""
        steps = guide.get("steps", [])
        if steps:
            guide_summary = "\n".join([
                f"{i+1}. {step.get('title', '')}"
                for i, step in enumerate(steps[:5])
            ])
        
        # 체크리스트 요약
        checklist_items = checklist.get("items", [])
        checklist_summary = ""
        if checklist_items:
            high_priority = [item for item in checklist_items if item.get("priority") == "high"]
            checklist_summary = "\n".join([f"  - {item.get('title', '')}" for item in high_priority[:3]])
        
        answer = f"""## {owner}/{repo} 기여자 가이드

**첫 기여를 위한 단계별 가이드가 준비되었습니다!**

### 주요 단계
{guide_summary if guide_summary else "상세 가이드를 우측 리포트에서 확인하세요."}

### PR 제출 전 필수 체크
{checklist_summary if checklist_summary else "체크리스트를 우측 리포트에서 확인하세요."}

---
**팁:** 우측의 \"기여자 가이드\" 섹션에서 상세 정보와 체크리스트를 확인할 수 있습니다.
Good First Issue를 찾으시려면 `이슈 추천해줘`라고 말해보세요!
"""
        
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
    
    result_updates = {}  # 최종 state에 반환할 값들
    
    if agent_result and isinstance(agent_result, dict):
        result_type = agent_result.get("type")
        
        # Diagnosis 결과 저장
        if result_type == "full_diagnosis" or target_agent == "diagnosis":
            data_generated.append("diagnosis_result")
            session.update_context("diagnosis_result", agent_result)
            session.update_context("last_topic", "diagnosis")
            result_updates["diagnosis_result"] = agent_result  # state에도 반환
            logger.info("Stored diagnosis_result in session context")
        
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
    
    session_store.update_session(session)
    logger.info(f"Session updated: {session_id}")
    
    return result_updates


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


async def run_additional_agents_node(state: SupervisorState) -> Dict[str, Any]:
    """추가 에이전트 순차 실행 (멀티 에이전트 협업)"""
    additional_agents = state.get("additional_agents", [])
    
    if not additional_agents:
        return {}
    
    logger.info(f"Running additional agents: {additional_agents}")
    
    multi_agent_results = dict(state.get("multi_agent_results", {}))
    
    # 메인 에이전트 결과 저장
    main_result = state.get("agent_result")
    target_agent = state.get("target_agent")
    if main_result and target_agent:
        multi_agent_results[target_agent] = main_result
    
    for agent_name in additional_agents:
        logger.info(f"Running additional agent: {agent_name}")
        
        try:
            if agent_name == "diagnosis":
                result = await run_diagnosis_agent_node(state)
                multi_agent_results["diagnosis"] = result.get("agent_result", result)
                
            elif agent_name == "security":
                result = await run_security_agent_node(state)
                multi_agent_results["security"] = result.get("agent_result", result)
                
            elif agent_name == "onboarding":
                result = await run_onboarding_agent_node(state)
                multi_agent_results["onboarding"] = result.get("agent_result", result)
                
            elif agent_name == "contributor":
                result = await run_contributor_agent_node(state)
                multi_agent_results["contributor"] = result.get("agent_result", result)
                
        except Exception as e:
            logger.error(f"Additional agent {agent_name} failed: {e}")
            multi_agent_results[agent_name] = {"error": str(e)}
    
    logger.info(f"Multi-agent execution completed: {list(multi_agent_results.keys())}")
    
    return {
        "multi_agent_results": multi_agent_results,
        "iteration": state.get("iteration", 0) + 1
    }


# === 그래프 빌드 ===

def build_supervisor_graph(enable_hitl: bool = False):
    """
    Supervisor Graph 빌드
    
    Args:
        enable_hitl: Human-in-the-Loop 패턴 활성화.
                     True면 clarification_response 노드 전에 중단.
    """
    
    graph = StateGraph(SupervisorState)
    
    # 노드 추가
    graph.add_node("load_session", load_or_create_session_node)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("clarification_response", clarification_response_node)
    graph.add_node("run_diagnosis_agent", run_diagnosis_agent_node)
    graph.add_node("run_onboarding_agent", run_onboarding_agent_node)
    graph.add_node("run_security_agent", run_security_agent_node)
    graph.add_node("run_recommend_agent", run_recommend_agent_node)
    graph.add_node("run_contributor_agent", run_contributor_agent_node)
    graph.add_node("chat_response", chat_response_node)
    graph.add_node("finalize_answer", finalize_answer_node)
    graph.add_node("update_session", update_session_node)
    
    # 엣지 연결
    graph.set_entry_point("load_session")
    graph.add_edge("load_session", "parse_intent")
    
    # Clarification 체크 및 Agent 라우팅
    def combined_routing(state: SupervisorState) -> Literal[
        "clarification_response", "run_diagnosis_agent", "run_onboarding_agent", 
        "run_security_agent", "run_recommend_agent", "run_contributor_agent", "chat_response"
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
        elif target == "recommend":
            return "run_recommend_agent"
        elif target == "contributor":
            return "run_contributor_agent"
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
            "run_recommend_agent": "run_recommend_agent",
            "run_contributor_agent": "run_contributor_agent",
            "chat_response": "chat_response"
        }
    )
    
    # Clarification 응답 → 종료
    graph.add_edge("clarification_response", "update_session")
    
    # 추가 에이전트 실행 노드
    graph.add_node("run_additional_agents", run_additional_agents_node)
    
    # 모든 agent → run_additional_agents → finalize
    graph.add_edge("run_diagnosis_agent", "run_additional_agents")
    graph.add_edge("run_onboarding_agent", "run_additional_agents")
    graph.add_edge("run_security_agent", "run_additional_agents")
    graph.add_edge("run_recommend_agent", "run_additional_agents")
    graph.add_edge("run_contributor_agent", "run_additional_agents")
    graph.add_edge("run_additional_agents", "finalize_answer")
    graph.add_edge("chat_response", "update_session")
    
    # finalize → update_session
    graph.add_edge("finalize_answer", "update_session")
    
    # update_session → END
    graph.add_edge("update_session", END)
    
    return graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["clarification_response"] if enable_hitl else None
    )


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
        "awaiting_clarification": final_state.get("awaiting_clarification", False),
        "target_agent": final_state.get("target_agent"),
        "agent_result": final_state.get("agent_result"),
        "needs_clarification": final_state.get("needs_clarification", False),
    }
