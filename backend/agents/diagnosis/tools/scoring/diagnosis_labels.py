"""Diagnosis Labels - 건강/온보딩 레벨 및 문서/활동성 이슈 추출."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosisLabels:
    health_level: str  # good | warning | bad
    onboarding_level: str  # easy | normal | hard
    docs_issues: List[str] = field(default_factory=list)
    activity_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_health_level(health_score: int) -> str:
    """건강 점수 -> 레벨 (good/warning/bad)."""
    if health_score >= 70:
        return "good"
    elif health_score >= 50:
        return "warning"
    return "bad"


def compute_onboarding_level(onboarding_score: int) -> str:
    """온보딩 점수 -> 레벨 (easy/normal/hard)."""
    if onboarding_score >= 75:
        return "easy"
    elif onboarding_score >= 55:
        return "normal"
    return "hard"


def compute_docs_issues(
    doc_score: int,
    readme_categories: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """doc_score 및 readme_categories 기반 문서 이슈 추출."""
    issues: List[str] = []

    # 전반적 문서화 부족
    if doc_score < 40:
        issues.append("weak_documentation")

    # 개별 카테고리 검사
    if readme_categories:
        category_map = {
            "WHAT": "missing_what",
            "WHY": "missing_why",
            "HOW": "missing_how",
            "CONTRIBUTING": "missing_contributing",
        }
        for cat_key, issue_name in category_map.items():
            cat_info = readme_categories.get(cat_key, {})
            if isinstance(cat_info, dict):
                if not cat_info.get("present", False):
                    issues.append(issue_name)
            elif not cat_info:  # bool False
                issues.append(issue_name)

    return issues


def compute_activity_issues(
    activity_score: int,
    activity_scores: Optional[Dict[str, float]] = None,
) -> List[str]:
    """activity_score 및 세부 점수 기반 활동성 이슈 추출."""
    issues: List[str] = []

    # 전반적 비활성
    if activity_score < 30:
        issues.append("inactive_project")

    # 세부 점수 기반
    if activity_scores:
        if activity_scores.get("commit_score", 1.0) < 0.3:
            issues.append("no_recent_commits")
        if activity_scores.get("issue_score", 1.0) < 0.3:
            issues.append("low_issue_closure")
        if activity_scores.get("pr_score", 1.0) < 0.4:
            issues.append("slow_pr_merge")

    return issues


def create_diagnosis_labels(
    health_score: int,
    onboarding_score: int,
    doc_score: int,
    activity_score: int,
    readme_categories: Optional[Dict[str, Any]] = None,
    activity_scores: Optional[Dict[str, float]] = None,
) -> DiagnosisLabels:
    """진단 점수들로부터 구조적 라벨 생성."""
    return DiagnosisLabels(
        health_level=compute_health_level(health_score),
        onboarding_level=compute_onboarding_level(onboarding_score),
        docs_issues=compute_docs_issues(doc_score, readme_categories),
        activity_issues=compute_activity_issues(activity_score, activity_scores),
    )
