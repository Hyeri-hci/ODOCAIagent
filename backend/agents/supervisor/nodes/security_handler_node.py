"""
Security Handler Node
Supervisor에서 Security Agent를 호출하고 결과를 처리하는 노드입니다.
"""

import os
import logging
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.common.cache_manager import get_cache_manager
from backend.agents.supervisor.utils import check_repo_size_and_warn
from backend.agents.security.agent.security_agent import SecurityAgent

logger = logging.getLogger(__name__)

async def run_security_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """보안 Agent 실행 (캐시 우선 + SecurityAgent 연결)
    
    이미 보안 분석 결과가 세션 컨텍스트에 있거나 캐시에 있으면 재사용합니다.
    """
    logger.info("Running Security Agent")
    
    owner = state.get("owner", "")
    repo = state.get("repo", "")
    ref = state.get("ref", "main")
    
    # 1. 세션 컨텍스트에서 기존 보안 결과 확인
    accumulated_context = state.get("accumulated_context", {})
    # update_session_node에서 'security_scan'으로 저장하므로 그 키로 확인
    cached_security = accumulated_context.get("security_scan") or accumulated_context.get("security_result")
    
    if cached_security and isinstance(cached_security, dict):
        security_score = cached_security.get("results", {}).get("security_score") or cached_security.get("security_score")
        if security_score is not None:
            logger.info(f"Using cached security from session context (score: {security_score})")
            cached_security["from_cache"] = True
            cached_security["cache_source"] = "session_context"
            return {
                "agent_result": cached_security,
                "security_result": cached_security,
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 2. 글로벌 캐시에서 확인 (12시간 TTL - 보안은 더 자주 갱신)
    cache_manager = get_cache_manager()
    cache_key = f"security:{owner}/{repo}:{ref}"
    cached_result = cache_manager.get(cache_key)
    
    if cached_result and isinstance(cached_result, dict):
        security_score = cached_result.get("results", {}).get("security_score") or cached_result.get("security_score")
        if security_score is not None:
            logger.info(f"Using cached security from global cache (score: {security_score})")
            cached_result["from_cache"] = True
            cached_result["cache_source"] = "global_cache"
            return {
                "agent_result": cached_result,
                "security_result": cached_result,
                "iteration": state.get("iteration", 0) + 1
            }
    
    # 3. 캐시 미스 - 새로 보안 분석 실행
    logger.info("Cache miss - running fresh security analysis")
    
    # 대용량 저장소 체크
    repo_size_info = await check_repo_size_and_warn(owner, repo)
    warning_message = repo_size_info.get("warning_message") if repo_size_info["is_large"] else None
    
    try:
        # SecurityAgent 초기화
        agent = SecurityAgent(
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "gpt-4"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            execution_mode="fast",  # supervisor에서는 빠른 모드 사용
            max_iterations=8,  # 분석 품질을 위해 반복 횟수 조정 (5는 너무 빠름)
        )
        
        # 분석 요청 구성
        user_message = state.get("user_message", "")
        
        # SecurityAgent 실행
        result = await agent.analyze(
            user_request=user_message if user_message else f"{owner}/{repo} 보안 분석",
            owner=owner,
            repository=repo,
            github_token=os.getenv("GITHUB_TOKEN")
        )
        
        logger.info(f"Security analysis completed: success={result.get('success', False)}")
        
        # 4. 결과를 글로벌 캐시에 저장 (12시간 TTL)
        if result and not result.get("error"):
            cache_manager.set(cache_key, result, ttl_hours=12)
            logger.info(f"Security result cached: {cache_key}")
        
        # 메타인지: 보안 분석 품질 체크
        security_score = result.get("results", {}).get("security_score", result.get("security_score"))
        vulnerabilities = result.get("results", {}).get("vulnerabilities", {})
        vuln_count = vulnerabilities.get("total", 0)
        
        if security_score is not None:
            quality = "high"
            confidence = 0.9
        elif vuln_count > 0:
            quality = "medium"
            confidence = 0.7
        else:
            quality = "low"
            confidence = 0.5
        
        logger.info(f"[METACOGNITION] Security completed:")
        logger.info(f"  - Score: {security_score}")
        logger.info(f"  - Vulnerabilities: {vuln_count}")
        logger.info(f"  - Quality: {quality} (confidence: {confidence:.2f})")
        
        # type 필드 추가 (finalize_answer_node에서 사용)
        result["type"] = "security_scan"
        
        # 대용량 저장소 정보 추가
        if warning_message:
            result["large_repo_warning"] = warning_message
        
        return {
            "agent_result": result,
            "security_result": result,  # finalize에서 사용
            "iteration": state.get("iteration", 0) + 1,
            "large_repo_warning": warning_message
        }
        
    except ImportError as e:
        logger.warning(f"SecurityAgent import failed: {e}")
        return {
            "agent_result": {
                "type": "security_scan",
                "message": f"보안 에이전트 모듈 로드 실패: {e}",
                "status": "import_error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception as e:
        logger.error(f"Security analysis failed: {e}")
        return {
            "agent_result": {
                "type": "security_scan",
                "message": f"보안 분석 오류: {e}",
                "status": "error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
