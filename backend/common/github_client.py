from __future__ import annotations
from typing import Any, Dict, List, Optional
import datetime as dt
import requests

from .config import GITHUB_API_BASE, GITHUB_TOKEN, DEFAULT_ACTIVITY_DAYS

class GitHubClientError(Exception):
    """GitHub API 호출 관련 예외 클래스"""
    pass

def _build_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

def fetch_repo(owner: str, repo: str) -> Dict[str, Any]:
    """repos/{owner}/{repo} 기본 정보 조회"""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=_build_headers(), timeout=10)
    if resp.status_code == 404:
        raise GitHubClientError(f"Repository {owner}/{repo} not found.")
    if resp.status_code != 200:
        raise GitHubClientError(f"Failed to fetch repository: {resp.status_code} {resp.text}")
    return resp.json()

def fetch_readme(owner: str, repo: str) -> Optional[Dict[str, Any]]:
    """
        repos/{owner}/{repo}/readme 정보 조회 (없으면 None 반환)
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    resp = requests.get(url, headers=_build_headers(), timeout=10)
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise GitHubClientError(f"Failed to fetch README: {resp.status_code} {resp.text}")
    return resp.json()

def fetch_recent_commits(
    owner: str,
    repo: str,
    days: int = DEFAULT_ACTIVITY_DAYS,
    per_page: int = 100,
) -> List[Dict[str, Any]]:
    """
        최근 커밋 내역 조회(최대 per_page 개)
    """
    since_dt = dt.datetime.now() - dt.timedelta(days=days)
    since_iso = since_dt.isoformat() + "Z"  

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params = {
        "since": since_iso,
        "per_page": per_page,
        # "page": 1,
    }

    resp = requests.get(url, headers=_build_headers(), params=params, timeout=15)
    if resp.status_code != 200:
        raise GitHubClientError(f"Failed to fetch commits: {resp.status_code} {resp.text}")
    return resp.json()