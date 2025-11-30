"""
Task Type 매핑 노드

Supervisor 전역 task_type을 각 Agent별 task_type으로 변환한다.
이 계층을 통해 LLM은 전역 task_type만 추론하면 되고,
Agent별 세부 task_type은 Python 코드에서 통제한다.

## Intent 추가 시
- intent_config.py의 INTENT_CONFIG에 diagnosis_task_type 정의
- 이 파일은 수정 불필요 (자동으로 INTENT_CONFIG 참조)
"""
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
    if "task_type" not in state:
        raise ValueError("map_task_types_node: state['task_type']가 없습니다.")

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
