"""Diagnosis Labels - 건강/온보딩 레벨 및 문서/활동성 이슈 추출."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.agents.diagnosis.config import get_labels_config


@dataclass
class DiagnosisLabels:
    health_level: str  # good | warning | bad
    onboarding_level: str  # easy | normal | hard
    docs_issues: List[str] = field(default_factory=list)
    activity_issues: List[str] = field(default_factory=list)
    data_quality_issues: List[str] = field(default_factory=list)  # 데이터 부족 경고
    insufficient_data: bool = False  # 점수표 숨김 플래그
    
    # v2 신규 필드
    gate_level: str = "unknown"  # active | maintained | stale | abandoned
    sustainability_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def has_low_confidence(self) -> bool:
        """점수 신뢰도가 낮은지 여부 (데이터 부족 시)."""
        return len(self.data_quality_issues) > 0


def compute_health_level(health_score: int) -> str:
    """건강 점수 -> 레벨 (good/warning/bad)."""
    config = get_labels_config()
    good_threshold = config.get("health_good", 70)
    warning_threshold = config.get("health_warning", 50)
    
    if health_score >= good_threshold:
        return "good"
    elif health_score >= warning_threshold:
        return "warning"
    return "bad"


def compute_onboarding_level(onboarding_score: int) -> str:
    """온보딩 점수 -> 레벨 (easy/normal/hard)."""
    config = get_labels_config()
    easy_threshold = config.get("onboarding_easy", 75)
    normal_threshold = config.get("onboarding_normal", 55)
    
    if onboarding_score >= easy_threshold:
        return "easy"
    elif onboarding_score >= normal_threshold:
        return "normal"
    return "hard"


def compute_docs_issues(
    doc_score: int,
    readme_categories: Optional[Dict[str, Any]] = None,
    is_marketing_heavy: bool = False,
    has_broken_refs: bool = False,
    docs_effective: Optional[int] = None,
) -> List[str]:
    """doc_score 및 readme_categories 기반 문서 이슈 추출 (v2: 마케팅/참조 이슈 포함)."""
    config = get_labels_config()
    issues: List[str] = []

    # 전반적 문서화 부족
    weak_threshold = config.get("weak_docs_threshold", 40)
    if doc_score < weak_threshold:
        issues.append("weak_documentation")

    # v2: 마케팅 과다 README
    if is_marketing_heavy:
        issues.append("marketing_heavy_readme")
    
    # v2: 깨진 참조
    if has_broken_refs:
        issues.append("broken_references")
    
    # v2: 유효 문서 점수가 형식 점수보다 많이 낮은 경우
    inflated_gap = config.get("inflated_gap_threshold", 20)
    if docs_effective is not None and doc_score > 0:
        gap = doc_score - docs_effective
        if gap >= inflated_gap:
            issues.append("inflated_docs_score")

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


def compute_sustainability_issues(
    gate_level: str,
    is_sustainable: bool = True,
) -> List[str]:
    """지속가능성 게이트 기반 이슈 추출."""
    issues: List[str] = []
    
    if gate_level == "abandoned":
        issues.append("project_abandoned")
    elif gate_level == "stale":
        issues.append("project_stale")
    
    if not is_sustainable:
        issues.append("sustainability_concern")
    
    return issues


def compute_data_quality_issues(
    repo_info: Optional[Dict[str, Any]] = None,
    activity_data: Optional[Dict[str, Any]] = None,
) -> tuple[List[str], bool]:
    """데이터 품질/부족 이슈 감지 - 신뢰도 경고 및 점수표 숨김 여부 반환."""
    issues: List[str] = []
    insufficient_data = False
    
    stars = 0
    forks = 0
    created_at = None
    
    if repo_info:
        stars = repo_info.get("stargazers_count") or 0
        forks = repo_info.get("forks_count") or 0
        created_at = repo_info.get("created_at")
        
        # Stars/Forks 0 → 신규 또는 테스트 프로젝트
        if stars == 0 and forks == 0:
            issues.append("no_community_engagement")
    
    total_commits = 0
    if activity_data:
        # activity_data 구조: {"commit": {...}, "issue": {...}, "pr": {...}}
        commit_data = activity_data.get("commit", {})
        total_commits = commit_data.get("total_commits") or 0
        
        # 최근 커밋 0 → 활동 없음
        if total_commits == 0:
            issues.append("no_recent_activity")
        
        # 이슈/PR 데이터 없음 (키는 "issue", "pr" - 단수형)
        issues_data = activity_data.get("issue", {})
        prs_data = activity_data.get("pr", {})
        if not issues_data and not prs_data:
            issues.append("insufficient_activity_data")
    
    # 신규 프로젝트 감지 (30일 미만)
    is_new_project = False
    if created_at:
        try:
            if isinstance(created_at, str):
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                created_dt = created_at
            days_since_creation = (datetime.now(timezone.utc) - created_dt).days
            if days_since_creation < 30:
                issues.append("new_project")
                is_new_project = True
        except (ValueError, TypeError):
            pass
    
    # 점수표 숨김 조건:
    # 1. 활동 없음: Stars=0, Forks=0, 최근 커밋=0
    # 2. 신규 프로젝트: 30일 미만
    # 3. 활동 미미: 총 커밋 10개 미만
    no_activity = (stars == 0 and forks == 0 and total_commits == 0)
    minimal_activity = (total_commits > 0 and total_commits < 10)
    
    if no_activity or is_new_project or minimal_activity:
        insufficient_data = True
        if minimal_activity and "minimal_activity" not in issues:
            issues.append("minimal_activity")
    
    return issues, insufficient_data


def create_diagnosis_labels(
    health_score: int,
    onboarding_score: int,
    doc_score: int,
    activity_score: int,
    readme_categories: Optional[Dict[str, Any]] = None,
    activity_scores: Optional[Dict[str, float]] = None,
    repo_info: Optional[Dict[str, Any]] = None,
    activity_data: Optional[Dict[str, Any]] = None,
    # v2 파라미터
    is_marketing_heavy: bool = False,
    has_broken_refs: bool = False,
    docs_effective: Optional[int] = None,
    gate_level: str = "unknown",
    is_sustainable: bool = True,
) -> DiagnosisLabels:
    """진단 점수들로부터 구조적 라벨 생성 (v2: 마케팅/지속가능성 이슈 포함)."""
    data_quality_issues, insufficient_data = compute_data_quality_issues(repo_info, activity_data)
    
    return DiagnosisLabels(
        health_level=compute_health_level(health_score),
        onboarding_level=compute_onboarding_level(onboarding_score),
        docs_issues=compute_docs_issues(
            doc_score, 
            readme_categories,
            is_marketing_heavy=is_marketing_heavy,
            has_broken_refs=has_broken_refs,
            docs_effective=docs_effective,
        ),
        activity_issues=compute_activity_issues(activity_score, activity_scores),
        data_quality_issues=data_quality_issues,
        insufficient_data=insufficient_data,
        gate_level=gate_level,
        sustainability_issues=compute_sustainability_issues(gate_level, is_sustainable),
    )
