"""활동성 분석 Core 레이어 - CHAOSS 메트릭 기반 (Pure Python)."""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Dict, List, Any

from backend.common.github_client import (
    fetch_recent_commits,
    fetch_recent_issues,
    fetch_recent_pull_requests,
    fetch_activity_summary,
    DEFAULT_ACTIVITY_DAYS,
)
from .models import ActivityCoreResult, RepoSnapshot

logger = logging.getLogger(__name__)


# 1. Data Structures (CHAOSS Metrics)

@dataclass
class CommitActivityMetrics:
    owner: str
    repo: str
    window_days: int
    total_commits: int
    unique_authors: int
    commits_per_day: float
    commits_per_week: float
    days_since_last_commit: Optional[int]
    first_commit_date: Optional[date]
    last_commit_date: Optional[date]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IssueActivityMetrics:
    owner: str
    repo: str
    window_days: int
    open_issues: int
    opened_issues_in_window: int
    closed_issues_in_window: int
    issue_closure_ratio: float
    median_time_to_close_days: Optional[float]
    avg_open_issue_age_days: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PullRequestActivityMetrics:
    owner: str
    repo: str
    window_days: int
    open_prs: int
    prs_in_window: int
    merged_in_window: int
    pr_merge_ratio: float
    median_time_to_merge_days: Optional[float]
    avg_open_pr_age_days: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActivityScoreBreakdown:
    commit_score: float
    issue_score: float
    pr_score: float
    overall: float

    def to_dict(self):
        return asdict(self)


# 2. Helper Functions

def _parse_iso8601(dt_str: str) -> Optional[datetime]:
    if not isinstance(dt_str, str) or not dt_str:
        return None
    text = dt_str.strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1]).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_commit_date(commit: Dict[str, Any]) -> Optional[date]:
    if not isinstance(commit, dict):
        return None
    commit_block = commit.get("commit") or {}
    author_block = commit_block.get("author") or {}
    committer_block = commit_block.get("committer") or {}
    dt_str = (author_block.get("date") or committer_block.get("date"))
    if not dt_str:
        return None
    dt = _parse_iso8601(dt_str)
    return dt.date() if dt else None


def _extract_author_id(commit: Dict[str, Any]) -> Optional[str]:
    if not isinstance(commit, dict):
        return None
    author = commit.get("author") or {}
    login = author.get("login")
    if isinstance(login, str) and login.strip():
        return f"login:{login.strip()}"
    commit_block = commit.get("commit") or {}
    author_block = commit_block.get("author") or {}
    email = author_block.get("email")
    if isinstance(email, str) and email.strip():
        return f"email:{email.strip().lower()}"
    name = author_block.get("name")
    if isinstance(name, str) and name.strip():
        return f"name:{name.strip()}"
    return None


# 3. Metric Computation Functions

# 3. Metric Computation Functions

def _compute_commit_metrics(
    commits: List[Dict[str, Any]],
    owner: str,
    repo: str,
    days: int
) -> CommitActivityMetrics:
    """Pure function to compute commit metrics from a list of commits."""
    total_commits = len(commits)
    author_ids = set()
    commit_dates: List[date] = []

    for c in commits:
        author_id = _extract_author_id(c)
        if author_id:
            author_ids.add(author_id)
        dt = _parse_commit_date(c)
        if dt is not None:
            commit_dates.append(dt)

    unique_authors = len(author_ids)
    if commit_dates:
        first_commit_date = min(commit_dates)
        last_commit_date = max(commit_dates)
    else:
        first_commit_date = None
        last_commit_date = None

    days_since_last_commit = None
    if last_commit_date is not None:
        today_utc = datetime.now(timezone.utc).date()
        days_since_last_commit = max(0, (today_utc - last_commit_date).days)

    window_days = max(days, 1)
    commits_per_day = float(total_commits) / float(window_days)
    commits_per_week = commits_per_day * 7.0

    return CommitActivityMetrics(
        owner=owner, repo=repo, window_days=window_days,
        total_commits=total_commits, unique_authors=unique_authors,
        commits_per_day=commits_per_day, commits_per_week=commits_per_week,
        days_since_last_commit=days_since_last_commit,
        first_commit_date=first_commit_date, last_commit_date=last_commit_date,
    )


def compute_commit_activity(owner: str, repo: str, days: int = 90) -> CommitActivityMetrics:
    try:
        commits = fetch_recent_commits(owner, repo, days=days) or []
    except Exception:
        commits = []
    return _compute_commit_metrics(commits, owner, repo, days)


def _compute_issue_metrics(
    issues: List[Dict[str, Any]],
    owner: str,
    repo: str,
    days: int
) -> IssueActivityMetrics:
    """Pure function to compute issue metrics from a list of issues."""
    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=days)
    
    open_issues = 0
    opened_in_window = 0
    closed_in_window = 0
    close_times: List[float] = []
    open_ages: List[float] = []

    for issue in issues:
        state = issue.get("state", "").upper()
        created_str = issue.get("createdAt")
        closed_str = issue.get("closedAt")
        created_dt = _parse_iso8601(created_str) if created_str else None
        closed_dt = _parse_iso8601(closed_str) if closed_str else None

        is_created_in_window = created_dt is not None and created_dt >= since_dt
        if is_created_in_window:
            opened_in_window += 1

        if state == "OPEN":
            open_issues += 1
            if created_dt:
                # Ensure non-negative age
                age = max(0.0, (now - created_dt).total_seconds() / 86400.0)
                open_ages.append(age)
        elif state == "CLOSED" and closed_dt:
            if is_created_in_window:
                closed_in_window += 1
            if created_dt:
                # Ensure non-negative duration
                duration = max(0.0, (closed_dt - created_dt).total_seconds() / 86400.0)
                close_times.append(duration)

    issue_closure_ratio = (float(closed_in_window) / float(opened_in_window)) if opened_in_window > 0 else 0.0
    
    median_time_to_close = None
    if close_times:
        sorted_times = sorted(close_times)
        mid = len(sorted_times) // 2
        if len(sorted_times) % 2 == 0:
            median_time_to_close = (sorted_times[mid - 1] + sorted_times[mid]) / 2.0
        else:
            median_time_to_close = sorted_times[mid]

    avg_open_issue_age = sum(open_ages) / len(open_ages) if open_ages else None

    return IssueActivityMetrics(
        owner=owner, repo=repo, window_days=max(days, 1),
        open_issues=open_issues, opened_issues_in_window=opened_in_window,
        closed_issues_in_window=closed_in_window, issue_closure_ratio=issue_closure_ratio,
        median_time_to_close_days=median_time_to_close, avg_open_issue_age_days=avg_open_issue_age,
    )


def compute_issue_activity(owner: str, repo: str, days: int = 90) -> IssueActivityMetrics:
    try:
        issues = fetch_recent_issues(owner, repo, days=days) or []
    except Exception:
        issues = []
    return _compute_issue_metrics(issues, owner, repo, days)


def _compute_pr_metrics(
    prs: List[Dict[str, Any]],
    owner: str,
    repo: str,
    days: int
) -> PullRequestActivityMetrics:
    """Pure function to compute PR metrics from a list of PRs."""
    now = datetime.now(timezone.utc)
    prs_in_window = 0
    merged_in_window = 0
    open_prs = 0
    merge_durations: List[float] = []
    open_ages: List[float] = []

    for pr in prs:
        state = (pr.get("state") or "").upper()
        created_dt = _parse_iso8601(pr.get("createdAt"))
        merged_dt = _parse_iso8601(pr.get("mergedAt"))

        if created_dt:
            prs_in_window += 1

        if state == "OPEN":
            open_prs += 1
            if created_dt:
                age = max(0.0, (now - created_dt).total_seconds() / 86400.0)
                open_ages.append(age)

        if state == "MERGED" and created_dt and merged_dt:
            merged_in_window += 1
            delta_days = (merged_dt - created_dt).total_seconds() / 86400.0
            if delta_days >= 0:
                merge_durations.append(delta_days)

    pr_merge_ratio = (float(merged_in_window) / float(prs_in_window)) if prs_in_window > 0 else 0.0

    median_time_to_merge = None
    if merge_durations:
        sorted_durations = sorted(merge_durations)
        mid = len(sorted_durations) // 2
        if len(sorted_durations) % 2 == 0:
            median_time_to_merge = (sorted_durations[mid - 1] + sorted_durations[mid]) / 2.0
        else:
            median_time_to_merge = sorted_durations[mid]

    avg_open_pr_age = sum(open_ages) / len(open_ages) if open_ages else None

    return PullRequestActivityMetrics(
        owner=owner, repo=repo, window_days=max(days, 1),
        open_prs=open_prs, prs_in_window=prs_in_window,
        merged_in_window=merged_in_window, pr_merge_ratio=pr_merge_ratio,
        median_time_to_merge_days=median_time_to_merge, avg_open_pr_age_days=avg_open_pr_age,
    )


def compute_pr_activity(owner: str, repo: str, days: int = 90) -> PullRequestActivityMetrics:
    try:
        prs = fetch_recent_pull_requests(owner, repo, days=days) or []
    except Exception:
        prs = []
    return _compute_pr_metrics(prs, owner, repo, days)


# 4. Scoring Functions

def score_commit_activity(m: CommitActivityMetrics) -> float:
    if m.total_commits == 0:
        return 0.0
    freq = min(m.commits_per_week / 10.0, 1.0)
    recency = math.exp(-m.days_since_last_commit / 15.0) if m.days_since_last_commit is not None else 0.0
    diversity = min(m.unique_authors / 5.0, 1.0)
    return 0.5 * freq + 0.3 * recency + 0.2 * diversity


def score_issue_activity(m: IssueActivityMetrics) -> float:
    if m.opened_issues_in_window == 0:
        return 0.5
    closure = min(m.issue_closure_ratio / 0.5, 1.0)
    duration = math.exp(-m.median_time_to_close_days / 30.0) if m.median_time_to_close_days is not None else 0.0
    return 0.5 * closure + 0.5 * duration


def score_pr_activity(m: PullRequestActivityMetrics) -> float:
    if m.prs_in_window == 0:
        return 0.5
    merge_ratio = m.pr_merge_ratio
    duration = math.exp(-m.median_time_to_merge_days / 7.0) if m.median_time_to_merge_days is not None else 0.0
    base = 0.4 * merge_ratio + 0.6 * duration
    if m.prs_in_window < 5:
        conf = m.prs_in_window / 5.0
        return conf * base + (1 - conf) * 0.5
    return base


def aggregate_activity_score(
    commit: CommitActivityMetrics,
    issue: IssueActivityMetrics,
    pr: PullRequestActivityMetrics,
) -> ActivityScoreBreakdown:
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


# 5. Main Analysis Function

from typing import Union

def analyze_activity(
    snapshot_or_owner: Union[RepoSnapshot, str],
    repo: Optional[str] = None,
    days: int = DEFAULT_ACTIVITY_DAYS,
) -> ActivityCoreResult:
    """CHAOSS 기반 활동성 분석 (Pure Python)."""
    if hasattr(snapshot_or_owner, "owner") and hasattr(snapshot_or_owner, "repo"):
        owner = snapshot_or_owner.owner
        repo = snapshot_or_owner.repo
    else:
        owner = str(snapshot_or_owner)
        if repo is None:
            raise ValueError("Repo argument is required when passing owner as string")

    commit = compute_commit_activity(owner, repo, days=days)
    issue = compute_issue_activity(owner, repo, days=days)
    pr = compute_pr_activity(owner, repo, days=days)

    breakdown = aggregate_activity_score(commit, issue, pr)
    total_score = activity_score_to_100(breakdown)

    return ActivityCoreResult(
        commit_score=breakdown.commit_score,
        issue_score=breakdown.issue_score,
        pr_score=breakdown.pr_score,
        total_score=total_score,
        days_since_last_commit=commit.days_since_last_commit,
        total_commits_in_window=commit.total_commits,
        unique_authors=commit.unique_authors,
        issue_close_rate=issue.issue_closure_ratio,
        median_pr_merge_days=pr.median_time_to_merge_days,
        median_issue_close_days=issue.median_time_to_close_days,
        open_issues_count=issue.open_issues,
        open_prs_count=pr.open_prs,
    )


def analyze_activity_optimized(
    snapshot_or_owner: Union[RepoSnapshot, str],
    repo: Optional[str] = None,
    days: int = DEFAULT_ACTIVITY_DAYS,
) -> ActivityCoreResult:
    """
    최적화된 활동성 분석 - 단일 GraphQL 호출 사용.
    
    기존 analyze_activity는 3번의 API 호출 (commits, issues, PRs)을 수행하지만,
    이 함수는 fetch_activity_summary를 사용하여 1번의 호출로 처리합니다.
    """
    if hasattr(snapshot_or_owner, "owner") and hasattr(snapshot_or_owner, "repo"):
        owner = snapshot_or_owner.owner
        repo = snapshot_or_owner.repo
    else:
        owner = str(snapshot_or_owner)
        if repo is None:
            raise ValueError("Repo argument is required when passing owner as string")

    try:
        summary = fetch_activity_summary(owner, repo, days=days)
        commits_data = summary.get("commits", [])
        issues_data = summary.get("issues", [])
        prs_data = summary.get("pull_requests", [])
    except Exception as e:
        logger.warning(f"fetch_activity_summary failed, falling back: {e}")
        return analyze_activity(snapshot_or_owner, repo, days)

    commit = _compute_commit_metrics(commits_data, owner, repo, days)
    issue = _compute_issue_metrics(issues_data, owner, repo, days)
    pr = _compute_pr_metrics(prs_data, owner, repo, days)

    breakdown = aggregate_activity_score(commit, issue, pr)
    total_score = activity_score_to_100(breakdown)

    return ActivityCoreResult(
        commit_score=breakdown.commit_score,
        issue_score=breakdown.issue_score,
        pr_score=breakdown.pr_score,
        total_score=total_score,
        days_since_last_commit=commit.days_since_last_commit,
        total_commits_in_window=commit.total_commits,
        unique_authors=commit.unique_authors,
        issue_close_rate=issue.issue_closure_ratio,
        median_pr_merge_days=pr.median_time_to_merge_days,
        median_issue_close_days=issue.median_time_to_close_days,
        open_issues_count=issue.open_issues,
        open_prs_count=pr.open_prs,
    )
