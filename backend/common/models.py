from pydantic import BaseModel
from typing import Optional, List, Dict

class StaticMetrics(BaseModel):
    stars: int
    forks: int
    watchers: int
    topics: List[str] = []
    license: Optional[str] = None
    main_language: Optional[str] = None
    languages: Dict[str, int] = {}
    release_cycle_days: Optional[float] = None
    contributors_count: Optional[int] = None
    has_ci : bool = False

class DynamicMetrics(BaseModel):
    recent_commits_90d: int
    recent_prs_90d: int
    recent_issues_90d: int
    recent_release_90d: int
    activity_contributors_90d: int
    maintainer_response_time_hrs: Optional[float] = None
    issue_close_time_hrs: Optional[float] = None
    pr_close_time_hrs: Optional[float] = None

class DoCQuailtyMetrics(BaseModel):
    has_readme: bool = False
    has_contributing: bool = False
    has_issue_template: bool = False
    has_pr_template: bool = False
    other_docs: Dict[str, bool] = {}

class ContributorMetrics(BaseModel):
    total_contributors: int
    top1_contrib_ratio: Optional[float] = None
    absence_of_bus_factor: Optional[float] = None

class RepoMetrics(BaseModel):
    full_name: str          # e.g., "owner/repo"
    static: StaticMetrics
    dynamic: DynamicMetrics
    doc_quality: DoCQuailtyMetrics
    contributor: ContributorMetrics

class DiagnosisReport(BaseModel):
    repo: str
    health_score: float         # 0.0 to 1.0
    activity_level: str         # "높음", "보통", "낮음"
    maintenance_level: str      # "높음", "보통", "낮음"
    onbording_difficulty: str   # "쉬움", "보통", "어려움" (문서 및 이슈 기반)
    summary: Optional[str] = None
    metrics: RepoMetrics 