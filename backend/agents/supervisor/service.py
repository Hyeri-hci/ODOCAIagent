"""Supervisor Agent Service V1: Graph invocation and helper functions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Dict, List, Optional

from backend.agents.diagnosis.service import run_diagnosis
from backend.common.github_client import (
    fetch_repo_overview,
    fetch_activity_summary,
    GitHubClientError,
)
from .models import SupervisorState, UserContext, RepoInfo


logger = logging.getLogger(__name__)
UserLevel = Literal["beginner", "intermediate", "advanced"]

README_HEAD_MAX_BYTES = 2048  # 1-2KB


@dataclass
class OverviewArtifacts:
    """Artifacts for Overview response."""
    repo_facts: Dict[str, Any] = field(default_factory=dict)
    readme_head: str = ""
    recent_activity: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    error: Optional[str] = None


def fetch_overview_artifacts(owner: str, repo: str) -> OverviewArtifacts:
    """Fetches 3 artifacts for Overview: repo_facts, readme_head, recent_activity."""
    artifacts = OverviewArtifacts()
    repo_id = f"{owner}/{repo}"
    
    # 1. repo_facts (필수)
    try:
        overview = fetch_repo_overview(owner, repo)
        artifacts.repo_facts = {
            "full_name": overview.get("full_name"),
            "description": overview.get("description"),
            "language": overview.get("language"),
            "stars": overview.get("stargazers_count", 0),
            "forks": overview.get("forks_count", 0),
            "open_issues": overview.get("open_issues_count", 0),
            "license": (overview.get("license") or {}).get("spdxId"),
            "created_at": overview.get("created_at"),
            "pushed_at": overview.get("pushed_at"),
            "archived": overview.get("archived", False),
        }
        artifacts.sources.append(f"ARTIFACT:REPO_FACTS:{repo_id}")
        
        # 2. readme_head (선택)
        readme_content = overview.get("readme_content")
        if readme_content:
            artifacts.readme_head = readme_content[:README_HEAD_MAX_BYTES]
            artifacts.sources.append(f"ARTIFACT:README_HEAD:{repo_id}")
            
    except GitHubClientError as e:
        logger.warning(f"Failed to fetch repo overview: {e}")
        artifacts.error = str(e)
        return artifacts
    except Exception as e:
        logger.error(f"Unexpected error fetching repo overview: {e}")
        artifacts.error = str(e)
        return artifacts
    
    # 3. recent_activity (선택)
    try:
        activity = fetch_activity_summary(owner, repo, days=30)
        commits = activity.get("commits", [])
        artifacts.recent_activity = {
            "commit_count_30d": len(commits),
            "last_commit_date": commits[0].get("date") if commits else None,
            "unique_authors_30d": len(set(c.get("author") for c in commits if c.get("author"))),
            "open_issues": activity.get("issues", {}).get("open_count", 0),
            "open_prs": activity.get("prs", {}).get("open_count", 0),
        }
        artifacts.sources.append(f"ARTIFACT:RECENT_ACTIVITY:{repo_id}")
    except Exception as e:
        logger.warning(f"Failed to fetch activity (non-critical): {e}")
        # Non-critical: overview can proceed without activity
    
    return artifacts


def call_diagnosis_agent(
    owner: str,
    repo: str,
    user_level: UserLevel = "beginner",
    advanced_analysis: bool = False,
) -> Dict[str, Any]:
    """Calls the Diagnosis Agent with standard payload."""
    payload = {
        "owner": owner,
        "repo": repo,
        "task_type": "full_diagnosis",
        "focus": ["documentation", "activity"],
        "user_context": {"level": user_level},
        "advanced_analysis": advanced_analysis,
    }
    return run_diagnosis(payload)


def build_initial_state(
    user_query: str,
    owner: str | None = None,
    repo: str | None = None,
    user_context: UserContext | None = None,
) -> SupervisorState:
    """Builds initial SupervisorState for graph invocation."""
    state: SupervisorState = {
        "user_query": user_query,
    }

    if owner and repo:
        state["repo"] = RepoInfo(
            owner=owner,
            name=repo,
            url=f"https://github.com/{owner}/{repo}",
        )

    if user_context:
        state["user_context"] = user_context

    return state


def build_followup_state(
    user_query: str,
    prev_state: SupervisorState,
    user_context: UserContext | None = None,
) -> SupervisorState:
    """Builds state for follow-up turn, preserving previous context."""
    state: SupervisorState = {
        "user_query": user_query,
    }
    
    # Preserve repo from previous turn
    if prev_state.get("repo"):
        state["repo"] = prev_state["repo"]
    
    # Preserve compare_repo if exists
    if prev_state.get("compare_repo"):
        state["compare_repo"] = prev_state["compare_repo"]
    
    # Preserve diagnosis_result for follow-up detection
    if prev_state.get("diagnosis_result"):
        state["diagnosis_result"] = prev_state["diagnosis_result"]
    
    # Preserve session for continuity
    if prev_state.get("_session_id"):
        state["_session_id"] = prev_state["_session_id"]
    
    # Preserve follow-up context (answer_kind → last_answer_kind)
    last_answer = prev_state.get("last_answer_kind") or prev_state.get("answer_kind")
    if last_answer:
        state["last_answer_kind"] = last_answer
    if prev_state.get("last_task_list"):
        state["last_task_list"] = prev_state["last_task_list"]
    if prev_state.get("last_brief"):
        state["last_brief"] = prev_state["last_brief"]
    
    # Preserve history
    if prev_state.get("history"):
        state["history"] = list(prev_state["history"])
    
    if user_context:
        state["user_context"] = user_context
    elif prev_state.get("user_context"):
        state["user_context"] = prev_state["user_context"]
    
    return state