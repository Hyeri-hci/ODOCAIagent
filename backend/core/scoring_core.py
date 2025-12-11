"""점수 계산 Core 레이어 - Health/Onboarding 공식 (Pure Python)."""
from __future__ import annotations

from typing import Literal, Optional, Any, cast

from .models import (
    DiagnosisCoreResult,
    DocsCoreResult,
    ActivityCoreResult,
    DependenciesSnapshot,
    StructureCoreResult,
    ProjectRules,
)

# 1. Constants (Thresholds)

HEALTH_GOOD_THRESHOLD = 70
HEALTH_WARNING_THRESHOLD = 50

ONBOARDING_EASY_THRESHOLD = 75
ONBOARDING_NORMAL_THRESHOLD = 55

WEAK_DOCS_THRESHOLD = 40
INACTIVE_ACTIVITY_THRESHOLD = 30

# 2. Score Computation Logic

def compute_health_score(doc: int, activity: int, structure: int = 0) -> int:
    """
    운영/유지보수 Health 점수.
    
    구조 점수가 있으면: doc 25% + activity 65% + structure 10%
    구조 점수가 없으면: doc 30% + activity 70% (기존 방식)
    """
    if structure > 0:
        return int(round(0.25 * doc + 0.65 * activity + 0.10 * structure))
    return int(round(0.3 * doc + 0.7 * activity))


def compute_onboarding_score(doc: int, activity: int, structure: int = 0) -> int:
    """
    온보딩 친화도 점수.
    
    구조 점수가 있으면: doc 55% + activity 35% + structure 10%
    구조 점수가 없으면: doc 60% + activity 40% (기존 방식)
    """
    if structure > 0:
        return int(round(0.55 * doc + 0.35 * activity + 0.10 * structure))
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
    readme_categories: Optional[dict[str, Any]] = None,
) -> list[str]:
    issues: list[str] = []

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
    activity_breakdown: Optional[dict[str, float]] = None,
) -> list[str]:
    issues: list[str] = []

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


def compute_dependency_complexity(deps: DependenciesSnapshot) -> tuple[int, list[str]]:
    """의존성 복잡도 점수 (0~100). 높을수록 관리 난이도가 높음.
    
    Note: 이것은 보안 취약점(Security Risk) 점수가 아님.
    단순히 의존성 개수와 버전 고정 여부를 기반으로 한 '구조적 복잡도'를 의미함.
    """
    if not deps or not deps.dependencies:
        return 0, []

    total_deps = len(deps.dependencies)
    pinned_count = 0
    for d in deps.dependencies:
        if d.version and (d.version.startswith("==") or d.version[0].isdigit()):
            pinned_count += 1
            
    pinned_ratio = pinned_count / total_deps if total_deps > 0 else 0.0
    
    flags: list[str] = []
    base_score = 0
    
    # 1. Total Dependencies Count Complexity
    if total_deps < 30:
        base_score = 20 + (total_deps / 30.0) * 20  # 20~40
    elif total_deps < 100:
        base_score = 40 + ((total_deps - 30) / 70.0) * 30  # 40~70
    else:
        base_score = 70 + min(((total_deps - 100) / 100.0) * 20, 20) # 70~90
        flags.append("many_dependencies")

    # 2. Pinned Ratio Complexity (Unpinned = Higher Complexity/Uncertainty)
    if pinned_ratio < 0.3:
        base_score += 15
        flags.append("unpinned_dependencies")
    elif pinned_ratio < 0.7:
        base_score += 5

    final_score = min(int(base_score), 100)
    
    return final_score, flags


# 3. Main Computation Function

def compute_diagnosis(
    repo_id: str,
    docs_result: DocsCoreResult,
    activity_result: ActivityCoreResult,
    structure_result: Optional[StructureCoreResult] = None,
    project_rules: Optional[ProjectRules] = None,
) -> DiagnosisCoreResult:
    """문서 + 활동성 + 구조 결과로 최종 진단 계산."""
    doc_score = docs_result.total_score
    activity_score = activity_result.total_score
    structure_score = structure_result.structure_score if structure_result else 0

    health = compute_health_score(doc_score, activity_score, structure_score)
    onboarding = compute_onboarding_score(doc_score, activity_score, structure_score)
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


def compute_scores(
    docs: DocsCoreResult,
    activity: ActivityCoreResult,
    deps: DependenciesSnapshot,
    structure: Optional[StructureCoreResult] = None,
) -> DiagnosisCoreResult:
    """CoreResult 객체들을 사용하여 최종 진단을 수행합니다."""
    result = compute_diagnosis(
        repo_id=deps.repo_id,
        docs_result=docs,
        activity_result=activity,
        structure_result=structure,
    )
    
    # 의존성 복잡도 계산
    complexity_score, dep_flags = compute_dependency_complexity(deps)
    
    # 결과에 의존성 정보 추가 (dataclass replace 대신 직접 할당 또는 재생성)
    # DiagnosisCoreResult는 frozen=False (default) 이므로 직접 수정 가능하지만,
    # 안전하게 새로운 객체를 생성하거나 필드를 업데이트.
    # 여기서는 compute_diagnosis가 반환한 객체에 필드를 설정.
    
    result.dependency_snapshot = deps
    result.dependency_complexity_score = complexity_score
    result.dependency_flags = dep_flags
    
    return result
