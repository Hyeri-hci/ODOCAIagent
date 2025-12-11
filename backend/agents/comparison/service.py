"""Comparison Agent 서비스 레이어."""
from __future__ import annotations

import logging
import asyncio
from typing import List

from backend.agents.comparison.models import ComparisonInput, ComparisonOutput

logger = logging.getLogger(__name__)


def run_comparison(input_data: ComparisonInput) -> ComparisonOutput:
    """
    다중 저장소 비교 분석 실행 (LangGraph 기반).
    
    Args:
        input_data: 비교 분석 입력 (저장소 목록)
    
    Returns:
        ComparisonOutput: 비교 분석 결과
    """
    # 비동기 버전 호출
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_comparison_async(input_data))
    finally:
        loop.close()


async def run_comparison_async(input_data: ComparisonInput) -> ComparisonOutput:
    """비동기 버전의 비교 분석 (LangGraph 사용)."""
    from backend.agents.comparison.graph import run_comparison_graph
    
    logger.info(f"Starting comparison for {len(input_data.repos)} repositories")
    
    try:
        result = await run_comparison_graph(
            repos=input_data.repos,
            ref=input_data.ref,
            use_cache=input_data.use_cache,
        )
        
        return ComparisonOutput(**result)
    
    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        return ComparisonOutput(
            warnings=[f"비교 분석 중 오류가 발생했습니다: {str(e)[:100]}"]
        )
