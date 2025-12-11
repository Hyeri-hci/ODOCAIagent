"""
API Request/Response 스키마 정의.
"""
from __future__ import annotations

from typing import Any, Optional, Union
from pydantic import BaseModel, Field, field_validator

from backend.core.models import DiagnosisCoreResult


class DiagnosisSummaryDTO(BaseModel):
    """
    프론트엔드 및 CLI에서 공통으로 사용할 진단 결과 요약 DTO.
    """
    
    # 필수 필드
    repo_id: str = Field(..., description="Repository ID (owner/repo)", examples=["facebook/react"])
    documentation_quality: int = Field(..., ge=0, le=100, description="Documentation quality score (0-100)")
    activity_maintainability: int = Field(..., ge=0, le=100, description="Activity & maintainability score (0-100)")
    health_score: int = Field(..., ge=0, le=100, description="Overall health score (0-100)")
    health_level: str = Field(..., description="Health level (bad/ok/good/excellent)")
    onboarding_score: int = Field(..., ge=0, le=100, description="Onboarding score (0-100)")
    onboarding_level: str = Field(..., description="Onboarding difficulty (hard/medium/easy)")
    dependency_complexity_score: int = Field(..., ge=0, le=100, description="Dependency complexity score (0-100)")
    dependency_complexity_level: str = Field(..., description="Dependency complexity level (low/medium/high)")
    dependency_flags: list[str] = Field(default_factory=list, description="Dependency warning flags")
    docs_issues: list[str] = Field(default_factory=list, description="Documentation issues")
    activity_issues: list[str] = Field(default_factory=list, description="Activity issues")
    docs_issues_count: int = Field(default=0, ge=0, description="Number of documentation issues")
    activity_issues_count: int = Field(default=0, ge=0, description="Number of activity issues")
    
    # 선택 필드
    summary_for_user: Optional[str] = Field(None, description="LLM-generated summary for user")
    
    # 상세 활동성 메트릭
    days_since_last_commit: Optional[int] = Field(None, ge=0, description="Days since last commit")
    total_commits_30d: int = Field(default=0, ge=0, description="Total commits in last 30 days")
    unique_contributors: int = Field(default=0, ge=0, description="Number of unique contributors")
    
    # 상세 메트릭 (UX 개선용)
    issue_close_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Issue close rate (0-1)")
    median_pr_merge_days: Optional[float] = Field(None, ge=0, description="Median PR merge time in days")
    median_issue_close_days: Optional[float] = Field(None, ge=0, description="Median issue close time in days")
    open_issues_count: int = Field(default=0, ge=0, description="Number of open issues")
    open_prs_count: int = Field(default=0, ge=0, description="Number of open PRs")
    
    # 문서 상세
    readme_sections: Optional[dict[str, bool]] = Field(None, description="README section presence (WHAT/WHY/HOW/CONTRIBUTING)")
    
    # 저장소 메타데이터
    stars: int = Field(default=0, ge=0, description="GitHub stars")
    forks: int = Field(default=0, ge=0, description="GitHub forks")
    
    # 구조 분석 결과 (내부 처리용 - Frontend 표시 안 함)
    structure_score: int = Field(default=0, ge=0, le=100, description="Structure score (0-100)")
    has_tests: bool = Field(default=False, description="Has test directory")
    has_ci: bool = Field(default=False, description="Has CI configuration")
    has_docs_folder: bool = Field(default=False, description="Has docs folder")
    has_build_config: bool = Field(default=False, description="Has build configuration")
    
    # 추천 이슈
    recommended_issues: Optional[list[dict[str, Any]]] = Field(None, description="Recommended issues for onboarding")
    
    # 유사 프로젝트 추천
    similar_projects: Optional[list[dict[str, Any]]] = Field(
        None, 
        description="Similar projects recommendation with metadata (name, owner, stars, forks, language, reason, similarity)"
    )
    
    # Agentic 플로우 결과
    warnings: list[str] = Field(default_factory=list, description="Agentic flow warnings")
    flow_adjustments: list[str] = Field(default_factory=list, description="Agentic flow adjustments")
    
    # 메타 에이전트 결과
    task_plan: Optional[list[dict[str, Any]]] = Field(None, description="Meta agent task plan")
    task_results: Optional[dict[str, Any]] = Field(None, description="Meta agent task results")
    chat_response: Optional[str] = Field(None, description="Chat agent response")
    onboarding_plan: Optional[list[dict[str, Any]]] = Field(None, description="Onboarding plan")
    
    @field_validator("health_level")
    @classmethod
    def validate_health_level(cls, v: str) -> str:
        """health_level 값 검증."""
        allowed = {"bad", "ok", "good", "excellent"}
        if v not in allowed:
            raise ValueError(f"health_level must be one of {allowed}, got {v}")
        return v
    
    @field_validator("onboarding_level")
    @classmethod
    def validate_onboarding_level(cls, v: str) -> str:
        """onboarding_level 값 검증."""
        # normal -> medium 매핑
        if v == "normal":
            v = "medium"
        allowed = {"hard", "medium", "easy"}
        if v not in allowed:
            raise ValueError(f"onboarding_level must be one of {allowed}, got {v}")
        return v
    
    @field_validator("dependency_complexity_level")
    @classmethod
    def validate_dependency_level(cls, v: str) -> str:
        """dependency_complexity_level 값 검증."""
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"dependency_complexity_level must be one of {allowed}, got {v}")
        return v
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "repo_id": "facebook/react",
                "documentation_quality": 85,
                "activity_maintainability": 92,
                "health_score": 88,
                "health_level": "excellent",
                "onboarding_score": 78,
                "onboarding_level": "easy",
                "dependency_complexity_score": 45,
                "dependency_complexity_level": "medium",
                "dependency_flags": ["outdated_deps"],
                "docs_issues": ["missing_api_docs"],
                "activity_issues": [],
                "docs_issues_count": 1,
                "activity_issues_count": 0,
                "stars": 225000,
                "forks": 45000,
            }]
        }
    }


def to_summary_dto(repo_id: str, res: Union[DiagnosisCoreResult, dict[str, Any]]) -> DiagnosisSummaryDTO:
 
    summary_for_user: Optional[str] = None
    days_since_last_commit: Optional[int] = None
    total_commits_30d: int = 0
    unique_contributors: int = 0
    readme_sections: Optional[dict[str, bool]] = None
    
    # 새 상세 메트릭 기본값
    issue_close_rate: float = 0.0
    median_pr_merge_days: Optional[float] = None
    median_issue_close_days: Optional[float] = None
    open_issues_count: int = 0
    open_prs_count: int = 0
    
    # 저장소 메타데이터 기본값
    stars: int = 0
    forks: int = 0
    
    if isinstance(res, dict):
        if "scores" in res:
            # 네스트된 구조 (DiagnosisCoreResult.to_dict() 형식)
            scores = res.get("scores", {})
            labels = res.get("labels", {})
            complexity = res.get("complexity", {})
            
            documentation_quality = scores.get("documentation_quality", 0)
            activity_maintainability = scores.get("activity_maintainability", 0)
            health_score = scores.get("health_score", 0)
            onboarding_score = scores.get("onboarding_score", 0)
            health_level = labels.get("health_level", "bad")
            onboarding_level = labels.get("onboarding_level", "hard")
            dependency_complexity_score = complexity.get("dependency_complexity_score", 0)
            dependency_flags = labels.get("dependency_flags", [])
            docs_issues = labels.get("docs_issues", [])
            activity_issues = labels.get("activity_issues", [])
            stars = res.get("stars", 0)
            forks = res.get("forks", 0)
        else:
            # 플랫한 구조 (DiagnosisOutput.to_dict() 형식)
            documentation_quality = res.get("docs", {}).get("total_score", 0)
            activity_maintainability = res.get("activity", {}).get("total_score", 0)
            health_score = int(res.get("health_score", 0))
            onboarding_score = int(res.get("onboarding_score", 0))
            health_level = res.get("health_level", "bad")
            onboarding_level = res.get("onboarding_level", "hard")
            dependency_complexity_score = res.get("dependency_complexity_score", 0)
            dependency_flags = res.get("dependency_flags", [])
            summary_for_user = res.get("summary_for_user")
            stars = res.get("stars", 0)
            forks = res.get("forks", 0)
            
            # 상세 활동성 메트릭 추출
            activity_data = res.get("activity", {})
            days_since_last_commit = activity_data.get("days_since_last_commit")
            total_commits_30d = activity_data.get("total_commits_in_window", 0)
            unique_contributors = activity_data.get("unique_authors", 0)
            
            # 새 상세 메트릭 추출
            issue_close_rate = activity_data.get("issue_close_rate", 0.0)
            median_pr_merge_days = activity_data.get("median_pr_merge_days")
            median_issue_close_days = activity_data.get("median_issue_close_days")
            open_issues_count = activity_data.get("open_issues_count", 0)
            open_prs_count = activity_data.get("open_prs_count", 0)
            
            # README 섹션 추출
            docs_data = res.get("docs", {})
            category_scores = docs_data.get("category_scores", {})
            readme_sections = {}
            for cat in ["WHAT", "WHY", "HOW", "CONTRIBUTING"]:
                cat_info = category_scores.get(cat, {})
                readme_sections[cat] = cat_info.get("present", False) if isinstance(cat_info, dict) else False
            
            # docs_issues는 raw_metrics에 있을 수 있음
            raw_metrics = res.get("raw_metrics", {})
            if "labels" in raw_metrics:
                docs_issues = raw_metrics.get("labels", {}).get("docs_issues", [])
                activity_issues = raw_metrics.get("labels", {}).get("activity_issues", [])
            else:
                docs_issues = []
                activity_issues = []
    else:
        # DiagnosisCoreResult 객체인 경우
        documentation_quality = res.documentation_quality
        activity_maintainability = res.activity_maintainability
        health_score = res.health_score
        onboarding_score = res.onboarding_score
        health_level = res.health_level
        onboarding_level = res.onboarding_level
        dependency_complexity_score = res.dependency_complexity_score
        dependency_flags = res.dependency_flags
        docs_issues = res.docs_issues
        activity_issues = res.activity_issues
        
        if res.activity_result:
            days_since_last_commit = res.activity_result.days_since_last_commit
            total_commits_30d = res.activity_result.total_commits_in_window
            unique_contributors = res.activity_result.unique_authors
            # 새 상세 메트릭 추출
            issue_close_rate = res.activity_result.issue_close_rate
            median_pr_merge_days = res.activity_result.median_pr_merge_days
            median_issue_close_days = res.activity_result.median_issue_close_days
            open_issues_count = res.activity_result.open_issues_count
            open_prs_count = res.activity_result.open_prs_count
        
        if res.docs_result and res.docs_result.category_scores:
            readme_sections = {}
            for cat in ["WHAT", "WHY", "HOW", "CONTRIBUTING"]:
                cat_info = res.docs_result.category_scores.get(cat, {})
                readme_sections[cat] = cat_info.get("present", False) if isinstance(cat_info, dict) else False
    
    # 의존성 복잡도 레벨 계산
    if dependency_complexity_score < 30:
        dep_level = "low"
    elif dependency_complexity_score < 70:
        dep_level = "medium"
    else:
        dep_level = "high"

    # Agentic 메타데이터 추출
    warnings = []
    flow_adjustments = []
    if isinstance(res, dict):
        warnings = res.get("warnings", [])
        flow_adjustments = res.get("flow_adjustments", [])
    
    # 구조 분석 결과 추출
    structure_score = 0
    has_tests = False
    has_ci = False
    has_docs_folder = False
    has_build_config = False
    if isinstance(res, dict):
        structure_data = res.get("structure", {})
        if structure_data:
            structure_score = structure_data.get("structure_score", 0)
            has_tests = structure_data.get("has_tests", False)
            has_ci = structure_data.get("has_ci", False)
            has_docs_folder = structure_data.get("has_docs_folder", False)
            has_build_config = structure_data.get("has_build_config", False)
    
    return DiagnosisSummaryDTO(
        repo_id=repo_id,
        documentation_quality=documentation_quality,
        activity_maintainability=activity_maintainability,
        health_score=health_score,
        health_level=health_level,
        onboarding_score=onboarding_score,
        onboarding_level=onboarding_level,
        dependency_complexity_score=dependency_complexity_score,
        dependency_complexity_level=dep_level,
        dependency_flags=list(dependency_flags),
        docs_issues=list(docs_issues),
        activity_issues=list(activity_issues),
        docs_issues_count=len(docs_issues),
        activity_issues_count=len(activity_issues),
        summary_for_user=summary_for_user,
        days_since_last_commit=days_since_last_commit,
        total_commits_30d=total_commits_30d,
        unique_contributors=unique_contributors,
        issue_close_rate=issue_close_rate,
        median_pr_merge_days=median_pr_merge_days,
        median_issue_close_days=median_issue_close_days,
        open_issues_count=open_issues_count,
        open_prs_count=open_prs_count,
        readme_sections=readme_sections,
        stars=stars,
        forks=forks,
        structure_score=structure_score,
        has_tests=has_tests,
        has_ci=has_ci,
        has_docs_folder=has_docs_folder,
        has_build_config=has_build_config,
        recommended_issues=res.get("recommended_issues") if isinstance(res, dict) else None,
        similar_projects=res.get("similar_projects") if isinstance(res, dict) else None,
        warnings=warnings,
        flow_adjustments=flow_adjustments,
        # 메타 에이전트 결과
        task_plan=res.get("task_plan") if isinstance(res, dict) else None,
        task_results=res.get("task_results") if isinstance(res, dict) else None,
        chat_response=res.get("chat_response") if isinstance(res, dict) else None,
        onboarding_plan=(
            res.get("task_results", {}).get("onboarding", {}).get("onboarding_plan") or
            res.get("onboarding_plan")
        ) if isinstance(res, dict) else None,
    )
