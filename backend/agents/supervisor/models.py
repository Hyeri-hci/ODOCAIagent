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
    agent: Literal["diagnosis", "security", "recommend", "chat", "onboarding", "compare"]
    mode: str = "auto"
    condition: str = "always"
    description: Optional[str] = None

class TaskPlan(BaseModel):
    """메타 에이전트 실행 계획."""
    steps: List[TaskStep] = Field(default_factory=list)
    created_by: str = "supervisor"

# 6. AnswerKind for response types
AnswerKind = Literal["none", "report", "plan", "explain"]


# 7. SupervisorState - 통합 상태 모델
class SupervisorState(BaseModel):
    """통합 Supervisor 상태 모델."""
    
    # TypedDict 호환을 위한 메서드들 (LangGraph 호환성)
    def get(self, key: str, default: Any = None) -> Any:
        """TypedDict 스타일의 get 메서드."""
        return getattr(self, key, default)
    
    def __getitem__(self, key: str) -> Any:
        """TypedDict 스타일의 인덱싱."""
        return getattr(self, key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """TypedDict 스타일의 인덱싱 할당."""
        setattr(self, key, value)
    
    def __contains__(self, key: str) -> bool:
        """TypedDict 스타일의 in 연산자."""
        return hasattr(self, key) and getattr(self, key) is not None
    
    # === 필수 입력 필드 ===
    owner: str = Field(..., description="저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    
    # === 선택적 입력 필드 ===
    ref: str = Field(default="main", description="브랜치/태그 참조")
    task_type: Optional[TaskType] = Field(default=None, description="태스크 타입")
    user_message: Optional[str] = Field(default=None, description="사용자 메시지")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="사용자 컨텍스트")
    
    # === 세션 관리 ===
    session_id: Optional[str] = Field(default=None, description="세션 ID")
    is_new_session: bool = Field(default=True, description="새 세션 여부")
    
    # === 진행 상태 ===
    step: int = Field(default=0, description="현재 단계")
    max_step: int = Field(default=10, description="최대 단계")
    iteration: int = Field(default=0, description="현재 반복 횟수")
    max_iterations: int = Field(default=5, description="최대 반복 횟수")
    
    # === 의도 분석 ===
    supervisor_intent: Optional[Dict[str, Any]] = Field(default=None, description="분석된 의도")
    target_agent: Optional[Literal["diagnosis", "onboarding", "security", "chat", "none"]] = Field(
        default=None, description="대상 에이전트"
    )
    detected_intent: Optional[str] = Field(default=None, description="감지된 의도")
    global_intent: Optional[str] = Field(default=None, description="글로벌 의도")
    intent_confidence: float = Field(default=0.0, description="의도 신뢰도")
    decision_reason: Optional[str] = Field(default=None, description="결정 이유")
    
    # === 명확화 처리 ===
    needs_clarification: bool = Field(default=False, description="명확화 필요 여부")
    awaiting_clarification: bool = Field(default=False, description="명확화 대기 중")
    clarification_questions: List[str] = Field(default_factory=list, description="명확화 질문 목록")
    
    # === 대화 이력 ===
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list, description="대화 이력")
    accumulated_context: Dict[str, Any] = Field(default_factory=dict, description="누적 컨텍스트")
    messages: List[Any] = Field(default_factory=list, description="메시지 목록")
    long_term_context: Optional[str] = Field(default=None, description="장기 컨텍스트")
    
    # === 진단 결과 ===
    diagnosis_result: Optional[Dict[str, Any]] = Field(default=None, description="진단 결과")
    repo_snapshot: Optional[RepoSnapshot] = Field(default=None, description="저장소 스냅샷")
    
    # === 온보딩 관련 ===
    candidate_issues: List[Dict[str, Any]] = Field(default_factory=list, description="후보 이슈")
    onboarding_plan: Optional[List[Dict[str, Any]]] = Field(default=None, description="온보딩 플랜")
    onboarding_progress_index: int = Field(default=0, description="온보딩 진행 인덱스")
    onboarding_summary: Optional[str] = Field(default=None, description="온보딩 요약")
    
    # === 에이전트 실행 ===
    agent_params: Dict[str, Any] = Field(default_factory=dict, description="에이전트 파라미터")
    agent_result: Optional[Dict[str, Any]] = Field(default=None, description="에이전트 실행 결과")
    additional_agents: List[str] = Field(default_factory=list, description="추가 실행할 에이전트들")
    security_result: Optional[Dict[str, Any]] = Field(default=None, description="보안 분석 결과")
    multi_agent_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="멀티 에이전트 결과")
    
    # === 응답 ===
    final_answer: Optional[str] = Field(default=None, description="최종 응답")
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list, description="제안 액션 목록")
    last_answer_kind: AnswerKind = Field(default="none", description="마지막 응답 종류")
    last_explain_target: Optional[str] = Field(default=None, description="마지막 설명 대상")
    
    # === 플로우 제어 ===
    next_node_override: Optional[str] = Field(default=None, description="다음 노드 오버라이드")
    flow_adjustments: List[str] = Field(default_factory=list, description="플로우 조정")
    warnings: List[str] = Field(default_factory=list, description="경고 목록")
    
    # === 에러 및 추적 ===
    error: Optional[str] = Field(default=None, description="에러 메시지")
    trace_id: Optional[str] = Field(default=None, description="추적 ID")
    
    # === 품질 검사 ===
    rerun_count: int = Field(default=0, description="재실행 횟수")
    max_rerun: int = Field(default=3, description="최대 재실행")
    quality_issues: List[str] = Field(default_factory=list, description="품질 이슈")
    
    # === 캐시 제어 ===
    use_cache: bool = Field(default=True, description="캐시 사용")
    cache_hit: bool = Field(default=False, description="캐시 히트")
    analysis_depth: str = Field(default="standard", description="분석 깊이")
    
    # === 비교 분석 ===
    compare_repos: List[str] = Field(default_factory=list, description="비교 저장소")
    compare_results: Dict[str, Any] = Field(default_factory=dict, description="비교 결과")
    compare_summary: Optional[str] = Field(default=None, description="비교 요약")
    
    # === 채팅 ===
    chat_message: Optional[str] = Field(default=None, description="채팅 메시지")
    chat_response: Optional[str] = Field(default=None, description="채팅 응답")
    chat_context: Dict[str, Any] = Field(default_factory=dict, description="채팅 컨텍스트")
    
    # === 메타 에이전트 ===
    user_preferences: Dict[str, Any] = Field(default_factory=dict, description="사용자 선호")
    priority: str = Field(default="thoroughness", description="우선순위")
    task_plan: List[Dict[str, Any]] = Field(default_factory=list, description="태스크 플랜")
    task_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="태스크 결과")
    replan_count: int = Field(default=0, description="재계획 횟수")
    max_replan: int = Field(default=1, description="최대 재계획")
    reflection_summary: Optional[str] = Field(default=None, description="반성 요약")
    plan_history: List[List[Dict[str, Any]]] = Field(default_factory=list, description="플랜 이력")

    class Config:
        validate_assignment = True
