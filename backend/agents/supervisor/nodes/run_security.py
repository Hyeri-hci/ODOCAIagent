"""
Security Agent 호출 노드

SupervisorState를 기반으로 Security Agent V2를 호출하여 보안 분석을 수행한다.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from .agent_runners import run_security_agent, extract_security_summary
from ..models import SupervisorState

logger = logging.getLogger(__name__)


def run_security_node(state: SupervisorState) -> Dict[str, Any]:
    """
    Security Agent 호출 노드

    state를 기반으로 보안 분석을 수행한다.
    Security Agent V2 (LLM + ReAct 패턴)를 사용한다.

    Args:
        state: SupervisorState

    Returns:
        Dict[str, Any]: security_result가 포함된 업데이트
    """
    owner = state.owner
    repo = state.repo
    
    if not owner or not repo:
        logger.error("run_security_node: owner 또는 repo가 없습니다.")
        return {"error": "owner/repo 정보가 필요합니다.", "security_result": None}

    security_task_type = state.get("security_task_type", "full")
    
    # task_type을 실행 모드로 변환
    mode_map = {
        "dependencies_only": "FAST",
        "vulnerabilities_only": "FULL",
        "full": "FULL",
    }
    mode = mode_map.get(security_task_type, "FULL")

    logger.info(
        "[run_security_node] owner=%s, repo=%s, mode=%s",
        owner,
        repo,
        mode,
    )

    # Security Agent V2 실행 (agent_runners 사용)
    security_result = run_security_agent(state, mode)

    # 에러 체크
    if security_result.get("error"):
        logger.error(f"[run_security_node] Security analysis failed: {security_result.get('error')}")
        return {
            "security_result": security_result,
            "error": security_result.get("error"),
        }

    # 결과 요약 추출
    summary = extract_security_summary(security_result)
    
    logger.info(
        "[run_security_node] security analysis completed, grade=%s, score=%s, vulns=%s",
        summary.get("security_grade"),
        summary.get("security_score"),
        summary.get("vulnerability_count"),
    )

    return {
        "security_result": security_result,
        "security_summary": summary,
    }
