"""
Diagnosis Agent Execution Nodes
진단 에이전트의 실제 분석 로직(Fast/Full/Reinterpret)을 실행하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.diagnosis.state import DiagnosisGraphState
from backend.agents.diagnosis.fast_path import execute_fast_path
from backend.agents.diagnosis.full_path import execute_full_path
from backend.agents.diagnosis.reinterpret_path import execute_reinterpret_path
from backend.agents.diagnosis.router import determine_cache_strategy
from backend.common.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)

async def fast_path_node(state: DiagnosisGraphState) -> Dict[str, Any]:
    """빠른 분석 경로 실행 (단일 파일 조회 등)"""
    logger.info("Executing fast path")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    target = intent.quick_query_target or "readme"
    result = await execute_fast_path(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main"),
        target=target,
        cached_result=state.get("cached_result")
    )
    
    return {
        "result": result,
        "execution_path": "fast_path"
    }

async def full_path_node(state: DiagnosisGraphState) -> Dict[str, Any]:
    """전체 분석 경로 실행 (심층 분석)"""
    logger.info("Executing full path")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    analysis_depth = intent.analysis_depth or 2
    force_refresh = intent.force_refresh or False
    
    result = await execute_full_path(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main"),
        analysis_depth=analysis_depth,
        use_llm_summary=True,
        force_refresh=force_refresh
    )
    
    cache_key = state.get("cache_key")
    if not result.get("error") and cache_key and intent:
        cache_manager = get_cache_manager()
        strategy = determine_cache_strategy(
            intent=intent,
            owner=state["owner"],
            repo=state["repo"],
            ref=state.get("ref", "main")
        )
        cache_manager.set(
            key=cache_key,
            data=result,
            ttl_hours=strategy["ttl_hours"]
        )
        logger.info(f"Result cached: {cache_key}")
    
    return {
        "result": result,
        "execution_path": "full_path"
    }

async def reinterpret_path_node(state: DiagnosisGraphState) -> Dict[str, Any]:
    """재해석 경로 실행 (기존 결과 다시 설명)"""
    logger.info("Executing reinterpret path")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    cached_result = state.get("cached_result")
    if not cached_result:
        logger.error("Reinterpret path requires cached result")
        return {
            "result": {
                "type": "reinterpret",
                "error": "No cached result available"
            },
            "execution_path": "reinterpret_path",
            "error": "No cached result"
        }
    
    perspective = intent.reinterpret_perspective or "beginner"
    detail_level = intent.reinterpret_detail_level or "standard"
    
    result = await execute_reinterpret_path(
        cached_result=cached_result,
        perspective=perspective,
        detail_level=detail_level,
        user_question=state.get("user_message")
    )
    
    return {
        "result": result,
        "execution_path": "reinterpret_path"
    }
