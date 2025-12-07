"""Agentic Routing Nodes - 의도 분석 및 결정 노드."""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)

# Intent <-> TaskType 매핑 테이블
TASK_TYPE_TO_INTENT = {
    "diagnose_repo": "diagnose",
    "build_onboarding_plan": "onboard",
}

INTENT_TO_TASK_TYPE = {
    "diagnose": "diagnose_repo",
    "onboard": "build_onboarding_plan",
}

# 의도 추론을 위한 키워드
INTENT_KEYWORDS = {
    "diagnose": ["진단", "분석", "건강", "health", "analyze", "diagnosis", "score"],
    "onboard": ["온보딩", "시작", "기여", "onboard", "contribute", "plan", "플랜"],
    "explain": ["설명", "왜", "무슨", "explain", "why", "what", "how"],
}


def map_task_type_to_intent(task_type: str) -> str:
    """task_type에서 intent로 직접 매핑."""
    return TASK_TYPE_TO_INTENT.get(task_type, "unknown")


def infer_intent_from_context(state: SupervisorState) -> Tuple[str, float]:
    """
    user_context 또는 task_type에서 의도 추론.
    
    Returns:
        (intent, confidence) 튜플
    """
    if state.task_type:
        intent = map_task_type_to_intent(state.task_type)
        if intent != "unknown":
            return intent, 1.0
    
    user_msg = state.user_context.get("message", "")
    if not user_msg:
        return map_task_type_to_intent(state.task_type), 1.0
    
    user_msg_lower = user_msg.lower()
    
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in user_msg_lower for kw in keywords):
            return intent, 0.8
    
    return "unknown", 0.0


def intent_analysis_node(state: SupervisorState) -> Dict[str, Any]:
    """
    사용자 입력 또는 task_type을 분석하여 의도 분류.
    
    설정하는 필드:
    - detected_intent: 분류된 의도
    - intent_confidence: 분류 신뢰도
    """
    intent, confidence = infer_intent_from_context(state)
    
    logger.info(
        f"Intent analysis: task_type={state.task_type}, "
        f"detected_intent={intent}, confidence={confidence}"
    )
    
    return {
        "detected_intent": intent,
        "intent_confidence": confidence,
        "step": state.step + 1,
    }


def decision_node(state: SupervisorState) -> Dict[str, Any]:
    """
    분석된 의도와 현재 상태를 기반으로 다음 행동 결정.
    
    설정하는 필드:
    - next_node_override: 다음 노드명
    - decision_reason: 결정 근거
    - flow_adjustments: 동적 플로우 조정 목록
    - warnings: 사용자 경고 메시지
    """
    intent = state.detected_intent or "unknown"
    adjustments = []
    warnings = []
    
    user_exp = state.user_context.get("experience_level", "beginner")
    
    if intent == "diagnose":
        next_node = "run_diagnosis_node"
        reason = f"Intent is diagnose for {state.owner}/{state.repo}"
    elif intent == "onboard":
        next_node = "run_diagnosis_node"
        reason = f"Intent is onboard, starting with diagnosis for {state.owner}/{state.repo}"
        if user_exp == "beginner":
            adjustments.append("beginner_friendly_plan")
    elif intent == "explain":
        if state.diagnosis_result:
            next_node = "__end__"
            reason = "Intent is explain, diagnosis result exists"
        else:
            next_node = "run_diagnosis_node"
            reason = "Intent is explain but no diagnosis result, running diagnosis first"
    else:
        next_node = "__end__"
        reason = f"Unknown intent: {intent}, ending flow"
    
    if state.diagnosis_result:
        health = state.diagnosis_result.get("health_score", 100)
        if health < 30:
            warnings.append("이 프로젝트는 건강 상태가 좋지 않아 기여 시 주의가 필요합니다.")
            adjustments.append("add_health_warning")
    
    logger.info(f"Decision: next_node={next_node}, reason={reason}, adjustments={adjustments}")
    
    return {
        "next_node_override": next_node,
        "decision_reason": reason,
        "flow_adjustments": adjustments,
        "warnings": warnings,
        "step": state.step + 1,
    }


def quality_check_node(state: SupervisorState) -> Dict[str, Any]:
    """
    결과 품질을 자체 평가하여 재실행 여부 결정 및 동적 플로우 조정.
    
    검사 항목:
    - diagnosis_result 존재 여부
    - health_score 범위 유효성 (0-100)
    - 필수 필드 존재 여부
    
    동적 조정:
    - 낮은 점수 시 경고 추가
    - 활동성/문서 이슈 시 관련 조정 추가
    
    설정하는 필드:
    - quality_issues: 발견된 품질 문제 목록
    - rerun_count: 재실행 횟수 (증가)
    - next_node_override: 재실행 또는 종료
    - flow_adjustments: 동적 플로우 조정
    - warnings: 사용자 경고
    """
    issues = []
    adjustments = list(state.flow_adjustments)
    warnings = list(state.warnings)
    diagnosis = state.diagnosis_result
    
    if diagnosis is None:
        issues.append("diagnosis_result is None")
    else:
        health_score = diagnosis.get("health_score")
        if health_score is None:
            issues.append("health_score is missing")
        elif not (0 <= health_score <= 100):
            issues.append(f"health_score out of range: {health_score}")
        
        required_fields = ["repo_id", "health_level", "onboarding_score"]
        for field in required_fields:
            if field not in diagnosis or diagnosis[field] is None:
                issues.append(f"required field missing: {field}")
        
        if health_score is not None and 0 <= health_score <= 100:
            if health_score < 30:
                if "add_health_warning" not in adjustments:
                    adjustments.append("recommend_deep_analysis")
                    warnings.append("프로젝트 건강 점수가 매우 낮습니다 (30점 미만).")
            elif health_score < 50:
                if "moderate_health_notice" not in adjustments:
                    adjustments.append("moderate_health_notice")
        
        activity_issues = diagnosis.get("activity_issues", [])
        if activity_issues and "enhance_issue_recommendations" not in adjustments:
            adjustments.append("enhance_issue_recommendations")
        
        docs_issues = diagnosis.get("docs_issues", [])
        if docs_issues and "add_docs_improvement_guide" not in adjustments:
            adjustments.append("add_docs_improvement_guide")
    
    if issues:
        logger.warning(f"Quality issues found: {issues}")
        
        if state.rerun_count < state.max_rerun:
            logger.info(
                f"Scheduling rerun ({state.rerun_count + 1}/{state.max_rerun})"
            )
            return {
                "quality_issues": issues,
                "rerun_count": state.rerun_count + 1,
                "next_node_override": "run_diagnosis_node",
                "flow_adjustments": adjustments,
                "warnings": warnings,
                "step": state.step + 1,
            }
        else:
            logger.warning(
                f"Max rerun reached ({state.max_rerun}), proceeding with issues"
            )
    
    logger.info(f"Quality check passed, adjustments={adjustments}")
    
    return {
        "quality_issues": issues,
        "next_node_override": "__end__",
        "flow_adjustments": adjustments,
        "warnings": warnings,
        "step": state.step + 1,
    }


def route_after_decision(state: SupervisorState) -> str:
    """decision_node 이후 라우팅. state.next_node_override 기반."""
    next_node = state.next_node_override or "__end__"
    logger.debug(f"Routing after decision: {next_node}")
    return next_node


def route_after_quality_check(state: SupervisorState) -> str:
    """quality_check_node 이후 라우팅."""
    if state.next_node_override == "run_diagnosis_node":
        return "run_diagnosis_node"
    
    if state.detected_intent == "onboard" and state.task_type == "build_onboarding_plan":
        return "fetch_issues_node"
    
    return "__end__"

