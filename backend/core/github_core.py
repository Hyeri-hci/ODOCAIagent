"""GitHub 데이터 fetch - Core 레이어 (LLM 의존성 없음)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.common.github_client import (
    check_repo_access,
    GITHUB_API_BASE,
    GITHUB_TOKEN,
)
from backend.common.errors import GitHubError, RepoNotFoundError
from backend.common.cache_manager import cached
from .models import RepoSnapshot

import requests
import logging

logger = logging.getLogger(__name__)


def _build_headers() -> dict:
    """GitHub API 헤더 생성."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """ISO 8601 datetime 문자열 파싱."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@cached(ttl=300)
def fetch_repo_snapshot(
    owner: str,
    repo: str,
    ref: str = "HEAD",
) -> RepoSnapshot:
    """GitHub 저장소 스냅샷 조회."""
    access = check_repo_access(owner, repo)
    if not access.accessible:
        if access.status_code == 404:
            raise RepoNotFoundError(owner, repo)
        else:
            raise GitHubError(
                f"Repository not accessible: {owner}/{repo} ({access.reason})",
                owner=owner,
                repo=repo,
                status_code=access.status_code,
            )

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise GitHubError(f"Failed to fetch repo: {e}", owner=owner, repo=repo) from e

    created_at = _parse_datetime(data.get("created_at"))
    pushed_at = _parse_datetime(data.get("pushed_at"))

    readme_content = _fetch_readme_content(owner, repo)
    has_readme = bool(readme_content)

    license_data = data.get("license")
    license_spdx = license_data.get("spdx_id") if license_data else None

    return RepoSnapshot(
        owner=owner,
        repo=repo,
        ref=ref,
        full_name=data.get("full_name", f"{owner}/{repo}"),
        description=data.get("description"),
        stars=data.get("stargazers_count", 0),
        forks=data.get("forks_count", 0),
        open_issues=data.get("open_issues_count", 0),
        primary_language=data.get("language"),
        created_at=created_at,
        pushed_at=pushed_at,
        is_archived=data.get("archived", False),
        is_fork=data.get("fork", False),
        readme_content=readme_content,
        has_readme=has_readme,
        license_spdx=license_spdx,
    )


def _fetch_readme_content(owner: str, repo: str) -> Optional[str]:
    """README 콘텐츠 조회."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    headers = _build_headers()
    headers["Accept"] = "application/vnd.github.v3.raw"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.text
        return None
    except requests.RequestException:
        return None


def verify_repo_access(owner: str, repo: str) -> tuple[bool, str]:
    """저장소 접근 가능 여부 확인."""
    access = check_repo_access(owner, repo)
    return access.accessible, access.reason


@cached(ttl=300)
def fetch_repo_tree(owner: str, repo: str, ref: str = "HEAD") -> list[str]:
    """저장소 파일 트리 조회 (경로 목록 반환)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=15)
        if resp.status_code != 200:
            logger.warning("Failed to fetch tree: %s", resp.status_code)
            return []
        data = resp.json()
        return [item.get("path", "") for item in data.get("tree", [])]
    except Exception as e:
        logger.error("Error fetching repo tree: %s", e)
        return []


def fetch_file_content(owner: str, repo: str, path: str, ref: str = "HEAD") -> Optional[str]:
    """파일 콘텐츠 조회 (Raw)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    headers = _build_headers()
    headers["Accept"] = "application/vnd.github.v3.raw"
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception as e:
        logger.error("Error fetching file content %s: %s", path, e)
        return None
