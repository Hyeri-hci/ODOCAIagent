"""
Comparison Agent Compare Nodes
진단 결과를 비교 분석하고 순위를 매기는 노드입니다.
"""

import logging
from typing import Dict, Any, List

from backend.agents.comparison.models import ComparisonState
from backend.agents.comparison.nodes.validation_nodes import safe_node
from backend.core.scoring_core import (
    compute_health_level,
    compute_onboarding_level,
    HEALTH_GOOD_THRESHOLD,
    HEALTH_WARNING_THRESHOLD,
    ONBOARDING_EASY_THRESHOLD,
    ONBOARDING_NORMAL_THRESHOLD,
)

logger = logging.getLogger(__name__)

def _analyze_repo_strengths(
    health_score: int,
    onboarding_score: int,
    docs_score: int,
    activity_score: int,
) -> List[str]:
    """저장소의 강점 분석"""
    strengths = []
    
    if health_score >= HEALTH_GOOD_THRESHOLD:
        strengths.append("excellent_maintenance")
    elif health_score >= HEALTH_WARNING_THRESHOLD:
        strengths.append("decent_maintenance")
    
    if onboarding_score >= ONBOARDING_EASY_THRESHOLD:
        strengths.append("beginner_friendly")
    elif onboarding_score >= ONBOARDING_NORMAL_THRESHOLD:
        strengths.append("moderate_learning_curve")
    
    if docs_score >= 70:
        strengths.append("well_documented")
    if activity_score >= 70:
        strengths.append("actively_maintained")
    
    return strengths


def _determine_best_for_purpose(comparison_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """목적별 최적 저장소 결정"""
    if not comparison_data:
        return {}
    
    recommendations = {
        "for_learning": None,
        "for_contribution": None,
        "for_production_reference": None,
        "overall_winner": None,
    }
    
    # 학습용: 온보딩 점수 최고
    learning_sorted = sorted(comparison_data, key=lambda x: x.get("onboarding_score", 0), reverse=True)
    if learning_sorted:
        recommendations["for_learning"] = {
            "repo": learning_sorted[0]["repo"],
            "reason": f"온보딩 점수 {learning_sorted[0].get('onboarding_score', 0)}점으로 가장 학습하기 좋음"
        }
    
    # 기여용: 활동성 + 문서화 균형
    contribution_sorted = sorted(
        comparison_data, 
        key=lambda x: x.get("activity_score", 0) * 0.6 + x.get("docs_score", 0) * 0.4, 
        reverse=True
    )
    if contribution_sorted:
        recommendations["for_contribution"] = {
            "repo": contribution_sorted[0]["repo"],
            "reason": f"활발한 유지보수와 문서화로 기여하기 좋음"
        }
    
    # 프로덕션 참고용: 전체 건강도 최고
    health_sorted = sorted(comparison_data, key=lambda x: x.get("health_score", 0), reverse=True)
    if health_sorted:
        recommendations["for_production_reference"] = {
            "repo": health_sorted[0]["repo"],
            "reason": f"건강도 점수 {health_sorted[0].get('health_score', 0)}점으로 가장 안정적"
        }
    
    # 전체 우승자: 종합 점수
    overall_sorted = sorted(
        comparison_data,
        key=lambda x: x.get("health_score", 0) * 0.5 + x.get("onboarding_score", 0) * 0.5,
        reverse=True
    )
    if overall_sorted:
        recommendations["overall_winner"] = {
            "repo": overall_sorted[0]["repo"],
            "health_score": overall_sorted[0].get("health_score", 0),
            "onboarding_score": overall_sorted[0].get("onboarding_score", 0),
        }
    
    return recommendations


@safe_node(default_updates={"comparison_data": [], "agent_analysis": {}})
async def compare_node(state: ComparisonState) -> Dict[str, Any]:
    """Core scoring을 활용한 비교 데이터 준비 및 분석"""
    logger.info("[Comparison Agent] Analyzing and comparing results")
    
    # 에러가 있으면 스킵
    if state.get("error"):
        return {}
    
    batch_results = state.get("batch_results", {})
    
    if not batch_results or len(batch_results) < 2:
        return {
            "error": "비교할 결과가 2개 이상 필요합니다.",
            "comparison_data": [],
            "execution_path": state.get("execution_path", "") + " → compare(ERROR)"
        }
    
    # 비교 데이터 준비 및 강점 분석
    comparison_data = []
    for repo_str, data in batch_results.items():
        health_score = data.get("health_score", 0)
        if health_score == 0 and data.get("health_level") == "unknown":
            logger.warning(f"[Comparison Agent] Skipping invalid result for {repo_str}")
            continue
        
        onboarding_score = data.get("onboarding_score", 0)
        docs_score = data.get("documentation_quality", data.get("docs", {}).get("total_score", 0))
        activity_score = data.get("activity_maintainability", data.get("activity", {}).get("total_score", 0))
        
        # Core scoring 레벨 재계산 (일관성 보장)
        health_level = compute_health_level(health_score)
        onboarding_level = compute_onboarding_level(onboarding_score)
        
        # 강점 분석
        strengths = _analyze_repo_strengths(health_score, onboarding_score, docs_score, activity_score)
        
        comparison_data.append({
            "repo": repo_str,
            "health_score": health_score,
            "onboarding_score": onboarding_score,
            "docs_score": docs_score,
            "activity_score": activity_score,
            "health_level": health_level,
            "onboarding_level": onboarding_level,
            "strengths": strengths,
        })
    
    # 점수 내림차순 정렬
    comparison_data.sort(key=lambda x: x["health_score"], reverse=True)
    
    # 목적별 추천 결정
    recommendations = _determine_best_for_purpose(comparison_data)
    
    logger.info(f"[Comparison Agent] Analyzed {len(comparison_data)} repos, overall winner: {recommendations.get('overall_winner', {}).get('repo', 'N/A')}")
    
    # 에이전트 분석 결과
    agent_analysis = {
        "comparison_data": comparison_data,
        "recommendations": recommendations,
        "total_repos_compared": len(comparison_data),
        "reasoning": f"Compared {len(comparison_data)} repositories based on health_score and onboarding_score",
    }
    
    return {
        "comparison_data": comparison_data,
        "agent_analysis": agent_analysis,
        "error": None,
        "execution_path": state.get("execution_path", "") + " → compare"
    }
