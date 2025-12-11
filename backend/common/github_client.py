from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import datetime as dt
import requests
import logging

from .config import GITHUB_API_BASE, GITHUB_TOKEN, DEFAULT_ACTIVITY_DAYS
from .cache_manager import cached, github_cache
from .errors import GitHubError, RepoNotFoundError, RepoPrivateError

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass
class RepoAccessResult:
    """Result of repo access check."""
    accessible: bool
    owner: str
    repo: str
    repo_id: str
    status_code: int
    reason: str  # "ok" | "not_found" | "private_no_access" | "rate_limit" | "error"
    default_branch: Optional[str] = None
    
    @property
    def is_private_error(self) -> bool:
        return self.status_code in (403, 404) and self.reason in ("not_found", "private_no_access")


def check_repo_access(owner: str, repo: str) -> RepoAccessResult:
    """Pre-flight check: verify repo exists and is accessible.
    
    This is the FIRST call before any diagnosis/analysis.
    Returns RepoAccessResult with accessibility status.
    """
    repo_id = f"{owner}/{repo}"
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            return RepoAccessResult(
                accessible=True,
                owner=owner,
                repo=repo,
                repo_id=repo_id,
                status_code=200,
                reason="ok",
                default_branch=data.get("default_branch", "main"),
            )
        elif resp.status_code == 404:
            return RepoAccessResult(
                accessible=False,
                owner=owner,
                repo=repo,
                repo_id=repo_id,
                status_code=404,
                reason="not_found",
            )
        elif resp.status_code == 403:
            # Check if rate limit or private repo
            if "rate limit" in resp.text.lower():
                return RepoAccessResult(
                    accessible=False,
                    owner=owner,
                    repo=repo,
                    repo_id=repo_id,
                    status_code=403,
                    reason="rate_limit",
                )
            return RepoAccessResult(
                accessible=False,
                owner=owner,
                repo=repo,
                repo_id=repo_id,
                status_code=403,
                reason="private_no_access",
            )
        else:
            return RepoAccessResult(
                accessible=False,
                owner=owner,
                repo=repo,
                repo_id=repo_id,
                status_code=resp.status_code,
                reason="error",
            )
    except requests.Timeout:
        return RepoAccessResult(
            accessible=False,
            owner=owner,
            repo=repo,
            repo_id=repo_id,
            status_code=0,
            reason="timeout",
        )
    except Exception as e:
        logger.warning(f"check_repo_access failed for {repo_id}: {e}")
        return RepoAccessResult(
            accessible=False,
            owner=owner,
            repo=repo,
            repo_id=repo_id,
            status_code=0,
            reason="error",
        )


def _build_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _github_graphql(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Common helper for making GitHub GraphQL calls."""
    logger.debug("GitHub GraphQL: variables=%s", variables)
    resp = requests.post(
        GITHUB_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=_build_headers(),
        timeout=15,
    )
    if resp.status_code != 200:
        raise GitHubError(
            f"GraphQL request failed: {resp.status_code} {resp.text}"
        )

    data = resp.json()
    if "errors" in data and data["errors"]:
        raise GitHubError(f"GraphQL errors: {data['errors']}")

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
    """Fetches basic repo info from `repos/{owner}/{repo}` (REST API for legacy compatibility)."""
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
    """Fetches README info (REST API for legacy compatibility)."""
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
    """Fetches recent commits (REST API)."""
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
    """Fetches commits, issues, and PRs in a single GraphQL call."""
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
    """Fetches a list of recent issues for N days via GraphQL."""
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
    """Fetches a list of recent PRs for N days via GraphQL."""
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


# Consilience 지원 함수

@cached(ttl=86400)  # 24시간 캐시
def fetch_repo_tree(owner: str, repo: str, sha: str = "HEAD") -> Dict[str, Any]:
    """리포지토리 트리 가져오기 (재귀적)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {"tree": []}
    except requests.Timeout:
        logger.warning("fetch_repo_tree timeout: %s/%s", owner, repo)
        return {"tree": []}
    except requests.RequestException as e:
        logger.warning("fetch_repo_tree failed: %s/%s - %s", owner, repo, e)
        return {"tree": []}


@cached(ttl=86400)  # 24시간 캐시
def fetch_workflow_runs(owner: str, repo: str, workflow_file: str = None) -> Dict[str, Any]:
    """GitHub Actions 워크플로 실행 기록 가져오기."""
    if workflow_file:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/actions/workflows/{workflow_file}/runs?per_page=5"
    else:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/actions/runs?per_page=10"
    
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {"workflow_runs": []}
    except requests.Timeout:
        logger.warning("fetch_workflow_runs timeout: %s/%s", owner, repo)
        return {"workflow_runs": []}
    except requests.RequestException as e:
        logger.warning("fetch_workflow_runs failed: %s/%s - %s", owner, repo, e)
        return {"workflow_runs": []}


@cached(ttl=86400)  # 24시간 캐시
def fetch_workflows(owner: str, repo: str) -> List[Dict[str, Any]]:
    """워크플로 목록 가져오기."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/actions/workflows"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json().get("workflows", [])
        return []
    except requests.Timeout:
        logger.warning("fetch_workflows timeout: %s/%s", owner, repo)
        return []
    except requests.RequestException as e:
        logger.warning("fetch_workflows failed: %s/%s - %s", owner, repo, e)
        return []


@cached(ttl=3600)  # 1시간 캐시
def fetch_repo_contents(owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
    """리포지토리 디렉토리 내용 가져오기."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            return result if isinstance(result, list) else []
        return []
    except requests.Timeout:
        logger.warning("fetch_repo_contents timeout: %s/%s/%s", owner, repo, path)
        return []
    except requests.RequestException as e:
        logger.warning("fetch_repo_contents failed: %s/%s/%s - %s", owner, repo, path, e)
        return []


def clear_repo_cache(owner: str, repo: str) -> None:
    """Invalidates the cache for a specific repository."""
    fetch_repo.invalidate(owner, repo)
    fetch_readme.invalidate(owner, repo)
    fetch_recent_commits.invalidate(owner, repo)
    fetch_recent_issues.invalidate(owner, repo)
    fetch_recent_pull_requests.invalidate(owner, repo)
    fetch_repo_overview.invalidate(owner, repo)
    fetch_activity_summary.invalidate(owner, repo)


def clear_all_cache() -> None:
    """Clears the entire GitHub cache."""
    github_cache.clear()


@cached(ttl=300)
def fetch_beginner_issues(
    owner: str,
    repo: str,
    labels: List[str] = None,
    max_count: int = 10,
) -> List[Dict[str, Any]]:
    """
    초보자 친화적 이슈 수집 (good first issue, help wanted 등).
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        labels: 필터링할 라벨 목록 (기본: 여러 초보자 친화적 라벨)
        max_count: 반환할 최대 이슈 수
        
    Returns:
        이슈 목록 [{number, title, labels, url, created_at}, ...]
    """
    # 다양한 초보자 친화적 라벨 (프로젝트마다 다를 수 있음)
    if labels is None:
        labels = [
            "good first issue",
            "help wanted", 
            "beginner",
            "easy",
            "starter",
            "first-timers-only",
            "good-first-issue",
            "help-wanted",
            "low-hanging-fruit",
            "hacktoberfest",
            "docs",
            "documentation",
        ]
    
    logger.debug(
        "GitHub GraphQL: fetch_beginner_issues %s/%s (labels=%s)",
        owner, repo, labels[:3],  # 로그에는 처음 3개만 표시
    )
    
    # 먼저 라벨 있는 이슈 검색
    result = _fetch_issues_with_labels(owner, repo, labels, max_count)
    
    # 라벨 있는 이슈가 부족하면 최근 열린 이슈 추가
    if len(result) < 3:
        recent_issues = _fetch_recent_open_issues(owner, repo, max_count - len(result))
        # 중복 제거
        existing_numbers = {issue["number"] for issue in result}
        for issue in recent_issues:
            if issue["number"] not in existing_numbers:
                result.append(issue)
                if len(result) >= max_count:
                    break
    
    logger.info("Fetched %d beginner issues for %s/%s", len(result), owner, repo)
    return result[:max_count]


def _fetch_issues_with_labels(
    owner: str,
    repo: str,
    labels: List[str],
    max_count: int = 10,
) -> List[Dict[str, Any]]:
    """라벨이 있는 이슈 검색."""
    query = """
    query($owner: String!, $name: String!, $labels: [String!], $first: Int!) {
      repository(owner: $owner, name: $name) {
        issues(
          first: $first
          states: OPEN
          labels: $labels
          orderBy: { field: CREATED_AT, direction: DESC }
        ) {
          nodes {
            number
            title
            url
            createdAt
            labels(first: 10) {
              nodes {
                name
              }
            }
            author {
              login
            }
          }
        }
      }
    }
    """
    
    variables = {
        "owner": owner,
        "name": repo,
        "labels": labels,
        "first": max_count,
    }
    
    try:
        data = _github_graphql(query, variables)
        repo_data = data.get("repository")
        if not repo_data:
            return []
        
        issues_data = repo_data.get("issues") or {}
        nodes = issues_data.get("nodes") or []
        
        return _format_issues(nodes)
        
    except GitHubClientError as e:
        logger.warning("Failed to fetch labeled issues: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetching labeled issues: %s", e)
        return []


def _fetch_recent_open_issues(
    owner: str,
    repo: str,
    max_count: int = 5,
) -> List[Dict[str, Any]]:
    """최근 열린 이슈 검색 (라벨 무관)."""
    query = """
    query($owner: String!, $name: String!, $first: Int!) {
      repository(owner: $owner, name: $name) {
        issues(
          first: $first
          states: OPEN
          orderBy: { field: CREATED_AT, direction: DESC }
        ) {
          nodes {
            number
            title
            url
            createdAt
            labels(first: 10) {
              nodes {
                name
              }
            }
            author {
              login
            }
          }
        }
      }
    }
    """
    
    variables = {
        "owner": owner,
        "name": repo,
        "first": max_count,
    }
    
    try:
        data = _github_graphql(query, variables)
        repo_data = data.get("repository")
        if not repo_data:
            return []
        
        issues_data = repo_data.get("issues") or {}
        nodes = issues_data.get("nodes") or []
        
        return _format_issues(nodes)
        
    except GitHubClientError as e:
        logger.warning("Failed to fetch recent issues: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetching recent issues: %s", e)
        return []


def _format_issues(nodes: List[Dict]) -> List[Dict[str, Any]]:
    """이슈 노드를 표준 형식으로 변환."""
    result = []
    for node in nodes:
        label_nodes = (node.get("labels") or {}).get("nodes") or []
        label_names = [ln.get("name") for ln in label_nodes if ln.get("name")]
        
        result.append({
            "number": node.get("number"),
            "title": node.get("title"),
            "url": node.get("url"),
            "labels": label_names,
            "created_at": node.get("createdAt"),
            "author": (node.get("author") or {}).get("login"),
        })
    return result


@cached(ttl=300)
def search_repositories(
    query: str,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    GitHub Search API를 사용하여 저장소 검색.
    
    Args:
        query: 검색어 (저장소 이름)
        max_results: 반환할 최대 결과 수
        
    Returns:
        저장소 목록 [{owner, repo, full_name, stars, description, url}, ...]
        인기순(스타 수)으로 정렬됨
    """
    logger.debug("GitHub API: search_repositories query=%s", query)
    
    url = f"{GITHUB_API_BASE}/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": max_results,
    }
    
    try:
        resp = requests.get(url, headers=_build_headers(), params=params, timeout=10)
        
        if resp.status_code != 200:
            logger.warning("search_repositories failed: %s", resp.status_code)
            return []
        
        data = resp.json()
        items = data.get("items", [])
        
        results = []
        for item in items[:max_results]:
            owner_data = item.get("owner") or {}
            results.append({
                "owner": owner_data.get("login", ""),
                "repo": item.get("name", ""),
                "full_name": item.get("full_name", ""),
                "stars": item.get("stargazers_count", 0),
                "description": item.get("description") or "",
                "url": item.get("html_url", ""),
                "language": item.get("language"),
            })
        
        logger.info("Found %d repos for query '%s'", len(results), query)
        return results
        
    except requests.Timeout:
        logger.warning("search_repositories timeout: %s", query)
        return []
    except Exception as e:
        logger.warning("search_repositories failed: %s - %s", query, e)
        return []

