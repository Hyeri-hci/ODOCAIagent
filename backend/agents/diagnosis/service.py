from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from backend.agents.diagnosis.tools.readme_loader import (
    fetch_readme_content,
    compute_reademe_metrics,
)
from backend.agents.diagnosis.tools.readme_categories import classify_readme_sections
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

    입력 payload 예시:
    {
        "owner": "microsoft",
        "repo": "vscode",
        "task_type": "full_diagnosis",
        "focus": ["documentation", "activity"],
        "user_context": {"level": "beginner"}
    }
    """

    # 0) 입력 파싱
    owner = (payload.get("owner") or "").strip()
    repo = (payload.get("repo") or "").strip()
    if not owner or not repo:
        raise ValueError("owner 및 repo는 필수 항목입니다.")

    task_type = parse_task_type(payload.get("task_type"))
    focus = payload.get("focus") or []
    user_context = payload.get("user_context") or {}
    user_level = user_context.get("level", "beginner")

    # 기본 Repository 정보
    repo_info = fetch_repo_info(owner, repo)

    # README 내용 + 기본 메트릭
    readme_text = fetch_readme_content(owner, repo) or ""
    readme_metrics = None
    if readme_text:
        readme_metrics = compute_reademe_metrics(readme_text)

    # README 섹션 분류 (8 카테고리)
    if readme_text:
        readme_categories, readme_category_score = classify_readme_sections(readme_text)
    else:
        readme_categories, readme_category_score = {}, 0

    # 세부 정보 기본값 구성
    details: Dict[str, Any] = {
        "repo_info": asdict(repo_info),
    }
    if readme_metrics is not None:
        details["readme_metrics"] = asdict(readme_metrics)
    details["readme_categories"] = readme_categories
    details["readme_category_score"] = readme_category_score

    # task_type 별로 commit_metrics / scores 계산
    commit_metrics = None   # type: ignore[assignment]
    scores: HealthScore

    if task_type == DiagnosisTaskType.FULL:
        # 활동성 메트릭
        commit_metrics = compute_commit_activity(
            owner=owner,
            repo=repo,
            days=DEFAULT_ACTIVITY_DAYS,
        )

        # HealthScore 집계 (문서 + 활동성)
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

    # 규칙 기반 요약 (fallback)
    natural_summary = _summarize_common(
        repo_info=repo_info,
        scores=scores,
        commit_metrics=commit_metrics,
    )

    # JSON 결과 구성
    result_json: Dict[str, Any] = {
        "input": {
            "owner": owner,
            "repo": repo,
            "task_type": task_type.value if isinstance(task_type, DiagnosisTaskType) else str(task_type),
            "focus": focus,
            "user_context": user_context,
        },
        "scores": asdict(scores),
        "details": details,
    }

    # 8) LLM 요약 (Kanana / Ollama)
    if USE_LLM_SUMMARY:
        natural_summary = summarize_diagnosis_repository(
            diagnosis_result=result_json,
            user_level=user_level,
            language="ko",
        )

    result_json["natural_language_summary_for_user"] = natural_summary
    return result_json


