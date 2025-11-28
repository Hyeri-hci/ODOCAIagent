from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import datetime as dt
import requests
import logging

from .config import GITHUB_API_BASE, GITHUB_TOKEN, DEFAULT_ACTIVITY_DAYS
from .cache import cached, github_cache

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


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


def _github_graphql(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """GitHub GraphQL 호출 공통 헬퍼."""
    logger.debug("GitHub GraphQL: variables=%s", variables)
    resp = requests.post(
        GITHUB_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=_build_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        raise GitHubClientError(
            f"GraphQL request failed: {resp.status_code} {resp.text}"
        )

    data = resp.json()
    if "errors" in data and data["errors"]:
        raise GitHubClientError(f"GraphQL errors: {data['errors']}")

    return data.get("data") or {}


@cached(ttl=300)
def fetch_repo_overview(owner: str, repo: str) -> Dict[str, Any]:
    logger.debug("GitHub GraphQL: fetch_repo_overview %s/%s", owner, repo)
    
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        name
        nameWithOwner
        description
        url
        homepageUrl
        stargazerCount
        forkCount
        watchers { totalCount }
        issues(states: OPEN) { totalCount }
        primaryLanguage { name }
        licenseInfo { name spdxId }
        createdAt
        updatedAt
        pushedAt
        isArchived
        isFork
        object(expression: "HEAD:README.md") {
          ... on Blob {
            text
            byteSize
          }
        }
        readmeUpper: object(expression: "HEAD:README.MD") {
          ... on Blob {
            text
            byteSize
          }
        }
        readmeLower: object(expression: "HEAD:readme.md") {
          ... on Blob {
            text
            byteSize
          }
        }
      }
    }
    """
    
    data = _github_graphql(query, {"owner": owner, "name": repo})
    repo_data = data.get("repository")
    if not repo_data:
        raise GitHubClientError(f"Repository {owner}/{repo} not found.")
    
    readme_blob = (
        repo_data.get("object") 
        or repo_data.get("readmeUpper") 
        or repo_data.get("readmeLower")
    )
    
    return {
        "full_name": repo_data.get("nameWithOwner"),
        "name": repo_data.get("name"),
        "description": repo_data.get("description"),
        "html_url": repo_data.get("url"),
        "homepage": repo_data.get("homepageUrl"),
        "stargazers_count": repo_data.get("stargazerCount", 0),
        "forks_count": repo_data.get("forkCount", 0),
        "watchers_count": (repo_data.get("watchers") or {}).get("totalCount", 0),
        "open_issues_count": (repo_data.get("issues") or {}).get("totalCount", 0),
        "language": (repo_data.get("primaryLanguage") or {}).get("name"),
        "license": repo_data.get("licenseInfo"),
        "created_at": repo_data.get("createdAt"),
        "updated_at": repo_data.get("updatedAt"),
        "pushed_at": repo_data.get("pushedAt"),
        "archived": repo_data.get("isArchived", False),
        "fork": repo_data.get("isFork", False),
        "readme_content": readme_blob.get("text") if readme_blob else None,
        "readme_size": readme_blob.get("byteSize") if readme_blob else None,
        "has_readme": readme_blob is not None,
    }


@cached(ttl=300)
def fetch_repo(owner: str, repo: str) -> Dict[str, Any]:
    """repos/{owner}/{repo} 기본 정보 조회 (REST API, 하위 호환용)"""
    logger.debug("GitHub API: fetch_repo %s/%s", owner, repo)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=_build_headers(), timeout=10)
    if resp.status_code == 404:
        raise GitHubClientError(f"Repository {owner}/{repo} not found.")
    if resp.status_code != 200:
        raise GitHubClientError(f"Failed to fetch repository: {resp.status_code} {resp.text}")
    return resp.json()


@cached(ttl=300)
def fetch_readme(owner: str, repo: str) -> Optional[Dict[str, Any]]:
    """README 정보 조회 (REST API, 하위 호환용)"""
    logger.debug("GitHub API: fetch_readme %s/%s", owner, repo)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    resp = requests.get(url, headers=_build_headers(), timeout=10)
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise GitHubClientError(f"Failed to fetch README: {resp.status_code} {resp.text}")
    return resp.json()


@cached(ttl=180)
def fetch_recent_commits(
    owner: str,
    repo: str,
    days: int = DEFAULT_ACTIVITY_DAYS,
    per_page: int = 100,
) -> List[Dict[str, Any]]:
    """최근 커밋 내역 조회 (REST API)."""
    logger.debug("GitHub API: fetch_recent_commits %s/%s (days=%d)", owner, repo, days)
    since_dt = dt.datetime.now() - dt.timedelta(days=days)
    since_iso = since_dt.isoformat() + "Z"

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params = {
        "since": since_iso,
        "per_page": per_page,
    }

    resp = requests.get(url, headers=_build_headers(), params=params, timeout=15)
    if resp.status_code != 200:
        raise GitHubClientError(f"Failed to fetch commits: {resp.status_code} {resp.text}")
    return resp.json()


@cached(ttl=180)
def fetch_activity_summary(
    owner: str,
    repo: str,
    days: int = DEFAULT_ACTIVITY_DAYS,
    commits_limit: int = 100,
    issues_limit: int = 100,
    prs_limit: int = 100,
) -> Dict[str, Any]:
    """
    GraphQL 한 번 호출로 commits + issues + PRs 조회.
    """
    logger.debug(
        "GitHub GraphQL: fetch_activity_summary %s/%s (days=%d)",
        owner, repo, days,
    )
    
    since_dt = dt.datetime.now() - dt.timedelta(days=days)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    query = """
    query(
      $owner: String!,
      $name: String!,
      $since: GitTimestamp!,
      $issueSince: DateTime!,
      $commitsLimit: Int!,
      $issuesLimit: Int!,
      $prsLimit: Int!
    ) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: $commitsLimit, since: $since) {
                totalCount
                nodes {
                  oid
                  message
                  committedDate
                  author {
                    name
                    email
                    user { login }
                  }
                }
              }
            }
          }
        }
        issues(
          first: $issuesLimit,
          states: [OPEN, CLOSED],
          filterBy: { since: $issueSince },
          orderBy: { field: CREATED_AT, direction: DESC }
        ) {
          totalCount
          nodes {
            number
            state
            createdAt
            closedAt
          }
        }
        pullRequests(
          first: $prsLimit,
          states: [OPEN, CLOSED, MERGED],
          orderBy: { field: CREATED_AT, direction: DESC }
        ) {
          totalCount
          nodes {
            number
            state
            createdAt
            closedAt
            mergedAt
          }
        }
      }
    }
    """
    
    variables = {
        "owner": owner,
        "name": repo,
        "since": since_iso,
        "issueSince": since_iso,
        "commitsLimit": commits_limit,
        "issuesLimit": issues_limit,
        "prsLimit": prs_limit,
    }
    
    data = _github_graphql(query, variables)
    repo_data = data.get("repository")
    if not repo_data:
        return {"commits": [], "issues": [], "pull_requests": []}
    
    commits_data = (
        ((repo_data.get("defaultBranchRef") or {})
         .get("target") or {})
        .get("history") or {}
    )
    
    commits = []
    for node in commits_data.get("nodes") or []:
        author = node.get("author") or {}
        commits.append({
            "sha": node.get("oid"),
            "commit": {
                "message": node.get("message"),
                "author": {
                    "name": author.get("name"),
                    "email": author.get("email"),
                    "date": node.get("committedDate"),
                },
                "committer": {
                    "date": node.get("committedDate"),
                },
            },
            "author": {
                "login": (author.get("user") or {}).get("login"),
            },
        })
    
    issues_data = repo_data.get("issues") or {}
    issues = issues_data.get("nodes") or []
    
    prs_data = repo_data.get("pullRequests") or {}
    all_prs = prs_data.get("nodes") or []
    prs = [
        pr for pr in all_prs
        if pr.get("createdAt") and pr.get("createdAt") >= since_iso
    ]
    
    return {
        "commits": commits,
        "commits_total": commits_data.get("totalCount", 0),
        "issues": issues,
        "issues_total": issues_data.get("totalCount", 0),
        "pull_requests": prs,
        "pull_requests_total": prs_data.get("totalCount", 0),
    }


@cached(ttl=180)
def fetch_recent_issues(
    owner: str,
    repo: str,
    days: int = DEFAULT_ACTIVITY_DAYS,
    per_page: int = 100,
) -> List[Dict[str, Any]]:
    """GitHub GraphQL로 최근 N일 기준 이슈 목록 조회."""
    logger.debug(
        "GitHub GraphQL: fetch_recent_issues %s/%s (days=%d)",
        owner, repo, days,
    )

    since_dt = dt.datetime.now() - dt.timedelta(days=days)
    since_iso = since_dt.isoformat() + "Z"

    query = """
    query($owner: String!, $name: String!, $since: DateTime!, $perPage: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        issues(
          first: $perPage
          states: [OPEN, CLOSED]
          filterBy: { since: $since }
          orderBy: { field: CREATED_AT, direction: DESC }
          after: $cursor
        ) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            number
            state
            createdAt
            closedAt
          }
        }
      }
    }
    """

    all_issues: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        variables = {
            "owner": owner,
            "name": repo,
            "since": since_iso,
            "perPage": per_page,
            "cursor": cursor,
        }
        data = _github_graphql(query, variables)
        repo_data = data.get("repository")
        if not repo_data:
            break

        issues_conn = repo_data.get("issues") or {}
        nodes = issues_conn.get("nodes") or []
        all_issues.extend(nodes)

        page_info = issues_conn.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

        if len(all_issues) >= 2000:
            break

    return all_issues


@cached(ttl=180)
def fetch_recent_pull_requests(
    owner: str,
    repo: str,
    days: int = DEFAULT_ACTIVITY_DAYS,
    per_page: int = 100,
) -> List[Dict[str, Any]]:
    """GitHub GraphQL로 최근 N일 기준 PR 목록 조회."""
    logger.debug(
        "GitHub GraphQL: fetch_recent_pull_requests %s/%s (days=%d)",
        owner, repo, days,
    )

    now = dt.datetime.now()
    since_dt = now - dt.timedelta(days=days)

    query = """
    query($owner: String!, $name: String!, $perPage: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequests(
          first: $perPage
          states: [OPEN, CLOSED, MERGED]
          orderBy: { field: CREATED_AT, direction: DESC }
          after: $cursor
        ) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            number
            state
            createdAt
            closedAt
            mergedAt
          }
        }
      }
    }
    """

    all_prs: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    done = False

    while not done:
        variables = {
            "owner": owner,
            "name": repo,
            "perPage": per_page,
            "cursor": cursor,
        }
        data = _github_graphql(query, variables)
        repo_data = data.get("repository")
        if not repo_data:
            break

        pr_conn = repo_data.get("pullRequests") or {}
        nodes = pr_conn.get("nodes") or []

        for pr in nodes:
            created_str = pr.get("createdAt")
            if not created_str:
                continue
            try:
                created_dt = dt.datetime.strptime(
                    created_str, "%Y-%m-%dT%H:%M:%SZ"
                )
            except ValueError:
                all_prs.append(pr)
                continue

            if created_dt >= since_dt:
                all_prs.append(pr)
            else:
                done = True
                break

        page_info = pr_conn.get("pageInfo") or {}
        if done or not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

        if len(all_prs) >= 2000:
            break

    return all_prs


def clear_repo_cache(owner: str, repo: str) -> None:
    """repo 캐시 무효화."""
    fetch_repo.invalidate(owner, repo)
    fetch_readme.invalidate(owner, repo)
    fetch_recent_commits.invalidate(owner, repo)
    fetch_recent_issues.invalidate(owner, repo)
    fetch_recent_pull_requests.invalidate(owner, repo)
    fetch_repo_overview.invalidate(owner, repo)
    fetch_activity_summary.invalidate(owner, repo)


def clear_all_cache() -> None:
    """GitHub 캐시 전체 삭제."""
    github_cache.clear()