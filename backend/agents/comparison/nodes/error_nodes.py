"""
Comparison Agent Error Nodes
에러 처리를 담당하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.comparison.models import ComparisonState, ComparisonOutput

logger = logging.getLogger(__name__)

async def error_handler_node(state: ComparisonState) -> Dict[str, Any]:
    """에러 발생 시 안전한 결과 반환"""
    logger.warning(f"[Comparison Agent] Error handler triggered: {state.get('error')}")
    
    error_msg = state.get("error", "Unknown error occurred")
    warnings = state.get("warnings", []) + [error_msg]
    
    # 에러 결과 생성
    result = ComparisonOutput(
        results=state.get("batch_results", {}),
        comparison_summary=f"비교 분석 중 오류가 발생했습니다: {error_msg}",
        warnings=warnings,
        cache_hits=state.get("cache_hits", []),
        cache_misses=state.get("cache_misses", []),
    )
    
    return {
        "result": result.dict(),
        "execution_path": (state.get("execution_path") or "") + " → error_handler"
    }
