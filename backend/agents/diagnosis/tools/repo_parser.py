from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.common.github_client import fetch_repo_overview
from .readme.readme_loader import (
    compute_reademe_metrics,
    ReadmeContent,
)

@dataclass
class RepoInfo:
    full_name: str
    description: Optional[str]
    stars: int
    forks: int
    watchers: int
    open_issues: int
    has_readme: bool
    readme_stats: Optional[ReadmeContent] = None

def fetch_repo_info(owner: str, repo: str) -> RepoInfo:
    overview = fetch_repo_overview(owner, repo)

    has_readme = overview.get("has_readme", False)
    readme_stats: Optional[ReadmeContent] = None

    if has_readme and overview.get("readme_content"):
        readme_stats = compute_reademe_metrics(overview["readme_content"])

    return RepoInfo(
        full_name=overview.get("full_name", f"{owner}/{repo}"),
        description=overview.get("description"),
        stars=overview.get("stargazers_count", 0),
        forks=overview.get("forks_count", 0),
        watchers=overview.get("watchers_count", 0),
        open_issues=overview.get("open_issues_count", 0),
        has_readme=has_readme,
        readme_stats=readme_stats,
    )