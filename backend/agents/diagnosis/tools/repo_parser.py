from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.common.github_client import fetch_readme, fetch_repo

@dataclass
class RepoInfo:
    full_name: str
    description: Optional[str]
    stars: int
    forks: int
    watchers: int
    open_issues: int
    has_readme: bool

def fetch_repo_info(owner: str, repo: str) -> RepoInfo:
    repo_data = fetch_repo(owner, repo)
    readme_data = fetch_readme(owner, repo)

    return RepoInfo(
        full_name=repo_data.get("full_name", f"{owner}/{repo}"),
        description=repo_data.get("description"),
        stars=repo_data.get("stargazers_count", 0),
        forks=repo_data.get("forks_count", 0),
        watchers=repo_data.get("watchers_count", 0),
        open_issues=repo_data.get("open_issues_count", 0),
        has_readme=readme_data is not None,
    )