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

async def check_repo_size_and_warn(owner: str, repo: str) -> Dict[str, Any]:
    """
    저장소 크기 체크 및 대용량 저장소 경고 생성
    
    Returns:
        Dict with:
        - is_large: 대용량 여부
        - warning_message: 경고 메시지 (대용량일 경우)
        - estimated_time: 예상 시간 (초)
        - repo_stats: 저장소 통계
    """
    import aiohttp
    import os
    
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    result = {
        "is_large": False,
        "warning_message": None,
        "estimated_time": 30,  # 기본 30초
        "repo_stats": {}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # 저장소 기본 정보 가져오기
            async with session.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    repo_data = await resp.json()
                    size_kb = repo_data.get("size", 0)  # KB 단위
                    size_mb = size_kb / 1024
                    
                    result["repo_stats"] = {
                        "size_mb": round(size_mb, 2),
                        "stars": repo_data.get("stargazers_count", 0),
                        "forks": repo_data.get("forks_count", 0),
                        "open_issues": repo_data.get("open_issues_count", 0)
                    }
                    
                    # 대용량 기준: 100MB 이상 또는 star 10000개 이상 (큰 프로젝트)
                    if size_mb > 100 or repo_data.get("stargazers_count", 0) > 10000:
                        result["is_large"] = True
                        
                        # 크기에 따른 예상 시간 계산
                        if size_mb > 500:
                            result["estimated_time"] = 180  # 3분
                            time_str = "약 3분"
                        elif size_mb > 200:
                            result["estimated_time"] = 120  # 2분
                            time_str = "약 2분"
                        else:
                            result["estimated_time"] = 60  # 1분
                            time_str = "약 1분"
                        
                        result["warning_message"] = (
                            f"⏳ **{owner}/{repo}**는 대용량 저장소입니다 "
                            f"(크기: {size_mb:.1f}MB, Stars: {repo_data.get('stargazers_count', 0):,}). "
                            f"분석에 {time_str} 정도 소요될 수 있습니다. 잠시만 기다려주세요..."
                        )
                        
                        logger.info(f"Large repo detected: {owner}/{repo} ({size_mb:.1f}MB)")
    except Exception as e:
        logger.warning(f"Failed to check repo size: {e}")
    
    return result


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
    
    # === 0단계: 이전 clarification 요청에 대한 응답 처리 ===
    # pending_request가 있으면 원래 요청과 현재 응답을 합침
    # 단, 현재 메시지가 새로운 의도(분석/진단)면 합치지 않고 새 요청으로 처리
    pending_request = accumulated_context.get("pending_request")
    if pending_request:
        original_message = pending_request.get("original_message", "")
        original_task_type = pending_request.get("task_type", "")
        
        # 현재 메시지가 분석/진단 요청인지 체크 (의도 변경 감지)
        diagnosis_keywords = ["분석해", "진단해", "analyze", "diagnose", "확인해봐", "살펴봐"]
        is_new_diagnosis_intent = any(kw in msg_lower for kw in diagnosis_keywords)
        
        if is_new_diagnosis_intent and original_task_type == "recommend":
            # 의도 변경 감지: recommend → diagnosis
            # pending_request를 클리어하고 새로운 진단 요청으로 처리
            logger.info(f"Intent change detected: '{original_task_type}' → 'diagnosis', skipping pending_request merge")
            del accumulated_context["pending_request"]
            # 세션에 저장된 추천 결과에서 '첫 번째 프로젝트' 등 참조 해결 필요
            # 이건 대명사 해결 단계에서 처리됨
        else:
            # 일반적인 clarification 응답: 합치기
            combined_message = f"{original_message}. 추가 조건: {user_message}"
            logger.info(f"Combining pending_request: '{original_message[:30]}...' + '{user_message[:30]}...'")
            user_message = combined_message
            msg_lower = user_message.lower()
            # pending_request 클리어 (한 번만 사용)
            del accumulated_context["pending_request"]
    
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
    
    # 2-1. GitHub URL 패턴 먼저 확인 (예: https://github.com/facebook/react)
    github_url_pattern = r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
    github_url_match = re.search(github_url_pattern, user_message)
    if github_url_match:
        detected_owner = github_url_match.group(1)
        detected_repo = github_url_match.group(2).replace('.git', '')
        logger.info(f"Detected repo from GitHub URL: {detected_owner}/{detected_repo}")
    else:
        # 2-2. owner/repo 패턴 (예: facebook/react)
        repo_pattern = r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
        repo_match = re.search(repo_pattern, user_message)
        if repo_match:
            # github.com/owner 같은 잘못된 매칭 방지
            potential_owner = repo_match.group(1)
            if potential_owner.lower() not in ['github', 'www', 'com', 'http', 'https']:
                detected_owner = potential_owner
                detected_repo = repo_match.group(2)
                logger.info(f"Detected repo from pattern: {detected_owner}/{detected_repo}")
    
    if detected_owner and detected_repo:
        accumulated_context["last_mentioned_repo"] = {
            "owner": detected_owner,
            "repo": detected_repo,
            "full_name": f"{detected_owner}/{detected_repo}"
        }
    
    # 2-2. 단독 프로젝트명 (예: "react 분석해줘")
    # 이미 분석 중인 저장소가 있으면, 단일 단어를 프로젝트명으로 오인하지 않도록 스킵 (LLM이 문맥 전환 판단)
    # 단, "이제 jquery 분석해줘" 처럼 명시적으로 새로운 분석을 요청하는 경우는 LLM 단계에서 처리됨
    has_existing_repo = False
    last_mentioned = accumulated_context.get("last_mentioned_repo", {})
    if last_mentioned.get("owner") and last_mentioned.get("repo"):
        has_existing_repo = True
        logger.info(f"Existing repo in session: {last_mentioned['owner']}/{last_mentioned['repo']}")
    else:
        logger.info("No existing repo in session accumulated_context")

    if not detected_repo and not has_existing_repo:
        # LLM 기반 저장소 감지 (룰 베이스 키워드 리스트 제거)
        from backend.agents.supervisor.repo_detector import detect_repository_from_message
        
        try:
            session_context = {
                "owner": state.get("owner"),
                "repo": state.get("repo"),
                "accumulated_context": accumulated_context,
            }
            
            llm_owner, llm_repo, reasoning = await detect_repository_from_message(
                user_message=user_message,
                session_context=session_context,
            )
            
            logger.info(f"[METACOGNITION] Repo detection: owner={llm_owner}, repo={llm_repo}, reason={reasoning}")
            
            if llm_owner and llm_repo:
                detected_owner = llm_owner
                detected_repo = llm_repo
                accumulated_context["last_mentioned_repo"] = {
                    "owner": detected_owner,
                    "repo": detected_repo,
                    "full_name": f"{detected_owner}/{detected_repo}",
                }
                logger.info(f"LLM detected repo: {detected_owner}/{detected_repo}")
            
        except Exception as e:
            logger.warning(f"LLM repo detection failed, fallback to session: {e}")
    
    
    # 2-3. last_mentioned_repo에서 복원
    # 단, 추천/검색 요청에서는 세션 repo를 사용하지 않음 (새 프로젝트 검색)
    recommend_keywords = ["찾아줘", "찾고", "추천", "프로젝트 찾", "유사", "similar", "recommend"]
    is_recommend_request = any(kw in msg_lower for kw in recommend_keywords)
    
    if not detected_repo:
        if has_existing_repo and not is_recommend_request:
            detected_owner = last_mentioned["owner"]
            detected_repo = last_mentioned["repo"]
            logger.info(f"Using last mentioned repo: {detected_owner}/{detected_repo}")
        elif is_recommend_request:
            logger.info("Recommend request detected, skipping session repo fallback")
    
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
                            "additional_agents": ["security"], # 기본 진단 시 보안 포함
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
    
    # === 4단계: 검색 결과가 있지만 정확 매칭이 없으면 clarification 요청 ===
    # 검색 결과가 1개 이상이고 정확 매칭이 없으면 사용자에게 선택지 제시
    if search_results and len(search_results) >= 1 and not detected_owner:
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
    # last_mentioned_repo 우선, 없으면 state의 owner/repo 사용
    context_owner = state["owner"]
    context_repo = state["repo"]
    
    if has_existing_repo:
        context_owner = last_mentioned["owner"]
        context_repo = last_mentioned["repo"]
        logger.info(f"Using session repo for context: {context_owner}/{context_repo}")
    
    session_context = {
        "owner": context_owner,
        "repo": context_repo,
        "ref": state.get("ref", "main"),
        "conversation_history": conversation_history,
        "accumulated_context": accumulated_context,
        "pronoun_detected": pronoun_detected,
        "detected_repo": f"{detected_owner}/{detected_repo}" if detected_owner else f"{context_owner}/{context_repo}" if context_owner and context_repo else None
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
        # 원래 요청 저장 (다음 응답에서 합치기 위해)
        accumulated_context["pending_request"] = {
            "original_message": user_message,
            "task_type": intent.task_type,
            "target_agent": intent.target_agent,
        }
        logger.info(f"Stored pending_request: {user_message[:50]}...")
    
    # 결과 구성
    result = {
        "supervisor_intent": intent.dict(),
        "needs_clarification": needs_clarification,
        "clarification_questions": clarification_questions,
        "target_agent": intent.target_agent,
        "additional_agents": intent.additional_agents,  # 멀티 에이전트 협업
        "accumulated_context": accumulated_context
    }
    
    # 대화 연속성을 위해 last_intent 저장
    accumulated_context["last_intent"] = {
        "task_type": intent.task_type,
        "target_agent": intent.target_agent,
        "needs_clarification": needs_clarification,
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
    
    # 규칙 기반 detected_owner/detected_repo 우선 (unknown 제외)
    def is_valid_repo(owner: str, repo: str) -> bool:
        if not owner or not repo:
            return False
        if owner.lower() == "unknown" or repo.lower() == "unknown":
            return False
        return True
    
    if detected_owner and detected_repo and is_valid_repo(detected_owner, detected_repo):
        result["owner"] = detected_owner
        result["repo"] = detected_repo
        # 정확 매칭 시 clarification 건너뛰기
        result["needs_clarification"] = False
        result["clarification_questions"] = []
        logger.info(f"Using pre-detected repo: {detected_owner}/{detected_repo} (skipping clarification)")
    elif result.get("needs_clarification") and not is_valid_repo(result.get("owner", ""), result.get("repo", "")):
        # 저장소가 없고 clarification이 필요하면 clarification 유지
        logger.info("No valid repo detected, keeping clarification")
        
    # [사용자 규칙] 진단 요청 시 보안 분석도 함께 수행
    if result.get("target_agent") == "diagnosis":
        additional = result.get("additional_agents") or []
        if "security" not in additional:
            additional.append("security")
            result["additional_agents"] = additional
            logger.info("Added security agent to diagnosis request (Global Rule)")
    
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
    """진단 Agent 실행 (캐시 우선 + 보안 분석 자동 추가 + 메타인지)
    
    이미 진단 결과가 세션 컨텍스트에 있거나 캐시에 있으면 재사용합니다.
    """
    from backend.agents.shared.metacognition import (
        AgentResult, QualityChecker, Source, QualityLevel,
        create_github_source
    )
    from backend.common.cache_manager import get_cache_manager
    
    logger.info("Running Diagnosis Agent V2")
    
    owner = state["owner"]
    repo = state["repo"]
    ref = state.get("ref", "main")
    
    # 1. 세션 컨텍스트에서 기존 진단 결과 확인
    accumulated_context = state.get("accumulated_context", {})
    cached_diagnosis = accumulated_context.get("diagnosis_result")
    
    if cached_diagnosis and isinstance(cached_diagnosis, dict):
        health_score = cached_diagnosis.get("health_score")
        if health_score is not None:
            logger.info(f"Using cached diagnosis from session context (health_score: {health_score})")
            cached_diagnosis["from_cache"] = True
            cached_diagnosis["cache_source"] = "session_context"
            return {
                "agent_result": cached_diagnosis,
                "diagnosis_result": cached_diagnosis,
                "target_agent": "diagnosis",
                "additional_agents": ["security"],
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 2. 글로벌 캐시에서 확인 (24시간 TTL)
    cache_manager = get_cache_manager()
    cache_key = f"diagnosis:{owner}/{repo}:{ref}"
    cached_result = cache_manager.get(cache_key)
    
    if cached_result and isinstance(cached_result, dict):
        health_score = cached_result.get("health_score")
        if health_score is not None:
            logger.info(f"Using cached diagnosis from global cache (health_score: {health_score})")
            cached_result["from_cache"] = True
            cached_result["cache_source"] = "global_cache"
            return {
                "agent_result": cached_result,
                "diagnosis_result": cached_result,
                "target_agent": "diagnosis",
                "additional_agents": ["security"],
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 3. 캐시 미스 - 새로 진단 실행
    logger.info("Cache miss - running fresh diagnosis")
    
    # 대용량 저장소 체크 (첫 분석일 때만)
    repo_size_info = await check_repo_size_and_warn(owner, repo)
    
    # 대용량 저장소 경고 메시지 추가
    warning_message = None
    if repo_size_info["is_large"]:
        warning_message = repo_size_info["warning_message"]
        logger.info(f"Large repo warning: {warning_message}")
    
    result = await run_diagnosis(
        owner=owner,
        repo=repo,
        ref=ref,
        user_message=state["user_message"],
        supervisor_intent=state.get("supervisor_intent")
    )
    
    # 진단 결과에 type 명시
    if isinstance(result, dict) and "type" not in result:
        result["type"] = "full_diagnosis"
    
    # 4. 결과를 글로벌 캐시에 저장 (24시간 TTL)
    if result and not result.get("error"):
        cache_manager.set(cache_key, result, ttl_hours=24)
        logger.info(f"Diagnosis result cached: {cache_key}")
    
    # 메타인지: 품질 체크 및 근거 수집
    quality_level, confidence, gaps = QualityChecker.evaluate_diagnosis(result)
    
    # 근거 수집 (분석에 사용된 파일들)
    sources = []
    documentation = result.get("documentation", {})
    if isinstance(documentation, dict):
        if documentation.get("readme_present"):
            sources.append(create_github_source(owner, repo, "README.md", "README.md"))
        if documentation.get("contributing_present"):
            sources.append(create_github_source(owner, repo, "CONTRIBUTING.md", "CONTRIBUTING.md"))
    
    # 메타인지 로그 출력
    logger.info(f"[METACOGNITION] Diagnosis completed:")
    logger.info(f"  - Quality: {quality_level.value} (confidence: {confidence:.2f})")
    logger.info(f"  - Sources: {len(sources)} files")
    if gaps:
        logger.info(f"  - Gaps: {', '.join(gaps)}")
    
    # 결과에 대용량 저장소 정보 추가
    if warning_message:
        result["large_repo_warning"] = warning_message
        result["repo_stats"] = repo_size_info.get("repo_stats", {})
    
    return {
        "agent_result": result,
        "diagnosis_result": result,  # finalize에서 사용
        "target_agent": "diagnosis",
        "additional_agents": ["security"],  # 보안 분석 자동 추가!
        "iteration": state.get("iteration", 0) + 1,
        "large_repo_warning": warning_message  # 대용량 경고 전달
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
    
    # 메타인지: 품질 체크
    plan = result.get("plan", [])
    plan_weeks = len(plan)
    has_summary = bool(result.get("summary"))
    has_error = "error" in result
    
    if has_error:
        quality = "failed"
        confidence = 0.0
    elif plan_weeks >= 4:
        quality = "high"
        confidence = 0.9
    elif plan_weeks >= 2:
        quality = "medium"
        confidence = 0.7
    else:
        quality = "low"
        confidence = 0.4
    
    logger.info(f"[METACOGNITION] Onboarding completed:")
    logger.info(f"  - Plan weeks: {plan_weeks}")
    logger.info(f"  - Quality: {quality} (confidence: {confidence:.2f})")
    
    return {
        "agent_result": result,
        "target_agent": "onboarding",  # 프론트엔드에서 인식하도록
        "onboarding_result": result,  # 프론트엔드에서 직접 접근 가능하도록
        "iteration": state.get("iteration", 0) + 1
    }


async def run_security_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """보안 Agent 실행 (캐시 우선 + SecurityAgent 연결)
    
    이미 보안 분석 결과가 세션 컨텍스트에 있거나 캐시에 있으면 재사용합니다.
    """
    import os
    from backend.common.cache_manager import get_cache_manager
    
    logger.info("Running Security Agent")
    
    owner = state.get("owner", "")
    repo = state.get("repo", "")
    ref = state.get("ref", "main")
    
    # 1. 세션 컨텍스트에서 기존 보안 결과 확인
    accumulated_context = state.get("accumulated_context", {})
    # update_session_node에서 'security_scan'으로 저장하므로 그 키로 확인
    cached_security = accumulated_context.get("security_scan") or accumulated_context.get("security_result")
    
    if cached_security and isinstance(cached_security, dict):
        security_score = cached_security.get("results", {}).get("security_score") or cached_security.get("security_score")
        if security_score is not None:
            logger.info(f"Using cached security from session context (score: {security_score})")
            cached_security["from_cache"] = True
            cached_security["cache_source"] = "session_context"
            return {
                "agent_result": cached_security,
                "security_result": cached_security,
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 2. 글로벌 캐시에서 확인 (12시간 TTL - 보안은 더 자주 갱신)
    cache_manager = get_cache_manager()
    cache_key = f"security:{owner}/{repo}:{ref}"
    cached_result = cache_manager.get(cache_key)
    
    if cached_result and isinstance(cached_result, dict):
        security_score = cached_result.get("results", {}).get("security_score") or cached_result.get("security_score")
        if security_score is not None:
            logger.info(f"Using cached security from global cache (score: {security_score})")
            cached_result["from_cache"] = True
            cached_result["cache_source"] = "global_cache"
            return {
                "agent_result": cached_result,
                "security_result": cached_result,
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 3. 캐시 미스 - 새로 보안 분석 실행
    logger.info("Cache miss - running fresh security analysis")
    
    # 대용량 저장소 체크
    repo_size_info = await check_repo_size_and_warn(owner, repo)
    warning_message = repo_size_info.get("warning_message") if repo_size_info["is_large"] else None
    
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
        
        # SecurityAgent 실행
        result = await agent.analyze(
            user_request=user_message if user_message else f"{owner}/{repo} 보안 분석",
            owner=owner,
            repository=repo,
            github_token=os.getenv("GITHUB_TOKEN")
        )
        
        logger.info(f"Security analysis completed: success={result.get('success', False)}")
        
        # 4. 결과를 글로벌 캐시에 저장 (12시간 TTL)
        if result and not result.get("error"):
            cache_manager.set(cache_key, result, ttl_hours=12)
            logger.info(f"Security result cached: {cache_key}")
        
        # 메타인지: 보안 분석 품질 체크
        security_score = result.get("results", {}).get("security_score", result.get("security_score"))
        vulnerabilities = result.get("results", {}).get("vulnerabilities", {})
        vuln_count = vulnerabilities.get("total", 0)
        
        if security_score is not None:
            quality = "high"
            confidence = 0.9
        elif vuln_count > 0:
            quality = "medium"
            confidence = 0.7
        else:
            quality = "low"
            confidence = 0.5
        
        logger.info(f"[METACOGNITION] Security completed:")
        logger.info(f"  - Score: {security_score}")
        logger.info(f"  - Vulnerabilities: {vuln_count}")
        logger.info(f"  - Quality: {quality} (confidence: {confidence:.2f})")
        
        # type 필드 추가 (finalize_answer_node에서 사용)
        result["type"] = "security_scan"
        
        # 대용량 저장소 정보 추가
        if warning_message:
            result["large_repo_warning"] = warning_message
        
        return {
            "agent_result": result,
            "security_result": result,  # finalize에서 사용
            "iteration": state.get("iteration", 0) + 1,
            "large_repo_warning": warning_message
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
        
        # 구조만 요청하는 경우 감지
        structure_only = any(kw in user_message for kw in ["구조", "폴더", "structure", "트리", "tree", "디렉토리"])
        structure_only = structure_only and not any(kw in user_message for kw in ["기여", "가이드", "이슈", "pr", "체크리스트"])
        
        result = {
            "type": "structure" if structure_only else "contributor",
            "owner": owner,
            "repo": repo,
            "features": {}
        }
        
        # 코드 구조 시각화 (구조 요청 시 우선 처리)
        if any(kw in user_message for kw in ["구조", "폴더", "structure", "코드 구조", "트리", "tree"]):
            accumulated_context = state.get("accumulated_context", {})
            file_tree = accumulated_context.get("file_tree", [])
            
            # file_tree가 없으면 GitHub에서 직접 조회
            if not file_tree:
                try:
                    from backend.common.github_client import fetch_repo_tree
                    tree_result = fetch_repo_tree(owner, repo)
                    if isinstance(tree_result, dict):
                        file_tree = tree_result.get("tree", [])
                    else:
                        file_tree = tree_result if isinstance(tree_result, list) else []
                    logger.info(f"[Contributor] Fetched file tree from GitHub: {len(file_tree)} items")
                except Exception as e:
                    logger.warning(f"[Contributor] Failed to fetch file tree: {e}")
                    file_tree = []
            
            if file_tree:
                visualization = generate_structure_visualization(owner, repo, file_tree)
                result["features"]["structure_visualization"] = visualization
                logger.info(f"[Contributor] Structure visualization generated")
        
        # 구조만 요청한 경우 기여 가이드 생략
        if structure_only:
            logger.info(f"[Contributor] Structure-only request, skipping contribution guide")
            return {
                "agent_result": result,
                "target_agent": "contributor",
                "structure_visualization": result["features"].get("structure_visualization"),
                "iteration": state.get("iteration", 0) + 1
            }
        
        # 첫 기여 가이드 (기본 제공)
        guide = generate_first_contribution_guide(owner, repo)
        result["features"]["first_contribution_guide"] = guide
        
        # 기여 체크리스트 (기본 제공)
        checklist = generate_contribution_checklist(owner, repo)
        result["features"]["contribution_checklist"] = checklist
        
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
        
        # 메타인지: 품질 체크
        features = result.get("features", {})
        feature_count = len(features)
        has_structure = bool(features.get("structure_visualization"))
        has_guide = bool(features.get("first_contribution_guide"))
        
        if feature_count >= 3 or has_structure:
            quality = "high"
            confidence = 0.9
        elif feature_count >= 1:
            quality = "medium"
            confidence = 0.7
        else:
            quality = "low"
            confidence = 0.4
        
        logger.info(f"[METACOGNITION] Contributor completed:")
        logger.info(f"  - Features: {list(features.keys())}")
        logger.info(f"  - Quality: {quality} (confidence: {confidence:.2f})")
        
        logger.info(f"Contributor agent completed: {list(result['features'].keys())}")
        
        return {
            "agent_result": result,
            "target_agent": "contributor",  # 프론트엔드에서 인식하도록
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
    """추천 에이전트 실행 (onboarding 점수 기반 프로젝트 추천)
    
    Note: 추천은 진단 결과만 참고하며, 보안 분석은 제외합니다.
    유사도 0.3 이상 + 온보딩 점수 60점 이상인 프로젝트만 추천합니다.
    """
    import asyncio
    
    logger.info("Running Recommend Agent (with onboarding score filter)")
    
    async def calculate_onboarding_score(owner: str, repo: str) -> int:
        """프로젝트의 온보딩 점수를 빠르게 계산"""
        try:
            from backend.core.docs_core import analyze_documentation
            from backend.core.activity_core import analyze_activity_optimized
            from backend.core.scoring_core import compute_onboarding_score
            from backend.common.github_client import fetch_readme
            import base64
            
            # README 가져오기 (docs 분석에 필요)
            readme_task = asyncio.create_task(
                asyncio.to_thread(fetch_readme, owner, repo)
            )
            # Activity 분석 (owner, repo 문자열 직접 사용 가능)
            activity_task = asyncio.create_task(
                asyncio.to_thread(analyze_activity_optimized, owner, repo)
            )
            
            readme_content, activity_result = await asyncio.gather(
                readme_task, activity_task, return_exceptions=True
            )
            
            # 에러 처리
            docs_score = 50  # 기본값
            activity_score = 50  # 기본값
            
            # Docs 분석 (README 내용 직접 전달)
            # fetch_readme는 dict를 반환, content 필드에 base64 인코딩된 README가 있음
            if not isinstance(readme_content, Exception) and readme_content:
                try:
                    # Base64 디코딩하여 실제 README 텍스트 추출
                    encoded_content = readme_content.get("content", "")
                    if encoded_content:
                        readme_text = base64.b64decode(encoded_content).decode("utf-8")
                        docs_result = analyze_documentation(readme_text)
                        docs_score = docs_result.total_score  # 문서 품질 점수 (0-100)
                    else:
                        logger.warning(f"[ONBOARDING] README content is empty for {owner}/{repo}")
                except Exception as e:
                    logger.warning(f"[ONBOARDING] docs_core failed for {owner}/{repo}: {e}")
            else:
                logger.warning(f"[ONBOARDING] README fetch failed for {owner}/{repo}: {readme_content}")
                
            # Activity 분석 결과 (ActivityCoreResult 객체)
            if not isinstance(activity_result, Exception):
                activity_score = activity_result.total_score  # 객체 속성 접근
            else:
                logger.warning(f"[ONBOARDING] activity_core failed for {owner}/{repo}: {activity_result}")
            
            onboarding = compute_onboarding_score(docs_score, activity_score)
            logger.info(f"[ONBOARDING] {owner}/{repo}: docs={docs_score}, activity={activity_score}, onboarding={onboarding}")
            return onboarding
            
        except Exception as e:
            logger.warning(f"Failed to calculate onboarding score for {owner}/{repo}: {e}")
            return 0  # 계산 실패시 0 반환 (필터링됨)
    
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
        
        # 결과 포맷팅 - Pydantic 모델과 dict 모두 처리
        if hasattr(result, 'search_results'):
            search_results = result.search_results
        elif isinstance(result, dict):
            search_results = result.get("search_results", [])
        else:
            search_results = []
            
        if hasattr(result, 'final_summary'):
            final_summary = result.final_summary
        elif isinstance(result, dict):
            final_summary = result.get("final_summary", "")
        else:
            final_summary = ""
            
        logger.info(f"[RECOMMEND] Vector search returned {len(search_results)} candidates")
        
        # 1단계: 유사도 0.3 이상 필터링
        similarity_filtered = []
        for item in search_results:
            if hasattr(item, "score"):
                rerank_score = getattr(item, "score", 0) or 0
                if rerank_score >= 0.3:
                    similarity_filtered.append({
                        # 백엔드 필드
                        "owner": getattr(item, "owner", ""),
                        "name": getattr(item, "name", ""),
                        "full_name": f"{getattr(item, 'owner', '')}/{getattr(item, 'name', '')}",
                        "description": getattr(item, "description", ""),
                        "stars": getattr(item, "stars", 0),
                        "html_url": getattr(item, "html_url", ""),
                        "main_language": getattr(item, "main_language", ""),
                        "similarity_score": rerank_score,
                        "ai_reason": getattr(item, "ai_reason", "") or getattr(item, "match_snippet", ""),
                        # 프론트엔드 호환 필드
                        "url": getattr(item, "html_url", ""),
                        "language": getattr(item, "main_language", ""),
                        "reason": getattr(item, "ai_reason", "") or getattr(item, "match_snippet", ""),
                        "similarity": rerank_score,
                    })
            elif isinstance(item, dict):
                rerank_score = item.get("score", 0) or item.get("rerank_score", 0) or 0
                if rerank_score >= 0.3:
                    item["similarity_score"] = rerank_score
                    item["similarity"] = rerank_score  # 프론트엔드 호환
                    item["url"] = item.get("html_url", "")
                    item["language"] = item.get("main_language", "")
                    item["reason"] = item.get("ai_reason", "")
                    similarity_filtered.append(item)
        
        logger.info(f"[RECOMMEND] After similarity filter (>=0.3): {len(similarity_filtered)} candidates")
        
        # 2단계: 온보딩 점수 50점 이상 필터링, 상위 6개 추천
        formatted_result = {
            "type": "recommend",
            "recommendations": [],
            "summary": final_summary
        }
        
        if similarity_filtered:
            # 온보딩 점수 병렬 계산
            onboarding_tasks = [
                calculate_onboarding_score(item["owner"], item["name"])
                for item in similarity_filtered
            ]
            onboarding_scores = await asyncio.gather(*onboarding_tasks, return_exceptions=True)
            
            # 모든 항목에 온보딩 점수 추가 후 50점 이상만 필터링
            candidates_with_scores = []
            for item, onboarding in zip(similarity_filtered, onboarding_scores):
                if isinstance(onboarding, Exception):
                    onboarding = 0
                
                item["onboarding_score"] = onboarding
                
                if onboarding >= 50:
                    candidates_with_scores.append(item)
                    logger.info(f"[RECOMMEND] ✅ {item['full_name']}: similarity={item['similarity_score']:.2f}, onboarding={onboarding}")
                else:
                    logger.info(f"[RECOMMEND] ❌ {item['full_name']}: onboarding={onboarding} (filtered out, threshold=50)")
            
            # 온보딩 점수로 정렬 (내림차순), 상위 6개만 선택
            candidates_with_scores.sort(key=lambda x: x["onboarding_score"], reverse=True)
            formatted_result["recommendations"] = candidates_with_scores[:6]
            # 프론트엔드 리포트 호환성을 위해 similar_projects도 설정
            formatted_result["similar_projects"] = candidates_with_scores[:6]
        
        logger.info(f"[RECOMMEND] Final recommendations (onboarding>=50, top 6): {len(formatted_result['recommendations'])} projects")
        
        # 메타인지: 추천 품질 체크
        rec_count = len(formatted_result["recommendations"])
        if rec_count >= 5:
            quality = "high"
            confidence = 0.9
        elif rec_count >= 2:
            quality = "medium"
            confidence = 0.7
        else:
            quality = "low"
            confidence = 0.4
        
        logger.info(f"[METACOGNITION] Recommend completed:")
        logger.info(f"  - Recommendations: {rec_count}")
        logger.info(f"  - Quality: {quality} (confidence: {confidence:.02f})")
        
        # 사용자 메시지에 '온보딩' 키워드가 있으면 onboarding도 추가 실행
        user_message = state.get("user_message", "").lower()
        additional_agents = []
        if "온보딩" in user_message or "onboarding" in user_message or "기여" in user_message or "contribution" in user_message:
            additional_agents.append("onboarding")
            logger.info("Adding onboarding agent to recommend request (keyword detected)")
        
        return {
            "agent_result": formatted_result,
            "recommend_result": formatted_result,
            "additional_agents": additional_agents,
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
            "additional_agents": [],  # security 제외
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
            "additional_agents": [],  # security 제외
            "iteration": state.get("iteration", 0) + 1
        }


async def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
    """
    일반 채팅 응답 (ReAct + 메타인지 통합)
    
    복잡한 질문은 ReAct 에이전트 사용, 단순 질문은 직접 LLM 호출.
    """
    from backend.agents.supervisor.nodes.react_chat_agent import ReactChatAgent, needs_react_response
    from backend.agents.supervisor.nodes.chat_tools import get_chat_tools
    from backend.common.config import LLM_MODEL_NAME, LLM_API_BASE, LLM_API_KEY, LLM_TEMPERATURE
    
    logger.info("Generating chat response")
    
    user_message = state.get("user_message") or ""
    accumulated_context = state.get("accumulated_context", {})
    
    # 저장소 정보 가져오기
    repo_info = accumulated_context.get("last_mentioned_repo", {})
    owner = repo_info.get("owner") or state.get("owner") or "unknown"
    repo = repo_info.get("repo") or state.get("repo") or "unknown"
    
    logger.info(f"[Chat] message='{user_message[:50] if user_message else ''}...', repo={owner}/{repo}")
    
    # user_message가 비어있으면 기본 응답
    if not user_message.strip():
        answer = "안녕하세요! 저장소 분석이나 질문이 있으시면 말씀해주세요."
        return {
            "agent_result": {"type": "chat", "response": answer},
            "final_answer": answer
        }
    
    # ReAct 응답 필요 여부 판단
    needs_react = needs_react_response(user_message, accumulated_context)
    logger.info(f"[Chat] needs_react={needs_react}")
    
    if needs_react:
        logger.info("[Chat] Using ReAct agent for complex question")
        try:
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(
                model=LLM_MODEL_NAME,
                base_url=LLM_API_BASE,
                api_key=LLM_API_KEY,
                temperature=float(LLM_TEMPERATURE) if LLM_TEMPERATURE else 0.7
            )
            
            tools = get_chat_tools()
            
            agent = ReactChatAgent(
                llm=llm,
                tools=tools,
                owner=owner,
                repo=repo,
                max_iterations=5
            )
            
            # ReAct 에이전트로 응답 생성
            answer, collected_info = await agent.generate_response(
                user_message,
                context={
                    "accumulated_context": accumulated_context,
                    "repo_info": repo_info
                }
            )
            
            # 수집된 정보에서 결과 추출 (메타인지)
            security_result = None
            diagnosis_result = None
            sources = []
            
            for info in collected_info:
                tool_name = info.get("tool", "")
                result = info.get("result", {})
                
                # 소스 수집
                if result.get("success"):
                    if tool_name == "read_file":
                        file_path = info.get("parameters", {}).get("path", "")
                        if file_path:
                            sources.append({
                                "type": "file",
                                "title": file_path,
                                "url": f"https://github.com/{owner}/{repo}/blob/main/{file_path}"
                            })
                    
                    if tool_name == "call_security_agent" and result.get("security_score") is not None:
                        security_result = {
                            "security_score": result.get("security_score"),
                            "security_grade": result.get("security_grade"),
                            "risk_level": result.get("risk_level", "low"),
                            "vulnerability_count": result.get("vulnerability_count", 0),
                        }
                        logger.info(f"[Chat] Security result extracted: score={security_result.get('security_score')}")
                    
                    elif tool_name == "call_diagnosis_agent" and result.get("health_score") is not None:
                        diagnosis_result = result
                        logger.info(f"[Chat] Diagnosis result extracted: score={diagnosis_result.get('health_score')}")
            
            logger.info(f"[Chat] ReAct completed with {len(collected_info)} tool calls, {len(sources)} sources")
            
            result_data = {
                "agent_result": {
                    "type": "chat",
                    "response": answer,
                    "sources": sources,
                    "tool_calls": len(collected_info),
                },
                "final_answer": answer,
            }
            
            if security_result:
                result_data["security_result"] = security_result
            if diagnosis_result:
                result_data["diagnosis_result"] = diagnosis_result
            
            return result_data
            
        except Exception as e:
            logger.warning(f"[Chat] ReAct failed, falling back to direct LLM: {e}")
    
    # 기존 방식 (단순 질문 또는 ReAct 실패 시)
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        import asyncio
        
        # 시스템 프롬프트 구성 (상세한 ODOC 소개 포함)
        system_prompt = f"""당신은 ODOC(Open-source Doctor, 오픈소스 닥터) AI 어시스턴트입니다.

## ODOC이란?
ODOC은 GitHub와 같은 오픈소스 저장소를 분석하고 진단해주는 AI 기반 도구입니다.
주요 기능은 다음과 같습니다:

### 1. 저장소 건강도 진단 (Project Diagnosis)
- **종합 점수 제공**: 전체적인 저장소 건강도를 0-100점으로 평가
- **세부 지표 분석**: 활동성, 문서화, 코드 구조 등을 종합하여 건강도 진단
- **개선 권장사항**: README, CONTRIBUTING.md, 테스트 커버리지 등 개선점 제안
- **상세 메트릭**: 최근 커밋 수, 기여자 수, 이슈/PR 응답 시간 등

### 2. 보안 취약점 분석 (Security Analysis)
- **의존성 스캔**: 코드나 의존성(dependencies)에서 보안상 문제가 될 수 있는 부분을 찾아냄
- **CVE 검색**: NVD 데이터베이스에서 알려진 취약점 확인
- **위험도 평가**: Critical, High, Medium, Low 등급 분류

### 3. 온보딩 가이드 생성 (Onboarding Guide)
- **학습 플랜**: 신규 기여자가 프로젝트에 쉽게 참여할 수 있도록 온보딩 가이드를 자동으로 만들어줌
- **기여 체크리스트**: PR 제출 전 확인사항
- **Good First Issue**: 초보자에게 적합한 이슈 추천

### 4. 코드 구조 시각화 (Structure Visualization)
- **트리 구조**: 프로젝트의 코드 구조를 시각적으로 표현해 이해를 돕습니다
- **다이어그램**: 주요 디렉토리 및 파일 관계 시각화

## 목표
ossdoctor는 오픈소스 프로젝트의 품질을 높이고, 기여자들이 더 쉽게 참여할 수 있도록 돕는 것을 목표로 하고 있습니다.

## 현재 컨텍스트
- 분석 중인 저장소: {owner}/{repo if repo else '(없음)'}

## 응답 지침
1. ODOC/ossdoctor에 대한 질문 → 위 상세 소개를 바탕으로 **구체적이고 친절하게** 설명
2. 저장소 관련 질문 → 해당 저장소 정보 기반으로 답변
3. 기능 안내 질문 → 각 기능 설명과 함께 사용법 안내
4. 마크다운 형식(헤더, 목록, 굵게 등)을 활용하여 가독성 있게 답변

상세하고 친절하게 답변해주세요."""
        
        llm = fetch_llm_client()
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_message)
            ]
        )
        
        # 비동기 실행
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, llm.chat, request)
        answer = response.content
        
    except Exception as e:
        logger.warning(f"[Chat] LLM call failed: {e}")
        answer = f"질문을 받았습니다: {user_message}\n\n저장소 정보가 필요한 경우 owner와 repo를 지정해주세요."
    
    return {
        "agent_result": {"type": "chat", "response": answer},
        "final_answer": answer
    }


async def finalize_answer_node(state: SupervisorState) -> Dict[str, Any]:
    """
    최종 답변 생성 (메타인지 + 근거 포함)
    
    - 대명사 해결 컨텍스트 포함
    - 분석에 사용된 파일 근거 링크 포함
    - 품질/신뢰도 정보 포함
    """
    from backend.agents.shared.metacognition import Source
    from backend.agents.supervisor.metacognition import format_response_with_sources
    
    logger.info("Finalizing answer")
    
    # 메인 에이전트 결과 (target_agent 기준으로 가져오기)
    target_agent = state.get("target_agent")
    multi_agent_results = state.get("multi_agent_results", {})
    
    # 메인 에이전트 결과 우선 사용
    agent_result = state.get("agent_result")
    if target_agent and target_agent in multi_agent_results:
        agent_result = multi_agent_results[target_agent]
        logger.info(f"Using main agent result from multi_agent_results: {target_agent}")
    
    # diagnosis_result가 있으면 우선 사용 (진단 요청의 경우)
    diagnosis_result = state.get("diagnosis_result")
    if diagnosis_result and target_agent == "diagnosis":
        agent_result = diagnosis_result
        logger.info("Using diagnosis_result for finalization")
    
    if not agent_result:
        return {"final_answer": "결과를 생성할 수 없습니다.", "error": "No agent result"}
    
    # 대명사 해결 정보 가져오기
    accumulated_context = state.get("accumulated_context", {})
    pronoun_info = accumulated_context.get("last_pronoun_reference", {})
    user_message = state["user_message"]
    
    # 저장소 정보 요청 처리 (GitHub에서 저장소를 찾은 경우)
    if accumulated_context.get("found_repo_info"):
        repo_info = accumulated_context.get("last_mentioned_repo", {})
        if repo_info:
            owner = repo_info.get("owner", "")
            repo = repo_info.get("repo", "")
            full_name = repo_info.get("full_name", f"{owner}/{repo}")
            description = repo_info.get("description", "")
            stars = repo_info.get("stars", 0)
            url = repo_info.get("url", f"https://github.com/{owner}/{repo}")
            
            # 저장소 정보 응답 생성
            answer_parts = [
                f"**{full_name}** 저장소를 찾았습니다!\n",
                f"- **URL**: [{url}]({url})",
                f"- **스타**: {stars:,}",
            ]
            if description:
                answer_parts.insert(1, f"- **설명**: {description}")
            
            answer_parts.append("\n이 저장소를 **분석**하거나 **기여 가이드**를 받고 싶으시면 말씀해주세요.")
            
            answer = "\n".join(answer_parts)
            logger.info(f"Returning found repo info: {full_name}")
            
            return {
                "final_answer": answer,
                "owner": owner,
                "repo": repo,
                "agent_result": {
                    "type": "repo_info",
                    "owner": owner,
                    "repo": repo,
                    "url": url,
                    "description": description,
                    "stars": stars
                }
            }
    
    # 대명사 참조가 있는 경우 컨텍스트 데이터 가져오기
    referenced_data = None
    if pronoun_info.get("resolved") and pronoun_info.get("confidence", 0) > 0.5:
        refers_to = pronoun_info.get("refers_to")
        if refers_to and refers_to in accumulated_context:
            referenced_data = accumulated_context.get(refers_to)
            logger.info(f"Using referenced data from: {refers_to}")
    
    # 구조 요청 감지 (코드 구조, 폴더 구조, 트리 구조 등)
    structure_keywords = ["구조", "structure", "트리", "tree", "폴더", "folder", "디렉토리", "directory"]
    is_structure_request = any(kw in user_message.lower() for kw in structure_keywords)
    
    if is_structure_request:
        # 세션에서 structure_visualization 확인
        structure_viz = accumulated_context.get("structure_visualization")
        diagnosis_result = accumulated_context.get("diagnosis_result")
        
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        if structure_viz:
            # 이미 구조 시각화가 있으면 반환
            answer = f"## {owner}/{repo} 코드 구조\n\n코드 구조는 우측 리포트의 '구조' 탭에서 확인할 수 있습니다."
            logger.info("Returning existing structure_visualization")
            return {"final_answer": answer, "structure_visualization": structure_viz}
        elif diagnosis_result:
            # 진단 결과에서 구조 정보 추출
            file_tree = diagnosis_result.get("file_tree", diagnosis_result.get("structure", {}))
            if file_tree:
                answer = f"## {owner}/{repo} 코드 구조\n\n진단 결과에서 코드 구조를 확인할 수 있습니다."
                logger.info("Returning structure from diagnosis_result")
                return {"final_answer": answer, "agent_result": {"type": "structure", "file_tree": file_tree}}
        
        # 구조 정보가 없으면 contributor 에이전트 결과 사용
        logger.info("No cached structure, using agent_result")
    
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
        
        # 근거 링크 추가 (메타인지) - 실제 존재하는 파일만 추가
        analyzed_files = []
        
        # documentation 결과에서 실제 존재하는 파일 확인
        documentation = agent_result.get("documentation", {})
        if isinstance(documentation, dict):
            if documentation.get("readme_present"):
                analyzed_files.append("README.md")
            if documentation.get("contributing_present"):
                analyzed_files.append("CONTRIBUTING.md")
            if documentation.get("license_present"):
                analyzed_files.append("LICENSE")
        
        # dependencies 결과에서 실제 분석된 파일 확인
        dependencies = agent_result.get("dependencies", {})
        if isinstance(dependencies, dict):
            dep_analyzed_files = dependencies.get("analyzed_files", [])
            if dep_analyzed_files:
                analyzed_files.extend(dep_analyzed_files[:3])  # 최대 3개
        
        # structure 결과에서 빌드 파일 확인
        structure = agent_result.get("structure", {})
        if isinstance(structure, dict):
            build_files = structure.get("build_files", [])
            if build_files:
                analyzed_files.extend(build_files[:2])  # 최대 2개
        
        if analyzed_files:
            sources = []
            seen = set()
            for file_path in analyzed_files:
                if file_path and file_path not in seen:
                    seen.add(file_path)
                    sources.append(Source(
                        url=f"https://github.com/{owner}/{repo}/blob/main/{file_path}",
                        title=file_path,
                        type="file"
                    ))
            if sources:
                answer = format_response_with_sources(answer, sources, max_sources=5)
        
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
        
        # AI 판단 근거 (로그에만 기록, UI에는 표시 안 함)
        if reasoning or decision_reason:
            logger.info(f"[AI 판단 과정] {reasoning or decision_reason}")
        
        answer = answer + next_steps
        
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
                step_lines = []
                for i, step in enumerate(plan[:5]):
                    if isinstance(step, dict):
                        title = step.get('title') or f"Week {step.get('week', i+1)}"
                        desc = step.get('description', '')
                        if not desc and step.get('tasks'):
                            desc = step['tasks'][0] if step['tasks'] else ''
                        desc_preview = desc[:50] if desc else ''
                        step_lines.append(f"{i+1}. {title}: {desc_preview}")
                steps_preview = "\n".join(step_lines)
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
        
        # 보안 분석 근거 링크 추가 (메타인지)
        vuln_details = results.get("vulnerability_details", agent_result.get("vulnerability_details", []))
        sources = []
        
        # 실제 분석된 의존성 파일만 링크 (진단 결과에서 가져옴)
        analyzed_files = results.get("analyzed_files", agent_result.get("analyzed_files", []))
        
        # analyzed_files가 없으면 vulnerabilities에서 추론
        if not analyzed_files and vuln_details:
            # 취약점에서 언급된 패키지 매니저 추론
            for vuln in vuln_details:
                pkg = vuln.get("package", "")
                if pkg and not analyzed_files:
                    # 언어별 매니저 파일 추론 (취약점이 있으면 해당 파일이 존재)
                    if any(x in pkg.lower() for x in ["django", "flask", "requests", "numpy"]):
                        analyzed_files.append("requirements.txt")
                    elif any(x in pkg.lower() for x in ["express", "react", "lodash"]):
                        analyzed_files.append("package.json")
        
        # 분석된 파일만 참고자료에 추가
        for dep_file in analyzed_files[:3]:
            if isinstance(dep_file, str) and dep_file:
                sources.append(Source(
                    url=f"https://github.com/{owner}/{repo}/blob/main/{dep_file}",
                    title=dep_file,
                    type="file"
                ))
        
        # CVE 링크 추가
        for vuln in vuln_details[:3]:
            cve_id = vuln.get("cve_id", "")
            if cve_id:
                sources.append(Source(
                    url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    title=cve_id,
                    type="cve"
                ))
        
        if sources:
            answer = format_response_with_sources(answer, sources, max_sources=5)
        
        # security_result 포함하여 반환 (프론트엔드에서 사용)
        security_result_data = {
            "security_score": security_score,
            "security_grade": security_grade,
            "risk_level": risk_level,
            "vulnerabilities": vulnerabilities,
            "vulnerability_details": vuln_details,
        }
        
        return {
            "final_answer": answer,
            "security_result": security_result_data,
        }
    
    elif result_type == "structure":
        # 구조만 요청한 경우 (기여 가이드 없이)
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        features = agent_result.get("features", {})
        structure_viz = features.get("structure_visualization", {})
        
        answer = f"## {owner}/{repo} 코드 구조\n\n"
        if structure_viz:
            answer += "코드 구조는 우측의 '구조' 탭에서 확인할 수 있습니다.\n"
            answer += "다이어그램 또는 트리 구조로 전환하여 살펴보세요."
        else:
            answer += "구조 정보를 가져오지 못했습니다. 저장소를 확인해주세요."
        
        logger.info(f"Structure-only response for {owner}/{repo}")
        return {
            "final_answer": answer,
            "structure_visualization": structure_viz,
            "agent_result": agent_result
        }
    
    elif result_type == "recommend":
        # 프로젝트 추천 결과
        # 디버깅: agent_result 내용 확인
        logger.info(f"[DEBUG finalize] agent_result type: {type(agent_result)}")
        logger.info(f"[DEBUG finalize] agent_result keys: {list(agent_result.keys()) if isinstance(agent_result, dict) else 'N/A'}")
        if isinstance(agent_result, dict):
            logger.info(f"[DEBUG finalize] agent_result.recommendations count: {len(agent_result.get('recommendations', []))}")
        
        # 1. state.recommend_result 확인 (run_recommend_agent_node에서 직접 저장한 경우)
        recommend_result = state.get("recommend_result", {})
        logger.info(f"[DEBUG finalize] state.recommend_result: {bool(recommend_result)}, recommendations: {len(recommend_result.get('recommendations', []))}")
        
        # 2. 없으면 agent_result에서 가져오기 (multi_agent_results를 통해 온 경우)
        if not recommend_result or not recommend_result.get("recommendations"):
            recommend_result = agent_result if isinstance(agent_result, dict) else {}
            logger.info(f"[DEBUG finalize] Using agent_result as recommend_result")
        
        recommendations = recommend_result.get("recommendations", [])
        summary = recommend_result.get("summary", "")
        
        logger.info(f"Finalize recommend: {len(recommendations)} projects (from {'state' if state.get('recommend_result') else 'agent_result'})")
        
        if recommendations:
            answer = f"## 추천 프로젝트 목록\n\n"
            answer += f"{summary}\n\n" if summary else ""
            
            for i, proj in enumerate(recommendations[:5], 1):
                name = proj.get("name") or proj.get("full_name", "Unknown")
                desc = proj.get("description", "설명 없음")
                stars = proj.get("stars", 0)
                url = proj.get("html_url", "")
                language = proj.get("main_language", "")
                similarity = proj.get("similarity_score", 0)
                onboarding = proj.get("onboarding_score", 0)
                ai_reason = proj.get("ai_reason", "")
                
                # 점수 표시 형식
                similarity_pct = int(similarity * 100) if similarity else 0
                
                answer += f"### {i}. [{name}]({url})\n"
                answer += f"- **언어**: {language}\n" if language else ""
                answer += f"- **Stars**: {stars:,}\n"
                answer += f"- **온보딩 점수**: {onboarding}점\n" if onboarding else ""
                answer += f"- **유사도**: {similarity_pct}%\n" if similarity_pct else ""
                answer += f"- {desc}\n"
                answer += f"- **추천 이유**: {ai_reason}\n\n" if ai_reason else "\n"
            
            answer += "\n---\n더 자세한 정보는 우측의 '추천' 탭에서 확인하세요."
        else:
            answer = "죄송합니다. 조건에 맞는 프로젝트를 찾지 못했습니다. 다른 키워드로 다시 검색해 보세요."
        
        # agent_result에 recommendations 포함 (프론트엔드가 agent_result.recommendations를 사용)
        return {
            "final_answer": answer,
            "recommend_result": recommend_result,
            "agent_result": {
                "type": "recommend",
                "recommendations": recommendations,
                "summary": summary,
            },
        }
    
    elif result_type == "contributor":
        # 구조 요청인 경우 기여자 가이드 대신 구조만 표시
        if is_structure_request:
            owner = state.get("owner", "")
            repo = state.get("repo", "")
            features = agent_result.get("features", {})
            structure_viz = features.get("structure_visualization", {})
            
            if structure_viz:
                answer = f"## {owner}/{repo} 코드 구조\n\n코드 구조는 우측의 '구조' 탭에서 확인할 수 있습니다.\n클릭하여 트리 구조 또는 다이어그램으로 확인해보세요."
                logger.info("Structure request - returning structure_visualization only")
                return {
                    "final_answer": answer,
                    "structure_visualization": structure_viz,
                    "agent_result": {"type": "structure", "structure_visualization": structure_viz}
                }
        
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
        
        # 기여자 가이드 근거 링크 추가 (실제 존재 여부는 클라이언트에서 처리)
        sources = []
        
        # agent_result에서 실제 분석된 파일 확인
        first_contribution_guide = features.get("first_contribution_guide", {})
        contributing_url = first_contribution_guide.get("contributing_url")
        
        if contributing_url:
            sources.append(Source(
                url=contributing_url,
                title="CONTRIBUTING.md",
                type="file"
            ))
        
        # README.md는 기본으로 추가
        sources.append(Source(
            url=f"https://github.com/{owner}/{repo}/blob/main/README.md",
            title="README.md",
            type="file"
        ))
        
        # Issues 페이지 링크
        sources.append(Source(
            url=f"https://github.com/{owner}/{repo}/issues?q=label%3A%22good+first+issue%22",
            title="Good First Issues",
            type="issue"
        ))
        
        if sources:
            answer = format_response_with_sources(answer, sources, max_sources=5)
        
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


# === 라우팅 함수 ===

def route_to_agent_node(state: SupervisorState) -> Literal[
    "run_diagnosis_agent", "run_onboarding_agent", "run_security_agent", "run_recommend_agent", "chat_response"
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
    elif target == "recommend":
        return "run_recommend_agent"
    else:
        return "chat_response"


async def run_additional_agents_node(state: SupervisorState) -> Dict[str, Any]:
    """추가 에이전트 병렬 실행 (멀티 에이전트 협업)
    
    asyncio.gather를 사용하여 여러 에이전트를 동시에 실행합니다.
    이를 통해 진단 후 보안 분석 등을 병렬로 처리하여 응답 시간을 단축합니다.
    """
    import asyncio
    import time
    
    additional_agents = state.get("additional_agents", [])
    
    if not additional_agents:
        return {}
    
    start_time = time.time()
    logger.info(f"[PARALLEL] Starting {len(additional_agents)} additional agents in parallel: {additional_agents}")
    
    multi_agent_results = dict(state.get("multi_agent_results", {}))
    
    # 메인 에이전트 결과 저장
    main_result = state.get("agent_result")
    target_agent = state.get("target_agent")
    if main_result and target_agent:
        multi_agent_results[target_agent] = main_result
    
    # 에이전트 실행 함수 매핑
    agent_runners = {
        "diagnosis": run_diagnosis_agent_node,
        "security": run_security_agent_node,
        "onboarding": run_onboarding_agent_node,
        "contributor": run_contributor_agent_node,
    }
    
    # 병렬 실행할 태스크 생성
    async def run_agent(agent_name: str):
        """개별 에이전트 실행 래퍼"""
        agent_start = time.time()
        try:
            runner = agent_runners.get(agent_name)
            if runner:
                logger.info(f"[PARALLEL] Starting agent: {agent_name} at T+{agent_start - start_time:.2f}s")
                result = await runner(state)
                elapsed = time.time() - agent_start
                logger.info(f"[PARALLEL] Completed agent: {agent_name} in {elapsed:.2f}s")
                return (agent_name, result.get("agent_result", result))
            else:
                logger.warning(f"Unknown agent: {agent_name}")
                return (agent_name, {"error": f"Unknown agent: {agent_name}"})
        except Exception as e:
            logger.error(f"Additional agent {agent_name} failed: {e}")
            return (agent_name, {"error": str(e)})
    
    # 모든 에이전트를 병렬로 실행
    tasks = [run_agent(agent_name) for agent_name in additional_agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_elapsed = time.time() - start_time
    
    # 결과 수집
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Agent task failed with exception: {result}")
            continue
        if isinstance(result, tuple) and len(result) == 2:
            agent_name, agent_result = result
            multi_agent_results[agent_name] = agent_result
    
    logger.info(f"[PARALLEL] All {len(additional_agents)} agents completed in {total_elapsed:.2f}s total")
    logger.info(f"[PARALLEL] Results: {list(multi_agent_results.keys())}")
    
    # security_result를 별도로 추출하여 프론트엔드에서 직접 접근할 수 있게 함
    security_result = multi_agent_results.get("security")
    onboarding_result = multi_agent_results.get("onboarding")
    
    return {
        "multi_agent_results": multi_agent_results,
        "security_result": security_result,  # 프론트엔드에서 직접 접근 가능
        "onboarding_result": onboarding_result,  # 온보딩 결과도 직접 접근 가능
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
    
    # 세션 ID가 없으면 미리 생성 (LangGraph Checkpointer에 thread_id가 필요함)
    if not session_id:
        from backend.common.session import get_session_store
        session_store = get_session_store()
        session = session_store.create_session(owner=owner, repo=repo, ref=ref)
        session_id = session.session_id
        logger.info(f"Initialized new session in run_supervisor: {session_id}")
    
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
    
    # checkpointer 설정 (thread_id 필수)
    config = {"configurable": {"thread_id": session_id}}
    
    final_state = await graph.ainvoke(initial_state, config=config)
    
    # 최종 상태에서 owner/repo 추출 (세션에서 업데이트된 값 사용)
    final_owner = final_state.get("owner") or owner
    final_repo = final_state.get("repo") or repo
    
    return {
        "session_id": final_state.get("session_id"),
        "final_answer": final_state.get("final_answer"),
        "suggested_actions": final_state.get("suggested_actions", []),
        "awaiting_clarification": final_state.get("awaiting_clarification", False),
        "target_agent": final_state.get("target_agent"),
        "agent_result": final_state.get("agent_result"),
        "diagnosis_result": final_state.get("diagnosis_result"),
        "onboarding_result": final_state.get("onboarding_result"),  # 온보딩 결과
        "multi_agent_results": final_state.get("multi_agent_results", {}),
        "security_result": final_state.get("security_result") or final_state.get("multi_agent_results", {}).get("security"),
        "structure_visualization": final_state.get("structure_visualization"),
        "needs_clarification": final_state.get("needs_clarification", False),
        "large_repo_warning": final_state.get("large_repo_warning"),  # 대용량 저장소 경고
        "owner": final_owner,  # 프론트엔드 동기화용
        "repo": final_repo,    # 프론트엔드 동기화용
    }
