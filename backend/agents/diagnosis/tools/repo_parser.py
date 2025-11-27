from backend.common.github_client import get_repo_info
from backend.common.models import RepoMetrics
from backend.common.utils import split_full_name

def build_repo_metrics(full_name: str) -> RepoMetrics:
    owner, repo = split_full_name(full_name)
    repo_data = get_repo_info(owner, repo)

    metrics = RepoMetrics(
        repo_full_name=full_name,
        stars=repo_data.get("stargazers_count", 0),
        forks=repo_data.get("forks_count", 0),
        watchers=repo_data.get("subscribers_count", 0),
        open_issues=repo_data.get("open_issues_count", 0),
        last_commit_date=repo_data.get("pushed_at")
    )
    return metrics