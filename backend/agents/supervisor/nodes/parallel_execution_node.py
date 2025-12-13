"""
Parallel Execution Node
Supervisor에서 여러 에이전트를 병렬로 실행하는 노드입니다.
"""

import logging
import asyncio
import time
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.diagnosis_handler_node import run_diagnosis_agent_node
from backend.agents.supervisor.nodes.security_handler_node import run_security_agent_node
from backend.agents.supervisor.nodes.onboarding_handler_node import run_onboarding_agent_node
# contributor is now handled by onboarding_handler_node (Unified Onboarding Agent)

logger = logging.getLogger(__name__)

async def run_additional_agents_node(state: SupervisorState) -> Dict[str, Any]:
    """추가 에이전트 병렬 실행 (멀티 에이전트 협업)
    
    asyncio.gather를 사용하여 여러 에이전트를 동시에 실행합니다.
    이를 통해 진단 후 보안 분석 등을 병렬로 처리하여 응답 시간을 단축합니다.
    """
    
    additional_agents = state.get("additional_agents", [])
    
    if not additional_agents:
        return {}
    
    start_time = time.time()
    logger.info(f"[PARALLEL] Starting {len(additional_agents)} additional agents in parallel: {additional_agents}")
    
    multi_agent_results = dict(state.get("multi_agent_results", {}))
    
    # 메인 에이전트 결과 저장
    main_result = state.get("agent_result")
    target_agent = state.get("target_agent")
    if main_result and target_agent:
        multi_agent_results[target_agent] = main_result
    
    # 에이전트 실행 함수 매핑
    agent_runners = {
        "diagnosis": run_diagnosis_agent_node,
        "security": run_security_agent_node,
        "onboarding": run_onboarding_agent_node,
        "contributor": run_onboarding_agent_node,  # contributor → onboarding (Unified)
    }
    
    # 병렬 실행할 태스크 생성
    async def run_agent(agent_name: str):
        """개별 에이전트 실행 래퍼"""
        agent_start = time.time()
        try:
            runner = agent_runners.get(agent_name)
            if runner:
                logger.info(f"[PARALLEL] Starting agent: {agent_name} at T+{agent_start - start_time:.2f}s")
                result = await runner(state)
                elapsed = time.time() - agent_start
                logger.info(f"[PARALLEL] Completed agent: {agent_name} in {elapsed:.2f}s")
                return (agent_name, result.get("agent_result", result))
            else:
                logger.warning(f"Unknown agent: {agent_name}")
                return (agent_name, {"error": f"Unknown agent: {agent_name}"})
        except Exception as e:
            logger.error(f"Additional agent {agent_name} failed: {e}")
            return (agent_name, {"error": str(e)})
    
    # 모든 에이전트를 병렬로 실행
    tasks = [run_agent(agent_name) for agent_name in additional_agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_elapsed = time.time() - start_time
    
    # 결과 수집
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Agent task failed with exception: {result}")
            continue
        if isinstance(result, tuple) and len(result) == 2:
            agent_name, agent_result = result
            multi_agent_results[agent_name] = agent_result
    
    logger.info(f"[PARALLEL] All {len(additional_agents)} agents completed in {total_elapsed:.2f}s total")
    logger.info(f"[PARALLEL] Results: {list(multi_agent_results.keys())}")
    
    # security_result를 별도로 추출하여 프론트엔드에서 직접 접근할 수 있게 함
    security_result = multi_agent_results.get("security")
    onboarding_result = multi_agent_results.get("onboarding")
    
    return {
        "multi_agent_results": multi_agent_results,
        "security_result": security_result,  # 프론트엔드에서 직접 접근 가능
        "onboarding_result": onboarding_result,  # 온보딩 결과도 직접 접근 가능
        "iteration": state.get("iteration", 0) + 1
    }
