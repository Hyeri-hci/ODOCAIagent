"""
Supervisor 상태 및 타입 정의.

v2: Agentic Orchestrator 지원
- SupervisorPlanOutput: Plan 수립 결과
- InferenceHints: Active Inference 결과
- Event/Artifact 추적 필드 추가
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict, List, Optional, Dict


SupervisorIntent = Literal["analyze", "followup", "general_qa", "smalltalk", "help", "overview"]

SubIntent = Literal[
    "health",
    "onboarding",
    "compare",
    "explain",
    "refine",
    "concept",          # 지표 개념 설명
    "chat",             # 일반 대화
    "greeting",         # 인사 (smalltalk)
    "chitchat",         # 잡담 (smalltalk)
    "getting_started",  # 도움말 (help)
    "repo",             # 레포 개요 (overview)
]

# 라우팅 모드: Fast Chat vs Expert Tool
RoutingMode = Literal["fast_chat", "expert_tool"]

# 응답 종류 (UI 배지 표시용)
AnswerKind = Literal[
    "report",    # 진단 리포트 (analyze → health/onboarding/compare)
    "explain",   # 점수 해설 (followup → explain)
    "refine",    # Task 필터링 (followup → refine)
    "concept",   # 개념 설명 (general_qa → concept)
    "chat",      # 일반 대화 (general_qa → chat)
    "greeting",  # 인사 응답 (smalltalk)
    "help",      # 도움말 (help)
    "overview",  # 레포 개요 (overview)
]

# Explain 모드에서 설명 타깃 구분
ExplainTarget = Literal[
    "metric",              # 점수/지표 설명 (diagnosis_result 기반)
    "task_recommendation", # 온보딩 Task 추천 근거 설명
    "general",             # 일반 대화 기반 (정량 점수 없음)
]

VALID_INTENTS: List[SupervisorIntent] = [
    "analyze", "followup", "general_qa", "smalltalk", "help", "overview"
]
VALID_SUB_INTENTS: List[SubIntent] = [
    "health", "onboarding", "compare", "explain", "refine", 
    "concept", "chat", "greeting", "chitchat", "getting_started", "repo"
]

# 기본값
DEFAULT_INTENT: SupervisorIntent = "analyze"
DEFAULT_SUB_INTENT: SubIntent = "health"


# =============================================================================
# 레거시 호환용 (기존 7개 Intent → 새 구조 매핑)
# =============================================================================

SupervisorTaskType = Literal[
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
    "concept_qa_metric",      # 지표 개념 설명 (repo 불필요)
    "concept_qa_process",     # 프로세스/절차 설명 (repo 불필요)
]

# 레거시 task_type → (intent, sub_intent) 변환 매핑
LEGACY_TASK_TYPE_MAP: dict[str, tuple[SupervisorIntent, SubIntent]] = {
    "diagnose_repo_health": ("analyze", "health"),
    "diagnose_repo_onboarding": ("analyze", "onboarding"),
    "compare_two_repos": ("analyze", "compare"),
    "refine_onboarding_tasks": ("followup", "refine"),
    "explain_scores": ("followup", "explain"),
    "concept_qa_metric": ("general_qa", "concept"),
    "concept_qa_process": ("general_qa", "concept"),
}


def convert_legacy_task_type(task_type: str) -> tuple[SupervisorIntent, SubIntent]:
    """
    레거시 task_type을 새 (intent, sub_intent) 구조로 변환.
    매핑되지 않으면 기본값 ("analyze", "health") 반환.
    """
    return LEGACY_TASK_TYPE_MAP.get(task_type, (DEFAULT_INTENT, DEFAULT_SUB_INTENT))

# Agent별 태스크 타입 (각 Agent 모듈에서 구체화)
DiagnosisTaskType = str
SecurityTaskType = str
RecommendTaskType = str


class DiagnosisNeeds(TypedDict):
    """Diagnosis Agent가 실행할 Phase를 결정하는 플래그"""
    need_health: bool       # 건강 점수 계산 필요
    need_readme: bool       # README 분석 필요
    need_activity: bool     # 활동성(커밋/이슈/PR) 분석 필요
    need_onboarding: bool   # 온보딩 Task 생성 필요


def diagnosis_needs_from_task_type(task_type: str) -> DiagnosisNeeds:
    """
    diagnosis_task_type에서 DiagnosisNeeds를 생성
    
    Supervisor가 결정한 task_type에 따라 Diagnosis가 어떤 Phase를 실행할지 결정합니다.
    
    NOTE: need_onboarding은 항상 True입니다.
    - 온보딩 Task는 항상 계산하고, 요약 단계에서 표시 개수를 조절합니다.
    - health 모드: Task 3개 간략히 표시
    - onboarding 모드: Task 5개+ 상세 표시
    """
    # 온보딩 Task는 항상 계산 (요약에서 표시 개수 조절)
    return {
        "need_health": True,
        "need_readme": True,
        "need_activity": True,
        "need_onboarding": True,  # 항상 True
    }


class RepoInfo(TypedDict):
    """저장소 기본 정보"""
    owner: str
    name: str
    url: str


class UserContext(TypedDict, total=False):
    """사용자 맥락 정보"""
    level: Literal["beginner", "intermediate", "advanced"]
    goal: str
    time_budget_hours: float
    preferred_language: str


class Turn(TypedDict):
    """대화 턴 구조"""
    role: Literal["user", "assistant"]
    content: str


class SupervisorState(TypedDict, total=False):
    """
    Supervisor Agent의 상태 정의
    
    LangGraph 기반 워크플로우에서 노드 간 전달되는 상태 객체.
    
    ## 새 구조 (v2)
    - intent: analyze | followup | general_qa
    - sub_intent: health | onboarding | compare | explain | refine | concept | chat
    - task_type: 레거시 호환용 (기존 7개 Intent)
    """
    # 입력
    user_query: str
    
    # ========================================
    # 새 Intent 구조 (v2)
    # ========================================
    intent: SupervisorIntent           # analyze | followup | general_qa
    sub_intent: SubIntent              # health | onboarding | compare | explain | refine | concept | chat
    
    # 레거시 호환 (기존 7개 Intent)
    task_type: SupervisorTaskType

    # 저장소 정보
    repo: RepoInfo
    compare_repo: RepoInfo
    repos: List[RepoInfo]              # compare용 저장소 리스트 (나중에 확장용)

    # 사용자 맥락
    user_context: UserContext

    # Agent별 태스크 타입 (Supervisor 매핑 노드에서 설정)
    diagnosis_task_type: DiagnosisTaskType
    diagnosis_needs: DiagnosisNeeds  # Diagnosis가 실행할 Phase 결정
    security_task_type: SecurityTaskType
    recommend_task_type: RecommendTaskType

    # Agent 실행 결과
    diagnosis_result: dict[str, Any]
    compare_diagnosis_result: dict[str, Any]

    # 최종 응답
    llm_summary: str
    
    # 응답 메타데이터 (UI 표시용)
    answer_kind: AnswerKind
    last_brief: str
    
    # Explain 모드 타깃 (followup/explain에서 사용)
    explain_target: ExplainTarget      # metric | task_recommendation | general
    explain_metrics: list[str]         # metric 모드에서만 사용 (예: ["health_score", "activity_maintainability"])
    
    # 에러 메시지 (LLM 호출 없이 바로 반환할 때 사용)
    error_message: str

    # 대화 히스토리 (dict 형태로 통일: {"role": "user"|"assistant", "content": "..."})
    history: list[Turn]

    # ========================================
    # 멀티턴 상태 관리 필드
    # ========================================
    
    # 이전 턴 메타데이터 (follow-up 처리용)
    last_repo: RepoInfo
    last_intent: SupervisorIntent
    last_sub_intent: SubIntent
    last_answer_kind: AnswerKind
    last_explain_target: ExplainTarget
    last_task_list: list[dict]
    
    # 현재 턴 분류 결과
    is_followup: bool
    followup_type: Literal[
        "refine_easier",
        "refine_harder",
        "refine_different",
        "ask_detail",
        "compare_similar",
        "continue_same",
        None
    ]
    
    # 진행 상황 콜백 (UI 표시용)
    _progress_callback: Any
    
    # ========================================
    # Agentic Orchestrator 필드 (v2)
    # ========================================
    
    # Plan 수립 결과 (contracts.SupervisorPlanOutput)
    plan_output: Any  # SupervisorPlanOutput 타입, 순환 임포트 방지로 Any
    
    # Active Inference 결과
    _inference_hints: Dict[str, Any]
    _inference_confidence: float
    _needs_disambiguation: bool
    
    # Plan 실행 결과
    _plan_execution_result: Dict[str, Any]
    _plan_status: str  # completed | partial | aborted | disambiguation
    
    # 최종 Agentic 출력 (AgenticSupervisorOutput.model_dump())
    _agentic_output: Dict[str, Any]
    
    # 내부 추론 로그 (사용자에게 노출 안 함)
    _reasoning_trace: str
    _mapped_intent: str
    
    # Intent 분류 신뢰도
    _intent_confidence: float
    
    # 세션/턴 ID (관측성용)
    _session_id: str
    _turn_id: str


def decide_explain_target(state: SupervisorState) -> ExplainTarget:
    """이전 턴 정보를 기반으로 explain 모드의 타깃을 결정. (레거시 호환용)"""
    last_answer_kind = state.get("last_answer_kind")
    last_explain_target = state.get("last_explain_target")
    last_task_list = state.get("last_task_list")
    diagnosis_result = state.get("diagnosis_result")
    
    if last_answer_kind == "report":
        return "metric"
    
    if last_answer_kind == "explain" and last_explain_target == "metric":
        return "metric"
    
    if last_explain_target == "task_recommendation":
        return "task_recommendation"
    
    if last_task_list:
        return "task_recommendation"
    
    if diagnosis_result and isinstance(diagnosis_result, dict):
        if diagnosis_result.get("scores"):
            return "metric"
        if diagnosis_result.get("onboarding_tasks"):
            return "task_recommendation"
    
    return "general"