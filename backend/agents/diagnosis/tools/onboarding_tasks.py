"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .onboarding.onboarding_tasks import (
    # Models
    TaskSuggestion,
    OnboardingTasks,
    Difficulty,
    TaskKind,
    TaskIntent,
    UserTaskContext,
    # Labels
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
    # Scoring
    compute_task_score,
    determine_intent,
    generate_reason_tags,
    generate_fallback_reason,
    # Fetchers
    fetch_open_issues_for_tasks,
    fetch_open_issues_for_tasks_rest,
    # Generators
    create_tasks_from_issues,
    create_meta_tasks_from_labels,
    create_minimum_meta_tasks,
    create_study_meta_tasks,
    DOC_META_TASKS,
    # Main
    compute_onboarding_tasks,
    # Personalization
    filter_tasks_by_user_level,
    filter_tasks_for_user,
    filter_tasks_by_context,
    create_personalized_task_set,
    rank_tasks_for_user,
    generate_personalized_recommendation,
    # Legacy
    HEALTHY_PROJECT_META_TASKS,
    STUDY_META_TASKS,
)
# Internal functions for testing
from .onboarding.onboarding_tasks import (
    _fetch_issues_rest,
    _estimate_hours_from_level,
    _calculate_skill_match_score,
    _calculate_time_fit_score,
)
