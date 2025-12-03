"""점수 계산 Core 레이어 - Health/Onboarding 공식 (Pure Python)."""
from __future__ import annotations

from typing import List, Literal, Optional, Dict, Any, cast

from .models import (
    DiagnosisCoreResult,
    DocsCoreResult,
    ActivityCoreResult,
    ProjectRules,
)

# -------------------------------------------------------------------------
# 1. Constants (Thresholds)
# -------------------------------------------------------------------------

HEALTH_GOOD_THRESHOLD = 70
HEALTH_WARNING_THRESHOLD = 50

ONBOARDING_EASY_THRESHOLD = 75
ONBOARDING_NORMAL_THRESHOLD = 55

WEAK_DOCS_THRESHOLD = 40
INACTIVE_ACTIVITY_THRESHOLD = 30

# -------------------------------------------------------------------------
# 2. Score Computation Logic
# -------------------------------------------------------------------------

def compute_health_score(doc: int, activity: int) -> int:
    """모델 2: 운영/유지보수 Health (doc 30% + activity 70%)"""
    return int(round(0.3 * doc + 0.7 * activity))


def compute_onboarding_score(doc: int, activity: int) -> int:
    """모델 1: 온보딩 친화도 (doc 60% + activity 40%)"""
    return int(round(0.6 * doc + 0.4 * activity))


def compute_is_healthy(doc: int, activity: int) -> bool:
    """모델 3: 임계값 기반 건강 플래그"""
    return doc >= 60 and activity >= 50


def compute_health_level(health_score: int) -> str:
    if health_score >= HEALTH_GOOD_THRESHOLD:
        return "good"
    elif health_score >= HEALTH_WARNING_THRESHOLD:
        return "warning"
    return "bad"


def compute_onboarding_level(onboarding_score: int) -> str:
    if onboarding_score >= ONBOARDING_EASY_THRESHOLD:
        return "easy"
    elif onboarding_score >= ONBOARDING_NORMAL_THRESHOLD:
        return "normal"
    return "hard"


def compute_docs_issues(
    doc_score: int,
    readme_categories: Optional[Dict[str, Any]] = None,
) -> List[str]:
    issues: List[str] = []

    if doc_score < WEAK_DOCS_THRESHOLD:
        issues.append("weak_documentation")

    if readme_categories:
        category_map = {
            "WHAT": "missing_what",
            "WHY": "missing_why",
            "HOW": "missing_how",
            "CONTRIBUTING": "missing_contributing",
        }
        for cat_key, issue_name in category_map.items():
            cat_info = readme_categories.get(cat_key, {})
            # cat_info가 dict인 경우 present 체크, 아니면(None 등) missing 취급
            if isinstance(cat_info, dict):
                if not cat_info.get("present", False):
                    issues.append(issue_name)
            elif not cat_info:
                issues.append(issue_name)

    return issues


def compute_activity_issues(
    activity_score: int,
    activity_breakdown: Optional[Dict[str, float]] = None,
) -> List[str]:
    issues: List[str] = []

    if activity_score < INACTIVE_ACTIVITY_THRESHOLD:
        issues.append("inactive_project")

    if activity_breakdown:
        if activity_breakdown.get("commit_score", 1.0) < 0.3:
            issues.append("no_recent_commits")
        if activity_breakdown.get("issue_score", 1.0) < 0.3:
            issues.append("low_issue_closure")
        if activity_breakdown.get("pr_score", 1.0) < 0.4:
            issues.append("slow_pr_merge")

    return issues


# -------------------------------------------------------------------------
# 3. Main Computation Function
# -------------------------------------------------------------------------

def compute_diagnosis(
    repo_id: str,
    docs_result: DocsCoreResult,
    activity_result: ActivityCoreResult,
    project_rules: Optional[ProjectRules] = None,
) -> DiagnosisCoreResult:
    """문서 + 활동성 결과로 최종 진단 계산."""
    doc_score = docs_result.total_score
    activity_score = activity_result.total_score

    health = compute_health_score(doc_score, activity_score)
    onboarding = compute_onboarding_score(doc_score, activity_score)
    is_healthy = compute_is_healthy(doc_score, activity_score)

    health_level_str = compute_health_level(health)
    onboarding_level_str = compute_onboarding_level(onboarding)

    docs_issues = compute_docs_issues(
        doc_score,
        docs_result.category_scores if docs_result.readme_present else None,
    )

    activity_breakdown = {
        "commit_score": activity_result.commit_score,
        "issue_score": activity_result.issue_score,
        "pr_score": activity_result.pr_score,
    }
    activity_issues = compute_activity_issues(activity_score, activity_breakdown)

    return DiagnosisCoreResult(
        repo_id=repo_id,
        documentation_quality=doc_score,
        activity_maintainability=activity_score,
        health_score=health,
        onboarding_score=onboarding,
        is_healthy=is_healthy,
        health_level=cast(Literal["good", "warning", "bad"], health_level_str),
        onboarding_level=cast(Literal["easy", "normal", "hard"], onboarding_level_str),
        docs_issues=docs_issues,
        activity_issues=activity_issues,
        docs_result=docs_result,
        activity_result=activity_result,
    )
