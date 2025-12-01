"""Diagnosis Tools Module."""

from .scoring.health_score import create_health_score
from .scoring.health_formulas import SCORE_FORMULA_DESC, METRIC_EXPLANATION
from .scoring.activity_scores import activity_score_to_100, aggregate_activity_score
from .scoring.reasoning_builder import build_explain_context, classify_explain_depth, build_warning_text
from .scoring.chaoss_metrics import (
    compute_commit_activity,
    compute_issue_activity,
    compute_pr_activity,
    CommitActivityMetrics,
    IssueActivityMetrics,
    PullRequestActivityMetrics,
)
from .scoring.diagnosis_labels import create_diagnosis_labels

from .readme.readme_summarizer import (
    ReadmeUnifiedSummary,
    ReadmeAdvancedSummary,
    generate_readme_unified_summary,
    generate_readme_advanced_summary,
    generate_readme_category_summaries,
    summarize_readme_category_for_embedding,
)
from .readme.readme_categories import (
    ReadmeCategory,
    CategoryInfo,
    classify_readme_sections,
)
from .readme.readme_loader import fetch_readme_content

from .onboarding.onboarding_tasks import (
    TaskSuggestion,
    OnboardingTasks,
    compute_onboarding_tasks,
    filter_tasks_by_user_level,
    filter_tasks_for_user,
    rank_tasks_for_user,
    generate_personalized_recommendation,
)
from .onboarding.onboarding_recommender_llm import (
    EnrichedTask,
    OnboardingScenario,
    LLMEnrichedTasks,
    enrich_onboarding_tasks,
    enrich_tasks_with_llm,
    generate_onboarding_scenario,
)
from .onboarding.onboarding_plan import create_onboarding_plan

from .repo_parser import fetch_repo_info


__all__ = [
    "create_health_score",
    "SCORE_FORMULA_DESC",
    "METRIC_EXPLANATION",
    "activity_score_to_100",
    "aggregate_activity_score",
    "build_explain_context",
    "classify_explain_depth",
    "build_warning_text",
    "compute_commit_activity",
    "compute_issue_activity",
    "compute_pr_activity",
    "CommitActivityMetrics",
    "IssueActivityMetrics",
    "PullRequestActivityMetrics",
    "create_diagnosis_labels",
    "ReadmeUnifiedSummary",
    "ReadmeAdvancedSummary",
    "ReadmeCategory",
    "CategoryInfo",
    "classify_readme_sections",
    "generate_readme_unified_summary",
    "generate_readme_advanced_summary",
    "generate_readme_category_summaries",
    "summarize_readme_category_for_embedding",
    "fetch_readme_content",
    "TaskSuggestion",
    "OnboardingTasks",
    "compute_onboarding_tasks",
    "filter_tasks_by_user_level",
    "filter_tasks_for_user",
    "rank_tasks_for_user",
    "generate_personalized_recommendation",
    "EnrichedTask",
    "OnboardingScenario",
    "LLMEnrichedTasks",
    "enrich_onboarding_tasks",
    "enrich_tasks_with_llm",
    "generate_onboarding_scenario",
    "create_onboarding_plan",
    "fetch_repo_info",
]
