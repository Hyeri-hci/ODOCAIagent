from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from backend.common.github_client import DEFAULT_ACTIVITY_DAYS
from .tools.repo_parser import fetch_repo_info
from .tools.chaoss_metrics import compute_commit_activity
from .tools.health_score import aggregate_health_scores


def run_diagnosis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
        Diagnosis Agent 최소 버전
        입력: { owner, repo, task_type, focus, user_context? }
        출력: scores + details
    """

    owner = payload["owner"]
    repo = payload["repo"]
    task_type = payload.get("task_type", "full_diagnosis")
    focus: List[str] = payload.get("focus", ["documentation", "activity"])

    # 1. 리포지토리 기본 정보 및 README 존재 여부 조회
    repo_info = fetch_repo_info(owner, repo)

    # 2. 커밋 활동 지표 계산
    commit_metrics = compute_commit_activity(
        owner=owner,
        repo=repo,
        days=DEFAULT_ACTIVITY_DAYS,
    )

    # 3. 건강 점수 산출
    scores = aggregate_health_scores(
        has_readme=repo_info.has_readme,
        commit_metrics=commit_metrics,
    )

    # 4. 간단 자연어 요약 (현재는 규칙 기반)
    summary_parts: List[str] = []
    summary_parts.append(f"Repository: {repo_info.full_name}")
    if repo_info.description:
        summary_parts.append(f"Description: {repo_info.description}")
    
    summary_parts.append(f"Stars: {repo_info.stars}, Forks: {repo_info.forks}, Watchers: {repo_info.watchers}")
    
    summary_parts.append(f"Open Issues: {repo_info.open_issues}")
    
    summary_parts.append(
        f"README Present: {'Yes' if repo_info.has_readme else 'No'} "
        f"(Documentation Quality Score: {scores.documentation_quality}/100)"
    )

    if commit_metrics.days_since_last_commit is not None:
        summary_parts.append(
            f"Total Commits in last {commit_metrics.window_days} days: {commit_metrics.total_commits}, "
            f"Days since last commit: {commit_metrics.days_since_last_commit} "
        )
    else:
        summary_parts.append(
            f"No commits in the last {commit_metrics.window_days} days."
        )

    summary_parts.append(
        f"Activity & Maintainability Score: {scores.activity_maintainability}/100"
        f"\nOverall Health Score: {scores.overall_score}/100"
    )

    natural_summary = "\n".join(summary_parts)

    return {
        "input": {
            "owner": owner,
            "repo": repo,
            "task_type": task_type,
            "focus": focus,
        },
        "scores": asdict(scores),
        "details": {
            "repo_info": asdict(repo_info),
            "commit_metrics": {
                "total_commits": commit_metrics.total_commits,
                "days_since_last_commit": commit_metrics.days_since_last_commit,
                "window_days": commit_metrics.window_days,
            },
        },
        "natural_language_summary": natural_summary,
        "natural_language_summary_for_user": natural_summary,
    }

