"""
Diagnosis Agent 태스크 타입 정의
"""
from __future__ import annotations

from enum import Enum


class DiagnosisTaskType(str, Enum):
    """Diagnosis Agent가 처리하는 태스크 유형"""
    FULL = "full_diagnosis"
    DOCS_ONLY = "docs_only"
    ACTIVITY_ONLY = "activity_only"


DEFAULT_TASK_TYPE = DiagnosisTaskType.FULL


def parse_task_type(value: str | None) -> DiagnosisTaskType:
    """문자열 입력을 DiagnosisTaskType으로 변환"""
    if value is None:
        return DEFAULT_TASK_TYPE

    normalized = value.strip().lower()
    for task_type in DiagnosisTaskType:
        if task_type.value == normalized:
            return task_type

    return DEFAULT_TASK_TYPE