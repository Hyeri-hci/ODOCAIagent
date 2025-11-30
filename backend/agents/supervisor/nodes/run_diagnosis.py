"""
Diagnosis Agent 호출 노드

SupervisorState의 diagnosis_task_type을 기반으로 Diagnosis Agent를 호출한다.
어떤 종류의 진단을 할지는 오직 diagnosis_task_type만이 결정하며,
그 값은 map_task_types_node에서 관리한다.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.agents.diagnosis.service import run_diagnosis

from ..models import SupervisorState

logger = logging.getLogger(__name__)


def run_diagnosis_node(state: SupervisorState) -> SupervisorState:
    """
    Diagnosis Agent 호출 노드
    
    state.repo, user_context, diagnosis_task_type을 기반으로 진단을 수행한다.
    compare_two_repos intent인 경우 compare_repo도 함께 진단한다.
    diagnosis_task_type이 'none'이면 진단을 건너뛴다.
    """
    if "repo" not in state:
        raise ValueError("run_diagnosis_node: state['repo']가 없습니다.")

    diagnosis_task_type = state.get("diagnosis_task_type", "none")
    if diagnosis_task_type == "none":
        return state

    repo = state["repo"]
    user_context = state.get("user_context", {})
    intent = state.get("intent", "")
    diagnosis_needs = state.get("diagnosis_needs")
    user_query = state.get("user_query", "")
    
    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")

    # 첫 번째 저장소 진단
    if progress_cb:
        progress_cb("저장소 분석 중", f"{repo.get('owner')}/{repo.get('name')} 정보 수집...")
    
    diagnosis_input = _build_diagnosis_input(
        repo, diagnosis_task_type, user_context, diagnosis_needs, user_query
    )

    logger.info(
        "[run_diagnosis_node] repo=%s/%s, diagnosis_task_type=%s",
        repo.get("owner"),
        repo.get("name"),
        diagnosis_task_type,
    )

    if progress_cb:
        progress_cb("GitHub 데이터 수집 중", "커밋, 이슈, PR 활동 분석...")
    
    diagnosis_result = run_diagnosis(diagnosis_input)

    # health_score는 scores 딕셔너리 안에 있음
    scores = diagnosis_result.get("scores", {}) if isinstance(diagnosis_result, dict) else {}
    
    if progress_cb:
        progress_cb("점수 계산 완료", f"Health: {scores.get('health_score', 'N/A')}")
    
    logger.info(
        "[run_diagnosis_node] diagnosis completed, health_score=%s, onboarding_score=%s",
        scores.get("health_score"),
        scores.get("onboarding_score"),
    )

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    new_state["diagnosis_result"] = diagnosis_result
    
    # 비교 모드: 두 번째 저장소도 진단
    compare_repo = state.get("compare_repo")
    if intent == "compare_two_repos" and compare_repo:
        if progress_cb:
            progress_cb("비교 대상 분석 중", f"{compare_repo.get('owner')}/{compare_repo.get('name')}...")
        
        logger.info(
            "[run_diagnosis_node] compare mode: diagnosing second repo=%s/%s",
            compare_repo.get("owner"),
            compare_repo.get("name"),
        )
        
        compare_input = _build_diagnosis_input(
            compare_repo, diagnosis_task_type, user_context, diagnosis_needs, user_query
        )
        compare_result = run_diagnosis(compare_input)
        
        compare_scores = compare_result.get("scores", {}) if isinstance(compare_result, dict) else {}
        logger.info(
            "[run_diagnosis_node] compare diagnosis completed, health_score=%s",
            compare_scores.get("health_score"),
        )
        
        new_state["compare_diagnosis_result"] = compare_result
    
    return new_state


def _build_diagnosis_input(
    repo: dict[str, Any],
    diagnosis_task_type: str,
    user_context: dict[str, Any],
    diagnosis_needs: dict[str, bool] | None = None,
    user_query: str = "",
) -> dict[str, Any]:
    """Diagnosis 서비스 호출을 위한 입력 데이터 구성"""
    return {
        "owner": repo["owner"],
        "repo": repo["name"],
        "task_type": _map_to_diagnosis_service_task_type(diagnosis_task_type),
        "focus": ["documentation", "activity"],
        "user_context": user_context,
        "needs": diagnosis_needs,  # Phase 실행 분기용
        "user_query": user_query,  # 미래 확장용
    }


def _map_to_diagnosis_service_task_type(diagnosis_task_type: str) -> str:
    """
    Supervisor의 diagnosis_task_type을 Diagnosis 서비스의 task_type으로 변환
    
    Diagnosis 서비스는 현재 'full_diagnosis', 'docs_only', 'activity_only'를 지원.
    Supervisor 레벨의 task_type과 Diagnosis 서비스 task_type 간 매핑.
    """
    mapping = {
        "health_core": "full_diagnosis",
        "health_plus_onboarding": "full_diagnosis",
        "reuse_last_onboarding_result": "full_diagnosis",
        "explain_scores": "full_diagnosis",
    }
    return mapping.get(diagnosis_task_type, "full_diagnosis")
