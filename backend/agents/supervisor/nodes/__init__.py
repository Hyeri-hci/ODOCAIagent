"""
Supervisor 노드 모듈

LangGraph 워크플로우에서 사용하는 노드 함수들을 제공한다.

## 노드 구성
- **Intent Classification**: 사용자 의도 분류
- **Task Mapping**: 의도 → Agent Task 매핑
- **Diagnosis**: 진단 실행
- **Summarize**: 응답 생성 및 설명
"""
from .intent_classifier import classify_intent_node
from .task_mapping import (
    map_task_types_node,
    map_to_diagnosis_task_type,
    map_to_security_task_type,
    map_to_recommend_task_type,
)
from .run_diagnosis import run_diagnosis_node
from .summarize_node import (
    summarize_node,
    # Explain 관련 내부 함수 (테스트용 export)
    _ensure_metrics_exist,
    _extract_target_metrics,
    _format_diagnosis_for_explain,
    _format_diagnosis_for_explain_multi,
    _postprocess_explain_response,
    METRIC_NOT_FOUND_MESSAGE,
    METRIC_NAME_KR,
    METRIC_ALIAS_MAP,
    AVAILABLE_METRICS,
)
from .refine_tasks import refine_tasks_node


__all__ = [
    # Core Nodes
    "classify_intent_node",
    "map_task_types_node",
    "run_diagnosis_node",
    "summarize_node",
    "refine_tasks_node",
    # Task Mapping Helpers
    "map_to_diagnosis_task_type",
    "map_to_security_task_type",
    "map_to_recommend_task_type",
    # Explain Utilities (for testing)
    "_ensure_metrics_exist",
    "_extract_target_metrics",
    "_format_diagnosis_for_explain",
    "_format_diagnosis_for_explain_multi",
    "_postprocess_explain_response",
    "METRIC_NOT_FOUND_MESSAGE",
    "METRIC_NAME_KR",
    "METRIC_ALIAS_MAP",
    "AVAILABLE_METRICS",
]
