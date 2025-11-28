from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timezone

from backend.common.github_client import fetch_recent_commits

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
    
def _parse_iso8601(dt_str: str) -> Optional[datetime]:
    if not instance(dt_str, str) or not dt_str:
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
    
    return _parse_iso8601(dt_str)

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
        
        dt= _parse_commit_date(c)
        if dt is not None:
            commit_dates.append(dt.date())

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