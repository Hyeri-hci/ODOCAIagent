from __future__ import annotations
import math
from typing import Optional
from dataclasses import dataclass, asdict
from .chaoss_metrics import (
    CommitActivityMetrics,
    IssueActivityMetrics,
    PullRequestActivityMetrics,
)


@dataclass
class ActivityScoreBreakdown:
    """Activity 점수 세부 내역."""
    commit_score: float
    issue_score: float
    pr_score: float
    overall: float

    def to_dict(self):
        return asdict(self)


# === Commit Activity Scoring ===

def score_commit_activity(m: CommitActivityMetrics) -> float:
    """
    Commit 활동 점수 (0.0 ~ 1.0).
    
    기준:
    - commits_per_week: 주당 커밋 수 (10 이상이면 만점)
    - days_since_last_commit: 최근 커밋 이후 경과일 (0일이면 만점, 30일 이상이면 0점)
    - unique_authors: 기여자 다양성 (5명 이상이면 만점)
    """
    if m.total_commits == 0:
        return 0.0

    # 1. 커밋 빈도 점수 (주당 10 커밋 기준)
    freq_score = min(m.commits_per_week / 10.0, 1.0)

    # 2. 최근성 점수 (30일 기준 감쇠)
    if m.days_since_last_commit is None:
        recency_score = 0.0
    else:
        # exp 감쇠: τ=15일 기준
        recency_score = math.exp(-m.days_since_last_commit / 15.0)

    # 3. 기여자 다양성 점수 (5명 기준)
    diversity_score = min(m.unique_authors / 5.0, 1.0)

    # 가중 평균: 빈도 50%, 최근성 30%, 다양성 20%
    return 0.5 * freq_score + 0.3 * recency_score + 0.2 * diversity_score


# === Issue Activity Scoring ===

def score_issue_activity(m: IssueActivityMetrics) -> float:
    """
    Issue 활동 점수 (0.0 ~ 1.0).
    
    기준:
    - issue_closure_ratio: 이슈 해결률 (높을수록 좋음)
    - median_time_to_close_days: 해결 시간 중앙값 (짧을수록 좋음, τ=14일)
    - 이슈가 없으면 중립 점수 0.5 반환
    """
    # 이슈가 없는 경우 중립 점수
    if m.opened_issues_in_window == 0:
        return 0.5

    # 1. 이슈 해결률 점수
    closure_score = m.issue_closure_ratio

    # 2. 해결 시간 점수 (τ=14일 기준 exp 감쇠)
    if m.median_time_to_close_days is not None:
        # 빠를수록 좋음
        duration_score = math.exp(-m.median_time_to_close_days / 14.0)
    else:
        # 닫힌 이슈가 없으면 0점
        duration_score = 0.0

    # 가중 평균: 해결률 60%, 해결 시간 40%
    return 0.6 * closure_score + 0.4 * duration_score


# === PR Activity Scoring ===

def score_pr_activity(m: PullRequestActivityMetrics) -> float:
    """
    PR 활동 점수 (0.0 ~ 1.0).
    
    기준:
    - pr_merge_ratio: PR 머지율 (높을수록 좋음)
    - median_time_to_merge_days: 머지 시간 중앙값 (짧을수록 좋음, τ=7일)
    - PR이 없으면 중립 점수 0.5 반환
    """
    # PR이 없는 경우 중립 점수
    if m.prs_in_window == 0:
        return 0.5

    # 1. PR 머지율 점수
    merge_ratio_score = m.pr_merge_ratio

    # 2. 머지 시간 점수 (τ=7일 기준 exp 감쇠)
    if m.median_time_to_merge_days is not None:
        duration_score = math.exp(-m.median_time_to_merge_days / 7.0)
    else:
        # 머지된 PR이 없으면 0점
        duration_score = 0.0

    # 가중 평균: 머지율 40%, 머지 시간 60%
    return 0.4 * merge_ratio_score + 0.6 * duration_score


# === Aggregate Activity Score ===

def aggregate_activity_score(
    commit: CommitActivityMetrics,
    issue: IssueActivityMetrics,
    pr: PullRequestActivityMetrics,
) -> ActivityScoreBreakdown:
    """
    CHAOSS 기반 종합 Activity 점수 계산.
    
    가중치:
    - Commit: 40% (코드 기여 활동)
    - Issue: 30% (이슈 관리 효율)
    - PR: 30% (코드 리뷰 효율)
    
    Returns:
        ActivityScoreBreakdown: 개별 점수 + 종합 점수 (0.0 ~ 1.0)
    """
    commit_score = score_commit_activity(commit)
    issue_score = score_issue_activity(issue)
    pr_score = score_pr_activity(pr)

    overall = 0.4 * commit_score + 0.3 * issue_score + 0.3 * pr_score

    return ActivityScoreBreakdown(
        commit_score=round(commit_score, 4),
        issue_score=round(issue_score, 4),
        pr_score=round(pr_score, 4),
        overall=round(overall, 4),
    )


def activity_score_to_100(breakdown: ActivityScoreBreakdown) -> int:
    """0-1 스케일을 0-100 스케일로 변환."""
    return round(breakdown.overall * 100)
