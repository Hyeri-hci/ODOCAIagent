"""
Intent 중앙 설정

모든 Intent 관련 설정을 한 곳에서 관리합니다.
새 Intent 추가 시 이 파일만 수정하면 됩니다.

## Intent 추가 체크리스트
1. INTENT_CONFIG에 새 Intent 정의 추가
2. (필요시) prompts.py에 새 프롬프트 상수 추가
3. (필요시) intent_classifier.py 프롬프트에 새 Intent 설명 추가
4. (필요시) 테스트 파일 추가
"""
from __future__ import annotations

from typing import Literal, TypedDict, List


# =============================================================================
# Intent 타입 정의
# =============================================================================

SupervisorIntent = Literal[
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
]

VALID_INTENTS: List[SupervisorIntent] = [
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
]

# 사용자 레벨 타입
UserLevel = Literal["beginner", "intermediate", "advanced"]

VALID_USER_LEVELS: List[UserLevel] = ["beginner", "intermediate", "advanced"]


# =============================================================================
# Intent 설정 구조
# =============================================================================

class IntentConfigEntry(TypedDict):
    """개별 Intent 설정"""
    needs_diagnosis: bool           # 진단 실행 필요 여부
    prompt_kind: str                # 프롬프트 종류 (health, onboarding, explain_scores, etc.)
    diagnosis_task_type: str        # Diagnosis Agent task_type 매핑
    is_ready: bool                  # 기능 준비 완료 여부
    description: str                # Intent 설명 (문서화용)


# =============================================================================
# Intent 중앙 설정 테이블
# =============================================================================

INTENT_CONFIG: dict[SupervisorIntent, IntentConfigEntry] = {
    "diagnose_repo_health": {
        "needs_diagnosis": True,
        "prompt_kind": "health",
        "diagnosis_task_type": "health_core",
        "is_ready": True,
        "description": "저장소 건강 상태 분석 및 리포트 생성",
    },
    "diagnose_repo_onboarding": {
        "needs_diagnosis": True,
        "prompt_kind": "onboarding",
        "diagnosis_task_type": "health_plus_onboarding",
        "is_ready": True,
        "description": "온보딩 Task 추천 및 기여 가이드 제공",
    },
    "explain_scores": {
        "needs_diagnosis": True,
        "prompt_kind": "explain_scores",
        "diagnosis_task_type": "explain_scores",
        "is_ready": True,
        "description": "점수 계산 방식 및 근거 상세 설명",
    },
    "compare_two_repos": {
        "needs_diagnosis": True,
        "prompt_kind": "compare",
        "diagnosis_task_type": "health_plus_onboarding",
        "is_ready": False,  # 아직 준비 안 됨
        "description": "두 저장소 비교 분석 (준비 중)",
    },
    "refine_onboarding_tasks": {
        "needs_diagnosis": False,  # 이전 결과 재사용
        "prompt_kind": "refine_tasks",
        "diagnosis_task_type": "reuse_last_onboarding_result",
        "is_ready": False,  # 아직 준비 안 됨
        "description": "Task 필터링 및 재정렬 (준비 중)",
    },
}


# =============================================================================
# 헬퍼 함수
# =============================================================================

def get_intent_config(intent: str) -> IntentConfigEntry:
    """Intent 설정 조회. 없으면 기본값(health) 반환."""
    if intent in INTENT_CONFIG:
        return INTENT_CONFIG[intent]  # type: ignore
    # Fallback: diagnose_repo_health
    return INTENT_CONFIG["diagnose_repo_health"]


def needs_diagnosis(intent: str) -> bool:
    """해당 Intent가 진단 실행이 필요한지 확인"""
    return get_intent_config(intent)["needs_diagnosis"]


def get_prompt_kind(intent: str) -> str:
    """해당 Intent의 프롬프트 종류 반환"""
    return get_intent_config(intent)["prompt_kind"]


def get_diagnosis_task_type(intent: str) -> str:
    """해당 Intent의 Diagnosis task_type 반환"""
    return get_intent_config(intent)["diagnosis_task_type"]


def is_intent_ready(intent: str) -> bool:
    """해당 Intent가 사용 가능한지 확인"""
    return get_intent_config(intent)["is_ready"]


def validate_user_level(level: str | None) -> UserLevel:
    """
    사용자 레벨 유효성 검사.
    유효하지 않은 값이면 'beginner'로 기본 설정.
    """
    if level in VALID_USER_LEVELS:
        return level  # type: ignore
    return "beginner"


def validate_intent(intent: str | None) -> SupervisorIntent:
    """
    Intent 유효성 검사.
    유효하지 않은 값이면 'diagnose_repo_health'로 기본 설정.
    """
    if intent in VALID_INTENTS:
        return intent  # type: ignore
    return "diagnose_repo_health"
