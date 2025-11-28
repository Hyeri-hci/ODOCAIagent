from __future__ import annotations

from dataclasses import dataclass

from .chaoss_metrics import CommitActivityMetrics
from .readme_loader import ReadmeContent

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
    
    if metrics.days_since_last_commit is None:
        score += 0
    elif metrics.days_since_last_commit <= 7:
        score += 40
    elif metrics.days_since_last_commit <= 30:
        score += 25
    elif metrics.days_since_last_commit <= 90:
        score += 10
    else:
        score += 0

    return min(score, 100)

def score_documentation(
        has_readme: bool,
        stats: ReadmeContent | None = None,
) -> int:
    """
        문서화 품질 점수 산출
        현재는 임시 버전 (README 존재 여부 기반)
    """
    if not has_readme:
        return 20 # README 없음
    
    score = 50 # README 존재 기본 점수

    if stats is None:
        return score
    
    # length 기반 추가 점수
    if stats.length_chars >= 4000:
        score += 20
    elif stats.length_chars >= 1000:
        score += 10
    elif stats.length_chars < 300:
        score -= 10

    # Heading 수 기반 추가 점수 - Section
    if stats.heading_count >= 8:
        score += 10
    elif stats.heading_count >= 3:
        score += 5
    else:
        score -= 5

    # link 수 기반 추가 점수 - References or Resources
    if stats.link_count >= 10:
        score += 5
    elif stats.link_count >= 3:
        score += 3

    # code block 수 기반 추가 점수 - Examples
    if stats.code_block_count >= 3:
        score += 5
    elif stats.code_block_count >= 1:
        score += 3

    score = max(0, min(score, 100))
    return score

def aggregate_health_scores(
        has_readme: bool,
        commit_metrics: CommitActivityMetrics,
        readme_stats: ReadmeContent | None = None,
) -> HealthScore:
    doc_score = score_documentation(has_readme, readme_stats)
    activity_score = score_commit_activity(commit_metrics)
    
    overall = int((doc_score + activity_score) / 2)
    
    return HealthScore(
        documentation_quality=doc_score,
        activity_maintainability=activity_score,
        overall_score=overall,
    )


__all__ = [
    "HealthScore",
    "score_commit_activity",
    "score_documentation",
    "aggregate_health_scores",
]