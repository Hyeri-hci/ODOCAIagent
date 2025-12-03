"""사용자 컨텍스트 기반 개인화 필터링 및 추천."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .models import TaskSuggestion, OnboardingTasks


LEVEL_HOURS_MAP: dict[int, float] = {
    1: 0.5, 2: 1.5, 3: 2.5, 4: 4.0, 5: 8.0, 6: 20.0,
}


@dataclass
class UserTaskContext:
    """사용자 Task 필터링 컨텍스트."""
    experience_level: str = "beginner"
    preferred_kinds: list[str] = field(default_factory=list)
    time_budget_hours: Optional[float] = None
    preferred_intent: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _estimate_hours_from_level(level: int) -> float:
    """레벨에서 예상 소요 시간 추정 (시간 단위)."""
    return LEVEL_HOURS_MAP.get(level, 2.0)


def filter_tasks_by_user_level(
    tasks: OnboardingTasks,
    user_level: str = "beginner",
) -> list[TaskSuggestion]:
    """사용자 레벨에 맞는 Task 필터링."""
    if user_level == "beginner":
        return tasks.beginner + tasks.intermediate[:3]
    elif user_level == "intermediate":
        return tasks.beginner[:3] + tasks.intermediate + tasks.advanced[:2]
    return tasks.beginner[:2] + tasks.intermediate + tasks.advanced


def filter_tasks_for_user(
    tasks: OnboardingTasks,
    user_level: str = "beginner",
    preferred_kinds: Optional[list[str]] = None,
    time_budget_hours: Optional[float] = None,
    intent_filter: Optional[str] = None,
) -> list[TaskSuggestion]:
    """사용자 컨텍스트에 맞는 Task 필터링 및 우선순위 정렬."""
    filtered = filter_tasks_by_user_level(tasks, user_level)

    if intent_filter:
        filtered = [t for t in filtered if t.intent == intent_filter]

    if preferred_kinds:
        preferred = [t for t in filtered if t.kind in preferred_kinds]
        others = [t for t in filtered if t.kind not in preferred_kinds]
        filtered = preferred + others

    if time_budget_hours is not None:
        limited: list[TaskSuggestion] = []
        total_hours = 0.0
        for task in filtered:
            estimated = _estimate_hours_from_level(task.level)
            if total_hours + estimated <= time_budget_hours:
                limited.append(task)
                total_hours += estimated
            elif not limited:
                limited.append(task)
                break
        filtered = limited

    # Beginner 전용: docs/test/meta를 상위로 끌어올림
    if user_level == "beginner" and not preferred_kinds:
        BEGINNER_FRIENDLY_KINDS = ("doc", "test", "meta")
        BEGINNER_FRIENDLY_BONUS = 15.0
        def beginner_sort_key(t: TaskSuggestion) -> float:
            bonus = BEGINNER_FRIENDLY_BONUS if t.kind in BEGINNER_FRIENDLY_KINDS else 0
            return t.task_score + bonus
        filtered.sort(key=beginner_sort_key, reverse=True)
    else:
        filtered.sort(key=lambda t: t.task_score, reverse=True)
    
    return filtered


def filter_tasks_by_context(
    tasks: OnboardingTasks,
    context: UserTaskContext,
) -> list[TaskSuggestion]:
    """사용자 컨텍스트 기반 개인화 필터링."""
    filtered = filter_tasks_by_user_level(tasks, context.experience_level)

    if context.preferred_intent:
        preferred = [t for t in filtered if t.intent == context.preferred_intent]
        others = [t for t in filtered if t.intent != context.preferred_intent]
        filtered = preferred + others

    if context.preferred_kinds:
        def kind_priority(task: TaskSuggestion) -> int:
            try:
                return context.preferred_kinds.index(task.kind)
            except ValueError:
                return len(context.preferred_kinds)

        preferred_kind_tasks = sorted(
            [t for t in filtered if t.kind in context.preferred_kinds],
            key=kind_priority,
        )
        other_tasks = [t for t in filtered if t.kind not in context.preferred_kinds]

        # 2:1 비율로 인터리브
        result: list[TaskSuggestion] = []
        pref_idx, other_idx = 0, 0
        while len(result) < len(filtered):
            for _ in range(2):
                if pref_idx < len(preferred_kind_tasks):
                    result.append(preferred_kind_tasks[pref_idx])
                    pref_idx += 1
            if other_idx < len(other_tasks):
                result.append(other_tasks[other_idx])
                other_idx += 1
            if pref_idx >= len(preferred_kind_tasks) and other_idx >= len(other_tasks):
                break
        filtered = result

    if context.time_budget_hours is not None:
        time_limited: list[TaskSuggestion] = []
        total_hours = 0.0
        for task in filtered:
            estimated = _estimate_hours_from_level(task.level)
            if total_hours + estimated <= context.time_budget_hours:
                time_limited.append(task)
                total_hours += estimated
            elif not time_limited:
                time_limited.append(task)
                break
        filtered = time_limited

    return filtered


def create_personalized_task_set(
    tasks: OnboardingTasks,
    context: UserTaskContext,
) -> dict[str, Any]:
    """개인화된 Task 세트 생성."""
    filtered = filter_tasks_by_context(tasks, context)

    today_tasks: list[TaskSuggestion] = []
    week_tasks: list[TaskSuggestion] = []
    challenge_tasks: list[TaskSuggestion] = []

    budget = context.time_budget_hours or 2.0
    level_threshold = {"beginner": 3, "intermediate": 5, "advanced": 6}
    max_level = level_threshold.get(context.experience_level, 6)

    for task in filtered:
        hours = _estimate_hours_from_level(task.level)
        if task.level > max_level:
            challenge_tasks.append(task)
        elif hours <= budget:
            today_tasks.append(task)
        elif hours <= budget * 5:
            week_tasks.append(task)
        else:
            challenge_tasks.append(task)

    return {
        "today_tasks": [t.to_dict() for t in today_tasks[:5]],
        "week_tasks": [t.to_dict() for t in week_tasks[:10]],
        "challenge_tasks": [t.to_dict() for t in challenge_tasks[:3]],
        "meta": {
            "experience_level": context.experience_level,
            "time_budget_hours": budget,
            "preferred_kinds": context.preferred_kinds,
            "total_filtered": len(filtered),
        },
    }


def _calculate_skill_match_score(task: TaskSuggestion, user_skills: list[str]) -> float:
    """태스크와 사용자 스킬 간 매칭 점수 계산."""
    if not user_skills or not task.required_skills:
        return 0.0
    
    user_skills_lower = {s.lower() for s in user_skills}
    task_skills_lower = {s.lower() for s in task.required_skills}
    
    if not task_skills_lower:
        return 0.0
    
    matched = user_skills_lower & task_skills_lower
    return len(matched) / len(task_skills_lower)


def _calculate_time_fit_score(task: TaskSuggestion, time_budget_hours: float) -> float:
    """시간 예산 대비 적합도 점수 계산."""
    task_hours = task.estimated_hours or _estimate_hours_from_level(task.level)
    
    if task_hours <= 0:
        return 0.5
    
    ratio = task_hours / time_budget_hours if time_budget_hours > 0 else 0
    
    if 0.3 <= ratio <= 0.8:
        return 1.0
    elif ratio < 0.3:
        return 0.7
    elif ratio <= 1.0:
        return 0.5
    else:
        return max(0.1, 1.0 - (ratio - 1.0) * 0.5)


def rank_tasks_for_user(
    tasks: list[TaskSuggestion],
    user_skills: Optional[list[str]] = None,
    time_budget_hours: float = 2.0,
    experience_level: str = "beginner",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """사용자 맞춤 태스크 순위 산정 및 추천 메시지 생성."""
    if not tasks:
        return []
    
    level_map = {"beginner": 3, "intermediate": 5, "advanced": 6}
    max_level = level_map.get(experience_level, 6)
    user_skills = user_skills or []
    
    scored_tasks: list[tuple] = []
    for task in tasks:
        if task.level > max_level + 1:
            continue
        
        skill_score = _calculate_skill_match_score(task, user_skills)
        time_score = _calculate_time_fit_score(task, time_budget_hours)
        level_fit = 1.0 - abs(task.level - max_level) * 0.15
        base_score = task.task_score if task.task_score else 0.5
        
        total_score = (
            0.3 * skill_score +
            0.25 * time_score +
            0.25 * level_fit +
            0.2 * base_score
        )
        scored_tasks.append((task, total_score, skill_score, time_score))
    
    scored_tasks.sort(key=lambda x: x[1], reverse=True)
    
    results = []
    for task, total, skill_sc, time_sc in scored_tasks[:top_k]:
        match_reasons = []
        if skill_sc >= 0.5:
            match_reasons.append("skill_match")
        if time_sc >= 0.8:
            match_reasons.append("time_fit")
        if task.level <= max_level:
            match_reasons.append("level_fit")
        
        results.append({
            "task": task.to_dict(),
            "match_score": round(total, 2),
            "match_reasons": match_reasons,
        })
    
    return results


def generate_personalized_recommendation(
    tasks: list[TaskSuggestion],
    user_skills: Optional[list[str]] = None,
    time_budget_hours: float = 2.0,
    experience_level: str = "beginner",
) -> dict[str, Any]:
    """개인화 추천 결과와 설명 메시지 생성."""
    ranked = rank_tasks_for_user(
        tasks, user_skills, time_budget_hours, experience_level, top_k=5
    )
    
    if not ranked:
        return {
            "top_picks": [],
            "message": "현재 조건에 맞는 태스크를 찾지 못했습니다.",
            "meta": {
                "experience_level": experience_level,
                "time_budget_hours": time_budget_hours,
                "user_skills": user_skills or [],
            },
        }
    
    level_desc = {"beginner": "입문자", "intermediate": "중급", "advanced": "숙련"}
    level_str = level_desc.get(experience_level, experience_level)
    
    top_count = min(3, len(ranked))
    message = f"{level_str} 수준이시라면 아래 {top_count}개가 특히 적합합니다:"
    
    return {
        "top_picks": ranked[:3],
        "other_picks": ranked[3:],
        "message": message,
        "meta": {
            "experience_level": experience_level,
            "time_budget_hours": time_budget_hours,
            "user_skills": user_skills or [],
            "total_ranked": len(ranked),
        },
    }
