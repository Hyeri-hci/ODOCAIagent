"""
Diagnosis Agent Intent Nodes
진단 에이전트의 의도를 파악하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.diagnosis.state import DiagnosisGraphState
from backend.agents.diagnosis.intent_parser import DiagnosisIntentParser

logger = logging.getLogger(__name__)

async def parse_diagnosis_intent_node(state: DiagnosisGraphState) -> Dict[str, Any]:
    """사용자 메시지와 Supervisor 의도를 기반으로 진단 의도를 파싱합니다."""
    logger.info("Parsing diagnosis intent")
    
    parser = DiagnosisIntentParser()
    
    user_msg = state.get("user_message") or ""
    supervisor_int = state.get("supervisor_intent") or {}
    
    intent = await parser.parse(
        user_message=user_msg,
        supervisor_intent=supervisor_int,
        cached_diagnosis=state.get("cached_result")
    )
    
    return {
        "diagnosis_intent": intent
    }
