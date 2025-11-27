from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.common.github_client import fetch_readme, fetch_repo
from .readme_loader import fetch_readme_content, compute_reademe_metrics, ReadmeContent

@dataclass
class RepoInfo:
    full_name: str
    description: Optional[str]
    stars: int
    forks: int
    watchers: int
    open_issues: int
    has_readme: bool
    readme_content: Optional[ReadmeContent] = None

def fetch_repo_info(owner: str, repo: str) -> RepoInfo:
    repo_data = fetch_repo(owner, repo)
    readme_data = fetch_readme(owner, repo)

    has_readme = readme_data is not None
    readme_content: Optional[ReadmeContent] = None

    if has_readme:
        readme_text = fetch_readme_content(owner, repo)
        if readme_text:
            readme_content = compute_reademe_metrics(readme_text)

    return RepoInfo(
        full_name=repo_data.get("full_name", f"{owner}/{repo}"),
        description=repo_data.get("description"),
        stars=repo_data.get("stargazers_count", 0),
        forks=repo_data.get("forks_count", 0),
        watchers=repo_data.get("watchers_count", 0),
        open_issues=repo_data.get("open_issues_count", 0),
        has_readme=has_readme,
        readme_content=readme_content,
    )