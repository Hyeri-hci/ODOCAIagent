"""GitHub API를 통한 이슈 조회."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .labels import PRIORITY_LABELS

logger = logging.getLogger(__name__)


def fetch_open_issues_for_tasks(owner: str, repo: str, limit: int = 50) -> List[Dict[str, Any]]:
    """GraphQL로 Open 이슈 목록 조회."""
    from backend.common.github_client import _github_graphql

    query = """
    query($owner: String!, $name: String!, $limit: Int!) {
      repository(owner: $owner, name: $name) {
        issues(first: $limit, states: [OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
            title
            url
            createdAt
            updatedAt
            labels(first: 10) { nodes { name } }
            comments { totalCount }
            assignees(first: 1) { totalCount }
          }
        }
      }
    }
    """

    try:
        data = _github_graphql(query, {"owner": owner, "name": repo, "limit": limit})
        repo_data = data.get("repository")
        if not repo_data:
            logger.warning("Repository not found: %s/%s", owner, repo)
            return []

        issues = repo_data.get("issues", {}).get("nodes", []) or []

        def priority_score(issue: Dict[str, Any]) -> int:
            label_nodes = issue.get("labels", {}).get("nodes", []) or []
            labels_lower = {node.get("name", "").lower() for node in label_nodes}
            for i, pl in enumerate(PRIORITY_LABELS):
                if pl.lower() in labels_lower:
                    return i
            return len(PRIORITY_LABELS)

        return sorted(issues, key=priority_score)

    except (KeyError, TypeError) as e:
        logger.warning("GraphQL response parsing failed: %s", e)
        return _fetch_issues_rest(owner, repo, limit)
    except Exception as e:
        logger.warning("GraphQL fetch failed (%s): %s", type(e).__name__, e)
        return _fetch_issues_rest(owner, repo, limit)


def _fetch_issues_rest(owner: str, repo: str, limit: int = 50) -> List[Dict[str, Any]]:
    """REST API로 Open 이슈 조회 (폴백)."""
    import requests
    from backend.common.github_client import _build_headers, GITHUB_API_BASE

    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
        params = {"state": "open", "per_page": limit, "sort": "updated", "direction": "desc"}
        resp = requests.get(url, headers=_build_headers(), params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning("REST API returned %d for %s/%s", resp.status_code, owner, repo)
            return []
        return [issue for issue in resp.json() if "pull_request" not in issue]
    except requests.exceptions.Timeout:
        logger.warning("REST API timeout for %s/%s", owner, repo)
        return []
    except requests.exceptions.RequestException as e:
        logger.warning("REST API request failed: %s", e)
        return []
    except (ValueError, KeyError) as e:
        logger.warning("REST API response parsing failed: %s", e)
        return []
