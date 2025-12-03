"""Common utilities for summarizers."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.diagnosis.tools.scoring.metric_definitions import (
    get_all_aliases,
    METRIC_DEFINITIONS,
)
from backend.agents.shared.contracts import (
    AnswerContract,
    safe_get,
)
from backend.common.events import EventType, emit_event

from ...models import SupervisorState

logger = logging.getLogger(__name__)


# Degrade Templates
DEGRADE_NO_ARTIFACT = """죄송합니다, 분석에 필요한 데이터를 가져오지 못했습니다.

**다음 행동을 시도해 보세요:**
1. 저장소 URL이 올바른지 확인해 주세요 (예: `facebook/react`)
2. 잠시 후 다시 시도해 주세요

문제가 계속되면 다른 저장소로 테스트해 보세요."""

DEGRADE_SCHEMA_FAIL = """분석 결과를 정리하는 중 문제가 발생했습니다.

**다음 행동을 시도해 보세요:**
1. 동일한 질문을 다시 시도해 주세요
2. 질문을 더 구체적으로 바꿔 보세요 (예: "health score 설명해줘")

데이터는 수집되었으나 요약에 실패했습니다."""

DEGRADE_LLM_FAIL = """응답 생성에 실패했습니다.

**다음 행동을 시도해 보세요:**
1. 잠시 후 다시 시도해 주세요
2. 더 간단한 질문으로 바꿔 보세요"""

DEGRADE_SOURCE_ID = "system_degrade_template"
DEGRADE_SOURCE_KIND = "system_template"


# Metric Constants
METRIC_ALIAS_MAP = get_all_aliases()
SORTED_ALIASES = sorted(METRIC_ALIAS_MAP.keys(), key=len, reverse=True)
METRIC_NAME_KR = {key: metric.name_ko for key, metric in METRIC_DEFINITIONS.items()}
AVAILABLE_METRICS = set(METRIC_DEFINITIONS.keys())
METRIC_LIST_TEXT = ", ".join(METRIC_NAME_KR.values())

METRIC_NOT_FOUND_MESSAGE = (
    "진단 결과에서 '{metrics}' 지표가 계산되지 않은 것으로 보입니다.\n"
    f"현재는 {METRIC_LIST_TEXT} 지표만 제공하고 있습니다."
)


# Source kinds by answer_kind
SOURCE_KIND_MAP = {
    "report": ["diagnosis_result"],
    "explain": ["diagnosis_result", "explain_context"],
    "greeting": ["system_template"],
    "chat": ["system_template"],
    "degrade": ["system_template"],
}


class LLMCallResult:
    """Result of LLM call with metadata."""
    def __init__(self, content: str, success: bool, retried: bool = False, degraded: bool = False):
        self.content = content
        self.success = success
        self.retried = retried
        self.degraded = degraded


def extract_target_metrics(user_query: str) -> List[str]:
    """Extracts metric keywords from user query using alias mapping."""
    query_lower = user_query.lower()
    found_metrics: List[str] = []
    
    for alias in SORTED_ALIASES:
        if alias in query_lower:
            metric_id = METRIC_ALIAS_MAP[alias]
            if metric_id not in found_metrics:
                found_metrics.append(metric_id)
    
    return found_metrics


def ensure_metrics_exist(
    state: SupervisorState, 
    requested_metrics: List[str]
) -> tuple[List[str], Optional[str]]:
    """Validates that requested metrics exist in diagnosis result."""
    diagnosis_result = safe_get(state, "diagnosis_result")
    if not diagnosis_result or not isinstance(diagnosis_result, dict):
        return [], "진단 결과가 없어 점수를 설명할 수 없습니다."
    
    scores = safe_get(diagnosis_result, "scores", {})
    available = set(scores.keys()) if isinstance(scores, dict) else set()
    
    valid = [m for m in requested_metrics if m in available]
    missing = [m for m in requested_metrics if m not in available and m not in AVAILABLE_METRICS]
    
    if not valid and missing:
        missing_names = ", ".join(missing)
        return [], METRIC_NOT_FOUND_MESSAGE.format(metrics=missing_names)
    
    if not valid and requested_metrics:
        unknown_names = ", ".join(requested_metrics)
        return [], METRIC_NOT_FOUND_MESSAGE.format(metrics=unknown_names)
    
    return valid, None


def generate_last_brief(summary: str, repo_id: str = "") -> str:
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


def call_llm_with_retry(
    system_prompt: str, 
    user_prompt: str, 
    params: dict,
    max_retries: int = 1,
) -> LLMCallResult:
    """Calls LLM with retry logic."""
    client = fetch_llm_client()
    last_error: Optional[Exception] = None
    retried = False
    
    for attempt in range(max_retries + 1):
        try:
            request = ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                temperature=params.get("temperature", 0.3),
                max_tokens=params.get("max_tokens", 1024),
                top_p=params.get("top_p", 0.9),
            )
            content = client.chat(request).content
            
            if content and content.strip():
                return LLMCallResult(content, success=True, retried=retried)
            
            retried = True
            logger.warning(f"LLM returned empty response, attempt {attempt + 1}")
            
        except Exception as e:
            last_error = e
            retried = True
            logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(0.5)
    
    logger.error(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
    return LLMCallResult(
        content=DEGRADE_LLM_FAIL,
        success=False,
        retried=True,
        degraded=True
    )


def call_llm(system_prompt: str, user_prompt: str, params: dict) -> str:
    """Calls LLM with the given prompts. Legacy wrapper."""
    result = call_llm_with_retry(system_prompt, user_prompt, params)
    return result.content


def build_response(
    state: SupervisorState,
    summary: str,
    answer_kind: str,
    diagnosis_result: Optional[Dict] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Builds the response state update with AnswerContract enforcement."""
    repo = safe_get(state, "repo")
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}" if owner or name else ""
    
    # Auto-select notice
    auto_select_notice = safe_get(state, "_auto_select_notice", "")
    if auto_select_notice and summary:
        summary = f"{auto_select_notice}\n\n---\n\n{summary}"
    
    # AnswerContract enforcement
    source_kinds = SOURCE_KIND_MAP.get(answer_kind, ["system_template"])
    sources: List[str] = []
    
    auto_select_source = safe_get(state, "_auto_select_source", "")
    if auto_select_source:
        sources.append(auto_select_source)
    
    if diagnosis_result and not degraded:
        sources.append(f"diagnosis_{repo_id.replace('/', '_')}")
    else:
        sources.append(DEGRADE_SOURCE_ID)
        source_kinds = [DEGRADE_SOURCE_KIND]
    
    answer_contract = AnswerContract(
        text=summary or "",
        sources=sources,
        source_kinds=source_kinds[:len(sources)] if sources else [],
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": answer_kind, "repo": repo_id},
        outputs={
            "text_length": len(summary or ""),
            "source_count": len(sources),
            "source_kinds": source_kinds,
        },
    )
    
    result: Dict[str, Any] = {
        "llm_summary": answer_contract.text,
        "answer_kind": answer_kind,
        "answer_contract": answer_contract.model_dump(),
        "last_brief": generate_last_brief(summary, repo_id),
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


def build_lightweight_response(
    state: SupervisorState,
    template: str,
    answer_kind: str,
    source_id: str,
) -> Dict[str, Any]:
    """Builds lightweight response without LLM call."""
    repo = safe_get(state, "repo")
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}" if owner or name else ""
    
    answer_contract = AnswerContract(
        text=template,
        sources=[source_id],
        source_kinds=["system_template"],
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": answer_kind, "lightweight": True},
        outputs={
            "text_length": len(template),
            "source_id": source_id,
            "latency_category": "instant",
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": answer_kind,
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"{answer_kind} 응답 완료",
        "last_answer_kind": answer_kind,
    }
