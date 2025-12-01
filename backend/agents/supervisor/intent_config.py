"""
Intent 중앙 설정

모든 Intent 관련 설정을 한 곳에서 관리합니다.
새 Intent 추가 시 이 파일만 수정하면 됩니다.

## 새 구조 (v2): 3개 Intent + SubIntent
- SupervisorIntent: analyze | followup | general_qa
- SubIntent: health | onboarding | compare | explain | refine | concept | chat
- INTENT_META: (intent, sub_intent) 튜플 키로 라우팅 플래그 관리

## Intent 추가 체크리스트
1. INTENT_META에 새 (intent, sub_intent) 조합 추가
2. (필요시) summarize_node.py에 응답 형식 규칙 추가
3. (필요시) intent_classifier.py 프롬프트에 분류 예시 추가
4. (필요시) 테스트 파일 추가
"""
from __future__ import annotations

from typing import Literal, TypedDict, List, Tuple

from .models import (
    SupervisorIntent, 
    SubIntent,
    AnswerKind,
    VALID_INTENTS,
    VALID_SUB_INTENTS,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)


# =============================================================================
# 레거시 Intent 타입 (기존 7개 - 하위 호환용)
# =============================================================================

LegacyIntent = Literal[
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
    "concept_qa_metric",
    "concept_qa_process",
]

VALID_LEGACY_INTENTS: List[LegacyIntent] = [
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
    "concept_qa_metric",
    "concept_qa_process",
]

# 사용자 레벨 타입
UserLevel = Literal["beginner", "intermediate", "advanced"]

VALID_USER_LEVELS: List[UserLevel] = ["beginner", "intermediate", "advanced"]

# Follow-up 타입
FollowupType = Literal[
    "refine_easier",       # "더 쉬운 거 없어?"
    "refine_harder",       # "더 어려운 거?"
    "refine_different",    # "다른 종류는?"
    "ask_detail",          # "이거 더 자세히"
    "compare_similar",     # "비슷한 repo는?"
    "continue_same",       # 같은 repo 계속 분석
]

VALID_FOLLOWUP_TYPES: List[FollowupType] = [
    "refine_easier",
    "refine_harder", 
    "refine_different",
    "ask_detail",
    "compare_similar",
    "continue_same",
]


# =============================================================================
# Intent 메타데이터 구조
# =============================================================================

class IntentMeta(TypedDict):
    """
    (intent, sub_intent) 조합별 라우팅 메타데이터
    
    Supervisor가 어떤 경로를 타야 하는지 결정하는 플래그입니다.
    - requires_repo: True면 repo가 없을 때 에러 메시지
    - runs_diagnosis: True면 Diagnosis Agent 실행
    - requires_previous_result: True면 이전 분석 결과 필요
    """
    requires_repo: bool             # repo 정보 필요 여부
    runs_diagnosis: bool            # Diagnosis Agent 실행 여부
    requires_previous_result: bool  # 이전 분석 결과 필요 여부


# =============================================================================
# 2차원 INTENT_META (핵심 테이블)
# =============================================================================

# (intent, sub_intent) 튜플 키로 메타데이터 매핑
INTENT_META: dict[Tuple[str, str], IntentMeta] = {
    # analyze: 새로운 분석 요청 (repo 필수, Diagnosis 실행)
    ("analyze", "health"): {
        "requires_repo": True,
        "runs_diagnosis": True,
        "requires_previous_result": False,
    },
    ("analyze", "onboarding"): {
        "requires_repo": True,
        "runs_diagnosis": True,
        "requires_previous_result": False,
    },
    ("analyze", "compare"): {
        "requires_repo": True,  # 실제로는 2개 필요 - 별도 검증
        "runs_diagnosis": True,
        "requires_previous_result": False,
    },
    
    # followup: 후속 질문 (repo 기준으로 Diagnosis 재실행)
    # 이전 결과 의존 제거 - 매번 독립적으로 Diagnosis 실행
    ("followup", "explain"): {
        "requires_repo": True,
        "runs_diagnosis": True,
        "requires_previous_result": False,
    },
    ("followup", "refine"): {
        "requires_repo": True,
        "runs_diagnosis": True,
        "requires_previous_result": False,
    },
    
    # general_qa: 일반 질문 (repo 불필요, Diagnosis 불필요)
    ("general_qa", "concept"): {
        "requires_repo": False,
        "runs_diagnosis": False,
        "requires_previous_result": False,
    },
    ("general_qa", "chat"): {
        "requires_repo": False,
        "runs_diagnosis": False,
        "requires_previous_result": False,
    },
}

# Fallback 메타데이터 (새 조합이 튀어나왔을 때 사용)
DEFAULT_INTENT_META: IntentMeta = {
    "requires_repo": False,
    "runs_diagnosis": False,
    "requires_previous_result": False,
}


# =============================================================================
# Answer Kind 매핑 (UI 배지 표시용)
# =============================================================================

# (intent, sub_intent) 조합 → AnswerKind 매핑
# - report: 진단 리포트 (새 분석 결과)
# - explain: 점수 해설 (기존 결과 상세 설명)
# - refine: Task 필터링 (조건에 맞게 Task 재정렬)
# - concept: 개념 설명 (지표/프로세스 교육)
# - chat: 일반 대화 (인사, 잡담)
ANSWER_KIND_MAP: dict[tuple[str, str], AnswerKind] = {
    # analyze: 진단 리포트
    ("analyze", "health"): "report",
    ("analyze", "onboarding"): "report",
    ("analyze", "compare"): "report",
    
    # followup: 해설/필터링
    ("followup", "explain"): "explain",
    ("followup", "refine"): "refine",
    
    # general_qa: 개념/대화
    ("general_qa", "concept"): "concept",
    ("general_qa", "chat"): "chat",
}

# 기본 AnswerKind (매핑되지 않는 조합)
DEFAULT_ANSWER_KIND: AnswerKind = "chat"


def get_answer_kind(intent: str, sub_intent: str | None = None) -> AnswerKind:
    """
    (intent, sub_intent) 조합의 AnswerKind 조회.
    
    UI에서 응답 유형에 따라 다른 배지를 표시하는 데 사용됩니다.
    - report: 진단 리포트 📊
    - explain: 점수 해설 💡
    - refine: Task 필터링 🔍
    - concept: 개념 설명 📚
    - chat: 일반 대화 💬
    
    Args:
        intent: analyze | followup | general_qa
        sub_intent: health | onboarding | compare | explain | refine | concept | chat
    
    Returns:
        AnswerKind (report/explain/refine/concept/chat)
    
    없는 조합이면 DEFAULT_ANSWER_KIND("chat") 반환 + 경고 로그.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    sub_intent = sub_intent or DEFAULT_SUB_INTENT
    
    answer_kind = ANSWER_KIND_MAP.get((intent, sub_intent))
    if answer_kind is not None:
        return answer_kind
    
    # Fallback: 경고 로그 + 기본값 반환
    logger.warning(
        f"Unknown (intent, sub_intent) combination: ({intent}, {sub_intent}). "
        f"Using default answer_kind: {DEFAULT_ANSWER_KIND}"
    )
    return DEFAULT_ANSWER_KIND


# =============================================================================
# 레거시 Intent 설정 (하위 호환)
# =============================================================================

class IntentConfigEntry(TypedDict):
    """개별 Intent 설정 (레거시)"""
    needs_diagnosis: bool           # 진단 실행 필요 여부
    prompt_kind: str                # 프롬프트 종류 (health, onboarding, explain_scores, etc.)
    diagnosis_task_type: str        # Diagnosis Agent task_type 매핑
    is_ready: bool                  # 기능 준비 완료 여부
    description: str                # Intent 설명 (문서화용)


INTENT_CONFIG: dict[LegacyIntent, IntentConfigEntry] = {
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
        "needs_diagnosis": False,
        "prompt_kind": "explain_scores",
        "diagnosis_task_type": "none",
        "is_ready": True,
        "description": "점수 계산 방식 및 근거 상세 설명",
    },
    "compare_two_repos": {
        "needs_diagnosis": True,
        "prompt_kind": "compare",
        "diagnosis_task_type": "health_plus_onboarding",
        "is_ready": True,
        "description": "두 저장소 비교 분석",
    },
    "refine_onboarding_tasks": {
        "needs_diagnosis": False,
        "prompt_kind": "refine_tasks",
        "diagnosis_task_type": "reuse_last_onboarding_result",
        "is_ready": True,
        "description": "Task 필터링 및 재정렬 (더 쉬운/어려운 Task 요청)",
    },
    "concept_qa_metric": {
        "needs_diagnosis": False,
        "prompt_kind": "concept_qa_metric",
        "diagnosis_task_type": "none",
        "is_ready": True,
        "description": "지표 개념 설명 (온보딩 용이성, Health Score 등)",
    },
    "concept_qa_process": {
        "needs_diagnosis": False,
        "prompt_kind": "concept_qa_process",
        "diagnosis_task_type": "none",
        "is_ready": True,
        "description": "OSS 기여 프로세스/절차 설명",
    },
}


# =============================================================================
# 2차원 INTENT_META 헬퍼 함수 (새 구조)
# =============================================================================

def get_intent_meta(intent: str, sub_intent: str | None = None) -> IntentMeta:
    """
    (intent, sub_intent) 조합의 라우팅 메타데이터 조회.
    
    Args:
        intent: analyze | followup | general_qa
        sub_intent: health | onboarding | compare | explain | refine | concept | chat
    
    Returns:
        IntentMeta 플래그 (requires_repo, runs_diagnosis, requires_previous_result)
    
    없는 조합이면 DEFAULT_INTENT_META 반환 (시스템 죽지 않음).
    """
    # sub_intent 기본값 처리
    sub_intent = sub_intent or DEFAULT_SUB_INTENT
    
    meta = INTENT_META.get((intent, sub_intent))
    if meta is not None:
        return meta
    
    # Fallback: 기본 메타데이터 반환
    return DEFAULT_INTENT_META


def should_run_diagnosis(intent: str, sub_intent: str | None = None) -> bool:
    """
    해당 (intent, sub_intent) 조합이 Diagnosis Agent 실행이 필요한지 확인.
    """
    return get_intent_meta(intent, sub_intent)["runs_diagnosis"]


def intent_requires_repo(intent: str, sub_intent: str | None = None) -> bool:
    """
    해당 조합이 repo 정보를 필수로 하는지 확인.
    False면 repo 없이도 실행 가능 (general_qa 등).
    """
    return get_intent_meta(intent, sub_intent)["requires_repo"]


def intent_requires_previous_result(intent: str, sub_intent: str | None = None) -> bool:
    """
    해당 조합이 이전 분석 결과를 필요로 하는지 확인.
    True면 diagnosis_result 또는 last_task_list가 없을 때 에러.
    """
    return get_intent_meta(intent, sub_intent)["requires_previous_result"]


def is_concept_qa(intent: str, sub_intent: str | None = None) -> bool:
    """
    Concept QA인지 확인 (repo 불필요, diagnosis 불필요).
    """
    return intent == "general_qa" and sub_intent in ("concept", "chat")


def is_chat(intent: str, sub_intent: str | None = None) -> bool:
    """
    일반 대화/인사인지 확인.
    """
    return intent == "general_qa" and sub_intent == "chat"


# =============================================================================
# 레거시 헬퍼 함수 (하위 호환)
# =============================================================================

def get_intent_config(intent: str) -> IntentConfigEntry:
    """Intent 설정 조회 (레거시). 없으면 기본값(health) 반환."""
    if intent in INTENT_CONFIG:
        return INTENT_CONFIG[intent]  # type: ignore
    return INTENT_CONFIG["diagnose_repo_health"]


def needs_diagnosis(intent: str) -> bool:
    """해당 Intent가 진단 실행이 필요한지 확인 (레거시)"""
    return get_intent_config(intent)["needs_diagnosis"]


def get_prompt_kind(intent: str) -> str:
    """해당 Intent의 프롬프트 종류 반환 (레거시)"""
    return get_intent_config(intent)["prompt_kind"]


def get_diagnosis_task_type(intent: str) -> str:
    """해당 Intent의 Diagnosis task_type 반환 (레거시)"""
    return get_intent_config(intent)["diagnosis_task_type"]


def is_intent_ready(intent: str) -> bool:
    """해당 Intent가 사용 가능한지 확인 (레거시)"""
    # 새 구조에서는 모든 조합이 ready
    if intent in INTENT_CONFIG:
        return INTENT_CONFIG[intent]["is_ready"]  # type: ignore
    return True  # 새 intent도 ready로 처리


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
    Intent 유효성 검사 (새 구조).
    유효하지 않은 값이면 'analyze'로 기본 설정.
    """
    if intent in VALID_INTENTS:
        return intent  # type: ignore
    return DEFAULT_INTENT


def validate_sub_intent(sub_intent: str | None) -> SubIntent:
    """
    SubIntent 유효성 검사.
    유효하지 않은 값이면 'health'로 기본 설정.
    """
    if sub_intent in VALID_SUB_INTENTS:
        return sub_intent  # type: ignore
    return DEFAULT_SUB_INTENT


def validate_followup_type(followup_type: str | None) -> FollowupType | None:
    """
    Follow-up 타입 유효성 검사.
    유효하지 않은 값이면 None 반환.
    """
    if followup_type in VALID_FOLLOWUP_TYPES:
        return followup_type  # type: ignore
    return None


def is_refine_intent(intent: str, sub_intent: str | None = None) -> bool:
    """해당 조합이 리파인(재필터링) 관련인지 확인"""
    return intent == "followup" and sub_intent == "refine"


def requires_previous_context(intent: str, sub_intent: str | None, followup_type: str | None = None) -> bool:
    """
    해당 조합이 이전 컨텍스트(last_repo, last_task_list)를 필요로 하는지 확인.
    """
    # 새 구조에서는 INTENT_META 기반
    if intent_requires_previous_result(intent, sub_intent):
        return True
    # followup_type 기반 추가 체크
    if followup_type in ["refine_easier", "refine_harder", "refine_different", "continue_same"]:
        return True
    return False


# 레거시 함수 별칭 (기존 코드 호환)
def is_concept_qa_intent(intent: str) -> bool:
    """레거시: Concept QA Intent인지 확인"""
    return intent in ("concept_qa_metric", "concept_qa_process")
