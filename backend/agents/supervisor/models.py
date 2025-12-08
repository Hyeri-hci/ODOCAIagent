from typing import Literal, Dict, Any, Optional, List
from pydantic import BaseModel, Field
from backend.core.models import RepoSnapshot

# 1. TaskType Definition (Hero Scenarios Only)
TaskType = Literal[
    "diagnose_repo",
    "build_onboarding_plan",
    "general_inquiry",
]

# 2. Intent Definition (Agentic Routing)
Intent = Literal[
    "diagnose",
    "onboard",
    "explain",
    "compare",
    "chat",
    "security",
    "full_audit",
    "unknown",
]

# 3. SupervisorInput Definition
class SupervisorInput(BaseModel):
    task_type: TaskType
    owner: str  # Required
    repo: str   # Required
    user_context: Dict[str, Any] = {}
    user_message: Optional[str] = None

# 4. OnboardingUserContext - 온보딩 사용자 컨텍스트 스키마
class OnboardingUserContext(BaseModel):
    """온보딩 플랜 생성을 위한 사용자 컨텍스트."""
    preferred_language: str = Field(default="ko", description="선호 언어 (ko, en)")
    experience_level: Literal["beginner", "intermediate", "advanced"] = Field(
        default="beginner", 
        description="개발 경험 수준"
    )
    available_hours_per_week: int = Field(
        default=5, 
        ge=1, 
        le=40, 
        description="주당 투자 가능 시간"
    )
    preferred_issue_types: List[str] = Field(
        default_factory=list, 
        description="선호 이슈 타입 (docs, bug-fix, feature, test)"
    )
    focus_areas: List[str] = Field(
        default_factory=list, 
        description="집중 영역 (frontend, backend, testing, docs)"
    )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OnboardingUserContext":
        """Dict에서 OnboardingUserContext 생성. 알 수 없는 키는 무시."""
        valid_keys = cls.model_fields.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


# 5. Meta Agent Models
class TaskStep(BaseModel):
    """메타 에이전트 실행 단계."""
    step: int
    agent: Literal["diagnosis", "security", "recommend", "chat"]
    mode: str = "auto"
    condition: str = "always"
    description: Optional[str] = None

class TaskPlan(BaseModel):
    """메타 에이전트 실행 계획."""
    steps: List[TaskStep] = Field(default_factory=list)
    created_by: str = "supervisor"

# 6. SupervisorState Definition
AnswerKind = Literal["none", "report", "plan", "explain"]

class SupervisorState(BaseModel):
    # 1) 입력 값
    task_type: TaskType
    owner: str
    repo: str
    user_context: Dict[str, Any] = {}

    # 2) 진행 상태
    step: int = 0
    max_step: int = 10

    # 3) Core 진단 결과 (DTO 기반)
    diagnosis_result: Optional[Dict[str, Any]] = None
    repo_snapshot: Optional[RepoSnapshot] = None

    # 4) 온보딩 관련 산출물
    candidate_issues: List[Dict[str, Any]] = []
    onboarding_plan: Optional[List[Dict[str, Any]]] = None
    onboarding_progress_index: int = 0
    onboarding_summary: Optional[str] = None

    # 5) 대화/요약 컨텍스트
    last_answer_kind: AnswerKind = "none"
    last_explain_target: Optional[str] = None
    messages: List[Any] = []

    # 6) 에러
    error: Optional[str] = None

    # 7) Agentic 판단 관련
    detected_intent: Optional[str] = None
    intent_confidence: float = 0.0
    decision_reason: Optional[str] = None
    next_node_override: Optional[str] = None

    # 8) 품질 검사 및 재실행
    rerun_count: int = 0
    max_rerun: int = 2
    quality_issues: List[str] = []

    # 9) 캐시 제어
    use_cache: bool = True
    cache_hit: bool = False

    # 10) 세션 및 대화 컨텍스트
    session_id: Optional[str] = None
    long_term_context: Optional[str] = None

    # 11) 동적 플로우 조정
    flow_adjustments: List[str] = []
    warnings: List[str] = []
    analysis_depth: str = "standard"

    # 12) 비교 분석
    compare_repos: List[str] = []
    compare_results: Dict[str, Any] = {}
    compare_summary: Optional[str] = None

    # 13) 채팅
    chat_message: Optional[str] = None
    chat_response: Optional[str] = None
    chat_context: Dict[str, Any] = {}
    
    # 14) 메타 에이전트 필드
    user_message: Optional[str] = None
    global_intent: Optional[str] = None
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "thoroughness"
    task_plan: List[Dict[str, Any]] = Field(default_factory=list)
    task_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    replan_count: int = 0
    max_replan: int = 1
    reflection_summary: Optional[str] = None
    plan_history: List[List[Dict[str, Any]]] = Field(default_factory=list)

