"""
Onboarding Agent Recommendation Nodes
유사 프로젝트 추천을 가져오는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.onboarding.models import OnboardingState
from backend.agents.onboarding.nodes.intent_nodes import safe_node

logger = logging.getLogger(__name__)

@safe_node(default_updates={"similar_projects": []})
async def fetch_recommendations_node(state: OnboardingState) -> Dict[str, Any]:
    """유사 프로젝트 추천 가져오기 (Recommend 에이전트 호출)"""
    
    # 추천 포함 여부 확인 (기본값: True)
    if not state.get("include_recommendations", True):
        logger.info("[Onboarding Agent] Skipping recommendations (disabled)")
        return {
            "similar_projects": [],
            "execution_path": state.get("execution_path", "") + " → fetch_recommendations(skipped)"
        }
    
    logger.info(f"[Onboarding Agent] Fetching recommendations for {state['owner']}/{state['repo']}")
    
    try:
        from backend.agents.recommend.agent.graph import run_recommend
        
        result = await run_recommend(
            owner=state["owner"],
            repo=state["repo"],
            user_message=state.get("user_message")
        )
        
        # 상위 5개 추천만 가져옴
        recommendations = result.get("recommendations", [])[:5]
        
        logger.info(f"[Onboarding Agent] Fetched {len(recommendations)} recommendations")
        
        return {
            "similar_projects": recommendations,
            "execution_path": state.get("execution_path", "") + " → fetch_recommendations"
        }
    except Exception as e:
        logger.warning(f"[Onboarding Agent] Failed to fetch recommendations: {e}")
        return {
            "similar_projects": [],
            "execution_path": state.get("execution_path", "") + " → fetch_recommendations(error)"
        }
