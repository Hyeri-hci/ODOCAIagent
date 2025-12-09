"""
Diagnosis Agent - Router
3가지 실행 경로(Fast/Full/Reinterpret) 라우팅
"""

from typing import Dict, Any, Optional, Literal
from backend.agents.diagnosis.intent_parser import DiagnosisIntentV2
import logging

logger = logging.getLogger(__name__)


def route_diagnosis_request(
    intent: DiagnosisIntentV2,
    cached_result: Optional[Dict[str, Any]] = None
) -> Literal["fast_path", "full_path", "reinterpret_path"]:
    """
    의도에 따라 실행 경로 결정
    
    Args:
        intent: Diagnosis Intent
        cached_result: 캐시된 진단 결과
    
    Returns:
        "fast_path" | "full_path" | "reinterpret_path"
    """
    
    execution_path = intent.execution_path
    
    logger.info(f"Routing diagnosis: path={execution_path}")
    
    # Path 1: Reinterpret (캐시 있고, 재해석 요청)
    if execution_path == "reinterpret":
        if cached_result:
            logger.info("Routing to reinterpret_path (cache available)")
            return "reinterpret_path"
        else:
            logger.warning("Reinterpret requested but no cache, falling back to full_path")
            return "full_path"
    
    # Path 2: Fast (빠른 조회)
    if execution_path == "fast":
        logger.info(f"Routing to fast_path (target={intent.quick_query_target})")
        return "fast_path"
    
    # Path 3: Full (전체 진단, 기본)
    logger.info(f"Routing to full_path (depth={intent.analysis_depth}, force_refresh={intent.force_refresh})")
    return "full_path"


def should_use_cache(
    intent: DiagnosisIntentV2,
    cached_result: Optional[Dict[str, Any]] = None
) -> bool:
    """
    캐시 사용 여부 결정
    
    Args:
        intent: Diagnosis Intent
        cached_result: 캐시된 결과
    
    Returns:
        True if cache should be used
    """
    
    # force_refresh 명시 시 캐시 무시
    if intent.force_refresh:
        logger.info("Cache disabled: force_refresh=True")
        return False
    
    # 캐시가 없으면 사용 불가
    if not cached_result:
        logger.debug("Cache not available")
        return False
    
    # Reinterpret Path는 항상 캐시 사용
    if intent.execution_path == "reinterpret":
        logger.info("Cache enabled for reinterpret path")
        return True
    
    # Fast Path는 캐시 우선
    if intent.execution_path == "fast":
        logger.info("Cache preferred for fast path")
        return True
    
    # Full Path는 캐시 사용 (force_refresh 아니면)
    logger.info("Cache enabled for full path")
    return True


def determine_cache_strategy(
    intent: DiagnosisIntentV2,
    owner: str,
    repo: str,
    ref: str
) -> Dict[str, Any]:
    """
    캐시 전략 결정
    
    Returns:
        {
            "cache_key": "facebook/react@main:diagnosis:standard",
            "use_cache": True,
            "ttl_hours": 6
        }
    """
    
    from backend.common.cache_manager import get_cache_manager
    
    cache_manager = get_cache_manager()
    
    # 캐시 키 생성
    cache_key = cache_manager.make_cache_key(
        owner=owner,
        repo=repo,
        ref=ref,
        analysis_type="diagnosis",
        analysis_depth=intent.analysis_depth
    )
    
    # 사용 여부
    use_cache = not intent.force_refresh
    
    # TTL 결정 (분석 깊이에 따라)
    ttl_map = {
        "quick": 3,      # 3시간
        "standard": 6,   # 6시간
        "thorough": 12   # 12시간
    }
    ttl_hours = ttl_map.get(intent.analysis_depth, 6)
    
    return {
        "cache_key": cache_key,
        "use_cache": use_cache,
        "ttl_hours": ttl_hours
    }
