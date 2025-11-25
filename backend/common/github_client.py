import requests
from .config import GITHUB_TOKEN

BASE_URL = "https://api.github.com"

def get_repo_info(owner: str, repo: str) -> dict:
    """Fetch repository information from GitHub."""
    url = f"{BASE_URL}/repos/{owner}/{repo}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()