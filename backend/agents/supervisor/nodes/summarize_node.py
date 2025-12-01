"""V1 Summarize Node: Generates final responses based on intent and diagnosis results."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.diagnosis.tools.scoring.metric_definitions import (
    get_all_aliases,
    METRIC_DEFINITIONS,
)
from backend.agents.shared.contracts import AnswerContract
from backend.common.events import EventType, emit_event

from ..models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Metric Constants
# =============================================================================

METRIC_ALIAS_MAP = get_all_aliases()
SORTED_ALIASES = sorted(METRIC_ALIAS_MAP.keys(), key=len, reverse=True)
METRIC_NAME_KR = {key: metric.name_ko for key, metric in METRIC_DEFINITIONS.items()}
AVAILABLE_METRICS = set(METRIC_DEFINITIONS.keys())
METRIC_LIST_TEXT = ", ".join(METRIC_NAME_KR.values())

METRIC_NOT_FOUND_MESSAGE = (
    "진단 결과에서 '{metrics}' 지표가 계산되지 않은 것으로 보입니다.\n"
    f"현재는 {METRIC_LIST_TEXT} 지표만 제공하고 있습니다."
)


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_target_metrics(user_query: str) -> List[str]:
    """Extracts metric keywords from user query using alias mapping."""
    query_lower = user_query.lower()
    found_metrics: List[str] = []
    
    for alias in SORTED_ALIASES:
        if alias in query_lower:
            metric_id = METRIC_ALIAS_MAP[alias]
            if metric_id not in found_metrics:
                found_metrics.append(metric_id)
    
    return found_metrics


def _ensure_metrics_exist(
    state: SupervisorState, 
    requested_metrics: List[str]
) -> tuple[List[str], Optional[str]]:
    """Validates that requested metrics exist in diagnosis result."""
    diagnosis_result = state.get("diagnosis_result")
    if not diagnosis_result or not isinstance(diagnosis_result, dict):
        return [], "진단 결과가 없어 점수를 설명할 수 없습니다."
    
    scores = diagnosis_result.get("scores", {})
    available = set(scores.keys())
    
    valid = [m for m in requested_metrics if m in available]
    missing = [m for m in requested_metrics if m not in available and m not in AVAILABLE_METRICS]
    
    if not valid and missing:
        missing_names = ", ".join(missing)
        return [], METRIC_NOT_FOUND_MESSAGE.format(metrics=missing_names)
    
    if not valid and requested_metrics:
        unknown_names = ", ".join(requested_metrics)
        return [], METRIC_NOT_FOUND_MESSAGE.format(metrics=unknown_names)
    
    return valid, None


def _generate_last_brief(summary: str, repo_id: str = "") -> str:
    """Generates a brief summary (max 200 chars) for next turn context."""
    if not summary or not summary.strip():
        return f"{repo_id} 분석 완료" if repo_id else ""
    
    lines = summary.split("\n")
    content_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("---"):
            continue
        if stripped.startswith("**"):
            continue
        content_lines.append(stripped)
    
    if not content_lines:
        return f"{repo_id} 분석 완료" if repo_id else "분석 완료"
    
    result = " ".join(content_lines)
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'^[-*]\s*', '', result)
    result = re.sub(r'\s[-*]\s', ' ', result)
    
    if len(result) > 200:
        result = result[:197]
        last_period = max(result.rfind("."), result.rfind("요"), result.rfind("다"))
        if last_period > 100:
            result = result[:last_period + 1]
        else:
            result = result[:197] + "..."
    
    return result


# =============================================================================
# LLM Call
# =============================================================================

def _call_llm(system_prompt: str, user_prompt: str, params: dict) -> str:
    """Calls LLM with the given prompts and parameters."""
    try:
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=params.get("temperature", 0.3),
            max_tokens=params.get("max_tokens", 1024),
            top_p=params.get("top_p", 0.9),
        )
        return client.chat(request).content
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return f"응답 생성 중 오류가 발생했습니다: {str(e)}"


# =============================================================================
# Response Builder (with AnswerContract enforcement)
# =============================================================================

# Source kinds by answer_kind
SOURCE_KIND_MAP = {
    "report": ["diagnosis_result"],
    "explain": ["diagnosis_result", "explain_context"],
    "greeting": [],
    "chat": [],
}


def _build_response(
    state: SupervisorState,
    summary: str,
    answer_kind: str,
    diagnosis_result: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Builds the response state update with AnswerContract enforcement."""
    repo = state.get("repo")
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}" if repo else ""
    
    # AnswerContract enforcement
    source_kinds = SOURCE_KIND_MAP.get(answer_kind, [])
    sources: List[str] = []
    if diagnosis_result and source_kinds:
        sources.append(f"diagnosis_{repo_id.replace('/', '_')}")
    
    answer_contract = AnswerContract(
        text=summary,
        sources=sources,
        source_kinds=source_kinds[:len(sources)] if sources else [],
    )
    
    # Emit ANSWER_GENERATED event
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": answer_kind, "repo": repo_id},
        outputs={
            "text_length": len(summary),
            "source_count": len(sources),
            "source_kinds": source_kinds,
        },
    )
    
    result: Dict[str, Any] = {
        "llm_summary": answer_contract.text,
        "answer_kind": answer_kind,
        "answer_contract": answer_contract.model_dump(),
        "last_brief": _generate_last_brief(summary, repo_id),
        "last_answer_kind": answer_kind,
    }
    
    # Save task list for follow-up
    if diagnosis_result:
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        if onboarding_tasks:
            task_list = []
            for difficulty in ["beginner", "intermediate", "advanced"]:
                for task in onboarding_tasks.get(difficulty, []):
                    task_copy = dict(task)
                    if "difficulty" not in task_copy:
                        task_copy["difficulty"] = difficulty
                    task_list.append(task_copy)
            result["last_task_list"] = task_list
    
    return result


# =============================================================================
# V1 Summarize Node (Main Entry Point)
# =============================================================================

def summarize_node_v1(state: SupervisorState) -> Dict[str, Any]:
    """V1 summarize node: routes to appropriate prompt based on (intent, sub_intent)."""
    from ..prompts import (
        GREETING_TEMPLATE,
        NOT_READY_TEMPLATE,
        build_health_report_prompt,
        build_score_explain_prompt,
        build_chat_prompt,
        get_llm_params,
    )
    from ..intent_config import is_v1_supported
    
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent", DEFAULT_SUB_INTENT)
    user_query = state.get("user_query", "")
    diagnosis_result = state.get("diagnosis_result")
    error_message = state.get("error_message")
    
    # 0. Error message takes priority
    if error_message:
        return _build_response(state, error_message, "chat")
    
    # 1. Check V1 support
    if not is_v1_supported(intent, sub_intent):
        return _build_response(state, NOT_READY_TEMPLATE, "chat")
    
    mode = (intent, sub_intent)
    
    # 2. Route by mode
    
    # --- Health Report Mode ---
    if mode in [("analyze", "health"), ("analyze", "onboarding")]:
        if not diagnosis_result:
            return _build_response(
                state, 
                "저장소 분석 결과가 없습니다. 먼저 저장소를 분석해 주세요.",
                "report"
            )
        
        system_prompt, user_prompt = build_health_report_prompt(diagnosis_result)
        llm_params = get_llm_params("health_report")
        summary = _call_llm(system_prompt, user_prompt, llm_params)
        return _build_response(state, summary, "report", diagnosis_result)
    
    # --- Score Explain Mode ---
    elif mode == ("followup", "explain"):
        if not diagnosis_result:
            return _build_response(
                state,
                "설명할 진단 결과가 없습니다. 먼저 저장소를 분석해 주세요. (예: 'facebook/react 분석해줘')",
                "explain"
            )
        
        target_metrics = _extract_target_metrics(user_query)
        if not target_metrics:
            target_metrics = ["health_score"]
        
        scores = diagnosis_result.get("scores", {})
        explain_context = diagnosis_result.get("explain_context", {})
        
        metric_name = target_metrics[0]
        metric_score = scores.get(metric_name, "N/A")
        
        system_prompt, user_prompt = build_score_explain_prompt(
            metric_name=metric_name,
            metric_score=metric_score,
            explain_context=explain_context,
            user_query=user_query,
        )
        llm_params = get_llm_params("score_explain")
        summary = _call_llm(system_prompt, user_prompt, llm_params)
        return _build_response(state, summary, "explain", diagnosis_result)
    
    # --- Greeting Mode ---
    elif intent == "smalltalk":
        return _build_response(state, GREETING_TEMPLATE, "greeting")
    
    # --- Chat Mode ---
    elif intent == "general_qa":
        repo = state.get("repo")
        repo_summary = ""
        if repo and diagnosis_result:
            scores = diagnosis_result.get("scores", {})
            repo_summary = f"이전 분석: {repo.get('owner')}/{repo.get('name')} (건강 점수: {scores.get('health_score', 'N/A')})"
        
        system_prompt, user_prompt = build_chat_prompt(user_query, repo_summary)
        llm_params = get_llm_params("chat")
        summary = _call_llm(system_prompt, user_prompt, llm_params)
        return _build_response(state, summary, "chat")
    
    # --- Fallback ---
    else:
        return _build_response(state, NOT_READY_TEMPLATE, "chat")


# =============================================================================
# Legacy Alias (for backward compatibility)
# =============================================================================

def summarize_node(state: SupervisorState) -> Dict[str, Any]:
    """Legacy alias for summarize_node_v1."""
    return summarize_node_v1(state)
