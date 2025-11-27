from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from backend.common.github_client import DEFAULT_ACTIVITY_DAYS
from .tools.repo_parser import fetch_repo_info
from .tools.chaoss_metrics import compute_commit_activity
from .tools.health_score import (
    aggregate_health_scores,
    HealthScore,
    score_commit_activity,
    score_documentation,
)
from .task_type import DiagnosisTaskType, parse_task_type
from .llm_summarizer import summarize_diagnosis_repository

USE_LLM_SUMMARY = True

def _summarize_common(repo_info, scores: HealthScore, commit_metrics=None) -> str:
    """
        간단 자연어 요약 (현재는 규칙 기반)
    """
    parts: List[str] = []
    parts.append(f"Repository: {repo_info.full_name}")
    if repo_info.description:
        parts.append(f"Description: {repo_info.description}")
    parts.append(f"Stars: {repo_info.stars}, Forks: {repo_info.forks}, Watchers: {repo_info.watchers}")
    parts.append(f"Open Issues: {repo_info.open_issues}")
    parts.append(
        f"README Present: {'Yes' if repo_info.has_readme else 'No'} "
        f"(Documentation Quality Score: {scores.documentation_quality}/100)"
    )
    parts.append(
        f"Activity & Maintainability Score: {scores.activity_maintainability}/100"
    )
    parts.append(
        f"Overall Health Score: {scores.overall_score}/100"
    )

    if commit_metrics is not None:
        if commit_metrics.days_since_last_commit is not None:
            parts.append(
                f"Total Commits in last {commit_metrics.window_days} days: {commit_metrics.total_commits}, "
                f"Days since last commit: {commit_metrics.days_since_last_commit} "
            )
        else:
            parts.append(
                f"No commits in the last {commit_metrics.window_days} days."
            )

    return "\n".join(parts)


def run_diagnosis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
        Diagnosis Agent 최소 버전
        입력: { owner, repo, task_type, focus, user_context? }
        출력: scores + details
    """

    owner = payload["owner"]
    repo = payload["repo"]
    task_type = parse_task_type(payload.get("task_type"))
    focus: List[str] = payload.get("focus", ["documentation", "activity"])

    # common setup: basic repo info fetch (READEME presence, stats)
    repo_info = fetch_repo_info(owner, repo)

    scores: HealthScore
    commit_metrics = None
    details: Dict[str, Any] = {
        "repo_info": asdict(repo_info),
    }

    # full_diagnosis
    if task_type == DiagnosisTaskType.FULL:
        commit_metrics = compute_commit_activity(
           owner=owner,
            repo=repo,
            days=DEFAULT_ACTIVITY_DAYS,
        )

        scores = aggregate_health_scores(
            has_readme=repo_info.has_readme,
            commit_metrics=commit_metrics,
            readme_stats=repo_info.readme_stats,
        )

        details["commit_metrics"] = {
            "total_commits": commit_metrics.total_commits,
            "days_since_last_commit": commit_metrics.days_since_last_commit,
            "window_days": commit_metrics.window_days,
        }

    # docs_only
    elif task_type == DiagnosisTaskType.DOCS_ONLY:
        docs_score = score_documentation(
            has_readme=repo_info.has_readme,
            stats=repo_info.readme_stats,
        )

        scores = HealthScore(
            documentation_quality=docs_score,
            activity_maintainability=0,
            overall_score=docs_score,
        )

    # activity_only
    elif task_type == DiagnosisTaskType.ACTIVITY_ONLY:
        commit_metrics = compute_commit_activity(
            owner=owner,
            repo=repo,
            days=DEFAULT_ACTIVITY_DAYS,
        )

        activity_score = score_commit_activity(commit_metrics)

        scores = HealthScore(
            documentation_quality=0,
            activity_maintainability=activity_score,
            overall_score=activity_score,
        )

        details["commit_metrics"] = {
            "total_commits": commit_metrics.total_commits,
            "days_since_last_commit": commit_metrics.days_since_last_commit,
            "window_days": commit_metrics.window_days,
        }

    else:
        scores = HealthScore(
            documentation_quality=0,
            activity_maintainability=0,
            overall_score=0,
        )

    # 간단 자연어 요약 (현재는 규칙 기반)
    natural_summary = _summarize_common(
        repo_info=repo_info,
        scores=scores,
        commit_metrics=commit_metrics,
    )

    result_json: Dict[str, Any] = {
        "input": {
            "owner": owner,
            "repo": repo,
            "task_type": task_type.value,
            "focus": focus,
        },
        "scores": asdict(scores),
        "details": details,
    }

    # LLM 요약 생성
    if USE_LLM_SUMMARY:
        natural_summary = summarize_diagnosis_repository(
            diagnosis_result=result_json,
            user_level=payload.get("user_context", {}).get("level", "beginner"),
            language="ko",
        )
    else:
        natural_summary = _summarize_common(
            repo_info=repo_info,
            scores=scores,
            commit_metrics=commit_metrics,
        )

    result_json["natural_language_summary_for_user"] = natural_summary

    return result_json

