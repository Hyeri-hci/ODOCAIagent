"""Classify Node: Intent classification and entity/access guards."""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.supervisor.models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)
from backend.agents.supervisor.intent_config import get_intent_meta
from backend.common.events import EventType, emit_event
from backend.agents.shared.contracts import safe_get
from backend.common.github_client import check_repo_access

logger = logging.getLogger(__name__)


def classify_node(state: SupervisorState) -> Dict[str, Any]:
    """Classifies user intent using simple rules or LLM."""
    from backend.agents.supervisor.nodes.intent_classifier import (
        classify_intent_node,
        _extract_keyword_candidates,
    )
    from backend.agents.supervisor.prompts import (
        MISSING_REPO_TEMPLATE,
        DISAMBIGUATION_CANDIDATES_TEMPLATE,
        DISAMBIGUATION_SOURCE_ID,
        AUTO_SELECT_REPO_TEMPLATE,
        AUTO_SELECT_SOURCE_ID,
        ACCESS_ERROR_NOT_FOUND_TEMPLATE,
        ACCESS_ERROR_PRIVATE_TEMPLATE,
        ACCESS_ERROR_RATE_LIMIT_TEMPLATE,
        ACCESS_ERROR_SOURCE_ID,
    )
    
    emit_event(
        EventType.NODE_STARTED,
        actor="classify_node",
        inputs={"query_length": len(state.get("user_query", ""))},
    )
    
    result = classify_intent_node(state)
    
    intent = result.get("intent", DEFAULT_INTENT)
    sub_intent = result.get("sub_intent", DEFAULT_SUB_INTENT)
    
    # Set default answer_kind based on intent
    answer_kind = _get_default_answer_kind(intent, sub_intent)
    result["answer_kind"] = answer_kind
    
    # Entity Guard: analyze/* intent requires repo - ALWAYS check
    meta = get_intent_meta(intent, sub_intent)
    if meta["requires_repo"] and not result.get("repo"):
        # Extract keyword candidates from query
        user_query = state.get("user_query", "")
        keyword, candidates = _extract_keyword_candidates(user_query)
        
        if keyword and candidates:
            if len(candidates) == 1:
                # Single candidate: auto-select with notice (no disambiguation)
                c = candidates[0]
                result["repo"] = {
                    "owner": c["owner"],
                    "name": c["name"],
                    "url": f"https://github.com/{c['owner']}/{c['name']}",
                }
                result["_auto_selected_repo"] = True
                result["_auto_select_notice"] = AUTO_SELECT_REPO_TEMPLATE.format(
                    keyword=keyword,
                    owner=c["owner"],
                    repo=c["name"],
                    desc=c.get("desc", ""),
                )
                result["_auto_select_source"] = AUTO_SELECT_SOURCE_ID
                
                logger.info(
                    "[entity_guard] analyze/%s: auto-selected %s/%s (single candidate for '%s')",
                    sub_intent, c["owner"], c["name"], keyword
                )
            else:
                # Multiple candidates: force disambiguation
                result["_needs_disambiguation"] = True
                
                candidate_lines = []
                candidate_sources = []
                for c in candidates[:3]:
                    candidate_lines.append(f"- `{c['owner']}/{c['name']}` - {c['desc']}")
                    candidate_sources.append(f"CANDIDATE:{c['owner']}/{c['name']}")
                candidates_text = "\n".join(candidate_lines)
                
                result["_disambiguation_template"] = DISAMBIGUATION_CANDIDATES_TEMPLATE.format(
                    keyword=keyword,
                    candidates=candidates_text,
                )
                result["_disambiguation_source"] = DISAMBIGUATION_SOURCE_ID
                result["_disambiguation_candidates"] = candidates
                result["_disambiguation_candidate_sources"] = candidate_sources
                result["answer_kind"] = "disambiguation"
                
                logger.info(
                    "[entity_guard] analyze/%s blocked: disambiguation forced (keyword=%s, candidates=%d)",
                    sub_intent, keyword, len(candidates)
                )
        else:
            # No candidates: force disambiguation with generic message
            result["_needs_disambiguation"] = True
            result["_disambiguation_template"] = MISSING_REPO_TEMPLATE
            result["_disambiguation_source"] = "SYS:TEMPLATES:MISSING_REPO"
            result["answer_kind"] = "disambiguation"
            
            logger.info(
                "[entity_guard] analyze/%s blocked: no repo, no candidates",
                sub_intent
            )
    
    # Access Guard: Pre-flight check for repo accessibility (BEFORE diagnosis)
    repo = result.get("repo")
    if repo and meta["requires_repo"] and not result.get("_needs_disambiguation"):
        owner = safe_get(repo, "owner", "")
        name = safe_get(repo, "name", "")
        
        if owner and name:
            access_result = check_repo_access(owner, name)
            
            # Store repo context for artifact validation
            result["_repo_context"] = {
                "owner": owner,
                "repo": name,
                "repo_id": access_result.repo_id,
                "default_branch": access_result.default_branch,
                "accessible": access_result.accessible,
            }
            
            if not access_result.accessible:
                # CRITICAL: Block diagnosis path - force ask_user
                result["_needs_ask_user"] = True
                result["_access_error"] = access_result.reason
                result["answer_kind"] = "ask_user"
                
                # Select appropriate error template
                if access_result.reason == "not_found":
                    result["_ask_user_template"] = ACCESS_ERROR_NOT_FOUND_TEMPLATE.format(
                        owner=owner, repo=name
                    )
                elif access_result.reason == "private_no_access":
                    result["_ask_user_template"] = ACCESS_ERROR_PRIVATE_TEMPLATE.format(
                        owner=owner, repo=name
                    )
                elif access_result.reason == "rate_limit":
                    result["_ask_user_template"] = ACCESS_ERROR_RATE_LIMIT_TEMPLATE
                else:
                    result["_ask_user_template"] = ACCESS_ERROR_NOT_FOUND_TEMPLATE.format(
                        owner=owner, repo=name
                    )
                result["_ask_user_source"] = ACCESS_ERROR_SOURCE_ID
                
                logger.info(
                    "[access_guard] %s/%s blocked: %s (status=%d)",
                    owner, name, access_result.reason, access_result.status_code
                )
                
                emit_event(
                    EventType.SUPERVISOR_ROUTE_SELECTED,
                    actor="supervisor",
                    outputs={
                        "selected_route": "ask_user",
                        "intent": intent,
                        "sub_intent": sub_intent,
                        "repo": f"{owner}/{name}",
                        "access_error": access_result.reason,
                        "status_code": access_result.status_code,
                    },
                )
    
    # Emit route selection event for disambiguation
    if result.get("_needs_disambiguation"):
        emit_event(
            EventType.SUPERVISOR_ROUTE_SELECTED,
            actor="supervisor",
            outputs={
                "selected_route": "disambiguation",
                "intent": intent,
                "sub_intent": sub_intent,
                "has_candidates": bool(result.get("_disambiguation_candidates")),
                "candidate_count": len(result.get("_disambiguation_candidates", [])),
            },
        )
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="classify_node",
        outputs={
            "intent": intent,
            "sub_intent": sub_intent,
            "answer_kind": result.get("answer_kind", answer_kind),
            "needs_disambiguation": result.get("_needs_disambiguation", False),
            "needs_ask_user": result.get("_needs_ask_user", False),
        },
    )
    
    return result


def _get_default_answer_kind(intent: str, sub_intent: str) -> str:
    """Maps (intent, sub_intent) to default answer_kind."""
    if intent == "analyze":
        return "report"
    elif intent == "followup" and sub_intent == "explain":
        return "explain"
    elif intent == "smalltalk":
        return "greeting"
    else:
        return "chat"
