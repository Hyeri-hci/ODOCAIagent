"""Diagnosis Node: Runs diagnosis using DiagnosisRunner."""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState
from backend.agents.shared.contracts import safe_get
from backend.common.events import EventType, emit_event

logger = logging.getLogger(__name__)


def diagnosis_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs diagnosis using DiagnosisRunner with error policy."""
    from backend.agents.supervisor.runners import DiagnosisRunner
    
    repo = state.get("repo")
    if not repo:
        return {"error_message": "저장소 정보가 없습니다."}
    
    user_context = safe_get(state, "user_context", {})
    current_repo_id = f"{safe_get(repo, 'owner', '')}/{safe_get(repo, 'name', '')}"
    
    # CRITICAL: Check for repo context mismatch (prevent cross-repo contamination)
    existing_diagnosis = state.get("diagnosis_result")
    if existing_diagnosis:
        existing_repo_id = ""
        if isinstance(existing_diagnosis, dict):
            input_data = existing_diagnosis.get("input", {})
            existing_owner = input_data.get("owner", "")
            existing_repo = input_data.get("repo", "")
            existing_repo_id = f"{existing_owner}/{existing_repo}"
        
        if existing_repo_id and existing_repo_id != current_repo_id:
            # Different repo - invalidate old diagnosis_result
            logger.info(
                "[diagnosis_node] Repo context changed: %s → %s, invalidating old result",
                existing_repo_id, current_repo_id
            )
        elif existing_repo_id == current_repo_id:
            # Same repo - skip re-diagnosis (followup case)
            return {}
    
    emit_event(
        EventType.NODE_STARTED,
        actor="diagnosis_node",
        inputs={"repo": current_repo_id},
    )
    
    # Run diagnosis using ExpertRunner
    runner = DiagnosisRunner(
        repo_id=current_repo_id,
        user_context=user_context,
    )
    result = runner.run()
    
    if not result.success:
        emit_event(
            EventType.NODE_FINISHED,
            actor="diagnosis_node",
            outputs={"status": "error", "error": result.error_message},
        )
        return {"error_message": result.error_message or "진단 중 오류가 발생했습니다."}
    
    # Get raw diagnosis result for state
    diagnosis_result = runner.get_diagnosis_result()
    
    emit_event(
        EventType.NODE_FINISHED,
        actor="diagnosis_node",
        outputs={
            "status": "success",
            "degraded": result.degraded,
            "artifact_count": len(result.artifacts_out),
        },
    )
    
    return {
        "diagnosis_result": diagnosis_result,
        "_expert_result": result,  # Store for summarize node if needed
    }
