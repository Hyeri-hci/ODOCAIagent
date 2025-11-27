from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
import datetime as dt

from backend.common.github_client import fetch_recent_commits

@dataclass
class CommitActivityMetrics:
    total_commits: int
    days_since_last_commit: int | None
    window_days: int

def compute_commit_activity(owner: str, repo: str, days: int) -> CommitActivityMetrics:
    commits: List[Dict[str, Any]] = fetch_recent_commits(owner, repo, days=days)
    
    total = len(commits)
    if not commits:
        return CommitActivityMetrics(
            total_commits=0,
            days_since_last_commit=None,
            window_days=days,
        )

    # 가장 최근 커밋 날짜 계산
    latest_commit = commits[0]
    latest_ts = latest_commit["commit"]["committer"]["date"]
    latest_dt = dt.datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))

    now = dt.datetime.now().replace(tzinfo=dt.timezone.utc)
    delta_days = (now - latest_dt).days

    return CommitActivityMetrics(
        total_commits=total,
        days_since_last_commit=delta_days,
        window_days=days,
    )
