"""V1 Summarize Node: Generates final responses based on intent and diagnosis results.

분리된 모듈:
- summarizers/common.py: 공통 유틸 (LLM 호출, 응답 빌더 등)
- summarizers/overview.py: overview 모드 핸들러
- summarizers/followup.py: followup.evidence 모드 핸들러
- summarizers/refine.py: followup.refine 모드 핸들러
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.shared.contracts import (
    AnswerContract,
    safe_get,
)
from backend.common.events import EventType, emit_event
from backend.common.config import DEGRADE_ENABLED

from ..models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)

# Import from separated modules
from .summarizers.common import (
    LLMCallResult,
    DEGRADE_NO_ARTIFACT,
    DEGRADE_SCHEMA_FAIL,
    DEGRADE_LLM_FAIL,
    DEGRADE_SOURCE_ID,
    DEGRADE_SOURCE_KIND,
    extract_target_metrics,
    call_llm_with_retry,
    build_response,
    build_lightweight_response,
)
from .summarizers.overview import handle_overview_mode
from .summarizers.followup import handle_followup_evidence_mode
from .summarizers.refine import handle_refine_mode

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
_extract_target_metrics = extract_target_metrics
_call_llm_with_retry = call_llm_with_retry
_build_response = build_response
_build_lightweight_response = build_lightweight_response
_handle_overview_mode = handle_overview_mode
_handle_followup_evidence_mode = handle_followup_evidence_mode
_handle_refine_mode = handle_refine_mode


def summarize_node_v1(state: SupervisorState) -> Dict[str, Any]:
    """V1 summarize node: routes to appropriate prompt based on (intent, sub_intent)."""
    from ..prompts import (
        GREETING_TEMPLATE,
        NOT_READY_TEMPLATE,
        SMALLTALK_GREETING_TEMPLATE,
        SMALLTALK_CHITCHAT_TEMPLATE,
        HELP_GETTING_STARTED_TEMPLATE,
        OVERVIEW_REPO_TEMPLATE,
        SMALLTALK_SOURCE_ID,
        HELP_SOURCE_ID,
        OVERVIEW_SOURCE_ID,
        OVERVIEW_FALLBACK_TEMPLATE,
        MISSING_REPO_TEMPLATE,
        MISSING_REPO_SOURCE_ID,
        DISAMBIGUATION_SOURCE_ID,
        build_health_report_prompt,
        build_score_explain_prompt,
        build_overview_prompt,
        build_chat_prompt,
        get_llm_params,
    )
    from ..intent_config import is_v1_supported
    from ..service import fetch_overview_artifacts
    
    # Null-safe state access
    intent = safe_get(state, "intent", DEFAULT_INTENT)
    sub_intent = safe_get(state, "sub_intent", DEFAULT_SUB_INTENT)
    user_query = safe_get(state, "user_query", "")
    diagnosis_result = safe_get(state, "diagnosis_result")
    error_message = safe_get(state, "error_message")
    repo = safe_get(state, "repo")
    
    # 0. Error message takes priority
    if error_message:
        return build_response(state, error_message, "chat")
    
    # 0.3. Expert node already generated response (compare/onepager)
    existing_contract = safe_get(state, "answer_contract")
    if existing_contract and isinstance(existing_contract, dict) and existing_contract.get("text"):
        runner_meta = safe_get(state, "_runner_meta", {})
        if runner_meta.get("incomplete_compare"):
            existing_text = existing_contract.get("text", "")
            if "불완전 비교" not in existing_text and "※" not in existing_text:
                logger.warning(
                    "[summarize] incomplete_compare but warning missing in text"
                )
            
            failed_repos = runner_meta.get("failed_repos", [])
            failed_repo_ids = {f"{fr.get('owner')}/{fr.get('repo')}" for fr in failed_repos}
            
            sources = existing_contract.get("sources", [])
            clean_sources = [
                s for s in sources 
                if not any(fid in s for fid in failed_repo_ids)
            ]
            if clean_sources != sources:
                existing_contract["sources"] = clean_sources
                logger.info(
                    "[summarize] Removed failed repo artifacts from sources: %s",
                    [s for s in sources if s not in clean_sources]
                )
        
        return {
            "llm_summary": existing_contract.get("text", ""),
            "answer_kind": safe_get(state, "answer_kind", "chat"),
            "answer_contract": existing_contract,
            "last_brief": safe_get(state, "last_brief", ""),
            "last_answer_kind": safe_get(state, "answer_kind", "chat"),
        }
    
    # 0.5. Disambiguation: repo required but missing
    if safe_get(state, "_needs_disambiguation"):
        template = safe_get(state, "_disambiguation_template", MISSING_REPO_TEMPLATE)
        source_id = safe_get(state, "_disambiguation_source", DISAMBIGUATION_SOURCE_ID)
        candidate_sources = safe_get(state, "_disambiguation_candidate_sources", [])
        
        sources = [source_id]
        if candidate_sources:
            sources.extend(candidate_sources[:3])
        
        answer_contract = AnswerContract(
            text=template,
            sources=sources,
            source_kinds=["disambiguation"] + ["repo_candidate"] * len(candidate_sources[:3]),
        )
        
        emit_event(
            event_type=EventType.ANSWER_GENERATED,
            actor="summarize_node",
            inputs={"answer_kind": "disambiguation", "route": "entity_guard"},
            outputs={
                "text_length": len(template),
                "source_id": source_id,
                "candidate_count": len(candidate_sources),
                "latency_category": "instant",
            },
        )
        
        return {
            "llm_summary": answer_contract.text,
            "answer_kind": "disambiguation",
            "answer_contract": answer_contract.model_dump(),
            "last_brief": "disambiguation 응답 완료",
            "last_answer_kind": "disambiguation",
            "_needs_disambiguation": True,
        }
    
    # 0.6. Access Guard: repo inaccessible
    if safe_get(state, "_needs_ask_user"):
        template = safe_get(state, "_ask_user_template", "")
        source_id = safe_get(state, "_ask_user_source", "SYS:ACCESS_GUARD:ERROR")
        access_error = safe_get(state, "_access_error", "unknown")
        repo_ctx = safe_get(state, "_repo_context", {})
        repo_id = safe_get(repo_ctx, "repo_id", "")
        
        answer_contract = AnswerContract(
            text=template,
            sources=[source_id],
            source_kinds=["access_guard"],
        )
        
        emit_event(
            event_type=EventType.ANSWER_GENERATED,
            actor="summarize_node",
            inputs={"answer_kind": "ask_user", "route": "access_guard"},
            outputs={
                "text_length": len(template),
                "source_id": source_id,
                "access_error": access_error,
                "repo_id": repo_id,
                "latency_category": "instant",
            },
        )
        
        return {
            "llm_summary": answer_contract.text,
            "answer_kind": "ask_user",
            "answer_contract": answer_contract.model_dump(),
            "last_brief": f"접근 오류: {repo_id}",
            "last_answer_kind": "ask_user",
            "_needs_ask_user": True,
            "diagnosis_result": None,
        }
    
    # 1. Check V1 support
    if not is_v1_supported(intent, sub_intent):
        return build_response(state, NOT_READY_TEMPLATE, "chat")
    
    mode = (intent, sub_intent)
    
    # 2. Fast path: Smalltalk/Help (LLM 호출 없이 즉답)
    if intent == "smalltalk":
        if sub_intent == "greeting":
            return build_lightweight_response(
                state, SMALLTALK_GREETING_TEMPLATE, "greeting", SMALLTALK_SOURCE_ID
            )
        else:
            return build_lightweight_response(
                state, SMALLTALK_CHITCHAT_TEMPLATE, "greeting", SMALLTALK_SOURCE_ID
            )
    
    if intent == "help":
        return build_lightweight_response(
            state, HELP_GETTING_STARTED_TEMPLATE, "chat", HELP_SOURCE_ID
        )
    
    # 3. Overview path
    if intent == "overview" and sub_intent == "repo":
        return handle_overview_mode(state, repo)
    
    # 3.5. Follow-up Evidence path
    if mode == ("followup", "evidence"):
        return handle_followup_evidence_mode(state, user_query, diagnosis_result)
    
    # 3.6. Follow-up Refine path
    if mode == ("followup", "refine"):
        return handle_refine_mode(state, user_query)
    
    # 4. Route by mode (LLM required)
    
    # Health Report Mode
    if mode in [("analyze", "health"), ("analyze", "onboarding")]:
        if not diagnosis_result:
            if DEGRADE_ENABLED:
                return build_response(
                    state, 
                    DEGRADE_NO_ARTIFACT,
                    "report",
                    degraded=True
                )
            return build_response(
                state, 
                "저장소 분석 결과가 없습니다. 먼저 저장소를 분석해 주세요.",
                "report",
                degraded=True
            )
        
        # insufficient_data 체크
        labels = diagnosis_result.get("labels", {})
        if labels.get("insufficient_data", False):
            repo_info = diagnosis_result.get("details", {}).get("repo_info", {})
            data_quality_issues = labels.get("data_quality_issues", [])
            reason = ", ".join(data_quality_issues) if data_quality_issues else "활동 데이터 부족"
            
            insufficient_response = f"""**{repo_info.get('full_name', 'Unknown')}**

| 항목 | 값 |
|------|-----|
| 언어 | {repo_info.get('primary_language', repo_info.get('language', 'N/A'))} |
| Stars | {repo_info.get('stargazers_count', 0)} |
| Forks | {repo_info.get('forks_count', 0)} |

> **데이터 부족**: 이 저장소는 활동 데이터가 충분하지 않아 점수 산정이 어렵습니다.
> (이유: {reason})

**권장 행동**
- 활성화된 프로젝트로 다시 시도해 보세요
- 예: `facebook/react 분석해줘`"""
            return build_response(state, insufficient_response, "report", diagnosis_result)
        
        system_prompt, user_prompt = build_health_report_prompt(diagnosis_result)
        llm_params = get_llm_params("health_report")
        
        llm_result = call_llm_with_retry(system_prompt, user_prompt, llm_params)
        
        if llm_result.degraded and DEGRADE_ENABLED:
            return build_response(state, DEGRADE_SCHEMA_FAIL, "report", diagnosis_result, degraded=True)
        
        return build_response(state, llm_result.content, "report", diagnosis_result)
    
    # Score Explain Mode
    elif mode == ("followup", "explain"):
        if not diagnosis_result:
            if DEGRADE_ENABLED:
                return build_response(
                    state,
                    DEGRADE_NO_ARTIFACT,
                    "explain",
                    degraded=True
                )
            return build_response(
                state,
                "설명할 진단 결과가 없습니다. 먼저 저장소를 분석해 주세요. (예: 'facebook/react 분석해줘')",
                "explain",
                degraded=True
            )
        
        target_metrics = extract_target_metrics(user_query)
        if not target_metrics:
            target_metrics = ["health_score"]
        
        scores = safe_get(diagnosis_result, "scores", {})
        explain_context = safe_get(diagnosis_result, "explain_context", {})
        
        metric_name = target_metrics[0]
        metric_score = safe_get(scores, metric_name, "N/A")
        
        system_prompt, user_prompt = build_score_explain_prompt(
            metric_name=metric_name,
            metric_score=metric_score,
            explain_context=explain_context,
            user_query=user_query,
        )
        llm_params = get_llm_params("score_explain")
        
        llm_result = call_llm_with_retry(system_prompt, user_prompt, llm_params)
        
        if llm_result.degraded and DEGRADE_ENABLED:
            return build_response(state, DEGRADE_SCHEMA_FAIL, "explain", diagnosis_result, degraded=True)
        
        return build_response(state, llm_result.content, "explain", diagnosis_result)
    
    # Chat Mode
    elif intent == "general_qa":
        repo_summary = ""
        if repo and diagnosis_result:
            scores = safe_get(diagnosis_result, "scores", {})
            owner = safe_get(repo, "owner", "")
            name = safe_get(repo, "name", "")
            health_score = safe_get(scores, "health_score", "N/A")
            repo_summary = f"이전 분석: {owner}/{name} (건강 점수: {health_score})"
        
        system_prompt, user_prompt = build_chat_prompt(user_query, repo_summary)
        llm_params = get_llm_params("chat")
        
        llm_result = call_llm_with_retry(system_prompt, user_prompt, llm_params)
        
        if llm_result.degraded and DEGRADE_ENABLED:
            return build_response(state, DEGRADE_LLM_FAIL, "chat", degraded=True)
        
        return build_response(state, llm_result.content, "chat")
    
    # Fallback
    else:
        return build_response(state, NOT_READY_TEMPLATE, "chat")


# Legacy Alias
def summarize_node(state: SupervisorState) -> Dict[str, Any]:
    """Legacy alias for summarize_node_v1."""
    return summarize_node_v1(state)
