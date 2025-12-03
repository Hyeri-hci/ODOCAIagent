"""Expert Node: Specialized runners for compare/onepager."""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState
from backend.agents.shared.contracts import safe_get
from backend.common.events import EventType, emit_event

logger = logging.getLogger(__name__)


def expert_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs specialized expert runners (compare, onepager)."""
    from backend.agents.supervisor.runners import CompareRunner, OnepagerRunner, DiagnosisRunner
    from backend.agents.supervisor.intent_config import COMPARE_ENABLED, ANSWER_KIND_MAP, DEFAULT_ANSWER_KIND
    from backend.agents.supervisor.nodes.summarize_node import _generate_last_brief
    
    intent = state.get("intent", "analyze")
    sub_intent = state.get("sub_intent", "health")
    repo = state.get("repo")
    user_context = safe_get(state, "user_context", {})
    
    if not repo:
        return {"error_message": "저장소 정보가 없습니다."}
    
    repo_id = f"{safe_get(repo, 'owner', '')}/{safe_get(repo, 'name', '')}"
    
    emit_event(
        EventType.NODE_STARTED,
        actor="expert_node",
        inputs={"intent": intent, "sub_intent": sub_intent, "repo": repo_id},
    )
    
    # Select appropriate runner
    if sub_intent == "compare":
        # Compare guard: check feature toggle
        if not COMPARE_ENABLED:
            return {
                "error_message": "비교 기능은 현재 준비 중입니다. 개별 저장소 분석을 이용해 주세요."
            }
        
        # Compare guard: need second repo
        repo_b = safe_get(state, "compare_repo")
        if not repo_b:
            return {
                "error_message": "비교할 두 번째 저장소를 찾지 못했습니다.\n"
                    "예시: 'facebook/react랑 vuejs/core 비교해줘'"
            }
        
        repo_b_id = f"{safe_get(repo_b, 'owner', '')}/{safe_get(repo_b, 'name', '')}"
        runner = CompareRunner(
            repo_a=repo_id,
            repo_b=repo_b_id,
            user_context=user_context,
        )
    elif sub_intent == "onepager":
        runner = OnepagerRunner(
            repo_id=repo_id,
            user_context=user_context,
        )
    else:
        # Fallback to diagnosis
        runner = DiagnosisRunner(
            repo_id=repo_id,
            user_context=user_context,
        )
    
    result = runner.run()
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="expert_node",
        outputs={
            "status": "success" if result.success else "error",
            "degraded": result.degraded,
            "runner": runner.runner_name,
            "incomplete_compare": result.meta.get("incomplete_compare", False),
        },
    )
    
    if not result.success:
        return {"error_message": result.error_message}
    
    # Expert node returns final response directly (no summarize needed)
    answer = result.answer
    answer_kind = ANSWER_KIND_MAP.get((intent, sub_intent), DEFAULT_ANSWER_KIND)
    
    emit_event(
        EventType.ANSWER_GENERATED,
        actor="expert_node",
        inputs={"answer_kind": answer_kind, "runner": runner.runner_name},
        outputs={
            "text_length": len(answer.text or "") if answer else 0,
            "source_count": len(answer.sources or []) if answer else 0,
            "degraded": result.degraded,
            "incomplete_compare": result.meta.get("incomplete_compare", False),
        },
    )
    
    # Pass runner meta to state for summarize validation
    runner_meta = {
        "status": result.meta.get("status", "ok"),
        "incomplete_compare": result.meta.get("incomplete_compare", False),
        "failed_repos": result.meta.get("failed_repos", []),
        "degrade_reason": result.meta.get("degrade_reason"),
    }
    
    return {
        "llm_summary": answer.text if answer else "",
        "answer_kind": answer_kind,
        "answer_contract": answer.model_dump() if answer else {},
        "last_brief": _generate_last_brief(answer.text if answer else ""),
        "last_answer_kind": answer_kind,
        "_runner_meta": runner_meta,
    }
