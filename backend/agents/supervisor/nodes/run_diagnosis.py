"""Diagnosis Agent 호출 노드."""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

from backend.agents.diagnosis.service import run_diagnosis

from ..models import SupervisorState, DEFAULT_INTENT

logger = logging.getLogger(__name__)

# 진단 결과 캐시 (repo+intent 기반 중복 실행 방지)
_diagnosis_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 50


def _make_cache_key(repo: dict, intent: str, sub_intent: str) -> str:
    """repo+intent+sub_intent로 캐시 키 생성."""
    key_str = f"{repo.get('owner')}/{repo.get('name')}:{intent}:{sub_intent}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_cached_result(key: str) -> Optional[dict]:
    """캐시된 진단 결과 조회."""
    return _diagnosis_cache.get(key)


def _set_cached_result(key: str, result: dict) -> None:
    """진단 결과 캐시 저장 (최대 크기 제한)."""
    if len(_diagnosis_cache) >= _CACHE_MAX_SIZE:
        # 가장 오래된 항목 제거 (단순 FIFO)
        oldest_key = next(iter(_diagnosis_cache))
        del _diagnosis_cache[oldest_key]
    _diagnosis_cache[key] = result


def clear_diagnosis_cache() -> int:
    """진단 캐시 초기화. 삭제된 항목 수 반환."""
    count = len(_diagnosis_cache)
    _diagnosis_cache.clear()
    return count


def run_diagnosis_node(state: SupervisorState) -> SupervisorState:
    """Diagnosis Agent 호출. intent=analyze일 때만 실행."""
    intent = state.get("intent", DEFAULT_INTENT)
    if intent != "analyze":
        logger.debug("[run_diagnosis_node] intent=%s, 진단 건너뜀", intent)
        return state
    
    repo = state.get("repo")
    
    # repo 정보 없음 에러 처리
    if not repo:
        error_message = """
## 저장소 정보가 필요합니다

진단을 수행하려면 GitHub 저장소를 지정해 주세요.

### 예시
- "facebook/react 상태 분석해줘"
- "https://github.com/vuejs/vue 건강 점수 알려줘"
- "이 저장소에 기여하고 싶어: owner/repo"

### 지표 개념이 궁금하시다면?
저장소 없이도 지표에 대한 설명은 가능합니다:
- "온보딩 용이성이 뭐야?"
- "Health Score가 어떻게 계산돼?"
""".strip()
        
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_state["llm_summary"] = error_message
        new_state["diagnosis_result"] = {"error": "no_repo"}
        
        # history에 에러 응답 추가
        history = list(state.get("history", []))
        history.append({"role": "assistant", "content": error_message})
        new_state["history"] = history
        
        logger.warning("[run_diagnosis_node] repo 정보 없음, 에러 반환")
        return new_state

    diagnosis_task_type = state.get("diagnosis_task_type", "none")
    if diagnosis_task_type == "none":
        return state

    repo = state["repo"]
    user_context = state.get("user_context", {})
    sub_intent = state.get("sub_intent", "health")
    diagnosis_needs = state.get("diagnosis_needs")
    user_query = state.get("user_query", "")
    
    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")
    
    # 중복 실행 방지: 캐시 체크
    cache_key = _make_cache_key(repo, intent, sub_intent)
    cached_result = _get_cached_result(cache_key)
    
    if cached_result:
        logger.info(
            "[run_diagnosis_node] 캐시 히트: %s/%s (%s.%s)",
            repo.get("owner"), repo.get("name"), intent, sub_intent
        )
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_state["diagnosis_result"] = cached_result
        new_state["_from_cache"] = True
        return new_state

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
    
    # 결과 캐시 저장
    _set_cached_result(cache_key, diagnosis_result)

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
    new_state["last_explain_target"] = None
    new_state["explain_metrics"] = []
    
    # 비교 모드: 두 번째 저장소도 진단 (sub_intent == "compare")
    compare_repo = state.get("compare_repo")
    if sub_intent == "compare" and compare_repo:
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
