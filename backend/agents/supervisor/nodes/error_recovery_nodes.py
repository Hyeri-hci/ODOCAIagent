from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """에러 타입 분류."""
    GITHUB_RATE_LIMIT = "github_rate_limit"
    GITHUB_NOT_FOUND = "github_not_found"
    GITHUB_AUTH = "github_auth"
    GITHUB_NETWORK = "github_network"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_CONTENT_FILTER = "llm_content_filter"
    LLM_ERROR = "llm_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


@dataclass
class RecoveryStrategy:
    """복구 전략."""
    action: str  # retry, skip, fallback, wait, abort
    wait_seconds: int = 0
    max_retries: int = 3
    fallback_node: Optional[str] = None
    message: str = ""
    skip_components: List[str] = None
    
    def __post_init__(self):
        if self.skip_components is None:
            self.skip_components = []


# 에러 타입별 복구 전략 매핑
ERROR_RECOVERY_STRATEGIES: Dict[ErrorType, RecoveryStrategy] = {
    ErrorType.GITHUB_RATE_LIMIT: RecoveryStrategy(
        action="wait",
        wait_seconds=60,
        max_retries=3,
        message="GitHub API 요청 한도 초과. 잠시 후 재시도합니다.",
    ),
    ErrorType.GITHUB_NOT_FOUND: RecoveryStrategy(
        action="abort",
        message="저장소를 찾을 수 없습니다. URL을 확인해주세요.",
    ),
    ErrorType.GITHUB_AUTH: RecoveryStrategy(
        action="abort",
        message="GitHub 인증에 실패했습니다. 토큰을 확인해주세요.",
    ),
    ErrorType.GITHUB_NETWORK: RecoveryStrategy(
        action="retry",
        wait_seconds=5,
        max_retries=3,
        message="GitHub 연결 실패. 재시도 중...",
    ),
    ErrorType.LLM_TIMEOUT: RecoveryStrategy(
        action="fallback",
        fallback_node="use_fallback_summary_node",
        message="LLM 응답 시간 초과. Fallback 요약을 사용합니다.",
        skip_components=["llm_summary"],
    ),
    ErrorType.LLM_RATE_LIMIT: RecoveryStrategy(
        action="wait",
        wait_seconds=30,
        max_retries=2,
        message="LLM 요청 한도 초과. 잠시 후 재시도합니다.",
    ),
    ErrorType.LLM_CONTENT_FILTER: RecoveryStrategy(
        action="fallback",
        fallback_node="use_fallback_summary_node",
        message="LLM 콘텐츠 필터링됨. Fallback 요약을 사용합니다.",
        skip_components=["llm_summary"],
    ),
    ErrorType.LLM_ERROR: RecoveryStrategy(
        action="fallback",
        fallback_node="use_fallback_summary_node",
        message="LLM 오류 발생. Fallback 요약을 사용합니다.",
        skip_components=["llm_summary"],
    ),
    ErrorType.NETWORK_ERROR: RecoveryStrategy(
        action="retry",
        wait_seconds=10,
        max_retries=3,
        message="네트워크 오류. 재시도 중...",
    ),
    ErrorType.VALIDATION_ERROR: RecoveryStrategy(
        action="skip",
        message="데이터 검증 실패. 부분 결과로 진행합니다.",
        skip_components=["validation"],
    ),
    ErrorType.UNKNOWN: RecoveryStrategy(
        action="retry",
        wait_seconds=5,
        max_retries=2,
        message="알 수 없는 오류. 재시도 중...",
    ),
}


def classify_error(error_message: str) -> ErrorType:
    """에러 메시지를 분석하여 에러 타입 분류."""
    error_lower = error_message.lower()
    
    # GitHub 에러
    if "rate limit" in error_lower and "github" in error_lower:
        return ErrorType.GITHUB_RATE_LIMIT
    if "403" in error_lower and "rate" in error_lower:
        return ErrorType.GITHUB_RATE_LIMIT
    if "404" in error_lower or "not found" in error_lower:
        return ErrorType.GITHUB_NOT_FOUND
    if "401" in error_lower or "unauthorized" in error_lower or "authentication" in error_lower:
        return ErrorType.GITHUB_AUTH
    if "github" in error_lower and ("connection" in error_lower or "timeout" in error_lower):
        return ErrorType.GITHUB_NETWORK
    
    # LLM 에러
    if "timeout" in error_lower and ("llm" in error_lower or "openai" in error_lower or "kanana" in error_lower):
        return ErrorType.LLM_TIMEOUT
    if "rate limit" in error_lower and ("openai" in error_lower or "llm" in error_lower):
        return ErrorType.LLM_RATE_LIMIT
    if "content_filter" in error_lower or "content policy" in error_lower:
        return ErrorType.LLM_CONTENT_FILTER
    if "llm" in error_lower or "openai" in error_lower or "kanana" in error_lower:
        return ErrorType.LLM_ERROR
    
    # 네트워크 에러
    if "connection" in error_lower or "network" in error_lower or "timeout" in error_lower:
        return ErrorType.NETWORK_ERROR
    
    # 검증 에러
    if "validation" in error_lower or "invalid" in error_lower:
        return ErrorType.VALIDATION_ERROR
    
    return ErrorType.UNKNOWN


def get_recovery_strategy(error_message: str) -> Tuple[ErrorType, RecoveryStrategy]:
    """에러 메시지에 따른 복구 전략 반환."""
    error_type = classify_error(error_message)
    strategy = ERROR_RECOVERY_STRATEGIES.get(error_type, ERROR_RECOVERY_STRATEGIES[ErrorType.UNKNOWN])
    return error_type, strategy


def smart_error_recovery_node(state: SupervisorState) -> Dict[str, Any]:
    """
    에러 원인을 분석하고 적절한 복구 전략을 결정.
    
    이 노드는 에러가 발생했을 때 quality_check_node 대신 호출되어
    에러 타입에 따른 복구 액션을 결정합니다.
    
    설정하는 필드:
    - recovery_action: 복구 액션 (retry, skip, fallback, wait, abort)
    - recovery_message: 사용자에게 표시할 메시지
    - next_node_override: 다음 노드
    - warnings: 경고 메시지 추가
    - rerun_count: 재시도 횟수 증가 (retry 시)
    """
    error = state.error or ""
    rerun_count = state.rerun_count
    
    if not error:
        # 에러가 없으면 정상 진행
        logger.info("No error to recover from, proceeding normally")
        return {
            "next_node_override": "quality_check_node",
            "step": state.step + 1,
        }
    
    error_type, strategy = get_recovery_strategy(error)
    
    logger.info(f"Error recovery: type={error_type.value}, action={strategy.action}, "
                f"rerun_count={rerun_count}/{strategy.max_retries}")
    
    warnings = list(state.warnings)
    warnings.append(strategy.message)
    
    result: Dict[str, Any] = {
        "warnings": warnings,
        "step": state.step + 1,
    }
    
    if strategy.action == "abort":
        # 복구 불가 - 종료
        logger.error(f"Unrecoverable error: {error}")
        result["next_node_override"] = "__end__"
        result["error"] = error  # 에러 유지
        
    elif strategy.action == "wait":
        # 대기 후 재시도
        if rerun_count < strategy.max_retries:
            logger.info(f"Waiting {strategy.wait_seconds}s before retry...")
            time.sleep(strategy.wait_seconds)
            result["next_node_override"] = "run_diagnosis_node"
            result["rerun_count"] = rerun_count + 1
            result["error"] = None  # 에러 클리어하고 재시도
        else:
            logger.warning(f"Max retries ({strategy.max_retries}) reached for wait action")
            result["next_node_override"] = "__end__"
            
    elif strategy.action == "retry":
        # 즉시 재시도
        if rerun_count < strategy.max_retries:
            if strategy.wait_seconds > 0:
                logger.info(f"Waiting {strategy.wait_seconds}s before retry...")
                time.sleep(strategy.wait_seconds)
            result["next_node_override"] = "run_diagnosis_node"
            result["rerun_count"] = rerun_count + 1
            result["error"] = None  # 에러 클리어하고 재시도
        else:
            logger.warning(f"Max retries ({strategy.max_retries}) reached")
            result["next_node_override"] = "__end__"
            
    elif strategy.action == "fallback":
        # Fallback 사용
        logger.info(f"Using fallback: {strategy.fallback_node}")
        # fallback_node가 없으면 skip_llm_summary 모드로 진행
        if strategy.fallback_node:
            result["next_node_override"] = strategy.fallback_node
        else:
            # LLM 요약 없이 진행하도록 설정
            user_context = dict(state.user_context)
            user_context["use_llm_summary"] = False
            user_context["skip_components"] = strategy.skip_components
            result["user_context"] = user_context
            result["next_node_override"] = "run_diagnosis_node"
            result["rerun_count"] = rerun_count + 1
        result["error"] = None  # 에러 클리어
        
    elif strategy.action == "skip":
        # 해당 단계 스킵하고 진행
        logger.info(f"Skipping failed component: {strategy.skip_components}")
        user_context = dict(state.user_context)
        user_context["skip_components"] = strategy.skip_components
        result["user_context"] = user_context
        result["next_node_override"] = "quality_check_node"
        result["error"] = None  # 에러 클리어
    
    return result


def partial_result_recovery_node(state: SupervisorState) -> Dict[str, Any]:
    """
    부분 결과로 진행하는 복구 노드.
    
    일부 분석이 실패해도 성공한 부분으로 결과를 생성합니다.
    """
    diagnosis = state.diagnosis_result or {}
    warnings = list(state.warnings)
    
    # 필수 필드가 없으면 기본값 설정
    if "health_score" not in diagnosis:
        diagnosis["health_score"] = 50  # 중립 점수
        warnings.append("일부 분석이 실패하여 기본 점수를 사용합니다.")
    
    if "health_level" not in diagnosis:
        score = diagnosis.get("health_score", 50)
        if score >= 80:
            diagnosis["health_level"] = "good"
        elif score >= 60:
            diagnosis["health_level"] = "fair"
        elif score >= 40:
            diagnosis["health_level"] = "warning"
        else:
            diagnosis["health_level"] = "bad"
    
    if "onboarding_score" not in diagnosis:
        diagnosis["onboarding_score"] = diagnosis.get("health_score", 50)
    
    if "onboarding_level" not in diagnosis:
        diagnosis["onboarding_level"] = diagnosis.get("health_level", "unknown")
    
    logger.info("Using partial result for recovery")
    
    return {
        "diagnosis_result": diagnosis,
        "warnings": warnings,
        "error": None,  # 에러 클리어
        "next_node_override": "__end__",
        "step": state.step + 1,
    }


def route_to_recovery(state: SupervisorState) -> str:
    """에러 발생 시 복구 노드로 라우팅."""
    if state.error:
        return "smart_error_recovery_node"
    return "quality_check_node"
