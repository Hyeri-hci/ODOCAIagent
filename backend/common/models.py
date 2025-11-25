from pydantic import BaseModel
from typing import Optional

class RepoMetrics(BaseModel):
    repo_full_name: str               # "owner/repo"
    stars: int
    forks: int
    watchers: int
    open_issues: int
    last_commit_date: Optional[str] = None


class DiagnosisResult(BaseModel):
    repo_full_name: str               # "owner/repo"
    health_score: float                # 0 ~ 100
    activity_level: str               # "low", "medium", "high"
    maintenance_level: str            # "poor", "average", "good"
    issue_responsiveness: str         # "slow", "moderate", "fast"
    recommendations: Optional[str] = None