"""
Diagnosis Handler Node
Supervisor에서 Diagnosis Agent를 호출하고 결과를 처리하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.agents.diagnosis.graph import run_diagnosis
from backend.agents.shared.metacognition import (
    AgentResult, QualityChecker, Source, QualityLevel,
    create_github_source
)
from backend.common.cache_manager import get_cache_manager
from backend.agents.supervisor.utils import check_repo_size_and_warn
# Eval trace hooks
from backend.eval.trace_collector import trace_agent_start, trace_agent_end

logger = logging.getLogger(__name__)

async def run_diagnosis_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """진단 Agent 실행 (캐시 우선 + 보안 분석 자동 추가 + 메타인지)
    
    이미 진단 결과가 세션 컨텍스트에 있거나 캐시에 있으면 재사용합니다.
    """
    logger.info("Running Diagnosis Agent V2")
    trace_agent_start("diagnosis", "FULL")
    
    owner = state["owner"]
    repo = state["repo"]
    ref = state.get("ref", "main")
    
    # 1. 세션 컨텍스트에서 기존 진단 결과 확인
    accumulated_context = state.get("accumulated_context", {})
    cached_diagnosis = accumulated_context.get("diagnosis_result")
    
    if cached_diagnosis and isinstance(cached_diagnosis, dict):
        health_score = cached_diagnosis.get("health_score")
        if health_score is not None:
            logger.info(f"Using cached diagnosis from session context (health_score: {health_score})")
            cached_diagnosis["from_cache"] = True
            cached_diagnosis["cache_source"] = "session_context"
            return {
                "agent_result": cached_diagnosis,
                "diagnosis_result": cached_diagnosis,
                "target_agent": "diagnosis",
                "additional_agents": ["security"],
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 2. 글로벌 캐시에서 확인 (24시간 TTL)
    cache_manager = get_cache_manager()
    cache_key = f"diagnosis:{owner}/{repo}:{ref}"
    cached_result = cache_manager.get(cache_key)
    
    if cached_result and isinstance(cached_result, dict):
        health_score = cached_result.get("health_score")
        if health_score is not None:
            logger.info(f"Using cached diagnosis from global cache (health_score: {health_score})")
            cached_result["from_cache"] = True
            cached_result["cache_source"] = "global_cache"
            return {
                "agent_result": cached_result,
                "diagnosis_result": cached_result,
                "target_agent": "diagnosis",
                "additional_agents": ["security"],
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 3. 캐시 미스 - 새로 진단 실행
    logger.info("Cache miss - running fresh diagnosis")
    
    import asyncio
    
    # 대용량 저장소 체크 (첫 분석일 때만)
    repo_size_info = await check_repo_size_and_warn(owner, repo)
    
    # 대용량 저장소 경고 메시지 추가
    warning_message = None
    if repo_size_info["is_large"]:
        warning_message = repo_size_info["warning_message"]
        logger.info(f"Large repo warning: {warning_message}")
        
        # 웹소켓으로 즉시 전송
        session_id = state.get("session_id")
        if session_id:
            try:
                from backend.api.websocket_router import manager
                await manager.send_json(session_id, {
                    "type": "warning",
                    "message": warning_message
                })
                logger.info(f"Sent large repo warning to session {session_id}")
            except ImportError:
                logger.warning("Could not import websocket manager (circular import avoided)")
            except Exception as e:
                logger.warning(f"Failed to send warning over websocket: {e}")
    
    result = await run_diagnosis(
        owner=owner,
        repo=repo,
        ref=ref,
        user_message=state["user_message"],
        supervisor_intent=state.get("supervisor_intent")
    )
    
    # 진단 결과에 type 명시
    if isinstance(result, dict) and "type" not in result:
        result["type"] = "full_diagnosis"
    
    # 4. 결과를 글로벌 캐시에 저장 (24시간 TTL)
    if result and not result.get("error"):
        cache_manager.set(cache_key, result, ttl_hours=24)
        logger.info(f"Diagnosis result cached: {cache_key}")
    
    # 메타인지: 품질 체크 및 근거 수집
    quality_level, confidence, gaps = QualityChecker.evaluate_diagnosis(result)
    
    # 근거 수집 (분석에 사용된 파일들)
    sources = []
    documentation = result.get("documentation", {})
    if isinstance(documentation, dict):
        if documentation.get("readme_present"):
            sources.append(create_github_source(owner, repo, "README.md", "README.md"))
        if documentation.get("contributing_present"):
            sources.append(create_github_source(owner, repo, "CONTRIBUTING.md", "CONTRIBUTING.md"))
    
    # 메타인지 로그 출력
    logger.info(f"[METACOGNITION] Diagnosis completed:")
    logger.info(f"  - Quality: {quality_level.value} (confidence: {confidence:.2f})")
    logger.info(f"  - Sources: {len(sources)} files")
    if gaps:
        logger.info(f"  - Gaps: {', '.join(gaps)}")
    
    # 결과에 대용량 저장소 정보 추가
    if warning_message:
        result["large_repo_warning"] = warning_message
        result["repo_stats"] = repo_size_info.get("repo_stats", {})
    
    # Trace hook: 진단 완료
    trace_agent_end("diagnosis", "FULL", ok=not result.get("error"))
    
    return {
        "agent_result": result,
        "diagnosis_result": result,  # finalize에서 사용
        "target_agent": "diagnosis",
        "additional_agents": ["security"],  # 보안 분석 자동 추가!
        "iteration": state.get("iteration", 0) + 1,
        "large_repo_warning": warning_message  # 대용량 경고 전달
    }

