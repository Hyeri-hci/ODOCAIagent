"""Onboarding Agent 노드 함수."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def fetch_issues(
    owner: str,
    repo: str,
    experience_level: str = "beginner",
    max_count: int = 10,
) -> List[Dict[str, Any]]:
    """
    GitHub에서 경험 수준에 맞는 이슈 수집 (비동기).
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        experience_level: 경험 수준 (beginner/intermediate/advanced)
        max_count: 최대 수집 개수
    
    Returns:
        이슈 목록
    """
    import asyncio
    from backend.common.github_client import fetch_beginner_issues
    
    label_map = {
        "beginner": ["good first issue", "help wanted", "beginner", "easy", "starter", "first-timers-only", "docs"],
        "intermediate": ["help wanted", "enhancement", "bug", "feature", "improvement"],
        "advanced": ["core", "architecture", "performance", "security", "critical", "priority"],
    }
    labels = label_map.get(experience_level, label_map["beginner"])
    
    logger.info(f"Fetching issues for {owner}/{repo}, level={experience_level}")
    
    try:
        # 동기 GitHub 호출을 비동기로 실행
        loop = asyncio.get_event_loop()
        issues = await loop.run_in_executor(
            None,
            lambda: fetch_beginner_issues(
                owner=owner,
                repo=repo,
                labels=labels,
                max_count=max_count,
            )
        )
        logger.info(f"Fetched {len(issues)} issues")
        return issues
    except Exception as e:
        logger.warning(f"Failed to fetch issues: {e}")
        return []


async def generate_plan(
    repo_id: str,
    diagnosis_summary: str = "",
    user_context: Dict[str, Any] = None,
    candidate_issues: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    LLM을 사용하여 주차별 온보딩 플랜 생성 (비동기).
    
    Returns:
        {"plan": [...], "error": None} 또는 {"plan": None, "error": "..."}
    """
    import asyncio
    from backend.llm.kanana_wrapper import KananaWrapper
    
    kanana = KananaWrapper()
    
    try:
        # 동기 LLM 호출을 비동기로 실행
        loop = asyncio.get_event_loop()
        plan = await loop.run_in_executor(
            None,
            lambda: kanana.generate_onboarding_plan(
                repo_id=repo_id,
                diagnosis_summary=diagnosis_summary,
                user_context=user_context or {},
                candidate_issues=candidate_issues or [],
            )
        )
        logger.info(f"Onboarding plan generated: {len(plan)} weeks")
        return {"plan": plan, "error": None}
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"LLM JSON parse failed: {error_msg}")
        return {"plan": None, "error": f"LLM_JSON_PARSE_ERROR: {error_msg[:100]}"}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Plan generation failed: {error_msg}")
        return {"plan": None, "error": f"ONBOARDING_PLAN_ERROR: {error_msg[:100]}"}


async def summarize_plan(
    repo_id: str, 
    plan: List[Dict[str, Any]], 
    summary_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    LLM을 사용하여 온보딩 플랜을 자연어로 요약 (비동기).
    
    Args:
        repo_id: 저장소 식별자
        plan: 주차별 플랜 목록
        summary_context: 에이전트 분석 결과 (health_level, onboarding_level, risks 등)
    """
    import asyncio
    from backend.llm.kanana_wrapper import KananaWrapper
    
    if not plan:
        return "온보딩 플랜이 생성되지 않았습니다."
    
    kanana = KananaWrapper()
    
    try:
        # 동기 LLM 호출을 비동기로 실행
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None,
            lambda: kanana.summarize_onboarding_plan(
                repo_id=repo_id,
                plan=plan,
            )
        )
        
        # 에이전트 분석 결과가 있으면 리스크 정보 추가
        if summary_context:
            risks = summary_context.get("risks", [])
            onboarding_level = summary_context.get("onboarding_level", "unknown")
            health_level = summary_context.get("health_level", "unknown")
            
            if risks:
                risk_section = "\n\n⚠️ **주의사항**:\n"
                for risk in risks[:3]:  # 최대 3개만 표시
                    risk_section += f"- {risk.get('message', '')}\n"
                summary += risk_section
            
            # 난이도 표시 추가
            level_emoji = {"easy": "🟢", "normal": "🟡", "hard": "🔴"}.get(onboarding_level, "⚪")
            summary = f"{level_emoji} **온보딩 난이도**: {onboarding_level}\n\n" + summary
        
        return summary
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Summary generation failed: {error_msg}")
        return f"요약 생성 중 오류가 발생했습니다: {error_msg[:100]}"
