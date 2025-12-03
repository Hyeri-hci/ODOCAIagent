"""Onboarding Tasks Generator - 메인 진입점 및 레거시 호환 re-export."""
from __future__ import annotations

import logging
from typing import Any, Optional

from .models import (
    TaskSuggestion,
    OnboardingTasks,
    Difficulty,
    TaskKind,
    TaskIntent,
)
from .labels import (
    BEGINNER_LABELS,
    INTERMEDIATE_LABELS,
    ADVANCED_LABELS,
    PRIORITY_LABELS,
    LEVEL_HOURS_MAP,
    LABEL_SKILL_MAP,
    determine_difficulty_from_labels,
    determine_level,
    determine_kind_from_labels,
    get_estimated_hours_from_level,
    extract_skills_from_labels,
)
from .scoring import (
    compute_task_score,
    determine_intent,
    generate_reason_tags,
    generate_fallback_reason,
)
from .fetchers import (
    fetch_open_issues_for_tasks,
    _fetch_issues_rest,
)
from .generators import (
    create_tasks_from_issues,
    create_meta_tasks_from_labels,
    create_minimum_meta_tasks,
    create_study_meta_tasks,
    DOC_META_TASKS,
)
from .personalization import (
    UserTaskContext,
    filter_tasks_by_user_level,
    filter_tasks_for_user,
    filter_tasks_by_context,
    create_personalized_task_set,
    rank_tasks_for_user,
    generate_personalized_recommendation,
    _estimate_hours_from_level,
)

logger = logging.getLogger(__name__)


# 레거시 호환: 미리 정의된 메타 Task
HEALTHY_PROJECT_META_TASKS: list[TaskSuggestion] = [
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:write_tutorial", title="사용자를 위한 튜토리얼 작성",
        labels=["documentation", "meta"],
        reason_tags=["community_contribution", "docs_improvement"],
        meta_flags=["healthy_project"],
        fallback_reason="건강한 프로젝트에 튜토리얼 문서로 기여할 수 있습니다",
        intent="contribute", task_score=60.0,
    ),
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:improve_examples", title="코드 예제 보강",
        labels=["documentation", "meta"],
        reason_tags=["community_contribution", "beginner_friendly"],
        meta_flags=["healthy_project"],
        fallback_reason="예제 코드 추가/개선으로 다른 사용자에게 도움을 줄 수 있습니다",
        intent="contribute", task_score=55.0,
    ),
    TaskSuggestion(
        kind="meta", difficulty="intermediate", level=3,
        id="meta:triage_issues", title="이슈 정리 및 라벨링 도움",
        labels=["meta", "community"],
        reason_tags=["community_contribution", "organization"],
        meta_flags=["healthy_project"],
        fallback_reason="이슈 분류, 중복 확인 등 커뮤니티 기여가 가능합니다",
        intent="contribute", task_score=50.0,
    ),
]

STUDY_META_TASKS: list[TaskSuggestion] = [
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:analyze_architecture", title="프로젝트 아키텍처 분석 및 학습",
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "architecture"],
        meta_flags=["study_mode"],
        fallback_reason="코드를 읽고 아키텍처를 분석하여 학습할 수 있습니다",
        intent="study", task_score=70.0,
    ),
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:document_learnings", title="학습 내용 개인 블로그/노트 정리",
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "personal_growth"],
        meta_flags=["study_mode"],
        fallback_reason="프로젝트에서 배운 내용을 정리하여 지식을 공고히 할 수 있습니다",
        intent="study", task_score=65.0,
    ),
]


def compute_onboarding_tasks(
    owner: str,
    repo: str,
    labels: dict[str, Any],
    onboarding_plan: Optional[dict[str, Any]] = None,
    max_issues: int = 30,
    min_tasks: int = 3,
) -> OnboardingTasks:
    """진단 결과를 바탕으로 온보딩 Task 목록 생성."""
    repo_url = f"https://github.com/{owner}/{repo}"

    health_level = labels.get("health_level", "warning")
    activity_issues = labels.get("activity_issues", [])
    docs_issues = labels.get("docs_issues", [])

    is_healthy = health_level == "good"
    is_active = "no_recent_commits" not in activity_issues and "inactive_project" not in activity_issues

    # 1. GitHub 이슈 기반 Task
    logger.info("Fetching open issues for onboarding tasks...")
    issues = fetch_open_issues_for_tasks(owner, repo, limit=max_issues)
    issue_tasks = create_tasks_from_issues(issues, repo_url, is_healthy, is_active)
    logger.info("Created %d tasks from %d issues", len(issue_tasks), len(issues))

    # 2. 메타 Task (진단 결과 기반)
    meta_tasks = create_meta_tasks_from_labels(docs_issues, activity_issues, health_level, repo_url)
    logger.info("Created %d meta tasks from diagnosis labels", len(meta_tasks))

    # 3. 최소 Task 보장
    all_tasks = issue_tasks + meta_tasks

    if len(all_tasks) < min_tasks:
        existing_ids = {t.id for t in all_tasks}
        extra_tasks = (
            create_minimum_meta_tasks(repo_url) if (is_healthy and is_active)
            else create_study_meta_tasks(repo_url)
        )
        for task in extra_tasks:
            if task.id not in existing_ids and len(all_tasks) < min_tasks:
                all_tasks.append(task)
                logger.info("Added extra task: %s", task.id)

    # 4. task_score 기준 정렬 후 난이도별 그룹핑
    def sort_key(t: TaskSuggestion):
        return (-t.task_score, t.level)

    beginner_tasks = sorted([t for t in all_tasks if t.difficulty == "beginner"], key=sort_key)
    intermediate_tasks = sorted([t for t in all_tasks if t.difficulty == "intermediate"], key=sort_key)
    advanced_tasks = sorted([t for t in all_tasks if t.difficulty == "advanced"], key=sort_key)

    # 5. Beginner 보충
    MIN_BEGINNER_TASKS = 2
    if len(beginner_tasks) < MIN_BEGINNER_TASKS and is_healthy and is_active:
        existing_ids = {t.id for t in all_tasks}
        for task in create_minimum_meta_tasks(repo_url):
            if task.id not in existing_ids and task.difficulty == "beginner":
                beginner_tasks.append(task)
                logger.info("Added beginner meta task: %s (beginner shortage)", task.id)
                if len(beginner_tasks) >= MIN_BEGINNER_TASKS:
                    break
        beginner_tasks.sort(key=sort_key)

    issue_count = len([t for t in all_tasks if t.kind != "meta"])
    meta_count = len([t for t in all_tasks if t.kind == "meta"])

    return OnboardingTasks(
        beginner=beginner_tasks[:10],
        intermediate=intermediate_tasks[:10],
        advanced=advanced_tasks[:5],
        total_count=len(all_tasks),
        issue_count=issue_count,
        meta_count=meta_count,
    )


# 레거시 호환: REST 폴백 함수 별칭
fetch_open_issues_for_tasks_rest = _fetch_issues_rest


__all__ = [
    # Models
    "TaskSuggestion",
    "OnboardingTasks",
    "Difficulty",
    "TaskKind",
    "TaskIntent",
    "UserTaskContext",
    # Labels
    "BEGINNER_LABELS",
    "INTERMEDIATE_LABELS",
    "ADVANCED_LABELS",
    "PRIORITY_LABELS",
    "LEVEL_HOURS_MAP",
    "LABEL_SKILL_MAP",
    "determine_difficulty_from_labels",
    "determine_level",
    "determine_kind_from_labels",
    "get_estimated_hours_from_level",
    "extract_skills_from_labels",
    # Scoring
    "compute_task_score",
    "determine_intent",
    "generate_reason_tags",
    "generate_fallback_reason",
    # Fetchers
    "fetch_open_issues_for_tasks",
    "fetch_open_issues_for_tasks_rest",
    # Generators
    "create_tasks_from_issues",
    "create_meta_tasks_from_labels",
    "create_minimum_meta_tasks",
    "create_study_meta_tasks",
    "DOC_META_TASKS",
    # Main
    "compute_onboarding_tasks",
    # Personalization
    "filter_tasks_by_user_level",
    "filter_tasks_for_user",
    "filter_tasks_by_context",
    "create_personalized_task_set",
    "rank_tasks_for_user",
    "generate_personalized_recommendation",
    # Legacy
    "HEALTHY_PROJECT_META_TASKS",
    "STUDY_META_TASKS",
]
