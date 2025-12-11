"""Supervisor intent parsing node."""
from __future__ import annotations
import json
import logging
import re
from typing import Any, Dict, cast, Tuple, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.supervisor.models import SupervisorState, TaskType
from backend.common.config import LLM_MODEL_NAME, LLM_API_BASE, LLM_API_KEY
from backend.agents.supervisor.nodes.routing_nodes import INTENT_TO_TASK_TYPE, INTENT_KEYWORDS
from backend.agents.supervisor.prompts import INTENT_PARSE_PROMPT

logger = logging.getLogger(__name__)


def _extract_github_repo(message: str) -> Optional[Tuple[str, str]]:
    """GitHub 저장소 URL/단축 포맷에서 owner/repo 추출."""
    if not message:
        return None
    
    url_match = re.search(r'github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)', message, re.IGNORECASE)
    if url_match:
        owner, repo = url_match.group(1), url_match.group(2)
        if repo.endswith('.git'):
            repo = repo[:-4]
        return owner, repo
    
    short_match = re.search(r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)', message)
    if short_match:
        owner, repo = short_match.group(1), short_match.group(2)
        if len(owner) > 2 and len(repo) > 2:
            return owner, repo
    
    return None


def _get_llm() -> ChatOpenAI:
    """Get ChatOpenAI instance."""
    return ChatOpenAI(
        model=LLM_MODEL_NAME,
        api_key=LLM_API_KEY,  # type: ignore
        base_url=LLM_API_BASE,
        temperature=0.1
    )


def _invoke_chain(prompt: ChatPromptTemplate, params: Dict[str, Any]) -> str:
    try:
        llm = _get_llm()
        chain = prompt | llm
        response = chain.invoke(params)
        content = str(response.content).strip() if response.content else ""
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return content
    except Exception as e:
        logger.error(f"Chain invoke failed: {e}")
        raise


async def _ainvoke_chain(prompt: ChatPromptTemplate, params: Dict[str, Any]) -> str:
    try:
        llm = _get_llm()
        chain = prompt | llm
        response = await chain.ainvoke(params)
        content = str(response.content).strip() if response.content else ""
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return content
    except Exception as e:
        logger.error(f"Async chain invoke failed: {e}")
        raise


def _map_intent_to_task_type(intent: str, fallback: TaskType) -> TaskType:
    mapped = INTENT_TO_TASK_TYPE.get(intent)
    if mapped in ("diagnose_repo", "build_onboarding_plan", "general_inquiry"):
        return cast(TaskType, mapped)
    return fallback


def _detect_onboard_intent(message: str) -> bool:
    if not message:
        return False
    msg_lower = message.lower()
    for keyword in INTENT_KEYWORDS.get("onboard", []):
        if keyword.lower() in msg_lower:
            return True
    return False


def _extract_experience_level(message: str) -> str:
    if not message:
        return "beginner"
    msg_lower = message.lower()
    
    intermediate_keywords = ["중급", "intermediate", "중간", "보통", "일반"]
    advanced_keywords = ["고급", "advanced", "숙련", "전문가", "expert", "senior", "시니어"]
    
    for kw in advanced_keywords:
        if kw in msg_lower:
            return "advanced"
    
    for kw in intermediate_keywords:
        if kw in msg_lower:
            return "intermediate"
    
    return "beginner"


def parse_supervisor_intent(state: SupervisorState) -> Dict[str, Any]:
    user_msg = state.user_message or state.chat_message or ""
    
    new_repo = _extract_github_repo(user_msg)
    new_owner, new_repo_name = None, None
    if new_repo:
        extracted_owner, extracted_repo = new_repo
        if (extracted_owner.lower() != (state.owner or "").lower() or 
            extracted_repo.lower() != (state.repo or "").lower()):
            new_owner, new_repo_name = extracted_owner, extracted_repo
            logger.info(f"New repository detected in message: {new_owner}/{new_repo_name}")
    
    if _detect_onboard_intent(user_msg):
        exp_level = _extract_experience_level(user_msg)
        focus_map = {
            "beginner": ["beginner-friendly", "good first issue", "easy"],
            "intermediate": ["help wanted", "enhancement", "bug"],
            "advanced": ["core", "architecture", "performance", "security"],
        }
        focus = focus_map.get(exp_level, focus_map["beginner"])
        
        logger.info(f"Onboard intent detected via keyword matching: '{user_msg[:50]}...', experience_level={exp_level}")
        result = {
            "global_intent": "onboard",
            "detected_intent": "onboard",
            "task_type": "build_onboarding_plan",
            "user_preferences": {"focus": focus, "ignore": [], "experience_level": exp_level},
            "priority": "thoroughness",
            "step": state.step + 1,
        }
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
    
    response = None
    try:
        response = _invoke_chain(INTENT_PARSE_PROMPT, {
            "user_message": user_msg,
            "task_type": state.task_type,
            "owner": state.owner or "",
            "repo": state.repo or "",
        })
        parsed = json.loads(response)
        
        logger.info(f"Parsed intent: {parsed}")
        global_intent = parsed.get("task_type", "chat")
        mapped_task_type = _map_intent_to_task_type(global_intent, state.task_type)
        
        result = {
            "global_intent": global_intent,
            "detected_intent": global_intent,
            "task_type": mapped_task_type,
            "user_preferences": parsed.get("user_preferences", {"focus": [], "ignore": []}),
            "priority": parsed.get("priority", "thoroughness"),
            "step": state.step + 1,
        }
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}, raw_response={response!r}")
        fallback_intent = "chat"
        result = {
            "global_intent": fallback_intent,
            "detected_intent": fallback_intent,
            "task_type": state.task_type,
            "user_preferences": {"focus": [], "ignore": []},
            "priority": "thoroughness",
            "step": state.step + 1,
        }
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result


async def parse_supervisor_intent_async(state: SupervisorState) -> Dict[str, Any]:
    """Parse top-level intent from user message (async)."""
    user_msg = state.user_message or state.chat_message or ""
    
    new_repo = _extract_github_repo(user_msg)
    new_owner, new_repo_name = None, None
    if new_repo:
        extracted_owner, extracted_repo = new_repo
        if (extracted_owner.lower() != (state.owner or "").lower() or 
            extracted_repo.lower() != (state.repo or "").lower()):
            new_owner, new_repo_name = extracted_owner, extracted_repo
            logger.info(f"New repository detected in message: {new_owner}/{new_repo_name}")
    
    if _detect_onboard_intent(user_msg):
        exp_level = _extract_experience_level(user_msg)
        focus_map = {
            "beginner": ["beginner-friendly", "good first issue", "easy"],
            "intermediate": ["help wanted", "enhancement", "bug"],
            "advanced": ["core", "architecture", "performance", "security"],
        }
        focus = focus_map.get(exp_level, focus_map["beginner"])
        
        logger.info(f"Onboard intent detected via keyword matching: '{user_msg[:50]}...', experience_level={exp_level}")
        result = {
            "global_intent": "onboard",
            "detected_intent": "onboard",
            "task_type": "build_onboarding_plan",
            "user_preferences": {"focus": focus, "ignore": [], "experience_level": exp_level},
            "priority": "thoroughness",
            "step": state.step + 1,
        }
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
    
    response = None
    try:
        response = await _ainvoke_chain(INTENT_PARSE_PROMPT, {
            "user_message": user_msg,
            "task_type": state.task_type,
            "owner": state.owner or "",
            "repo": state.repo or "",
        })
        parsed = json.loads(response)
        
        logger.info(f"Parsed intent (async): {parsed}")
        global_intent = parsed.get("task_type", "chat")
        mapped_task_type = _map_intent_to_task_type(global_intent, state.task_type)
        
        result = {
            "global_intent": global_intent,
            "detected_intent": global_intent,
            "task_type": mapped_task_type,
            "user_preferences": parsed.get("user_preferences", {"focus": [], "ignore": []}),
            "priority": parsed.get("priority", "thoroughness"),
            "step": state.step + 1,
        }
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
    except Exception as e:
        logger.error(f"Intent parsing failed (async): {e}, raw_response={response!r}")
        fallback_intent = "chat"
        result = {
            "global_intent": fallback_intent,
            "detected_intent": fallback_intent,
            "task_type": state.task_type,
            "user_preferences": {"focus": [], "ignore": []},
            "priority": "thoroughness",
            "step": state.step + 1,
        }
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
