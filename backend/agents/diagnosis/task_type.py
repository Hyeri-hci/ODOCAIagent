from __future__ import annotations

from enum import Enum

class DiagnosisTaskType(str, Enum):
  FULL = "full_diagnosis"
  DOCS_ONLY = "docs_only"
  ACTIVITY_ONLY = "activity_only"

DEFAULT_TASK_TYPE = DiagnosisTaskType.FULL

def parse_task_type(value: str | None) -> DiagnosisTaskType:
  """문자열 입력을 DiagnosisTaskType 열거형으로 변환"""
  if value is None:
    return DEFAULT_TASK_TYPE
  
  value = value.strip().lower()
  for t in DiagnosisTaskType:
    if t.value == value:
      return t
    
  return DEFAULT_TASK_TYPE