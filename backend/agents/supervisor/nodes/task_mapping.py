"""
Task Type 매핑 노드

Supervisor 전역 task_type을 각 Agent별 task_type으로 변환한다.
이 계층을 통해 LLM은 전역 task_type만 추론하면 되고,
Agent별 세부 task_type은 Python 코드에서 통제한다.
"""
from __future__ import annotations

from ..models import (
    SupervisorState,
    SupervisorTaskType,
    DiagnosisTaskType,
    SecurityTaskType,
    RecommendTaskType,
)


def map_to_diagnosis_task_type(task_type: SupervisorTaskType) -> DiagnosisTaskType:
    """
    Supervisor 전역 task_type -> Diagnosis Agent task_type 매핑
    
    현재는 임시 문자열이며, Diagnosis 모듈에서 Literal로 확정 필요.
    """
    mapping: dict[SupervisorTaskType, DiagnosisTaskType] = {
        "diagnose_repo_health": "health_core",
        "diagnose_repo_onboarding": "health_plus_onboarding",
        "compare_two_repos": "health_plus_onboarding",
        "refine_onboarding_tasks": "reuse_last_onboarding_result",
        "explain_scores": "explain_scores",
    }
    return mapping.get(task_type, "none")


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
    diagnosis_task_type / security_task_type / recommend_task_type을 설정한다.
    """
    if "task_type" not in state:
        raise ValueError("map_task_types_node: state['task_type']가 없습니다.")

    task_type = state["task_type"]

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    new_state["diagnosis_task_type"] = map_to_diagnosis_task_type(task_type)
    new_state["security_task_type"] = map_to_security_task_type(task_type)
    new_state["recommend_task_type"] = map_to_recommend_task_type(task_type)

    return new_state
