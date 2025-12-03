"""Follow-up evidence mode handler."""
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
    build_lightweight_response,
    call_llm_with_retry,
)

logger = logging.getLogger(__name__)


def handle_followup_evidence_mode(
    state: SupervisorState,
    user_query: str,
    diagnosis_result: Optional[Dict],
) -> Dict[str, Any]:
    """Handles follow-up evidence requests using previous turn artifacts."""
    from ...prompts import (
        build_followup_evidence_prompt,
        FOLLOWUP_NO_ARTIFACTS_TEMPLATE,
        FOLLOWUP_SOURCE_ID,
        get_llm_params,
    )
    
    # 직전 턴 정보 추출
    repo = safe_get(state, "repo")
    owner = safe_get(repo, "owner", "") if repo else ""
    name = safe_get(repo, "name", "") if repo else ""
    repo_id = f"{owner}/{name}" if owner or name else ""
    
    last_answer_kind = safe_get(state, "last_answer_kind", "")
    last_intent = safe_get(state, "intent", "analyze")
    
    # 직전 아티팩트 없음 → 안내 + 선택지
    if not diagnosis_result:
        return build_lightweight_response(
            state,
            FOLLOWUP_NO_ARTIFACTS_TEMPLATE,
            "chat",
            FOLLOWUP_SOURCE_ID,
        )
    
    # 아티팩트 추출
    artifacts: Dict[str, Any] = {}
    if "scores" in diagnosis_result:
        artifacts["scores"] = diagnosis_result["scores"]
    if "labels" in diagnosis_result:
        artifacts["labels"] = diagnosis_result["labels"]
    if "explain_context" in diagnosis_result:
        artifacts["explain_context"] = diagnosis_result["explain_context"]
    
    if not artifacts:
        return build_lightweight_response(
            state,
            FOLLOWUP_NO_ARTIFACTS_TEMPLATE,
            "chat",
            FOLLOWUP_SOURCE_ID,
        )
    
    # LLM 호출로 근거 설명 생성
    system_prompt, user_prompt = build_followup_evidence_prompt(
        user_query=user_query,
        prev_intent=last_intent,
        prev_answer_kind=last_answer_kind or "report",
        repo_id=repo_id,
        artifacts=artifacts,
    )
    
    llm_params = get_llm_params("followup_evidence")
    llm_result = call_llm_with_retry(system_prompt, user_prompt, llm_params, max_retries=1)
    
    # 응답 빌드
    artifact_sources = [
        f"PREV:{repo_id}:{key}" for key in artifacts.keys()
    ]
    
    return _build_followup_response(
        state,
        llm_result.content,
        artifact_sources,
        repo_id,
        diagnosis_result,
    )


def _build_followup_response(
    state: SupervisorState,
    summary: str,
    sources: List[str],
    repo_id: str,
    diagnosis_result: Optional[Dict],
) -> Dict[str, Any]:
    """Builds response for follow-up mode with artifact sources."""
    answer_contract = AnswerContract(
        text=summary,
        sources=sources if sources else [f"PREV:{repo_id}"],
        source_kinds=["prev_turn_artifact"] * len(sources) if sources else ["prev_turn_artifact"],
    )
    
    emit_event(
        event_type=EventType.ANSWER_GENERATED,
        actor="summarize_node",
        inputs={"answer_kind": "explain", "mode": "followup_evidence"},
        outputs={
            "text_length": len(summary),
            "source_count": len(sources),
            "sources": sources[:3],
        },
    )
    
    result: Dict[str, Any] = {
        "llm_summary": answer_contract.text,
        "answer_kind": "explain",
        "answer_contract": answer_contract.model_dump(),
        "last_brief": f"{repo_id} 근거 설명 완료",
        "last_answer_kind": "explain",
    }
    
    # 후속 질문용 Task 리스트 유지
    if diagnosis_result:
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        if onboarding_tasks:
            task_list = []
            for difficulty in ["beginner", "intermediate", "advanced"]:
                for task in onboarding_tasks.get(difficulty, []):
                    task_copy = dict(task)
                    if "difficulty" not in task_copy:
                        task_copy["difficulty"] = difficulty
                    task_list.append(task_copy)
            result["last_task_list"] = task_list
    
    return result
