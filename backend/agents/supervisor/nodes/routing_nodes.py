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

# 분석 깊이 임계값 설정
ANALYSIS_DEPTH_THRESHOLDS = {
    "deep": {
        "min_stars": 5000,        # 5000+ 스타 프로젝트
        "min_files": 500,         # 500+ 파일
        "description": "대규모 프로젝트 심층 분석"
    },
    "standard": {
        "min_stars": 100,         # 100-5000 스타 프로젝트
        "min_files": 50,          # 50-500 파일
        "description": "일반 프로젝트 표준 분석"
    },
    "quick": {
        "min_stars": 0,           # 100 미만 스타 프로젝트
        "min_files": 0,           # 50 미만 파일
        "description": "소규모 프로젝트 빠른 분석"
    }
}

# 분석 깊이별 키워드
DEPTH_KEYWORDS = {
    "deep": ["자세히", "심층", "깊이", "상세", "detailed", "deep", "thorough", "comprehensive"],
    "quick": ["빠르게", "간단히", "요약", "quick", "fast", "brief", "simple", "summary"],
}


def determine_analysis_depth(state: SupervisorState) -> str:
    """
    저장소 특성과 사용자 요청에 따라 분석 깊이를 결정.
    
    결정 우선순위:
    1. 사용자 명시적 요청 (user_context, chat_message)
    2. 저장소 크기/특성 기반 자동 결정
    3. 기본값 "standard"
    
    Returns:
        str: "deep", "standard", "quick" 중 하나
    """
    # 1. 사용자가 명시적으로 분석 깊이를 지정한 경우
    if state.user_context.get("analysis_depth"):
        depth = state.user_context["analysis_depth"]
        if depth in ["deep", "standard", "quick"]:
            logger.info(f"Analysis depth from user_context: {depth}")
            return depth
    
    # 2. 채팅 메시지에서 깊이 관련 키워드 탐색
    user_msg = state.chat_message or state.user_context.get("message", "")
    if user_msg:
        user_msg_lower = user_msg.lower()
        for depth, keywords in DEPTH_KEYWORDS.items():
            if any(kw in user_msg_lower for kw in keywords):
                logger.info(f"Analysis depth inferred from message keyword: {depth}")
                return depth
    
    # 3. quick_scan 플래그 확인
    if state.user_context.get("quick_scan") or state.user_context.get("quick"):
        logger.info("Analysis depth: quick (quick_scan flag)")
        return "quick"
    
    # 4. 저장소 스냅샷 기반 자동 결정
    if state.repo_snapshot:
        stars = getattr(state.repo_snapshot, 'stars', 0) or 0
        # 파일 수는 tree에서 추정 (있는 경우)
        file_count = len(getattr(state.repo_snapshot, 'tree', []) or [])
        
        if stars >= ANALYSIS_DEPTH_THRESHOLDS["deep"]["min_stars"]:
            logger.info(f"Analysis depth: deep (stars={stars})")
            return "deep"
        elif stars < ANALYSIS_DEPTH_THRESHOLDS["standard"]["min_stars"]:
            logger.info(f"Analysis depth: quick (stars={stars})")
            return "quick"
    
    # 5. 진단 결과가 이미 있고 explain/chat 의도인 경우 quick
    if state.diagnosis_result and state.detected_intent in ["explain", "chat"]:
        logger.info("Analysis depth: quick (existing diagnosis + explain/chat intent)")
        return "quick"
    
    # 6. 비교 분석인 경우 quick (여러 저장소를 빠르게 분석)
    if state.detected_intent == "compare" and len(state.compare_repos) > 2:
        logger.info(f"Analysis depth: quick (comparing {len(state.compare_repos)} repos)")
        return "quick"
    
    logger.info("Analysis depth: standard (default)")
    return "standard"


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
    - analysis_depth: 분석 깊이 (deep/standard/quick)
    """
    result = {"step": state.step + 1}
    
    # 이미 intent가 설정되어 있으면 유지 (API에서 직접 설정한 경우)
    if state.detected_intent and state.detected_intent != "unknown":
        logger.info(
            f"Intent already set: {state.detected_intent}, skipping analysis"
        )
    else:
        intent, confidence = infer_intent_from_context(state)
        result["detected_intent"] = intent
        result["intent_confidence"] = confidence
        logger.info(
            f"Intent analysis: task_type={state.task_type}, "
            f"detected_intent={intent}, confidence={confidence}"
        )
    
    # 분석 깊이 결정 (아직 설정되지 않은 경우에만)
    if state.analysis_depth == "standard":  # 기본값인 경우에만 재계산
        depth = determine_analysis_depth(state)
        if depth != state.analysis_depth:
            result["analysis_depth"] = depth
            logger.info(f"Analysis depth determined: {depth}")
    
    return result


def decision_node(state: SupervisorState) -> Dict[str, Any]:
    """
    분석된 의도와 현재 상태를 기반으로 다음 행동 결정.
    
    Agentic 기능:
    - 캐시 확인하여 이미 분석된 결과 재사용
    - 비교 분석 요청 시 여러 저장소 처리
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
        if state.chat_message and (state.diagnosis_result or state.chat_context):
            next_node = "chat_response_node"
            reason = "Intent is onboard with chat message, routing to chat response"
            if user_exp == "beginner":
                adjustments.append("beginner_friendly_plan")
        elif state.use_cache:
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
        if state.diagnosis_result or state.chat_context:
            next_node = "chat_response_node"
            reason = "Intent is explain, routing to chat response"
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
    elif intent == "chat":
        next_node = "chat_response_node"
        reason = "Intent is chat, routing to chat response"
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

