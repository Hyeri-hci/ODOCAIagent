"""
Intent Parser Node
Supervisor Agent의 의도 분석을 담당하는 노드입니다.
"""

import logging
import re
from typing import Dict, Any, List, cast

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.intent_parser import SupervisorIntentParserV2
from backend.common.github_client import search_repositories
from backend.common.intent_utils import extract_experience_level
from backend.common.pronoun_resolver import resolve_pronoun
from backend.common.session import ConversationTurn, AccumulatedContext
from backend.agents.supervisor.repo_detector import detect_repository_from_message
from backend.prompts.loader import render_prompt, get_system_prompt
from backend.common.example_selector import get_example_selector

logger = logging.getLogger(__name__)

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
                
                # 하이브리드 Few-shot 적용
                selector = get_example_selector()
                # 사용자 메시지를 쿼리로 사용하여 유사한 예제 검색
                selected_examples = selector.select_examples(user_message)
                
                # 예제를 문자열로 포맷팅
                example_text = ""
                for ex in selected_examples:
                    example_text += f"- User: {ex['input']}\n  Intent: {ex['output']}\n"
                
                system_prompt = render_prompt("supervisor_prompts", "intent_classification", examples=example_text)
                
                parser = SupervisorIntentParserV2(system_prompt=system_prompt)
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
        
        # 현재 메시지가 새로운 요청인지 체크 (의도 변경 감지)
        diagnosis_keywords = ["분석해", "진단해", "analyze", "diagnose", "확인해봐", "살펴봐"]
        recommend_keywords = ["추천", "recommend", "찾아줘", "알려줘"]
        is_new_diagnosis_intent = any(kw in msg_lower for kw in diagnosis_keywords)
        is_new_recommend_intent = any(kw in msg_lower for kw in recommend_keywords)
        
        if is_new_diagnosis_intent or is_new_recommend_intent:
            # 의도 변경 감지: 새로운 diagnosis/recommend 요청
            # pending_request를 클리어하고 새로운 요청으로 처리
            new_intent = "diagnosis" if is_new_diagnosis_intent else "recommend"
            logger.info(f"Intent change detected: '{original_task_type}' → '{new_intent}', skipping pending_request merge")
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
        if detected_owner and detected_repo:
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
    last_mentioned = accumulated_context.get("last_mentioned_repo") or {}
    if last_mentioned.get("owner") and last_mentioned.get("repo"):
        has_existing_repo = True
        logger.info(f"Existing repo in session: {last_mentioned['owner']}/{last_mentioned['repo']}")
    else:
        logger.info("No existing repo in session accumulated_context")

    if not detected_repo and not has_existing_repo:
        # LLM 기반 저장소 감지 (룰 베이스 키워드 리스트 제거)
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
            
            # 기술 스택 응답 처리
            if "기술 스택을 알려주세요" in last_response or last_intent.get("clarification_type") == "tech_stack":
                # 쉼표 또는 공백으로 구분된 기술 스택 파싱
                tech_input = user_message.strip()
                tech_list = [t.strip() for t in tech_input.replace(",", " ").split() if t.strip()]
                
                if tech_list:
                    logger.info(f"Tech stack from clarification: {tech_list}")
                    new_context = dict(accumulated_context)
                    user_profile = new_context.get("user_profile", {})
                    user_profile["tech_stack"] = tech_list
                    new_context["user_profile"] = user_profile
                    
                    # 원래 요청이 뭐였는지 확인
                    pending_action = accumulated_context.get("pending_action", "issues")
                    target = accumulated_context.get("pending_target_agent", "onboarding")
                    
                    return {
                        "supervisor_intent": {
                            "task_type": "onboarding" if target == "onboarding" else "contributor",
                            "target_agent": target,
                            "needs_clarification": False,
                            "confidence": 0.95,
                            "reasoning": f"Clarification 응답에서 기술 스택 '{tech_list}' 감지"
                        },
                        "needs_clarification": False,
                        "clarification_questions": [],
                        "target_agent": target,
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
        "detected_repo": f"{detected_owner}/{detected_repo}" if detected_owner and detected_repo else f"{context_owner}/{context_repo}" if context_owner and context_repo else None
    }
    
    # === 6단계: LLM 의도 파싱 ===
    parser = SupervisorIntentParserV2()
    
    # detected_owner/repo가 이미 있으면 intent_parser에게 전달
    pre_detected_repo = f"{detected_owner}/{detected_repo}" if detected_owner and detected_repo else None
    
    intent = await parser.parse(
        user_message=resolved_message,
        session_context=session_context,
        pre_detected_repo=pre_detected_repo  # 이미 감지된 저장소 전달
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

    # comparison_targets 처리
    if intent.comparison_targets:
        result["compare_repos"] = intent.comparison_targets
        logger.info(f"Comparison targets mapped to compare_repos: {intent.comparison_targets}")
    elif intent.task_type == "compare_repos" or intent.target_agent == "comparison":
        # 타겟이 없으면 히스토리에서 최근 2개 검색
        analyzed_repos = accumulated_context.get("analyzed_repos", [])
        if len(analyzed_repos) >= 2:
            # 최근 순서대로 정렬되어 있다고 가정 (또는 analyzed_at으로 정렬)
            # analyzed_repos는 append 되므로 뒤쪽이 최신
            recent_repos = analyzed_repos[-2:]
            targets = [f"{r['owner']}/{r['repo']}" for r in recent_repos]
            
            result["compare_repos"] = targets
            # result["needs_clarification"] = False # 명확화 불필요
            logger.info(f"No explicit comparison targets, using recent history: {targets}")
            
            # 사용자에게 알림 메시지를 주면 좋겠지만, 여기서는 state만 설정
    
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

# === Clarification Nodes ===

from typing import Literal

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

