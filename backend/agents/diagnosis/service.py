from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List
import logging

from backend.agents.diagnosis.tools.readme_loader import (
    fetch_readme_content,
    compute_reademe_metrics,
)
from backend.agents.diagnosis.tools.readme_categories import classify_readme_sections
from backend.common.github_client import DEFAULT_ACTIVITY_DAYS
from backend.common.parallel import run_parallel
from .tools.repo_parser import fetch_repo_info
from .tools.chaoss_metrics import (
    compute_commit_activity,
    compute_issue_activity,
    compute_pr_activity,
)
from .tools.health_score import (
    aggregate_health_scores,
    HealthScore,
    score_commit_activity,
    score_documentation,
)
from .task_type import DiagnosisTaskType, parse_task_type
from .llm_summarizer import summarize_diagnosis_repository

logger = logging.getLogger(__name__)

USE_LLM_SUMMARY = True


def _summarize_common(repo_info, scores: HealthScore, commit_metrics=None) -> str:
    """규칙 기반 자연어 요약."""
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
                f"Days since last commit: {commit_metrics.days_since_last_commit}"
            )
        else:
            parts.append(
                f"No commits in the last {commit_metrics.window_days} days."
            )

    return "\n".join(parts)


def run_diagnosis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Diagnosis Agent 진입점.
    payload: owner, repo, task_type, focus, user_context, advanced_analysis
    """

    owner = (payload.get("owner") or "").strip()
    repo = (payload.get("repo") or "").strip()
    if not owner or not repo:
        raise ValueError("owner 및 repo는 필수 항목입니다.")

    task_type = parse_task_type(payload.get("task_type"))
    focus = payload.get("focus") or []
    user_context = payload.get("user_context") or {}
    user_level = user_context.get("level", "beginner")
    
    # 고급 분석 모드: 카테고리별 상세 요약 포함 (LLM 5회, 기본 1회보다 느림)
    advanced_analysis = payload.get("advanced_analysis", False)

    # Phase 1: GitHub API 병렬 호출
    logger.info("Phase 1: Fetching GitHub data...")
    
    if task_type == DiagnosisTaskType.FULL:
        # FULL 모드: repo_info, readme, commits, issues, prs 병렬 호출
        parallel_results = run_parallel({
            "repo_info": lambda: fetch_repo_info(owner, repo),
            "readme_text": lambda: fetch_readme_content(owner, repo) or "",
            "commit_metrics": lambda: compute_commit_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "issue_metrics": lambda: compute_issue_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "pr_metrics": lambda: compute_pr_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
        })
        repo_info = parallel_results["repo_info"]
        readme_text = parallel_results["readme_text"]
        commit_metrics = parallel_results["commit_metrics"]
        issue_metrics = parallel_results["issue_metrics"]
        pr_metrics = parallel_results["pr_metrics"]
    else:
        # DOCS_ONLY 또는 ACTIVITY_ONLY: 필요한 것만 병렬 호출
        parallel_results = run_parallel({
            "repo_info": lambda: fetch_repo_info(owner, repo),
            "readme_text": lambda: fetch_readme_content(owner, repo) or "",
        })
        repo_info = parallel_results["repo_info"]
        readme_text = parallel_results["readme_text"]
        commit_metrics = None
        issue_metrics = None
        pr_metrics = None

    # README 메트릭 계산 (로컬, 빠름)
    readme_metrics = None
    if readme_text:
        readme_metrics = compute_reademe_metrics(readme_text)

    # Phase 2: README 분류 + 요약
    logger.info("Phase 2: README classification...")
    
    if readme_text:
        readme_categories, readme_category_score, unified_summary = classify_readme_sections(
            readme_text,
            advanced_mode=advanced_analysis,
        )
    else:
        from backend.agents.diagnosis.tools.llm_summarizer import ReadmeUnifiedSummary
        readme_categories, readme_category_score = {}, 0
        unified_summary = ReadmeUnifiedSummary(summary_en="", summary_ko="")

    # details 기본 구성
    details: Dict[str, Any] = {
        "repo_info": asdict(repo_info),
        "analysis_mode": "advanced" if advanced_analysis else "basic",
    }
    if readme_metrics is not None:
        details["readme_metrics"] = asdict(readme_metrics)

    details["docs"] = {
        "readme_categories": readme_categories,
        "readme_category_score": readme_category_score,
        "readme_summary_for_embedding": unified_summary.summary_en,
        "readme_summary_for_user": unified_summary.summary_ko,
    }

    details["readme_raw"] = readme_text

    # Phase 3: 점수 계산
    logger.info("Phase 3: Computing scores...")
    scores: HealthScore

    if task_type == DiagnosisTaskType.FULL:
        # commit_metrics는 Phase 1에서 이미 가져옴
        scores = aggregate_health_scores(
            has_readme=repo_info.has_readme,
            commit_metrics=commit_metrics,
            readme_stats=repo_info.readme_stats,
        )

        # CHAOSS 기반 activity 블록 (commit, issue, pr)
        details["activity"] = {
            "commit": asdict(commit_metrics),
            "issue": asdict(issue_metrics),
            "pr": asdict(pr_metrics),
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
        # ACTIVITY_ONLY: commit, issue, pr 메트릭 병렬 호출
        activity_results = run_parallel({
            "commit_metrics": lambda: compute_commit_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "issue_metrics": lambda: compute_issue_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "pr_metrics": lambda: compute_pr_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
        })
        commit_metrics = activity_results["commit_metrics"]
        issue_metrics = activity_results["issue_metrics"]
        pr_metrics = activity_results["pr_metrics"]

        activity_score = score_commit_activity(commit_metrics)

        scores = HealthScore(
            documentation_quality=0,
            activity_maintainability=activity_score,
            overall_score=activity_score,
        )

        details["activity"] = {
            "commit": asdict(commit_metrics),
            "issue": asdict(issue_metrics),
            "pr": asdict(pr_metrics),
        }

    else:
        scores = HealthScore(
            documentation_quality=0,
            activity_maintainability=0,
            overall_score=0,
        )

    # 규칙 기반 기본 요약
    natural_summary = _summarize_common(
        repo_info=repo_info,
        scores=scores,
        commit_metrics=commit_metrics,
    )

    # 최종 JSON 결과
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

    # LLM 기반 요약
    if USE_LLM_SUMMARY:
        natural_summary = summarize_diagnosis_repository(
            diagnosis_result=result_json,
            user_level=user_level,
            language="ko",
        )

    result_json["natural_language_summary_for_user"] = natural_summary
    return result_json
