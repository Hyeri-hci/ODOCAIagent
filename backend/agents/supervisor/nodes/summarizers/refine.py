"""Refine mode handler (Task 재정렬/발췌)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.agents.shared.contracts import (
    AnswerContract,
    safe_get,
)
from backend.common.events import EventType, emit_event

from ...models import SupervisorState
from .common import (
    build_lightweight_response,
    call_llm_with_retry,
)

logger = logging.getLogger(__name__)


def handle_refine_mode(
    state: SupervisorState, 
    user_query: str,
) -> Dict[str, Any]:
    """Handles followup.refine mode - Task 재정렬/발췌."""
    from ...prompts import (
        build_refine_prompt,
        extract_requested_count,
        get_llm_params,
        REFINE_NO_TASKS_TEMPLATE,
        REFINE_EMPTY_RESULT_TEMPLATE,
        REFINE_SOURCE_ID,
        REFINE_TASKS_SOURCE_KIND,
    )
    
    # 아티팩트 가드
    last_task_list = safe_get(state, "last_task_list")
    diagnosis_result = safe_get(state, "diagnosis_result")
    
    task_list: List[Dict[str, Any]] = []
    
    # 1순위: last_task_list
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
        return build_lightweight_response(
            state,
            REFINE_NO_TASKS_TEMPLATE,
            "refine",
            REFINE_SOURCE_ID,
        )
    
    # 요청된 개수 추출
    requested_count = extract_requested_count(user_query)
    
    # priority 기준 정렬
    sorted_tasks = sorted(
        task_list, 
        key=lambda t: (t.get("priority", 99), t.get("difficulty", "intermediate"))
    )
    
    # 상위 N개 발췌
    selected_tasks = sorted_tasks[:requested_count]
    
    if not selected_tasks:
        return build_lightweight_response(
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
    llm_result = call_llm_with_retry(system_prompt, user_prompt, llm_params, max_retries=1)
    
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
    """Builds response for refine mode."""
    from ...prompts import (
        REFINE_TASKS_SOURCE_KIND,
        REFINE_CONTEXT_HEADER,
        REFINE_SCORING_FORMULA,
    )
    from ...models import DEFAULT_RECOMMENDATION_CONTEXT, RecommendationContext
    
    rec_context: RecommendationContext = dict(DEFAULT_RECOMMENDATION_CONTEXT)
    
    # Detect based_on
    based_on = ["onboarding_tasks"]
    if any(t.get("source_id", "").startswith("readme") for t in selected_tasks):
        based_on.append("readme_analysis")
    rec_context["based_on"] = based_on
    
    # Add context header
    context_label = rec_context.get("context_label", "신규 기여자 · 온보딩 속도 기준")
    if "기준:" not in summary:
        summary = REFINE_CONTEXT_HEADER.format(context_label=context_label) + summary
    
    # sources
    sources = ["onboarding_tasks"]
    source_kinds = [REFINE_TASKS_SOURCE_KIND]
    
    for task in selected_tasks:
        task_id = task.get("id") or task.get("title", "unknown")[:20]
        source_id = task.get("source_id", f"task:meta:{task_id}")
        sources.append(source_id)
        source_kinds.append("task_item")
    
    answer_contract = AnswerContract(
        text=summary,
        sources=sources,
        source_kinds=source_kinds,
    )
    
    contract_dict = answer_contract.model_dump()
    contract_dict["meta"] = {
        "recommendation_context": rec_context,
        "scoring_formula": REFINE_SCORING_FORMULA,
        "persona_options": ["newcomer", "contributor", "maintainer"],
    }
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "refine"},
        outputs={
            "text_length": len(summary),
            "selected_count": len(selected_tasks),
            "total_tasks": len(all_tasks),
            "sources": sources[:5],
            "recommendation_who": rec_context.get("who"),
            "recommendation_goal": rec_context.get("goal"),
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": "refine",
        "answer_contract": contract_dict,
        "last_brief": f"Task {len(selected_tasks)}개 추천 완료",
        "last_answer_kind": "refine",
        "last_task_list": all_tasks,
        "_recommendation_context": rec_context,
    }


def _build_refine_fallback_response(
    state: SupervisorState,
    selected_tasks: List[Dict],
    requested_count: int,
) -> Dict[str, Any]:
    """Builds fallback response when LLM fails in refine mode."""
    from ...prompts import (
        REFINE_TASKS_SOURCE_KIND,
        REFINE_CONTEXT_HEADER,
        REFINE_SCORING_FORMULA,
    )
    from ...models import DEFAULT_RECOMMENDATION_CONTEXT, RecommendationContext
    
    rec_context: RecommendationContext = dict(DEFAULT_RECOMMENDATION_CONTEXT)
    context_label = rec_context.get("context_label", "신규 기여자 · 온보딩 속도 기준")
    
    # 규칙 기반 응답 생성
    lines = [
        REFINE_CONTEXT_HEADER.format(context_label=context_label).strip(),
        "",
        f"### 추천 Task {len(selected_tasks)}개",
        "",
    ]
    
    for i, task in enumerate(selected_tasks, 1):
        title = task.get("title", "제목 없음")
        difficulty = task.get("difficulty", "unknown")
        priority = task.get("priority", 99)
        rationale = task.get("rationale", "")
        source_id = task.get("source_id", "")
        
        lines.append(f"**{i}. {title}**")
        lines.append(f"- 난이도: {difficulty}, 우선순위: {priority}")
        if rationale:
            lines.append(f"- {rationale[:100]}")
        if source_id:
            lines.append(f"- 근거: `{source_id}`")
        lines.append("")
    
    lines.append("**선정 기준**")
    lines.append(f"- 우선순위 산식: `{REFINE_SCORING_FORMULA}`")
    lines.append("")
    lines.append("**다음 행동**")
    lines.append("- 더 쉬운 Task: `더 쉬운 거 없어?`")
    lines.append("- 상세 분석: `{Task 제목} 자세히 알려줘`")
    
    summary = "\n".join(lines)
    
    sources = ["onboarding_tasks"]
    source_kinds = [REFINE_TASKS_SOURCE_KIND]
    
    for task in selected_tasks:
        task_id = task.get("id") or task.get("title", "unknown")[:20]
        source_id = task.get("source_id", f"task:meta:{task_id}")
        sources.append(source_id)
        source_kinds.append("task_item")
    
    answer_contract = AnswerContract(
        text=summary,
        sources=sources,
        source_kinds=source_kinds,
    )
    
    contract_dict = answer_contract.model_dump()
    contract_dict["meta"] = {
        "recommendation_context": rec_context,
        "scoring_formula": REFINE_SCORING_FORMULA,
        "persona_options": ["newcomer", "contributor", "maintainer"],
    }
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "refine", "fallback": True},
        outputs={
            "text_length": len(summary),
            "selected_count": len(selected_tasks),
            "recommendation_who": rec_context.get("who"),
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": "refine",
        "answer_contract": contract_dict,
        "last_brief": f"Task {len(selected_tasks)}개 추천 완료",
        "last_answer_kind": "refine",
        "degraded": True,
        "_recommendation_context": rec_context,
    }
