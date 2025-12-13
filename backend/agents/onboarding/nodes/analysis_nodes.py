"""
Onboarding Agent Analysis Nodes
진단 결과를 분석하고 리스크를 평가하는 노드입니다.
"""

import logging
from typing import Dict, Any, List

from backend.agents.onboarding.models import OnboardingState
from backend.agents.onboarding.nodes.intent_nodes import safe_node
from backend.core.scoring_core import (
    compute_health_score,
    compute_onboarding_score,
    compute_health_level,
    compute_onboarding_level,
    HEALTH_WARNING_THRESHOLD,
    ONBOARDING_NORMAL_THRESHOLD,
    WEAK_DOCS_THRESHOLD,
    INACTIVE_ACTIVITY_THRESHOLD,
)

logger = logging.getLogger(__name__)

def _assess_onboarding_risks(
    onboarding_score: int,
    health_score: int,
    onboarding_level: str,
    health_level: str,
    experience_level: str,
) -> List[Dict[str, Any]]:
    """경험 수준에 따른 온보딩 리스크 평가"""
    risks = []
    
    # 초보자에게만 해당하는 리스크
    if experience_level == "beginner":
        if onboarding_score < ONBOARDING_NORMAL_THRESHOLD:
            risks.append({
                "type": "onboarding_difficulty",
                "severity": "high",
                "message": f"온보딩 점수가 {onboarding_score}점으로 낮습니다. 초보자에게 도전적인 프로젝트입니다.",
                "recommendation": "good-first-issue 라벨이 있는 이슈부터 시작하세요."
            })
        if health_score < HEALTH_WARNING_THRESHOLD:
            risks.append({
                "type": "project_health",
                "severity": "medium",
                "message": f"프로젝트 건강도가 {health_score}점으로 낮습니다. 유지보수가 활발하지 않을 수 있습니다.",
                "recommendation": "최근 커밋/PR 활동을 확인하고 메인테이너 응답 여부를 살펴보세요."
            })
    
    # 중급자에게 해당하는 리스크
    elif experience_level == "intermediate":
        if onboarding_score < WEAK_DOCS_THRESHOLD:
            risks.append({
                "type": "documentation_gap",
                "severity": "medium",
                "message": "문서화가 부족합니다. 코드를 직접 읽어가며 파악해야 할 수 있습니다.",
                "recommendation": "코드 구조 분석부터 시작하고, 테스트 코드를 참고하세요."
            })
    
    # 고급자에게는 더 적은 제약
    elif experience_level == "advanced":
        if health_score < INACTIVE_ACTIVITY_THRESHOLD:
            risks.append({
                "type": "inactive_project",
                "severity": "low",
                "message": "프로젝트 활동이 적습니다. 기여해도 머지되지 않을 수 있습니다.",
                "recommendation": "이슈에서 메인테이너 응답 현황을 먼저 확인하세요."
            })
    
    # 모든 수준 공통 리스크
    if health_level == "bad" and onboarding_level == "hard":
        risks.append({
            "type": "overall_challenge",
            "severity": "high" if experience_level == "beginner" else "medium",
            "message": "전체적으로 기여하기 어려운 프로젝트입니다.",
            "recommendation": "다른 프로젝트를 먼저 경험해보는 것을 권장합니다."
        })
    
    return risks


def _determine_plan_intensity(
    onboarding_level: str,
    health_level: str,
    experience_level: str,
    risk_count: int,
) -> Dict[str, Any]:
    """플랜 강도 및 기간 결정"""
    # 기본 설정
    config = {
        "weeks": 4,
        "issues_per_week": 2,
        "include_advanced_topics": False,
        "focus_areas": [],
    }
    
    # 경험 수준에 따른 기본 조정
    if experience_level == "beginner":
        config["weeks"] = 6
        config["issues_per_week"] = 1
        config["focus_areas"] = ["documentation_reading", "environment_setup", "small_fixes"]
    elif experience_level == "intermediate":
        config["weeks"] = 4
        config["issues_per_week"] = 2
        config["focus_areas"] = ["code_understanding", "feature_contribution", "testing"]
    else:  # advanced
        config["weeks"] = 3
        config["issues_per_week"] = 3
        config["include_advanced_topics"] = True
        config["focus_areas"] = ["architecture", "core_features", "performance"]
    
    # 온보딩 난이도에 따른 조정
    if onboarding_level == "hard":
        config["weeks"] += 2
        config["focus_areas"].insert(0, "deep_documentation_study")
    elif onboarding_level == "easy":
        config["weeks"] = max(2, config["weeks"] - 1)
    
    # 프로젝트 건강도에 따른 조정
    if health_level == "bad":
        config["focus_areas"].append("maintainer_communication")
    
    # 리스크가 많으면 더 긴 플랜
    if risk_count >= 3:
        config["weeks"] += 1
    
    return config


@safe_node(default_updates={
    "diagnosis_analysis": {
        "doc_score": 50, "activity_score": 50, "structure_score": 0,
        "health_score": 50, "onboarding_score": 50,
        "health_level": "warning", "onboarding_level": "normal"
    }
})
async def analyze_diagnosis_node(state: OnboardingState) -> Dict[str, Any]:
    """Core scoring을 활용한 진단 분석 - 에이전트 핵심 판단 노드"""
    logger.info(f"[Onboarding Agent] Analyzing diagnosis for {state['owner']}/{state['repo']}")
    
    diagnosis_summary = state.get("diagnosis_summary", "")
    
    # 진단 요약에서 점수 추출 시도
    doc_score = 50  # 기본값
    activity_score = 50  # 기본값
    structure_score = 0
    
    # diagnosis_summary가 dict인 경우 (진단 에이전트로부터 온 경우)
    if isinstance(diagnosis_summary, dict):
        doc_score = diagnosis_summary.get("documentation_quality", 50)
        activity_score = diagnosis_summary.get("activity_maintainability", 50)
        structure_score = diagnosis_summary.get("structure_score", 0)
    # diagnosis_summary가 문자열인 경우 파싱 시도
    elif isinstance(diagnosis_summary, str) and diagnosis_summary:
        import re
        # "문서화: 65점" 같은 패턴 파싱
        doc_match = re.search(r'(?:문서화|documentation)[:\s]*(\d+)', diagnosis_summary, re.IGNORECASE)
        if doc_match:
            doc_score = int(doc_match.group(1))
        activity_match = re.search(r'(?:활동성|activity)[:\s]*(\d+)', diagnosis_summary, re.IGNORECASE)
        if activity_match:
            activity_score = int(activity_match.group(1))
    
    # Core scoring 계산
    health_score = compute_health_score(doc_score, activity_score, structure_score)
    onboarding_score = compute_onboarding_score(doc_score, activity_score, structure_score)
    health_level = compute_health_level(health_score)
    onboarding_level = compute_onboarding_level(onboarding_score)
    
    logger.info(f"[Onboarding Agent] Computed scores - Health: {health_score} ({health_level}), Onboarding: {onboarding_score} ({onboarding_level})")
    
    # 분석 결과를 상태에 저장
    analysis = {
        "doc_score": doc_score,
        "activity_score": activity_score,
        "structure_score": structure_score,
        "health_score": health_score,
        "onboarding_score": onboarding_score,
        "health_level": health_level,
        "onboarding_level": onboarding_level,
    }
    
    return {
        "diagnosis_analysis": analysis,
        "execution_path": state.get("execution_path", "") + " → analyze_diagnosis"
    }


@safe_node(default_updates={
    "onboarding_risks": [],
    "plan_config": {"weeks": 4, "issues_per_week": 2, "focus_areas": []},
    "agent_decision": {}
})
async def assess_risks_node(state: OnboardingState) -> Dict[str, Any]:
    """경험 수준별 리스크 평가 및 플랜 설정 결정"""
    logger.info(f"[Onboarding Agent] Assessing risks for {state['owner']}/{state['repo']}")
    
    analysis = state.get("diagnosis_analysis", {})
    experience_level = state.get("experience_level", "beginner")
    
    # 리스크 평가
    risks = _assess_onboarding_risks(
        onboarding_score=analysis.get("onboarding_score", 50),
        health_score=analysis.get("health_score", 50),
        onboarding_level=analysis.get("onboarding_level", "normal"),
        health_level=analysis.get("health_level", "warning"),
        experience_level=experience_level,
    )
    
    # 플랜 강도 결정
    plan_config = _determine_plan_intensity(
        onboarding_level=analysis.get("onboarding_level", "normal"),
        health_level=analysis.get("health_level", "warning"),
        experience_level=experience_level,
        risk_count=len(risks),
    )
    
    logger.info(f"[Onboarding Agent] Identified {len(risks)} risks, plan config: {plan_config['weeks']} weeks")
    
    # 에이전트 결정 로그
    agent_decision = {
        "risks": risks,
        "plan_config": plan_config,
        "reasoning": f"Based on onboarding_level={analysis.get('onboarding_level')}, health_level={analysis.get('health_level')}, experience={experience_level}"
    }
    
    return {
        "onboarding_risks": risks,
        "plan_config": plan_config,
        "agent_decision": agent_decision,
        "execution_path": state.get("execution_path", "") + " → assess_risks"
    }
