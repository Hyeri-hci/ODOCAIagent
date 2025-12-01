"""Task 리파인 노드. 기존 결과 재사용하여 Task 재필터링."""
from __future__ import annotations

import logging
from typing import Any

from ..models import SupervisorState

logger = logging.getLogger(__name__)


def refine_tasks_node(state: SupervisorState) -> SupervisorState:
    """
    기존 Task 목록을 재필터링하는 노드
    
    새로운 Diagnosis 호출 없이 last_task_list 또는 diagnosis_result를 재사용.
    followup_type에 따라 필터링 로직을 적용한다.
    """
    followup_type = state.get("followup_type")
    user_context = state.get("user_context", {})
    user_level = user_context.get("level", "beginner")
    
    # 기존 Task 목록 가져오기
    task_list = state.get("last_task_list", [])
    
    # last_task_list가 없으면 diagnosis_result에서 추출
    if not task_list:
        diagnosis_result = state.get("diagnosis_result", {})
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        task_list = _flatten_tasks(onboarding_tasks)
    
    if not task_list:
        logger.warning("[refine_tasks_node] Task 목록이 없습니다.")
        return _create_no_tasks_response(state)
    
    # followup_type에 따라 필터링
    filtered_tasks = _filter_tasks_by_followup(task_list, followup_type, user_level)
    
    # 결과 저장
    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    new_state["refined_task_list"] = filtered_tasks
    new_state["refine_summary"] = _create_refine_summary(followup_type, filtered_tasks, task_list)
    
    logger.info(
        "[refine_tasks_node] followup_type=%s, original=%d, filtered=%d",
        followup_type,
        len(task_list),
        len(filtered_tasks),
    )
    
    return new_state


def _flatten_tasks(onboarding_tasks: dict) -> list[dict]:
    """OnboardingTasks 구조를 flat list로 변환"""
    tasks = []
    for difficulty in ["beginner", "intermediate", "advanced"]:
        for task in onboarding_tasks.get(difficulty, []):
            task_copy = dict(task)
            if "difficulty" not in task_copy:
                task_copy["difficulty"] = difficulty
            tasks.append(task_copy)
    return tasks


def _filter_tasks_by_followup(
    tasks: list[dict], 
    followup_type: str | None, 
    user_level: str
) -> list[dict]:
    """followup_type에 따라 Task 필터링"""
    
    if followup_type == "refine_easier":
        # 더 쉬운 Task: beginner만 또는 레벨 낮은 것
        return [t for t in tasks if t.get("difficulty") == "beginner" or t.get("level", 99) <= 2]
    
    elif followup_type == "refine_harder":
        # 더 어려운 Task: intermediate/advanced
        return [t for t in tasks if t.get("difficulty") in ["intermediate", "advanced"] or t.get("level", 0) >= 4]
    
    elif followup_type == "refine_different":
        # 다른 종류: 이전에 추천하지 않은 kind 위주
        # 일단 kind 기준으로 다양성 확보
        seen_kinds = set()
        diverse_tasks = []
        for task in tasks:
            kind = task.get("kind", "issue")
            if kind not in seen_kinds:
                diverse_tasks.append(task)
                seen_kinds.add(kind)
        return diverse_tasks if diverse_tasks else tasks[:5]
    
    else:
        # 기본: user_level 기반 필터링
        if user_level == "beginner":
            return [t for t in tasks if t.get("difficulty") in ["beginner", "intermediate"]]
        elif user_level == "advanced":
            return tasks  # 전체 반환
        else:
            return [t for t in tasks if t.get("difficulty") in ["beginner", "intermediate", "advanced"]]


def _create_refine_summary(
    followup_type: str | None, 
    filtered_tasks: list[dict], 
    original_tasks: list[dict]
) -> dict[str, Any]:
    """리파인 결과 요약 생성"""
    summary = {
        "followup_type": followup_type,
        "original_count": len(original_tasks),
        "filtered_count": len(filtered_tasks),
        "tasks": filtered_tasks[:10],  # 최대 10개
    }
    
    # 난이도별 분포
    difficulty_dist = {"beginner": 0, "intermediate": 0, "advanced": 0}
    for task in filtered_tasks:
        diff = task.get("difficulty", "intermediate")
        if diff in difficulty_dist:
            difficulty_dist[diff] += 1
    summary["difficulty_distribution"] = difficulty_dist
    
    return summary


def _create_no_tasks_response(state: SupervisorState) -> SupervisorState:
    """Task가 없을 때 응답 생성"""
    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    new_state["refined_task_list"] = []
    new_state["refine_summary"] = {
        "followup_type": state.get("followup_type"),
        "original_count": 0,
        "filtered_count": 0,
        "tasks": [],
        "message": "이전 분석 결과가 없습니다. 먼저 저장소를 분석해주세요.",
    }
    return new_state
