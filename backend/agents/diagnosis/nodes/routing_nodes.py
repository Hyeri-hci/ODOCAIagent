"""
Diagnosis Agent Routing Nodes
진단 에이전트의 실행 경로를 결정하는 노드입니다.
"""

import logging
from typing import Literal

from backend.agents.diagnosis.state import DiagnosisGraphState
from backend.agents.diagnosis.router import route_diagnosis_request

logger = logging.getLogger(__name__)

def route_execution_node(state: DiagnosisGraphState) -> Literal["fast_path_node", "full_path_node", "reinterpret_path_node"]:
    """의도와 캐시 상태에 따라 실행 경로(Fast/Full/Reinterpret)를 라우팅합니다."""
    intent = state.get("diagnosis_intent")
    if not intent:
        return "fast_path_node"  # 기본값
    
    cached_result = state.get("cached_result")
    path = route_diagnosis_request(intent, cached_result)
    
    logger.info(f"Routed to: {path}")
    
    if path == "fast_path":
        return "fast_path_node"
    elif path == "full_path":
        return "full_path_node"
    else:
        return "reinterpret_path_node"
