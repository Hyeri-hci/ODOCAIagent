"""Task Type 매핑 노드."""
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
    """
    Supervisor 전역 task_type -> Diagnosis Agent task_type 매핑
    
    INTENT_CONFIG 기반으로 매핑합니다.
    """
    return get_diagnosis_task_type(task_type)


def map_to_security_task_type(task_type: SupervisorTaskType) -> SecurityTaskType:
    """
    Supervisor 전역 task_type -> Security Agent task_type 매핑
    
    현재는 모든 경우에 'none'. 보안 기능 추가 시 갱신.
    """
    return "none"


def map_to_recommend_task_type(task_type: SupervisorTaskType) -> RecommendTaskType:
    """
    Supervisor 전역 task_type -> Recommend Agent task_type 매핑
    
    현재는 모든 경우에 'none'. 추천 기능 추가 시 갱신.
    """
    return "none"


def map_task_types_node(state: SupervisorState) -> SupervisorState:
    """
    LangGraph 노드: Agent별 task_type 매핑
    
    state.task_type(Supervisor 전역)을 읽고
    diagnosis_task_type / diagnosis_needs / security_task_type / recommend_task_type을 설정한다.
    """
    # [Crash Fix] task_type이 없으면 intent/sub_intent로 생성
    if "task_type" not in state or not state.get("task_type"):
        intent = state.get("intent", "general_qa")
        sub_intent = state.get("sub_intent", "chat")
        # smalltalk/help/overview 등은 diagnosis 불필요
        if intent in ("smalltalk", "help", "overview"):
            task_type = "concept_qa_process"  # 가벼운 경로로
        else:
            task_type = f"{intent}_{sub_intent}" if sub_intent else intent
        logger.warning("[map_task_types_node] task_type 없음, 생성: %s", task_type)
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
