"""Core domain models - LLM/LangGraph 의존성 없음."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


@dataclass(frozen=True)
class RepoSnapshot:
    """GitHub 저장소 스냅샷 (불변)."""
    owner: str
    repo: str
    ref: str  # branch or commit sha

    full_name: str
    description: Optional[str]
    stars: int
    forks: int
    open_issues: int
    primary_language: Optional[str]
    created_at: Optional[datetime]
    pushed_at: Optional[datetime]
    is_archived: bool
    is_fork: bool

    readme_content: Optional[str]
    has_readme: bool
    license_spdx: Optional[str]

    @property
    def repo_id(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass
class DependencyInfo:
    """단일 의존성 정보."""
    name: str
    version: Optional[str]
    source: str  # requirements.txt, package.json 등
    dep_type: Literal["runtime", "dev", "optional"]


@dataclass
class DependenciesSnapshot:
    """저장소 의존성 스냅샷."""
    repo_id: str
    dependencies: List[DependencyInfo] = field(default_factory=list)
    analyzed_files: List[str] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.dependencies)

    @property
    def runtime_count(self) -> int:
        return len([d for d in self.dependencies if d.dep_type == "runtime"])

# Alias for backward compatibility
DependencySnapshot = DependenciesSnapshot


@dataclass
class DocsCoreResult:
    """문서 분석 결과."""
    readme_present: bool
    readme_word_count: int
    category_scores: Dict[str, Dict[str, Any]]  # WHAT, WHY, HOW 등 (CategoryInfo dict)
    total_score: int  # 0-100
    missing_sections: List[str]
    present_sections: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "readme_present": self.readme_present,
            "readme_word_count": self.readme_word_count,
            "category_scores": self.category_scores,
            "total_score": self.total_score,
            "missing_sections": self.missing_sections,
            "present_sections": self.present_sections,
        }


@dataclass
class ActivityCoreResult:
    """활동성 분석 결과."""
    commit_score: float  # 0-1
    issue_score: float   # 0-1
    pr_score: float      # 0-1
    total_score: int     # 0-100

    days_since_last_commit: Optional[int]
    total_commits_in_window: int
    unique_authors: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commit_score": self.commit_score,
            "issue_score": self.issue_score,
            "pr_score": self.pr_score,
            "total_score": self.total_score,
            "days_since_last_commit": self.days_since_last_commit,
            "total_commits_in_window": self.total_commits_in_window,
            "unique_authors": self.unique_authors,
        }


@dataclass
class DiagnosisCoreResult:
    """진단 결과 (Core 레이어)."""
    repo_id: str

    documentation_quality: int      # 0-100
    activity_maintainability: int   # 0-100
    health_score: int               # 0-100
    onboarding_score: int           # 0-100
    is_healthy: bool

    health_level: Literal["good", "warning", "bad"]
    onboarding_level: Literal["easy", "normal", "hard"]
    docs_issues: List[str]
    activity_issues: List[str]

    docs_result: Optional[DocsCoreResult] = None
    activity_result: Optional[ActivityCoreResult] = None
    dependency_snapshot: Optional[DependenciesSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        """기존 코드 호환용 dict 변환."""
        return {
            "scores": {
                "documentation_quality": self.documentation_quality,
                "activity_maintainability": self.activity_maintainability,
                "health_score": self.health_score,
                "onboarding_score": self.onboarding_score,
                "is_healthy": self.is_healthy,
            },
            "labels": {
                "health_level": self.health_level,
                "onboarding_level": self.onboarding_level,
                "docs_issues": self.docs_issues,
                "activity_issues": self.activity_issues,
            },
        }


@dataclass
class ProjectRules:
    """프로젝트별 분석 규칙."""
    ignore_packages: List[str] = field(default_factory=list)
    min_health_score: int = 60
    required_sections: List[str] = field(default_factory=list)


@dataclass
class StructureCoreResult:
    """리포 구조 성숙도 분석 결과."""
    has_tests: bool
    has_ci: bool
    has_docs_folder: bool
    has_build_config: bool
    
    test_files: List[str] = field(default_factory=list)
    ci_files: List[str] = field(default_factory=list)
    build_files: List[str] = field(default_factory=list)
    
    structure_score: int = 0  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_tests": self.has_tests,
            "has_ci": self.has_ci,
            "has_docs_folder": self.has_docs_folder,
            "has_build_config": self.has_build_config,
            "test_files": self.test_files,
            "ci_files": self.ci_files,
            "build_files": self.build_files,
            "structure_score": self.structure_score,
        }


@dataclass
class UserGuidelines:
    """세션별 사용자 지침."""
    user_level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    preferred_language: str = "ko"
    focus_areas: List[str] = field(default_factory=list)
