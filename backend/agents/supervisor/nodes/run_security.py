"""
Security Agent 호출 노드

SupervisorState를 기반으로 Security Agent를 호출하여 의존성 및 보안 분석을 수행한다.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.agents.security.service import run_security_analysis

from ..models import SupervisorState

logger = logging.getLogger(__name__)


def run_security_node(state: SupervisorState) -> SupervisorState:
    """
    Security Agent 호출 노드

    state.repo를 기반으로 보안 분석을 수행한다.
    의존성 분석, 보안 점수 계산, 취약점 체크, 개선 제안을 포함한다.

    Args:
        state: SupervisorState

    Returns:
        SupervisorState: security_result가 추가된 상태
    """
    if "repo" not in state:
        raise ValueError("run_security_node: state['repo']가 없습니다.")

    repo = state["repo"]
    security_task_type = state.get("security_task_type", "full")

    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")

    # 보안 분석 시작
    if progress_cb:
        progress_cb("보안 분석 시작", f"{repo.get('owner')}/{repo.get('name')} 의존성 검사 중...")

    security_input = _build_security_input(repo, security_task_type)

    logger.info(
        "[run_security_node] repo=%s/%s, security_task_type=%s",
        repo.get("owner"),
        repo.get("name"),
        security_task_type,
    )

    if progress_cb:
        progress_cb("의존성 파일 탐색", "레포지토리에서 의존성 파일 찾는 중...")

    security_result = run_security_analysis(security_input)

    # 보안 점수 추출
    security_score = security_result.get("security_score", {})

    if progress_cb:
        score = security_score.get("score", "N/A")
        grade = security_score.get("grade", "N/A")
        progress_cb("보안 분석 완료", f"Security Grade: {grade} (Score: {score})")

    logger.info(
        "[run_security_node] security analysis completed, grade=%s, score=%s, deps=%s",
        security_score.get("grade"),
        security_score.get("score"),
        security_result.get("dependency_analysis", {}).get("total_dependencies", 0),
    )

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    new_state["security_result"] = security_result

    return new_state


def _build_security_input(
    repo: dict[str, Any],
    security_task_type: str,
) -> dict[str, Any]:
    """Security 서비스 호출을 위한 입력 데이터 구성"""
    return {
        "owner": repo["owner"],
        "repo": repo["name"],
        "analysis_type": _map_to_security_service_analysis_type(security_task_type),
        "max_workers": 5,
        "include_suggestions": True,
    }


def _map_to_security_service_analysis_type(security_task_type: str) -> str:
    """
    Supervisor의 security_task_type을 Security 서비스의 analysis_type으로 변환

    Security 서비스는 'dependencies', 'vulnerabilities', 'full'을 지원.
    """
    mapping = {
        "dependencies_only": "dependencies",
        "vulnerabilities_only": "vulnerabilities",
        "full": "full",
    }
    return mapping.get(security_task_type, "full")
