import requests
from .config import GITHUB_TOKEN

BASE_URL = "https://api.github.com"

def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
    }

def get_repo_info(owner: str, repo: str) -> dict:
    url = f"{BASE_URL}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()

def get_commits(owner: str, repo: str, since: str | None = None) -> list[dict]:
    url = f"{BASE_URL}/repos/{owner}/{repo}/commits"
    if since:
        params = {"since": since}
    else:
        params = {}
    resp = requests.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    return resp.json()

def get_contributors(owner: str, repo: str) -> list[dict]:
    url = f"{BASE_URL}/repos/{owner}/{repo}/contributors"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()

def get_languages(owner: str, repo: str) -> dict:
    url = f"{BASE_URL}/repos/{owner}/{repo}/languages"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()

def get_topics(owner: str, repo: str) -> list[str]:
    url = f"{BASE_URL}/repos/{owner}/{repo}/topics"
    headers = _headers()
    headers["Accept"] = "application/vnd.github.mercy-preview+json"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("names", [])

def get_license(owner: str, repo: str) -> dict | None:
    url = f"{BASE_URL}/repos/{owner}/{repo}/license"
    resp = requests.get(url, headers=_headers())
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()

def get_release_cycle(owner: str, repo: str) -> float | None:
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    releases = resp.json()
    if len(releases) < 2:
        return None
    release_dates = [release["published_at"] for release in releases]
    release_dates.sort()
    deltas = []
    for i in range(1, len(release_dates)):
        delta = ( 
            requests.utils.parse_date(release_dates[i]) - 
            requests.utils.parse_date(release_dates[i - 1])
        ).days
        deltas.append(delta)
    average_cycle = sum(deltas) / len(deltas)
    return average_cycle

def get_recent_prs(owner: str, repo: str, since: str) -> list[dict]:
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
    params = {
        "state": "all",
        "sort": "updated",
        "direction": "desc",
        "since": since
    }
    resp = requests.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    return resp.json()

def get_recent_issues(owner: str, repo: str, since: str) -> list[dict]:
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues"
    params = {
        "state": "all",
        "since": since
    }
    resp = requests.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    return resp.json()

def get_recent_releases(owner: str, repo: str, since: str) -> list[dict]:
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    releases = resp.json()
    recent_releases = [
        release for release in releases
        if release["published_at"] >= since
    ]
    return recent_releases
