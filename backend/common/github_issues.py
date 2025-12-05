"""GitHub 이슈 수집 모듈."""
import logging
from typing import List, Dict, Any, Optional

from backend.common.github_client import _github_graphql, GitHubClientError
from backend.common.cache import cached

logger = logging.getLogger(__name__)


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
        labels: 필터링할 라벨 목록 (기본: good first issue, help wanted)
        max_count: 반환할 최대 이슈 수
        
    Returns:
        이슈 목록 [{number, title, labels, url, created_at}, ...]
    """
    if labels is None:
        labels = ["good first issue", "help wanted"]
    
    logger.debug(
        "GitHub GraphQL: fetch_beginner_issues %s/%s (labels=%s)",
        owner, repo, labels,
    )
    
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
            logger.warning("Repository not found: %s/%s", owner, repo)
            return []
        
        issues_data = repo_data.get("issues") or {}
        nodes = issues_data.get("nodes") or []
        
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
        
        logger.info("Fetched %d beginner issues for %s/%s", len(result), owner, repo)
        return result
        
    except GitHubClientError as e:
        logger.warning("Failed to fetch beginner issues: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetching beginner issues: %s", e)
        return []
