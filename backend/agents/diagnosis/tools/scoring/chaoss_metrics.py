from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timezone, timedelta

from backend.common.github_client import (
    fetch_recent_commits,
    fetch_recent_issues,
    fetch_recent_pull_requests,
    fetch_activity_summary,
)

@dataclass
class CommitActivityMetrics:
    owner: str
    repo: str
    window_days: int

    # CHAOSS Metrics
    total_commits: int
    unique_authors: int
    commits_per_day: float
    commits_per_week: float
    days_since_last_commit: Optional[int]

    # 추가 메트릭
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
    
    # CHAOSS: Issue Resolution Duration (median) - 닫힌 이슈의 해결 시간 중앙값
    median_time_to_close_days: Optional[float]
    
    # CHAOSS: Issue Age (mean) - 현재 열려있는 이슈의 평균 개방 기간
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
    
    # CHAOSS: Change Requests Duration (median) - 머지된 PR의 머지 시간 중앙값
    median_time_to_merge_days: Optional[float]
    
    # CHAOSS: Change Request Age (mean) - 현재 열린 PR의 평균 개방 기간
    avg_open_pr_age_days: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    
def _parse_iso8601(dt_str: str) -> Optional[datetime]:
    if not isinstance(dt_str, str) or not dt_str:
        return None
    
    text = dt_str.strip()
    try:
        if text.endswith("Z"): # UTC 표기
            return datetime.fromisoformat(text[:-1]).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(text)
    except ValueError:
        return None

def _parse_commit_date(commit: Dict[str, Any]) -> Optional[date]:
    if not isinstance(commit, dict):
        return None
    
    commit_block = commit.get("commit") or {}
    author_block = commit_block.get("author") or {}
    comitter_block = commit_block.get("committer") or {}

    # 우선순위: author.date -> committer.date
    dt_str = (author_block.get("date") or comitter_block.get("date"))

    if not dt_str:
        return None
    
    dt = _parse_iso8601(dt_str)
    return dt.date() if dt else None

def _extract_author_id(commit: Dict[str, Any]) -> Optional[str]:
    if not isinstance(commit, dict):
        return None
    
    # GitHub Login Name
    author = commit.get("author") or {}
    login = author.get("login")
    if isinstance(login, str) and login.strip():
        return f"login:{login.strip()}"
    
    commit_block = commit.get("commit") or {}
    author_block = commit_block.get("author") or {}

    # email
    email = author_block.get("email")
    if isinstance(email, str) and email.strip():
        return f"email:{email.strip().lower()}"
    
    # name
    name = author_block.get("name")
    if isinstance(name, str) and name.strip():
        return f"name:{name.strip()}"
    
    return None

def compute_commit_activity(
        owner: str,
        repo: str,
        days: int = 90,
    ) -> CommitActivityMetrics:

    try:
        commits: List[Dict[str, Any]] = fetch_recent_commits(owner, repo, days=days) or []
    except Exception:
        return CommitActivityMetrics(
            owner=owner,
            repo=repo,
            window_days=max(days, 1),
            total_commits=0,
            unique_authors=0,
            commits_per_day=0.0,
            commits_per_week=0.0,
            days_since_last_commit=None,
            first_commit_date=None,
            last_commit_date=None,
        )
    
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

    # Today(UTC) 기준 마지막 커밋 이후 일수 계산
    if last_commit_date is not None:
        today_utc = datetime.now(timezone.utc).date()
        days_since_last_commit: Optional[int] = (today_utc - last_commit_date).days
        if days_since_last_commit < 0:
            days_since_last_commit = 0
    else:
        days_since_last_commit = None

    window_days = max(days, 1) # 최소 1일
    commits_per_day = float(total_commits) / float(window_days)
    commits_per_week = commits_per_day * 7.0

    return CommitActivityMetrics(
        owner=owner,
        repo=repo,
        window_days=window_days,
        total_commits=total_commits,
        unique_authors=unique_authors,
        commits_per_day=commits_per_day,
        commits_per_week=commits_per_week,
        days_since_last_commit=days_since_last_commit,
        first_commit_date=first_commit_date,
        last_commit_date=last_commit_date,
    )

def compute_issue_activity(
        owner: str,
        repo: str,
        days: int = 90,
    ) -> IssueActivityMetrics:
    try:
        issues: List[Dict[str, Any]] = fetch_recent_issues(owner, repo, days=days) or []
    except Exception:
        return IssueActivityMetrics(
            owner=owner,
            repo=repo,
            window_days=max(days, 1),
            open_issues=0,
            opened_issues_in_window=0,
            closed_issues_in_window=0,
            issue_closure_ratio=0.0,
            median_time_to_close_days=None,
            avg_open_issue_age_days=None,
        )

    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=days)  # 윈도우 시작 시점
    
    open_issues = 0           # 업데이트된 이슈 중 현재 OPEN 상태
    opened_in_window = 0      # 윈도우 내 새로 생성된 이슈 (CHAOSS 정의)
    closed_in_window = 0      # 윈도우 내 생성되어 닫힌 이슈
    close_times: List[float] = []   # Issue Resolution Duration 계산용
    open_ages: List[float] = []     # Issue Age 계산용

    for issue in issues:
        state = issue.get("state", "").upper()
        created_str = issue.get("createdAt")
        closed_str = issue.get("closedAt")

        created_dt = _parse_iso8601(created_str) if created_str else None
        closed_dt = _parse_iso8601(closed_str) if closed_str else None

        # CHAOSS 정의: 윈도우 내 '새로 생성된' 이슈만 카운트
        is_created_in_window = created_dt is not None and created_dt >= since_dt
        
        if is_created_in_window:
            opened_in_window += 1

        if state == "OPEN":
            open_issues += 1
            # Issue Age: 현재 열린 이슈의 개방 기간 (모든 OPEN 이슈 대상)
            if created_dt:
                age_days = (now - created_dt).total_seconds() / 86400.0
                open_ages.append(age_days)
        elif state == "CLOSED" and closed_dt:
            # 윈도우 내 생성되어 닫힌 이슈만 카운트
            if is_created_in_window:
                closed_in_window += 1
            # Issue Resolution Duration: 닫힌 이슈의 해결 시간 (모든 CLOSED 이슈 대상)
            if created_dt:
                close_time_days = (closed_dt - created_dt).total_seconds() / 86400.0
                close_times.append(close_time_days)

    # Issue closure ratio
    issue_closure_ratio = (
        float(closed_in_window) / float(opened_in_window)
        if opened_in_window > 0 else 0.0
    )

    # Median time to close
    median_time_to_close: Optional[float] = None
    if close_times:
        sorted_times = sorted(close_times)
        mid = len(sorted_times) // 2
        if len(sorted_times) % 2 == 0:
            median_time_to_close = (sorted_times[mid - 1] + sorted_times[mid]) / 2.0
        else:
            median_time_to_close = sorted_times[mid]

    # Average open issue age
    avg_open_issue_age: Optional[float] = None
    if open_ages:
        avg_open_issue_age = sum(open_ages) / len(open_ages)

    return IssueActivityMetrics(
        owner=owner,
        repo=repo,
        window_days=max(days, 1),
        open_issues=open_issues,
        opened_issues_in_window=opened_in_window,
        closed_issues_in_window=closed_in_window,
        issue_closure_ratio=issue_closure_ratio,
        median_time_to_close_days=median_time_to_close,
        avg_open_issue_age_days=avg_open_issue_age,
    )


def compute_pr_activity(
        owner: str,
        repo: str,
        days: int = 90,
    ) -> PullRequestActivityMetrics:
    try:
        prs: List[Dict[str, Any]] = fetch_recent_pull_requests(owner, repo, days=days) or []
    except Exception:
        return PullRequestActivityMetrics(
            owner=owner,
            repo=repo,
            window_days=max(days, 1),
            open_prs=0,
            prs_in_window=0,
            merged_in_window=0,
            pr_merge_ratio=0.0,
            median_time_to_merge_days=None,
            avg_open_pr_age_days=None,
        )

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
                age_days = (now - created_dt).total_seconds() / 86400.0
                open_ages.append(age_days)

        # Change Requests Duration: merged PR만 대상
        if state == "MERGED" and created_dt and merged_dt:
            merged_in_window += 1
            delta_days = (merged_dt - created_dt).total_seconds() / 86400.0
            if delta_days >= 0:
                merge_durations.append(delta_days)

    pr_merge_ratio = (
        float(merged_in_window) / float(prs_in_window)
        if prs_in_window > 0 else 0.0
    )

    # Median time to merge
    median_time_to_merge: Optional[float] = None
    if merge_durations:
        sorted_durations = sorted(merge_durations)
        mid = len(sorted_durations) // 2
        if len(sorted_durations) % 2 == 0:
            median_time_to_merge = (sorted_durations[mid - 1] + sorted_durations[mid]) / 2.0
        else:
            median_time_to_merge = sorted_durations[mid]

    # Average open PR age
    avg_open_pr_age: Optional[float] = None
    if open_ages:
        avg_open_pr_age = sum(open_ages) / len(open_ages)

    return PullRequestActivityMetrics(
        owner=owner,
        repo=repo,
        window_days=max(days, 1),
        open_prs=open_prs,
        prs_in_window=prs_in_window,
        merged_in_window=merged_in_window,
        pr_merge_ratio=pr_merge_ratio,
        median_time_to_merge_days=median_time_to_merge,
        avg_open_pr_age_days=avg_open_pr_age,
    )