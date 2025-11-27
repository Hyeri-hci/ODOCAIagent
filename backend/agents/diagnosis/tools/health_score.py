from __future__ import annotations

from dataclasses import dataclass

from .chaoss_metrics import CommitActivityMetrics

@dataclass
class HealthScore:
  documentation_quality: int
  activity_maintainability: int
  overall_score: int

def score_commit_activity(metrics: CommitActivityMetrics) -> int:
    """
        커밋 활동 지표 기반 점수 산출
        현재는 임시 버전 (커밋 수 + 마지막 커밋 시점 0~100 점수 매핑)
    """

    score = 0
    
    if metrics.total_commits >= 50:
        score += 60
    elif metrics.total_commits >= 20:
        score += 40
    elif metrics.total_commits >= 5:
        score += 25
    else:
        score += 10
    
    if metrics.days_since_last_commit <= 7:
        score += 40
    elif metrics.days_since_last_commit <= 30:
        score += 25
    elif metrics.days_since_last_commit <= 90:
        score += 10
    else:
        score += 0

    return min(score, 100)

def score_documentation(has_readme: bool) -> int:
    """
        문서화 품질 점수 산출
        현재는 README 존재 여부만으로 80 또는 20 점수 매핑
        추후 README 구조/8카테고리 반영
    """
    return 80 if has_readme else 20

def aggregate_health_scores(
        has_readme: bool,
        commit_metrics: CommitActivityMetrics,
) -> HealthScore:
    doc_score = score_documentation(has_readme)
    activity_score = score_commit_activity(commit_metrics)
    
    overall = int((doc_score + activity_score) / 2)
    
    return HealthScore(
        documentation_quality=doc_score,
        activity_maintainability=activity_score,
        overall_score=overall,
    )