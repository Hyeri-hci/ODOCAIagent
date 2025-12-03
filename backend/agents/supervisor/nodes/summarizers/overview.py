"""Overview mode handler."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.shared.contracts import (
    AnswerContract,
    safe_get,
)
from backend.common.events import EventType, emit_event

from ...models import SupervisorState
from .common import (
    build_response,
    call_llm_with_retry,
)

logger = logging.getLogger(__name__)


def handle_overview_mode(state: SupervisorState, repo: Optional[Dict]) -> Dict[str, Any]:
    """Handles overview.repo mode with artifact collection and LLM summary."""
    from ...prompts import (
        build_overview_prompt,
        OVERVIEW_FALLBACK_TEMPLATE,
        get_llm_params,
    )
    from ...service import fetch_overview_artifacts
    
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}"
    
    if not owner or not name:
        return build_response(
            state,
            "저장소 정보가 없습니다. `owner/repo` 형식으로 알려주세요.",
            "chat",
            degraded=True
        )
    
    # Fetch artifacts
    artifacts = fetch_overview_artifacts(owner, name)
    
    # API 제한 시 fallback
    if artifacts.error or not artifacts.repo_facts:
        logger.warning(f"Overview fallback for {repo_id}: {artifacts.error}")
        return build_response(
            state,
            f"저장소 정보를 가져오지 못했습니다: {artifacts.error or '알 수 없는 오류'}",
            "chat",
            degraded=True
        )
    
    # sources >= 2 보장
    if len(artifacts.sources) < 2:
        fallback = OVERVIEW_FALLBACK_TEMPLATE.format(
            owner=owner,
            repo=name,
            description=artifacts.repo_facts.get("description") or "(설명 없음)",
            language=artifacts.repo_facts.get("language") or "(없음)",
            stars=artifacts.repo_facts.get("stars", 0),
            forks=artifacts.repo_facts.get("forks", 0),
        )
        return _build_overview_response(state, fallback, artifacts.sources, repo_id)
    
    # Build prompt and call LLM
    system_prompt, user_prompt = build_overview_prompt(
        owner=owner,
        repo=name,
        repo_facts=artifacts.repo_facts,
        readme_head=artifacts.readme_head,
        recent_activity=artifacts.recent_activity,
    )
    
    llm_params = get_llm_params("overview")
    llm_result = call_llm_with_retry(system_prompt, user_prompt, llm_params, max_retries=1)
    
    if llm_result.degraded:
        fallback = OVERVIEW_FALLBACK_TEMPLATE.format(
            owner=owner,
            repo=name,
            description=artifacts.repo_facts.get("description") or "(설명 없음)",
            language=artifacts.repo_facts.get("language") or "(없음)",
            stars=artifacts.repo_facts.get("stars", 0),
            forks=artifacts.repo_facts.get("forks", 0),
        )
        return _build_overview_response(state, fallback, artifacts.sources, repo_id)
    
    return _build_overview_response(state, llm_result.content, artifacts.sources, repo_id)


def _build_overview_response(
    state: SupervisorState,
    summary: str,
    sources: List[str],
    repo_id: str,
) -> Dict[str, Any]:
    """Builds response for overview mode with artifact sources."""
    answer_contract = AnswerContract(
        text=summary,
        sources=sources if sources else ["ARTIFACT:REPO_FACTS:" + repo_id],
        source_kinds=["github_artifact"] * len(sources) if sources else ["github_artifact"],
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "chat", "mode": "overview"},
        outputs={
            "text_length": len(summary),
            "source_count": len(sources),
            "sources": sources[:3],
        },
    )
    
    return {
        "llm_summary": answer_contract.text,
        "answer_kind": "chat",
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"{repo_id} 개요 완료",
        "last_answer_kind": "chat",
    }
