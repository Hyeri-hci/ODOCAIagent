from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Union, Optional
from backend.core.models import DiagnosisCoreResult

@dataclass
class DiagnosisSummaryDTO:
    """프론트엔드 및 CLI에서 공통으로 사용할 진단 결과 요약 DTO."""
    repo_id: str
    documentation_quality: int
    activity_maintainability: int
    health_score: int
    health_level: str
    onboarding_score: int
    onboarding_level: str
    dependency_complexity_score: int
    dependency_complexity_level: str
    dependency_flags: List[str]
    docs_issues: List[str]
    activity_issues: List[str]
    docs_issues_count: int
    activity_issues_count: int
    summary_for_user: Optional[str] = None
    
    # 상세 활동성 메트릭
    days_since_last_commit: Optional[int] = None
    total_commits_30d: int = 0
    unique_contributors: int = 0
    
    # 상세 메트릭 (UX 개선용)
    issue_close_rate: float = 0.0  # 이슈 해결률 (0-1)
    median_pr_merge_days: Optional[float] = None  # PR 병합 중간값 (일)
    median_issue_close_days: Optional[float] = None  # 이슈 해결 중간값 (일)
    open_issues_count: int = 0  # 열린 이슈 수
    open_prs_count: int = 0  # 열린 PR 수
    
    # 문서 상세
    readme_sections: Optional[Dict[str, bool]] = None
    
    # 저장소 메타데이터
    stars: int = 0
    forks: int = 0
    
    # 구조 분석 결과 (내부 처리용 - Frontend 표시 안 함)
    structure_score: int = 0
    has_tests: bool = False
    has_ci: bool = False
    has_docs_folder: bool = False
    has_build_config: bool = False
    
    # 추천 이슈
    recommended_issues: Optional[List[Dict[str, Any]]] = None
    
    # Agentic 플로우 결과
    warnings: List[str] = field(default_factory=list)
    flow_adjustments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def to_summary_dto(repo_id: str, res: Union[DiagnosisCoreResult, Dict[str, Any]]) -> DiagnosisSummaryDTO:
    """DiagnosisCoreResult 또는 dict를 DiagnosisSummaryDTO로 변환합니다."""
    
    summary_for_user = None
    days_since_last_commit = None
    total_commits_30d = 0
    unique_contributors = 0
    readme_sections = None
    
    # 새 상세 메트릭 기본값
    issue_close_rate = 0.0
    median_pr_merge_days = None
    median_issue_close_days = None
    open_issues_count = 0
    open_prs_count = 0
    
    # 저장소 메타데이터 기본값
    stars = 0
    forks = 0
    
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
        warnings=warnings,
        flow_adjustments=flow_adjustments,
    )
