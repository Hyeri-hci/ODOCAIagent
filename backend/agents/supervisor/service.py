"""Supervisor Agent Service V1: Graph invocation and helper functions."""
from __future__ import annotations

from typing import Any, Literal, Dict

from backend.agents.diagnosis.service import run_diagnosis
from .models import SupervisorState, UserContext, RepoInfo


UserLevel = Literal["beginner", "intermediate", "advanced"]


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