"""Node for mapping task types."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from ..models import (
    SupervisorState,
    SupervisorTaskType,
    DiagnosisTaskType,
    SecurityTaskType,
    RecommendTaskType,
    diagnosis_needs_from_task_type,
)
from ..intent_config import get_diagnosis_task_type


def map_to_diagnosis_task_type(task_type: SupervisorTaskType) -> DiagnosisTaskType:
    """Maps the global Supervisor task_type to a Diagnosis Agent task_type based on INTENT_CONFIG."""
    return get_diagnosis_task_type(task_type)


def map_to_security_task_type(task_type: SupervisorTaskType) -> SecurityTaskType:
    """
    Maps the global Supervisor task_type to a Security Agent task_type.
    
    Currently returns 'none' for all cases. Update when security features are added.
    """
    return "none"


def map_to_recommend_task_type(task_type: SupervisorTaskType) -> RecommendTaskType:
    """
    Maps the global Supervisor task_type to a Recommend Agent task_type.
    
    Currently returns 'none' for all cases. Update when recommendation features are added.
    """
    return "none"


def map_task_types_node(state: SupervisorState) -> SupervisorState:
    """
    LangGraph Node: Maps task types for each agent.
    
    Reads state.task_type (global) and sets diagnosis_task_type,
    diagnosis_needs, security_task_type, and recommend_task_type.
    """
    # [Crash Fix] If task_type is missing, generate it from intent/sub_intent.
    if "task_type" not in state or not state.get("task_type"):
        intent = state.get("intent", "general_qa")
        sub_intent = state.get("sub_intent", "chat")
        # Lightweight paths like smalltalk/help/overview don't need diagnosis.
        if intent in ("smalltalk", "help", "overview"):
            task_type = "concept_qa_process"  # Use a light path
        else:
            task_type = f"{intent}_{sub_intent}" if sub_intent else intent
        logger.warning("[map_task_types_node] task_type missing, generated: %s", task_type)
    else:
        task_type = state["task_type"]

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    
    diagnosis_task_type = map_to_diagnosis_task_type(task_type)
    new_state["diagnosis_task_type"] = diagnosis_task_type
    new_state["diagnosis_needs"] = diagnosis_needs_from_task_type(diagnosis_task_type)
    new_state["security_task_type"] = map_to_security_task_type(task_type)
    new_state["recommend_task_type"] = map_to_recommend_task_type(task_type)

    logger.info(
        "[map_task_types_node] task_type=%s -> diagnosis=%s, needs=%s",
        task_type,
        new_state.get("diagnosis_task_type"),
        new_state.get("diagnosis_needs"),
    )

    return new_state
