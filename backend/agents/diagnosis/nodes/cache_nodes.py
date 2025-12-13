"""
Diagnosis Agent Cache Nodes
진단 에이전트의 캐시 확인 및 관리 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.diagnosis.state import DiagnosisGraphState
from backend.agents.diagnosis.router import determine_cache_strategy
from backend.common.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)

async def check_cache_node(state: DiagnosisGraphState) -> Dict[str, Any]:
    """캐시된 분석 결과가 있는지 확인합니다."""
    logger.info("Checking cache")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    cache_manager = get_cache_manager()
    
    strategy = determine_cache_strategy(
        intent=intent,
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main")
    )
    
    cache_key = strategy["cache_key"]
    use_cache = strategy["use_cache"]
    
    cached_result = None
    if use_cache:
        cached_result = cache_manager.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit: {cache_key}")
        else:
            logger.info(f"Cache miss: {cache_key}")
    
    return {
        "cache_key": cache_key,
        "cached_result": cached_result,
        "use_cache": use_cache
    }
