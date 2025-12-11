"""
Security Analysis Agent State
LLM 통합 및 자연어 처리를 위한 State 정의
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Literal
from operator import add
from datetime import datetime


class ThoughtRecord(TypedDict):
    """에이전트의 사고 기록"""
    timestamp: str
    thought: str
    reasoning: str


class ActionRecord(TypedDict):
    """에이전트의 행동 기록"""
    timestamp: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    success: bool
    error: Optional[str]


class MemoryItem(TypedDict):
    """메모리 항목"""
    key: str
    value: Any
    timestamp: str
    persist: bool  # 장기 메모리 여부


class ConversationTurn(TypedDict):
    """대화 턴"""
    user_input: str
    agent_response: str
    timestamp: str


class TaskIntent(TypedDict):
    """파싱된 사용자 의도"""
    primary_action: Literal[
        "analyze_all",
        "extract_dependencies",
        "scan_vulnerabilities",
        "check_license",
        "generate_report",
        "analyze_file",
        "custom"
    ]
    scope: Literal["full_repository", "specific_files", "specific_languages"]
    target_files: List[str]
    conditions: List[Dict[str, Any]]
    output_format: Literal["full_report", "summary", "json", "specific_fields"]
    parameters: Dict[str, Any]


class ExecutionPlan(TypedDict):
    """실행 계획"""
    steps: List[Dict[str, Any]]  # 실행 단계들
    estimated_duration: int  # 예상 소요 시간 (초)
    complexity: Literal["simple", "moderate", "complex"]
    requires_llm: bool  # LLM 사용 필요 여부


class SecurityAnalysisState(TypedDict, total=False):
    """보안 분석 에이전트 상태"""

    # ===== 기본 정보 =====
    session_id: str
    created_at: str

    # ===== 입력 정보 =====
    # 자연어 입력
    user_request: str  # 원본 자연어 요청
    parsed_intent: Optional[TaskIntent]  # 파싱된 의도

    # 레포지토리 정보
    owner: str
    repository: str
    github_token: Optional[str]

    # ===== 실행 모드 =====
    execution_mode: Literal["fast", "intelligent", "auto"]  # 실행 모드
    use_llm: bool  # LLM 사용 여부

    # ===== 진행 상태 =====
    current_step: str
    iteration: int
    max_iterations: int
    progress_percentage: int  # 0-100

    # ===== 계획 =====
    execution_plan: Optional[ExecutionPlan]
    plan_valid: bool
    plan_feedback: str

    # ===== 에이전트 사고 과정 (ReAct) =====
    thoughts: Annotated[List[ThoughtRecord], add]  # 사고 기록
    actions: Annotated[List[ActionRecord], add]  # 행동 기록
    observations: Annotated[List[str], add]  # 관찰 기록

    # ===== 대화 컨텍스트 =====
    conversation_history: Annotated[List[ConversationTurn], add]
    current_context: Dict[str, Any]  # 현재 컨텍스트

    # ===== 메모리 =====
    short_term_memory: Dict[str, MemoryItem]  # 현재 세션
    long_term_memory_keys: List[str]  # 영구 저장된 키들

    # ===== 분석 결과 =====
    # 의존성
    dependencies: Optional[Dict[str, Any]]
    dependency_count: int
    lock_files_found: List[str]
    dependency_tree: Optional[Dict[str, Any]]  # 의존성 트리

    # 취약점
    vulnerabilities: List[Dict[str, Any]]
    vulnerability_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

    # CPE 매핑
    cpe_mappings: Dict[str, List[str]]

    # 라이센스
    license_info: Optional[Dict[str, Any]]
    license_violations: List[Dict[str, Any]]

    # 코드 보안
    code_security: Optional[Dict[str, Any]]
    secrets_found: List[Dict[str, Any]]

    # ===== 보안 평가 =====
    security_score: Optional[Dict[str, Any]]
    security_grade: str
    risk_level: str

    # ===== 레포트 =====
    report: Optional[str]
    recommendations: List[str]

    # ===== Human-in-the-Loop =====
    needs_human_input: bool
    human_question: Optional[str]
    human_response: Optional[str]
    clarification_requested: bool

    # ===== 메타 정보 =====
    # 성능 메트릭
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    api_calls_count: int
    api_cost_usd: float

    # 전략
    current_strategy: str  # 현재 사용 중인 전략
    strategy_changes: Annotated[List[Dict[str, Any]], add]  # 전략 변경 이력

    # ===== 에러 및 로그 =====
    errors: Annotated[List[str], add]
    warnings: Annotated[List[str], add]
    info_logs: Annotated[List[str], add]

    # ===== 완료 여부 =====
    completed: bool
    success: bool
    final_result: Optional[Dict[str, Any]]


def create_initial_state(
    user_request: str,
    owner: Optional[str] = None,
    repository: Optional[str] = None,
    github_token: Optional[str] = None,
    execution_mode: Literal["fast", "intelligent", "auto"] = "auto",
    max_iterations: int = 20,
    session_id: Optional[str] = None
) -> SecurityAnalysisState:
    """
    초기 State 생성

    Args:
        user_request: 사용자의 자연어 요청
        owner: 레포지토리 소유자 (자연어에서 추출 가능)
        repository: 레포지토리 이름 (자연어에서 추출 가능)
        github_token: GitHub 토큰
        execution_mode: 실행 모드 (fast/intelligent/auto)
        max_iterations: 최대 반복 횟수
        session_id: 세션 ID

    Returns:
        초기화된 SecurityAnalysisState
    """
    import uuid

    now = datetime.now().isoformat()

    return SecurityAnalysisState(
        # 기본 정보
        session_id=session_id or str(uuid.uuid4()),
        created_at=now,

        # 입력
        user_request=user_request,
        parsed_intent=None,
        owner=owner or "",
        repository=repository or "",
        github_token=github_token,

        # 실행 모드
        execution_mode=execution_mode,
        use_llm=execution_mode in ["intelligent", "auto"],

        # 진행 상태
        current_step="initializing",
        iteration=0,
        max_iterations=max_iterations,
        progress_percentage=0,

        # 계획
        execution_plan=None,
        plan_valid=False,
        plan_feedback="",

        # ReAct
        thoughts=[],
        actions=[],
        observations=[],

        # 컨텍스트
        conversation_history=[],
        current_context={},

        # 메모리
        short_term_memory={},
        long_term_memory_keys=[],

        # 분석 결과
        dependency_count=0,
        lock_files_found=[],
        vulnerabilities=[],
        vulnerability_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        cpe_mappings={},
        license_violations=[],
        secrets_found=[],
        security_grade="",
        risk_level="",
        recommendations=[],

        # Human-in-the-Loop
        needs_human_input=False,
        clarification_requested=False,

        # 메타
        start_time=now,
        api_calls_count=0,
        api_cost_usd=0.0,
        current_strategy="initial",
        strategy_changes=[],

        # 에러
        errors=[],
        warnings=[],
        info_logs=[],

        # 완료
        completed=False,
        success=False,
    )


def update_thought(state: SecurityAnalysisState, thought: str, reasoning: str = "") -> Dict[str, Any]:
    """사고 기록 추가"""
    return {
        "thoughts": [{
            "timestamp": datetime.now().isoformat(),
            "thought": thought,
            "reasoning": reasoning
        }]
    }


def update_action(
    state: SecurityAnalysisState,
    tool_name: str,
    parameters: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """행동 기록 추가"""
    return {
        "actions": [{
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "success": success,
            "error": error
        }]
    }


def update_observation(state: SecurityAnalysisState, observation: str) -> Dict[str, Any]:
    """관찰 기록 추가"""
    return {
        "observations": [f"[{datetime.now().strftime('%H:%M:%S')}] {observation}"]
    }


def save_to_memory(
    state: SecurityAnalysisState,
    key: str,
    value: Any,
    persist: bool = False
) -> Dict[str, Any]:
    """메모리에 저장"""
    memory_item = MemoryItem(
        key=key,
        value=value,
        timestamp=datetime.now().isoformat(),
        persist=persist
    )

    update = {
        "short_term_memory": {**state.get("short_term_memory", {}), key: memory_item}
    }

    if persist:
        long_term_keys = state.get("long_term_memory_keys", [])
        if key not in long_term_keys:
            update["long_term_memory_keys"] = long_term_keys + [key]

    return update


def recall_from_memory(
    state: SecurityAnalysisState,
    key: str
) -> Optional[Any]:
    """메모리에서 불러오기"""
    memory = state.get("short_term_memory", {})
    item = memory.get(key)
    return item["value"] if item else None
