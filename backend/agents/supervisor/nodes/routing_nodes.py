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
    "diagnose": ["진단", "분석", "건강", "health", "analyze", "diagnosis", "score", "다시 분석", "재분석"],
    "onboard": ["온보딩", "시작", "기여", "onboard", "contribute", "plan", "플랜", "참여", "초보", "beginner", "PR", "pull request", "이슈", "issue"],
    "explain": ["설명", "왜", "무슨", "explain", "why", "what", "how", "점수가", "뭐야", "어떻게"],
    "compare": ["비교", "compare", "vs", "차이", "difference", "versus"],
}


def map_task_type_to_intent(task_type: str) -> str:
    """task_type에서 intent로 직접 매핑."""
    return TASK_TYPE_TO_INTENT.get(task_type, "unknown")


def infer_intent_from_context(state: SupervisorState) -> Tuple[str, float]:
    """user_context, chat_message 또는 task_type에서 의도 추론."""
    # 채팅 메시지가 있으면 우선 사용
    user_msg = state.chat_message or state.user_context.get("message", "")
    
    if user_msg:
        user_msg_lower = user_msg.lower()
        for intent, keywords in INTENT_KEYWORDS.items():
            if any(kw in user_msg_lower for kw in keywords):
                return intent, 0.8
        # 키워드 매칭 안 되면 일반 채팅
        if state.chat_message:
            return "chat", 0.7
    
    # task_type 기반 매핑
    if state.task_type:
        intent = map_task_type_to_intent(state.task_type)
        if intent != "unknown":
            return intent, 1.0
    
    return "unknown", 0.0


def intent_analysis_node(state: SupervisorState) -> Dict[str, Any]:
    """
    사용자 입력 또는 task_type을 분석하여 의도 분류.
    
    이미 detected_intent가 설정되어 있으면 재계산하지 않음.
    
    설정하는 필드:
    - detected_intent: 분류된 의도
    - intent_confidence: 분류 신뢰도
    """
    # 이미 intent가 설정되어 있으면 유지 (API에서 직접 설정한 경우)
    if state.detected_intent and state.detected_intent != "unknown":
        logger.info(
            f"Intent already set: {state.detected_intent}, skipping analysis"
        )
        return {
            "step": state.step + 1,
        }
    
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
    
    Agentic 기능:
    - 캐시 확인하여 이미 분석된 결과 재사용
    - 비교 분석 요청 시 여러 저장소 처리
    
    설정하는 필드:
    - next_node_override: 다음 노드명
    - decision_reason: 결정 근거
    - flow_adjustments: 동적 플로우 조정 목록
    - warnings: 사용자 경고 메시지
    - cache_hit: 캐시 히트 여부
    """
    intent = state.detected_intent or "unknown"
    adjustments = []
    warnings = []
    cache_hit = False
    
    user_exp = state.user_context.get("experience_level", "beginner")
    
    if intent == "diagnose":
        if state.use_cache:
            cached = _check_cache(state.owner, state.repo)
            if cached:
                next_node = "use_cached_result_node"
                reason = f"Cache hit for {state.owner}/{state.repo}, using cached result"
                cache_hit = True
            else:
                next_node = "run_diagnosis_node"
                reason = f"Intent is diagnose for {state.owner}/{state.repo}, no cache"
        else:
            next_node = "run_diagnosis_node"
            reason = f"Intent is diagnose for {state.owner}/{state.repo}, cache disabled"
    elif intent == "onboard":
        if state.use_cache:
            cached = _check_cache(state.owner, state.repo)
            if cached:
                next_node = "use_cached_result_node"
                reason = f"Cache hit for {state.owner}/{state.repo}, using cached for onboard"
                cache_hit = True
            else:
                next_node = "run_diagnosis_node"
                reason = f"Intent is onboard for {state.owner}/{state.repo}, no cache"
        else:
            next_node = "run_diagnosis_node"
            reason = f"Intent is onboard, starting with diagnosis for {state.owner}/{state.repo}"
        if user_exp == "beginner":
            adjustments.append("beginner_friendly_plan")
    elif intent == "compare":
        next_node = "batch_diagnosis_node"
        reason = f"Intent is compare, processing {len(state.compare_repos)} repositories"
        if not state.compare_repos:
            warnings.append("비교할 저장소 목록이 비어 있습니다.")
            next_node = "__end__"
    elif intent == "explain":
        if state.diagnosis_result:
            next_node = "__end__"
            reason = "Intent is explain, diagnosis result exists"
        else:
            if state.use_cache:
                cached = _check_cache(state.owner, state.repo)
                if cached:
                    next_node = "use_cached_result_node"
                    reason = "Intent is explain, using cached diagnosis result"
                    cache_hit = True
                else:
                    next_node = "run_diagnosis_node"
                    reason = "Intent is explain but no cache, running diagnosis first"
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
    
    logger.info(f"Decision: next_node={next_node}, reason={reason}, adjustments={adjustments}, cache_hit={cache_hit}")
    
    return {
        "next_node_override": next_node,
        "decision_reason": reason,
        "flow_adjustments": adjustments,
        "warnings": warnings,
        "cache_hit": cache_hit,
        "step": state.step + 1,
    }


def _check_cache(owner: str, repo: str, ref: str = "main") -> bool:
    """캐시에 분석 결과가 있는지 확인."""
    try:
        from backend.common.cache import analysis_cache
        cached = analysis_cache.get_analysis(owner, repo, ref)
        return cached is not None
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")
        return False


def use_cached_result_node(state: SupervisorState) -> Dict[str, Any]:
    """
    캐시에서 분석 결과를 로드하여 diagnosis_result에 설정.
    """
    try:
        from backend.common.cache import analysis_cache
        cached = analysis_cache.get_analysis(state.owner, state.repo, "main")
        
        if cached:
            logger.info(f"Loaded cached result for {state.owner}/{state.repo}")
            return {
                "diagnosis_result": cached,
                "cache_hit": True,
                "decision_reason": f"Loaded from cache: {state.owner}/{state.repo}",
                "step": state.step + 1,
            }
        else:
            logger.warning(f"Cache miss during load for {state.owner}/{state.repo}")
            return {
                "next_node_override": "run_diagnosis_node",
                "cache_hit": False,
                "step": state.step + 1,
            }
    except Exception as e:
        logger.error(f"Failed to load cached result: {e}")
        return {
            "next_node_override": "run_diagnosis_node",
            "cache_hit": False,
            "error": str(e),
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
                if "recommend_deep_analysis" not in adjustments:
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


def route_after_cached_result(state: SupervisorState) -> str:
    """use_cached_result_node 이후 라우팅."""
    if state.next_node_override == "run_diagnosis_node":
        return "run_diagnosis_node"
    
    if state.detected_intent == "onboard" and state.task_type == "build_onboarding_plan":
        return "fetch_issues_node"
    
    if state.detected_intent == "compare":
        return "compare_results_node"
    
    return "quality_check_node"


def route_after_quality_check(state: SupervisorState) -> str:
    """quality_check_node 이후 라우팅."""
    if state.next_node_override == "run_diagnosis_node":
        return "run_diagnosis_node"
    
    if state.detected_intent == "onboard" and state.task_type == "build_onboarding_plan":
        return "fetch_issues_node"
    
    if state.detected_intent == "compare":
        return "compare_results_node"
    
    return "__end__"

