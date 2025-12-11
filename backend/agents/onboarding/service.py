"""Onboarding Agent 서비스 레이어."""
from __future__ import annotations

import logging
import asyncio
from typing import Dict, Any, List

from backend.agents.onboarding.models import OnboardingInput, OnboardingOutput

logger = logging.getLogger(__name__)


def run_onboarding(input_data: OnboardingInput) -> OnboardingOutput:
    """
    온보딩 가이드 생성 (LangGraph 기반).
    
    Args:
        input_data: 온보딩 입력 (저장소 정보, 경험 수준)
    
    Returns:
        OnboardingOutput: 온보딩 가이드 결과
    """
    # 비동기 버전 호출
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_onboarding_async(input_data))
    finally:
        loop.close()


async def run_onboarding_async(input_data: OnboardingInput) -> OnboardingOutput:
    """비동기 버전의 온보딩 가이드 생성 (LangGraph 사용)."""
    from backend.agents.onboarding.graph import run_onboarding_graph
    
    repo_id = f"{input_data.owner}/{input_data.repo}"
    logger.info(f"Starting onboarding for {repo_id}, level={input_data.experience_level}")
    
    try:
        result = await run_onboarding_graph(
            owner=input_data.owner,
            repo=input_data.repo,
            experience_level=input_data.experience_level,
            diagnosis_summary=input_data.diagnosis_summary,
            user_context=input_data.user_context,
        )
        
        return OnboardingOutput(**result)
    
    except Exception as e:
        logger.error(f"Onboarding failed: {e}", exc_info=True)
        return OnboardingOutput(
            repo_id=repo_id,
            experience_level=input_data.experience_level,
            error=f"ONBOARDING_ERROR: {str(e)[:100]}"
        )
