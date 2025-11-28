from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from .chaoss_metrics import (
    CommitActivityMetrics,
    IssueActivityMetrics,
    PullRequestActivityMetrics,
)


@dataclass
class ActivityScoreBreakdown:
    commit_score: float
    issue_score: float
    pr_score: float
    overall: float

    def to_dict(self):
        return asdict(self)


def score_commit_activity(m: CommitActivityMetrics) -> float:
    """Commit 활동 점수 (0~1). 빈도 50% + 최근성 30% + 다양성 20%"""
    if m.total_commits == 0:
        return 0.0

    freq = min(m.commits_per_week / 10.0, 1.0)
    recency = math.exp(-m.days_since_last_commit / 15.0) if m.days_since_last_commit else 0.0
    diversity = min(m.unique_authors / 5.0, 1.0)

    return 0.5 * freq + 0.3 * recency + 0.2 * diversity


def score_issue_activity(m: IssueActivityMetrics) -> float:
    """Issue 활동 점수 (0~1). 해결률 50% + 해결시간 50% (τ=30일)"""
    if m.opened_issues_in_window == 0:
        return 0.5

    closure = min(m.issue_closure_ratio / 0.5, 1.0)
    duration = math.exp(-m.median_time_to_close_days / 30.0) if m.median_time_to_close_days else 0.0

    return 0.5 * closure + 0.5 * duration


def score_pr_activity(m: PullRequestActivityMetrics) -> float:
    """PR 활동 점수 (0~1). 머지율 40% + 머지시간 60% (τ=7일)"""
    if m.prs_in_window == 0:
        return 0.5

    merge_ratio = m.pr_merge_ratio
    duration = math.exp(-m.median_time_to_merge_days / 7.0) if m.median_time_to_merge_days else 0.0
    base = 0.4 * merge_ratio + 0.6 * duration

    # 샘플 5개 미만이면 중립(0.5)으로 보정
    if m.prs_in_window < 5:
        conf = m.prs_in_window / 5.0
        return conf * base + (1 - conf) * 0.5
    return base


def aggregate_activity_score(
    commit: CommitActivityMetrics,
    issue: IssueActivityMetrics,
    pr: PullRequestActivityMetrics,
) -> ActivityScoreBreakdown:
    """종합 Activity 점수. Commit 40% + Issue 30% + PR 30%"""
    c = score_commit_activity(commit)
    i = score_issue_activity(issue)
    p = score_pr_activity(pr)

    return ActivityScoreBreakdown(
        commit_score=round(c, 4),
        issue_score=round(i, 4),
        pr_score=round(p, 4),
        overall=round(0.4 * c + 0.3 * i + 0.3 * p, 4),
    )


def activity_score_to_100(breakdown: ActivityScoreBreakdown) -> int:
    return round(breakdown.overall * 100)
