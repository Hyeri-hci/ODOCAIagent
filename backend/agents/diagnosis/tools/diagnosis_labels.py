"""
Diagnosis Labels v1.0

규칙 기반으로 진단 결과에 레벨/태그를 부여하는 모듈.
LLM이 해석하기 전에 1차 분류를 제공합니다.

Related: docs/DIAGNOSIS_SCHEMA_v1.md
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosisLabels:
    """진단 결과 라벨 (규칙 기반)"""
    
    # 레벨 판정
    health_level: str  # "good" | "warning" | "bad"
    onboarding_level: str  # "easy" | "normal" | "hard"
    
    # 문제 태그
    docs_issues: List[str] = field(default_factory=list)
    activity_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_health_level(health_score: int) -> str:
    """
    health_score 기반 레벨 판정.
    
    - good: health ≥ 70
    - warning: 50 ≤ health < 70
    - bad: health < 50
    """
    if health_score >= 70:
        return "good"
    elif health_score >= 50:
        return "warning"
    else:
        return "bad"


def compute_onboarding_level(onboarding_score: int) -> str:
    """
    onboarding_score 기반 레벨 판정.
    
    - easy: onboarding ≥ 75
    - normal: 55 ≤ onboarding < 75
    - hard: onboarding < 55
    """
    if onboarding_score >= 75:
        return "easy"
    elif onboarding_score >= 55:
        return "normal"
    else:
        return "hard"


def compute_docs_issues(
    doc_score: int,
    readme_categories: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    문서 품질 기반 문제 태그 생성.
    
    readme_categories는 CategoryInfo dict들의 dict:
    { "WHAT": {"present": True, "raw_text": "...", ...}, ... }
    
    Tags:
    - missing_what: WHAT 카테고리 비어있음
    - missing_why: WHY 카테고리 비어있음
    - missing_how: HOW 카테고리 비어있음
    - missing_contributing: CONTRIBUTING 카테고리 비어있음
    - weak_documentation: 전체 문서 점수 < 40
    """
    issues: List[str] = []
    
    # 전체 문서 품질 체크
    if doc_score < 40:
        issues.append("weak_documentation")
    
    # 카테고리별 체크
    if readme_categories:
        category_checks = [
            ("WHAT", "missing_what"),
            ("WHY", "missing_why"),
            ("HOW", "missing_how"),
            ("CONTRIBUTING", "missing_contributing"),
        ]
        
        for cat_key, tag in category_checks:
            cat_info = readme_categories.get(cat_key, {})
            # CategoryInfo dict 형태: {"present": bool, "raw_text": str, ...}
            if isinstance(cat_info, dict):
                present = cat_info.get("present", False)
                raw_text = cat_info.get("raw_text", "")
                if not present or not (raw_text and raw_text.strip()):
                    issues.append(tag)
            elif isinstance(cat_info, str):
                # 혹시 문자열이면 그대로 체크
                if not cat_info or not cat_info.strip():
                    issues.append(tag)
            else:
                issues.append(tag)
    
    return issues


def compute_activity_issues(
    activity_score: int,
    activity_scores: Optional[Dict[str, float]] = None,
) -> List[str]:
    """
    활동성 기반 문제 태그 생성.
    
    Tags:
    - no_recent_commits: commit_score < 0.2
    - low_issue_closure: issue_score < 0.3
    - slow_pr_merge: pr_score < 0.4
    - inactive_project: 전체 activity < 30
    """
    issues: List[str] = []
    
    # 전체 활동성 체크
    if activity_score < 30:
        issues.append("inactive_project")
    
    # 세부 점수 체크
    if activity_scores:
        commit_score = activity_scores.get("commit_score", 0.5)
        issue_score = activity_scores.get("issue_score", 0.5)
        pr_score = activity_scores.get("pr_score", 0.5)
        
        if commit_score < 0.2:
            issues.append("no_recent_commits")
        if issue_score < 0.3:
            issues.append("low_issue_closure")
        if pr_score < 0.4:
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
    """
    진단 결과에서 라벨 생성.
    
    Args:
        health_score: HealthScore.health_score (0-100)
        onboarding_score: HealthScore.onboarding_score (0-100)
        doc_score: documentation_quality (0-100)
        activity_score: activity_maintainability (0-100)
        readme_categories: details.docs.readme_categories
        activity_scores: details.activity.scores
    
    Returns:
        DiagnosisLabels with levels and issue tags
    """
    return DiagnosisLabels(
        health_level=compute_health_level(health_score),
        onboarding_level=compute_onboarding_level(onboarding_score),
        docs_issues=compute_docs_issues(doc_score, readme_categories),
        activity_issues=compute_activity_issues(activity_score, activity_scores),
    )
