"""V1 Summarize Node: Generates final responses based on intent and diagnosis results."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.diagnosis.tools.scoring.metric_definitions import (
    get_all_aliases,
    METRIC_DEFINITIONS,
)
from backend.agents.shared.contracts import (
    AnswerContract,
    safe_get,
    safe_get_nested,
)
from backend.common.events import EventType, emit_event
from backend.common.config import DEGRADE_ENABLED

from ..models import (
    SupervisorState,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)

logger = logging.getLogger(__name__)


# Degrade Templates (아티팩트 부족/스키마 실패 시 응답)
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

# Source for degrade responses
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


# Helper Functions
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
    """Validates that requested metrics exist in diagnosis result. Null-safe."""
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


# LLM Call with Retry and Degrade
class LLMCallResult:
    """Result of LLM call with metadata."""
    def __init__(self, content: str, success: bool, retried: bool = False, degraded: bool = False):
        self.content = content
        self.success = success
        self.retried = retried
        self.degraded = degraded


def _call_llm_with_retry(
    system_prompt: str, 
    user_prompt: str, 
    params: dict,
    max_retries: int = 1,
) -> LLMCallResult:
    """Calls LLM with retry logic. Returns LLMCallResult."""
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
            
            # Empty response - retry
            retried = True
            logger.warning(f"LLM returned empty response, attempt {attempt + 1}")
            
        except Exception as e:
            last_error = e
            retried = True
            logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(0.5)  # Brief delay before retry
    
    # All retries failed - return degrade response
    logger.error(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
    return LLMCallResult(
        content=DEGRADE_LLM_FAIL,
        success=False,
        retried=True,
        degraded=True
    )


def _call_llm(system_prompt: str, user_prompt: str, params: dict) -> str:
    """Calls LLM with the given prompts and parameters. Legacy wrapper."""
    result = _call_llm_with_retry(system_prompt, user_prompt, params)
    return result.content


# Response Builder (with AnswerContract enforcement + Degrade support)
# Source kinds by answer_kind
SOURCE_KIND_MAP = {
    "report": ["diagnosis_result"],
    "explain": ["diagnosis_result", "explain_context"],
    "greeting": ["system_template"],
    "chat": ["system_template"],
    "degrade": ["system_template"],
}


def _build_response(
    state: SupervisorState,
    summary: str,
    answer_kind: str,
    diagnosis_result: Optional[Dict] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Builds the response state update with AnswerContract enforcement. Null-safe."""
    repo = safe_get(state, "repo")
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}" if owner or name else ""
    
    # AnswerContract enforcement (sources == [] 방지)
    source_kinds = SOURCE_KIND_MAP.get(answer_kind, ["system_template"])
    sources: List[str] = []
    
    if diagnosis_result and not degraded:
        # 정상 경로: 진단 결과 참조
        sources.append(f"diagnosis_{repo_id.replace('/', '_')}")
    else:
        # 디그레이드 경로: system_template 참조
        sources.append(DEGRADE_SOURCE_ID)
        source_kinds = [DEGRADE_SOURCE_KIND]
    
    answer_contract = AnswerContract(
        text=summary or "",
        sources=sources,
        source_kinds=source_kinds[:len(sources)] if sources else [],
    )
    
    # Emit ANSWER_GENERATED event
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


# Lightweight response builder (no LLM, instant response)
def _build_lightweight_response(
    state: SupervisorState,
    template: str,
    answer_kind: str,
    source_id: str,
) -> Dict[str, Any]:
    """Builds lightweight response without LLM call. For smalltalk/help/overview."""
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


# Overview handler (아티팩트 수집 + LLM 요약)
def _handle_overview_mode(state: SupervisorState, repo: Optional[Dict]) -> Dict[str, Any]:
    """Handles overview.repo mode with artifact collection and LLM summary."""
    from ..prompts import (
        build_overview_prompt,
        OVERVIEW_FALLBACK_TEMPLATE,
        get_llm_params,
    )
    from ..service import fetch_overview_artifacts
    
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}"
    
    if not owner or not name:
        return _build_response(
            state,
            "저장소 정보가 없습니다. `owner/repo` 형식으로 알려주세요.",
            "chat",
            degraded=True
        )
    
    # Fetch artifacts
    artifacts = fetch_overview_artifacts(owner, name)
    
    # API 제한 시 fallback (repo_facts만으로 개요)
    if artifacts.error or not artifacts.repo_facts:
        logger.warning(f"Overview fallback for {repo_id}: {artifacts.error}")
        return _build_response(
            state,
            f"저장소 정보를 가져오지 못했습니다: {artifacts.error or '알 수 없는 오류'}",
            "chat",
            degraded=True
        )
    
    # sources >= 2 보장 (repo_facts + readme_head 또는 recent_activity)
    if len(artifacts.sources) < 2:
        # Fallback to template-based response
        fallback = OVERVIEW_FALLBACK_TEMPLATE.format(
            owner=owner,
            repo=name,
            description=artifacts.repo_facts.get("description") or "(설명 없음)",
            language=artifacts.repo_facts.get("language") or "(없음)",
            stars=artifacts.repo_facts.get("stars", 0),
            forks=artifacts.repo_facts.get("forks", 0),
        )
        return _build_overview_response(state, fallback, artifacts.sources, repo_id)
    
    # Build prompt and call LLM
    system_prompt, user_prompt = build_overview_prompt(
        owner=owner,
        repo=name,
        repo_facts=artifacts.repo_facts,
        readme_head=artifacts.readme_head,
        recent_activity=artifacts.recent_activity,
    )
    
    llm_params = get_llm_params("overview")
    llm_result = _call_llm_with_retry(system_prompt, user_prompt, llm_params, max_retries=1)
    
    if llm_result.degraded:
        # LLM 실패 시 fallback
        fallback = OVERVIEW_FALLBACK_TEMPLATE.format(
            owner=owner,
            repo=name,
            description=artifacts.repo_facts.get("description") or "(설명 없음)",
            language=artifacts.repo_facts.get("language") or "(없음)",
            stars=artifacts.repo_facts.get("stars", 0),
            forks=artifacts.repo_facts.get("forks", 0),
        )
        return _build_overview_response(state, fallback, artifacts.sources, repo_id)
    
    return _build_overview_response(state, llm_result.content, artifacts.sources, repo_id)


def _build_overview_response(
    state: SupervisorState,
    summary: str,
    sources: List[str],
    repo_id: str,
) -> Dict[str, Any]:
    """Builds response for overview mode with artifact sources."""
    answer_contract = AnswerContract(
        text=summary,
        sources=sources if sources else ["ARTIFACT:REPO_FACTS:" + repo_id],
        source_kinds=["github_artifact"] * len(sources) if sources else ["github_artifact"],
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "chat", "mode": "overview"},
        outputs={
            "text_length": len(summary),
            "source_count": len(sources),
            "sources": sources[:3],
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": "chat",
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"{repo_id} 개요 완료",
        "last_answer_kind": "chat",
    }


# Follow-up handler (직전 턴 아티팩트 기반 근거 설명)
def _handle_followup_evidence_mode(
    state: SupervisorState,
    user_query: str,
    diagnosis_result: Optional[Dict],
) -> Dict[str, Any]:
    """Handles follow-up evidence requests using previous turn artifacts."""
    from ..prompts import (
        build_followup_evidence_prompt,
        FOLLOWUP_NO_ARTIFACTS_TEMPLATE,
        FOLLOWUP_SOURCE_ID,
        get_llm_params,
    )
    
    # 직전 턴 정보 추출
    repo = safe_get(state, "repo")
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}" if owner or name else ""
    
    last_answer_kind = safe_get(state, "last_answer_kind", "")
    last_intent = safe_get(state, "intent", "analyze")
    
    # 직전 아티팩트 없음 → 안내 + 선택지
    if not diagnosis_result:
        return _build_lightweight_response(
            state,
            FOLLOWUP_NO_ARTIFACTS_TEMPLATE,
            "chat",
            FOLLOWUP_SOURCE_ID,
        )
    
    # 아티팩트 추출 (scores, labels, explain_context)
    artifacts: Dict[str, Any] = {}
    if "scores" in diagnosis_result:
        artifacts["scores"] = diagnosis_result["scores"]
    if "labels" in diagnosis_result:
        artifacts["labels"] = diagnosis_result["labels"]
    if "explain_context" in diagnosis_result:
        artifacts["explain_context"] = diagnosis_result["explain_context"]
    
    # 아티팩트가 비어있으면 안내
    if not artifacts:
        return _build_lightweight_response(
            state,
            FOLLOWUP_NO_ARTIFACTS_TEMPLATE,
            "chat",
            FOLLOWUP_SOURCE_ID,
        )
    
    # LLM 호출로 근거 설명 생성
    system_prompt, user_prompt = build_followup_evidence_prompt(
        user_query=user_query,
        prev_intent=last_intent,
        prev_answer_kind=last_answer_kind or "report",
        repo_id=repo_id,
        artifacts=artifacts,
    )
    
    llm_params = get_llm_params("followup_evidence")
    llm_result = _call_llm_with_retry(system_prompt, user_prompt, llm_params, max_retries=1)
    
    # 응답 빌드 (sources에 직전 아티팩트 참조)
    artifact_sources = [
        f"PREV:{repo_id}:{key}" for key in artifacts.keys()
    ]
    
    return _build_followup_response(
        state,
        llm_result.content,
        artifact_sources,
        repo_id,
        diagnosis_result,
    )


def _build_followup_response(
    state: SupervisorState,
    summary: str,
    sources: List[str],
    repo_id: str,
    diagnosis_result: Optional[Dict],
) -> Dict[str, Any]:
    """Builds response for follow-up mode with artifact sources."""
    answer_contract = AnswerContract(
        text=summary,
        sources=sources if sources else [f"PREV:{repo_id}"],
        source_kinds=["prev_turn_artifact"] * len(sources) if sources else ["prev_turn_artifact"],
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "explain", "mode": "followup_evidence"},
        outputs={
            "text_length": len(summary),
            "source_count": len(sources),
            "sources": sources[:3],
        },
    )
    
    result: Dict[str, Any] = {
        "llm_summary": answer_contract.text,
        "answer_kind": "explain",
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"{repo_id} 근거 설명 완료",
        "last_answer_kind": "explain",
    }
    
    # 후속 질문용 Task 리스트 유지
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


# Refine handler (Task 재정렬/발췌)
def _handle_refine_mode(
    state: SupervisorState, 
    user_query: str,
) -> Dict[str, Any]:
    """Handles followup.refine mode - Task 재정렬/발췌."""
    from ..prompts import (
        build_refine_prompt,
        extract_requested_count,
        get_llm_params,
        REFINE_NO_TASKS_TEMPLATE,
        REFINE_EMPTY_RESULT_TEMPLATE,
        REFINE_SOURCE_ID,
        REFINE_TASKS_SOURCE_KIND,
    )
    
    # 아티팩트 가드: last_task_list 또는 diagnosis_result.onboarding_tasks 필요
    last_task_list = safe_get(state, "last_task_list")
    diagnosis_result = safe_get(state, "diagnosis_result")
    
    task_list: List[Dict[str, Any]] = []
    
    # 1순위: last_task_list (이전 턴에서 저장된 Task 목록)
    if last_task_list and isinstance(last_task_list, list) and len(last_task_list) > 0:
        task_list = list(last_task_list)
    # 2순위: diagnosis_result.onboarding_tasks
    elif diagnosis_result and isinstance(diagnosis_result, dict):
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        if onboarding_tasks:
            for difficulty in ["beginner", "intermediate", "advanced"]:
                for task in onboarding_tasks.get(difficulty, []):
                    task_copy = dict(task)
                    if "difficulty" not in task_copy:
                        task_copy["difficulty"] = difficulty
                    task_list.append(task_copy)
    
    # 아티팩트 없음 → 가드 발동
    if not task_list:
        logger.warning("[refine] No task artifacts found - guard triggered")
        emit_event(
            event_type=EventType.ANSWER_GENERATED,
            actor="summarize_node",
            inputs={"answer_kind": "refine", "guard": "no_tasks"},
            outputs={"status": "guard_triggered"},
        )
        return _build_lightweight_response(
            state,
            REFINE_NO_TASKS_TEMPLATE,
            "refine",
            REFINE_SOURCE_ID,
        )
    
    # 요청된 개수 추출 (기본 3개)
    requested_count = extract_requested_count(user_query)
    
    # priority 기준 정렬 (낮을수록 높은 우선순위)
    sorted_tasks = sorted(
        task_list, 
        key=lambda t: (t.get("priority", 99), t.get("difficulty", "intermediate"))
    )
    
    # 상위 N개 발췌
    selected_tasks = sorted_tasks[:requested_count]
    
    # 결과가 비어있으면 안내
    if not selected_tasks:
        return _build_lightweight_response(
            state,
            REFINE_EMPTY_RESULT_TEMPLATE,
            "refine",
            REFINE_SOURCE_ID,
        )
    
    # LLM으로 정리된 응답 생성
    system_prompt, user_prompt = build_refine_prompt(
        task_list=sorted_tasks,
        user_query=user_query,
        requested_count=requested_count,
    )
    
    llm_params = get_llm_params("refine")
    llm_result = _call_llm_with_retry(system_prompt, user_prompt, llm_params, max_retries=1)
    
    # LLM 실패 시 규칙 기반 응답
    if llm_result.degraded:
        return _build_refine_fallback_response(state, selected_tasks, requested_count)
    
    return _build_refine_response(state, llm_result.content, selected_tasks, sorted_tasks)


def _build_refine_response(
    state: SupervisorState,
    summary: str,
    selected_tasks: List[Dict],
    all_tasks: List[Dict],
) -> Dict[str, Any]:
    """Builds response for refine mode with task sources."""
    from ..prompts import REFINE_TASKS_SOURCE_KIND
    
    # sources: onboarding_tasks(필수) + 선택된 task IDs
    sources = ["onboarding_tasks"]
    source_kinds = [REFINE_TASKS_SOURCE_KIND]
    
    for task in selected_tasks:
        task_id = task.get("id") or task.get("title", "unknown")[:20]
        sources.append(f"task:{task_id}")
        source_kinds.append("task_item")
    
    answer_contract = AnswerContract(
        text=summary,
        sources=sources,
        source_kinds=source_kinds,
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "refine"},
        outputs={
            "text_length": len(summary),
            "selected_count": len(selected_tasks),
            "total_tasks": len(all_tasks),
            "sources": sources[:5],
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": "refine",
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"Task {len(selected_tasks)}개 추천 완료",
        "last_answer_kind": "refine",
        "last_task_list": all_tasks,  # 전체 Task 목록 유지
    }


def _build_refine_fallback_response(
    state: SupervisorState,
    selected_tasks: List[Dict],
    requested_count: int,
) -> Dict[str, Any]:
    """Builds fallback response when LLM fails in refine mode."""
    from ..prompts import REFINE_TASKS_SOURCE_KIND
    
    # 규칙 기반 응답 생성
    lines = [f"### 추천 Task {len(selected_tasks)}개", ""]
    
    for i, task in enumerate(selected_tasks, 1):
        title = task.get("title", "제목 없음")
        difficulty = task.get("difficulty", "unknown")
        priority = task.get("priority", 99)
        rationale = task.get("rationale", "")
        
        lines.append(f"**{i}. {title}**")
        lines.append(f"- 난이도: {difficulty}, 우선순위: {priority}")
        if rationale:
            lines.append(f"- {rationale[:100]}")
        lines.append("")
    
    lines.append("**다음 행동**")
    lines.append("- 더 쉬운 Task: `더 쉬운 거 없어?`")
    lines.append("- 상세 분석: `{Task 제목} 자세히 알려줘`")
    
    summary = "\n".join(lines)
    
    sources = ["onboarding_tasks"]
    source_kinds = [REFINE_TASKS_SOURCE_KIND]
    
    for task in selected_tasks:
        task_id = task.get("id") or task.get("title", "unknown")[:20]
        sources.append(f"task:{task_id}")
        source_kinds.append("task_item")
    
    answer_contract = AnswerContract(
        text=summary,
        sources=sources,
        source_kinds=source_kinds,
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "refine", "fallback": True},
        outputs={
            "text_length": len(summary),
            "selected_count": len(selected_tasks),
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": "refine",
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"Task {len(selected_tasks)}개 추천 완료",
        "last_answer_kind": "refine",
        "degraded": True,
    }


# V1 Summarize Node (Main Entry Point)

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
        return _build_response(state, error_message, "chat")
    
    # 0.3. Expert node already generated response (compare/onepager)
    existing_contract = safe_get(state, "answer_contract")
    if existing_contract and isinstance(existing_contract, dict) and existing_contract.get("text"):
        # Already have a valid answer from expert_node, pass through
        return {
            "llm_summary": existing_contract.get("text", ""),
            "answer_kind": safe_get(state, "answer_kind", "chat"),
            "answer_contract": existing_contract,
            "last_brief": safe_get(state, "last_brief", ""),
            "last_answer_kind": safe_get(state, "answer_kind", "chat"),
        }
    
    # 0.5. Disambiguation: repo required but missing - BLOCK expert path
    if safe_get(state, "_needs_disambiguation"):
        template = safe_get(state, "_disambiguation_template", MISSING_REPO_TEMPLATE)
        source_id = safe_get(state, "_disambiguation_source", DISAMBIGUATION_SOURCE_ID)
        candidate_sources = safe_get(state, "_disambiguation_candidate_sources", [])
        
        # Build sources list with candidates
        sources = [source_id]
        if candidate_sources:
            sources.extend(candidate_sources[:3])
        
        # Build AnswerContract with repo_candidates
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
    
    # 1. Check V1 support
    if not is_v1_supported(intent, sub_intent):
        return _build_response(state, NOT_READY_TEMPLATE, "chat")
    
    mode = (intent, sub_intent)
    
    # 2. Fast path: Smalltalk/Help (LLM 호출 없이 즉답)
    if intent == "smalltalk":
        if sub_intent == "greeting":
            return _build_lightweight_response(
                state, SMALLTALK_GREETING_TEMPLATE, "greeting", SMALLTALK_SOURCE_ID
            )
        else:  # chitchat
            return _build_lightweight_response(
                state, SMALLTALK_CHITCHAT_TEMPLATE, "greeting", SMALLTALK_SOURCE_ID
            )
    
    if intent == "help":
        return _build_lightweight_response(
            state, HELP_GETTING_STARTED_TEMPLATE, "chat", HELP_SOURCE_ID
        )
    
    # 3. Overview path (아티팩트 수집 + LLM 요약)
    if intent == "overview" and sub_intent == "repo":
        return _handle_overview_mode(state, repo)
    
    # 3.5. Follow-up Evidence path (직전 턴 아티팩트 기반 근거 설명)
    if mode == ("followup", "evidence"):
        return _handle_followup_evidence_mode(state, user_query, diagnosis_result)
    
    # 3.6. Follow-up Refine path (Task 재정렬/발췌)
    if mode == ("followup", "refine"):
        return _handle_refine_mode(state, user_query)
    
    # 4. Route by mode (LLM required)
    
    # --- Health Report Mode ---
    if mode in [("analyze", "health"), ("analyze", "onboarding")]:
        # 아티팩트 부족 시 디그레이드
        if not diagnosis_result:
            if DEGRADE_ENABLED:
                return _build_response(
                    state, 
                    DEGRADE_NO_ARTIFACT,
                    "report",
                    degraded=True
                )
            return _build_response(
                state, 
                "저장소 분석 결과가 없습니다. 먼저 저장소를 분석해 주세요.",
                "report",
                degraded=True
            )
        
        system_prompt, user_prompt = build_health_report_prompt(diagnosis_result)
        llm_params = get_llm_params("health_report")
        
        # LLM 호출 + 재시도 + 디그레이드
        llm_result = _call_llm_with_retry(system_prompt, user_prompt, llm_params)
        
        if llm_result.degraded and DEGRADE_ENABLED:
            return _build_response(state, DEGRADE_SCHEMA_FAIL, "report", diagnosis_result, degraded=True)
        
        return _build_response(state, llm_result.content, "report", diagnosis_result)
    
    # --- Score Explain Mode ---
    elif mode == ("followup", "explain"):
        if not diagnosis_result:
            if DEGRADE_ENABLED:
                return _build_response(
                    state,
                    DEGRADE_NO_ARTIFACT,
                    "explain",
                    degraded=True
                )
            return _build_response(
                state,
                "설명할 진단 결과가 없습니다. 먼저 저장소를 분석해 주세요. (예: 'facebook/react 분석해줘')",
                "explain",
                degraded=True
            )
        
        target_metrics = _extract_target_metrics(user_query)
        if not target_metrics:
            target_metrics = ["health_score"]
        
        # Null-safe nested access
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
        
        # LLM 호출 + 재시도 + 디그레이드
        llm_result = _call_llm_with_retry(system_prompt, user_prompt, llm_params)
        
        if llm_result.degraded and DEGRADE_ENABLED:
            return _build_response(state, DEGRADE_SCHEMA_FAIL, "explain", diagnosis_result, degraded=True)
        
        return _build_response(state, llm_result.content, "explain", diagnosis_result)
    
    # --- Chat Mode ---
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
        
        # LLM 호출 + 재시도 + 디그레이드
        llm_result = _call_llm_with_retry(system_prompt, user_prompt, llm_params)
        
        if llm_result.degraded and DEGRADE_ENABLED:
            return _build_response(state, DEGRADE_LLM_FAIL, "chat", degraded=True)
        
        return _build_response(state, llm_result.content, "chat")
    
    # --- Fallback ---
    else:
        return _build_response(state, NOT_READY_TEMPLATE, "chat")


# Legacy Alias
def summarize_node(state: SupervisorState) -> Dict[str, Any]:
    """Legacy alias for summarize_node_v1."""
    return summarize_node_v1(state)
