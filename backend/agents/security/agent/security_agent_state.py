# backend/agents/security/agent/state.py
# ============================================================================
# SecurityAnalysisState - LangGraph Agent State Definition
# ============================================================================
# 이 파일은 보안 분석 에이전트의 모든 상태를 정의합니다.
# State는 각 노드에서 데이터를 저장하고 전달하는 중앙 저장소 역할을 합니다.
# ============================================================================

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from enum import Enum
from datetime import datetime
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


# ============================================================================
# 1. Enums - 상태 값 정의
# ============================================================================

class CurrentStep(str, Enum):
    """에이전트의 현재 단계"""
    # 초기화 단계
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"

    # 계획 단계
    PLANNING = "planning"
    PLANNED = "planned"

    # 검증 단계
    VALIDATING_PLAN = "validating_plan"
    PLAN_VALIDATED = "plan_validated"
    PLAN_INVALID = "plan_invalid"
    REPLANNING = "replanning"

    # 실행 단계
    EXECUTING = "executing"
    EXECUTING_TOOLS = "executing_tools"

    # 관찰 단계
    OBSERVING = "observing"
    OBSERVATION_COMPLETE = "observation_complete"

    # 사람 개입
    NEED_HELP = "need_help"
    WAITING_FOR_HUMAN = "waiting_for_human"
    HUMAN_RESPONSE_RECEIVED = "human_response_received"

    # 레포트 단계
    GENERATING_REPORT = "generating_report"
    REPORT_GENERATED = "report_generated"

    # 완료 단계
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, Enum):
    """보안 위험 수준"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityGrade(str, Enum):
    """보안 등급 (A-F)"""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class VulnerabilitySeverity(str, Enum):
    """취약점 심각도"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# ============================================================================
# 2. TypedDict Models - State 필드 그룹화
# ============================================================================

class InputInfo(TypedDict):
    """에이전트 입력 정보"""
    owner: str
    repository: str
    github_token: Optional[str]
    enable_human_input: bool
    max_iterations: int


class PlanInfo(TypedDict):
    """계획 정보"""
    plan: List[str]
    plan_valid: bool
    plan_feedback: str
    current_plan_index: int


class DependencyAnalysisResult(TypedDict):
    """의존성 분석 결과"""
    dependencies: Optional[Dict[str, Any]]
    dependency_count: int
    lock_files_found: List[str]
    dependency_files_analyzed: List[str]
    analysis_timestamp: Optional[datetime]


class CVEInfo(TypedDict):
    """CVE/취약점 정보"""
    cve_id: str
    severity: VulnerabilitySeverity
    cvss_score: float
    description: str
    package_name: str
    affected_version: str
    published_date: str
    updated_date: str
    remediation: Optional[str]


class VulnerabilityAnalysisResult(TypedDict):
    """취약점 분석 결과"""
    vulnerabilities: List[CVEInfo]
    vulnerability_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    cpe_mappings: Dict[str, List[str]]  # {package_name: [cpe_ids]}
    analysis_timestamp: Optional[datetime]


class SecurityScoreInfo(TypedDict):
    """보안 점수 정보"""
    score: float  # 0-100
    grade: SecurityGrade
    risk_level: RiskLevel
    factors: Dict[str, Any]  # 점수 계산에 영향을 미친 요소들
    calculated_at: datetime


class ReportInfo(TypedDict):
    """레포트 생성 정보"""
    report: Optional[str]  # Markdown 형식의 레포트
    recommendations: List[str]
    executive_summary: Optional[str]
    report_path: Optional[str]
    export_formats: List[str]  # ["markdown", "pdf", "html"]


class HumanLoopInfo(TypedDict):
    """사람 개입 정보"""
    needs_human_input: bool
    human_question: Optional[str]
    human_response: Optional[str]
    response_timestamp: Optional[datetime]


class ErrorTrackingInfo(TypedDict):
    """에러 및 로그 추적"""
    errors: List[Dict[str, Any]]  # [{timestamp, step, error_type, message}]
    warnings: List[Dict[str, Any]]  # [{timestamp, step, message}]
    error_count: int
    warning_count: int


class ExecutionMetrics(TypedDict):
    """실행 메트릭"""
    total_iterations: int
    replan_count: int
    human_intervention_count: int
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_seconds: Optional[float]


class FinalResult(TypedDict):
    """최종 결과"""
    success: bool
    completion_status: str  # "completed", "failed", "partial"
    report_summary: Optional[str]
    vulnerabilities_found: int
    critical_issues: int
    recommendations_count: int
    analysis_metadata: Dict[str, Any]


# ============================================================================
# 3. Main SecurityAnalysisState - 전체 상태 정의
# ============================================================================

class SecurityAnalysisState(TypedDict):
    """
    LangGraph 보안 분석 에이전트의 상태

    이 TypedDict는 에이전트 실행 전체에 걸쳐 데이터를 저장합니다.
    각 노드는 이 상태를 읽고 업데이트합니다.
    """

    # ========================================================================
    # 1. 입력 정보 (Initialize 단계에서 설정, 읽기 전용)
    # ========================================================================
    owner: str  # GitHub 레포지토리 소유자
    repository: str  # GitHub 레포지토리 이름
    github_token: Optional[str]  # GitHub API 토큰
    enable_human_input: bool  # 사람 개입 활성화 여부
    max_iterations: int  # 최대 반복 횟수

    # ========================================================================
    # 2. 진행 상태 (모든 노드에서 업데이트)
    # ========================================================================
    current_step: CurrentStep  # 현재 단계
    iteration: int  # 현재 반복 횟수 (0부터 시작)
    completed: bool  # 분석 완료 여부
    started_at: datetime  # 분석 시작 시간

    # ========================================================================
    # 3. 계획 관리 (Plan 단계에서 설정, Observe 단계에서 조정)
    # ========================================================================
    plan: List[str]  # 실행할 작업 계획 리스트
    plan_valid: bool  # 계획의 타당성 여부
    plan_feedback: str  # 계획에 대한 피드백
    current_plan_index: int  # 현재 실행 중인 계획의 인덱스

    # ========================================================================
    # 4. ReAct 패턴 메시지 (모든 노드에서 추가)
    # Annotated[List, add_messages]를 사용하여 자동으로 메시지 병합
    # ========================================================================
    messages: Annotated[List[BaseMessage], add_messages]  # ReAct 대화 이력

    # ========================================================================
    # 5. 의존성 분석 결과 (Execution 단계에서 설정)
    # ========================================================================
    dependencies: Optional[Dict[str, Any]]  # 의존성 분석 결과 전체
    dependency_count: int  # 총 의존성 수
    lock_files_found: List[str]  # 발견된 Lock 파일 목록
    dependency_files_analyzed: List[str]  # 분석한 의존성 파일 목록
    dependencies_by_language: Dict[str, int]  # 언어별 의존성 수
    dependencies_with_known_versions: int  # 버전이 명시된 의존성 수

    # ========================================================================
    # 6. 취약점 분석 결과 (Execution 단계에서 설정)
    # ========================================================================
    vulnerabilities: List[CVEInfo]  # 발견된 취약점 목록
    vulnerability_count: int  # 총 취약점 수
    critical_count: int  # Critical 취약점 수
    high_count: int  # High 취약점 수
    medium_count: int  # Medium 취약점 수
    low_count: int  # Low 취약점 수
    cpe_mappings: Dict[str, List[str]]  # CPE 매핑 결과

    # ========================================================================
    # 7. 보안 평가 (Execution 단계에서 설정)
    # ========================================================================
    security_score: Optional[SecurityScoreInfo]  # 보안 점수 정보
    security_grade: SecurityGrade  # 보안 등급 (A-F)
    risk_level: RiskLevel  # 위험 수준
    score_calculated_at: Optional[datetime]  # 점수 계산 시간

    # ========================================================================
    # 8. 레포트 생성 (Report 단계에서 설정)
    # ========================================================================
    report: Optional[str]  # Markdown 형식 레포트
    recommendations: List[str]  # 보안 권장 사항
    executive_summary: Optional[str]  # 요약 리포트
    report_path: Optional[str]  # 저장된 레포트 경로

    # ========================================================================
    # 9. 사람 개입 정보 (Observe & Reflect 단계에서 설정)
    # ========================================================================
    needs_human_input: bool  # 사람 개입 필요 여부
    human_question: Optional[str]  # 사람에게 할 질문
    human_response: Optional[str]  # 사람의 응답
    human_intervention_count: int  # 사람 개입 횟수

    # ========================================================================
    # 10. 에러 및 경고 로그 (모든 노드에서 추가)
    # ========================================================================
    errors: List[Dict[str, Any]]  # 에러 로그 리스트
    warnings: List[Dict[str, Any]]  # 경고 로그 리스트
    error_count: int  # 총 에러 수
    warning_count: int  # 총 경고 수

    # ========================================================================
    # 11. 실행 메트릭 (모든 노드에서 업데이트)
    # ========================================================================
    total_iterations: int  # 총 반복 횟수
    replan_count: int  # 재계획 횟수
    tools_executed: List[str]  # 실행한 도구 이름 목록

    # ========================================================================
    # 12. 최종 결과 (Report 단계에서 설정)
    # ========================================================================
    final_result: Optional[FinalResult]  # 최종 분석 결과


# ============================================================================
# 4. State 초기화 함수
# ============================================================================

def create_initial_state(
        owner: str,
        repository: str,
        github_token: Optional[str] = None,
        enable_human_input: bool = True,
        max_iterations: int = 10,
) -> SecurityAnalysisState:
    """
    새로운 분석을 위한 초기 State를 생성합니다.

    Args:
        owner: GitHub 레포지토리 소유자
        repository: GitHub 레포지토리 이름
        github_token: GitHub API 토큰 (선택사항)
        enable_human_input: 사람 개입 활성화 여부 (기본값: True)
        max_iterations: 최대 반복 횟수 (기본값: 10)

    Returns:
        SecurityAnalysisState: 초기화된 상태
    """
    return SecurityAnalysisState(
        # 입력 정보
        owner=owner,
        repository=repository,
        github_token=github_token,
        enable_human_input=enable_human_input,
        max_iterations=max_iterations,

        # 진행 상태
        current_step=CurrentStep.INITIALIZING,
        iteration=0,
        completed=False,
        started_at=datetime.now(),

        # 계획
        plan=[],
        plan_valid=False,
        plan_feedback="",
        current_plan_index=0,

        # 메시지
        messages=[],

        # 의존성 분석
        dependencies=None,
        dependency_count=0,
        lock_files_found=[],
        dependency_files_analyzed=[],
        dependencies_by_language={},
        dependencies_with_known_versions=0,

        # 취약점 분석
        vulnerabilities=[],
        vulnerability_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        cpe_mappings={},

        # 보안 평가
        security_score=None,
        security_grade=SecurityGrade.F,  # 기본값: 최악
        risk_level=RiskLevel.CRITICAL,  # 기본값: 최고 위험
        score_calculated_at=None,

        # 레포트
        report=None,
        recommendations=[],
        executive_summary=None,
        report_path=None,

        # 사람 개입
        needs_human_input=False,
        human_question=None,
        human_response=None,
        human_intervention_count=0,

        # 에러 로그
        errors=[],
        warnings=[],
        error_count=0,
        warning_count=0,

        # 메트릭
        total_iterations=0,
        replan_count=0,
        tools_executed=[],

        # 최종 결과
        final_result=None,
    )


# ============================================================================
# 5. State 업데이트 헬퍼 함수들
# ============================================================================

def add_error(
        state: SecurityAnalysisState,
        error_type: str,
        message: str,
        step: Optional[str] = None,
) -> SecurityAnalysisState:
    """
    에러를 State에 추가합니다.

    Args:
        state: 현재 상태
        error_type: 에러 타입 (예: "APIError", "ValidationError")
        message: 에러 메시지
        step: 에러가 발생한 단계 (선택사항)

    Returns:
        SecurityAnalysisState: 업데이트된 상태
    """
    error_entry = {
        "timestamp": datetime.now(),
        "step": step or state["current_step"].value,
        "error_type": error_type,
        "message": message,
    }

    state["errors"].append(error_entry)
    state["error_count"] = len(state["errors"])

    return state


def add_warning(
        state: SecurityAnalysisState,
        message: str,
        step: Optional[str] = None,
) -> SecurityAnalysisState:
    """
    경고를 State에 추가합니다.

    Args:
        state: 현재 상태
        message: 경고 메시지
        step: 경고가 발생한 단계 (선택사항)

    Returns:
        SecurityAnalysisState: 업데이트된 상태
    """
    warning_entry = {
        "timestamp": datetime.now(),
        "step": step or state["current_step"].value,
        "message": message,
    }

    state["warnings"].append(warning_entry)
    state["warning_count"] = len(state["warnings"])

    return state


def should_ask_for_human_input(state: SecurityAnalysisState) -> bool:
    """
    사람 개입이 필요한지 판단합니다.

    Args:
        state: 현재 상태

    Returns:
        bool: 사람 개입 필요 여부
    """
    if not state["enable_human_input"]:
        return False

    # 1. Critical 취약점이 많은 경우
    if state["critical_count"] > 10:
        return True

    # 2. 에러가 많은 경우
    if state["error_count"] > 3:
        return True

    # 3. 최대 반복 횟수에 근접한 경우
    if state["iteration"] >= state["max_iterations"] - 2:
        return True

    # 4. 계획이 유효하지 않은 경우 (재계획 필요)
    if not state["plan_valid"] and state["iteration"] > 0:
        return True

    return False


def update_vulnerability_counts(
        state: SecurityAnalysisState,
        vulnerabilities: List[CVEInfo],
) -> SecurityAnalysisState:
    """
    취약점 수를 업데이트합니다.

    Args:
        state: 현재 상태
        vulnerabilities: 취약점 목록

    Returns:
        SecurityAnalysisState: 업데이트된 상태
    """
    state["vulnerabilities"] = vulnerabilities
    state["vulnerability_count"] = len(vulnerabilities)

    # 심각도별 수 계산
    severity_counts = {
        VulnerabilitySeverity.CRITICAL: 0,
        VulnerabilitySeverity.HIGH: 0,
        VulnerabilitySeverity.MEDIUM: 0,
        VulnerabilitySeverity.LOW: 0,
    }

    for vuln in vulnerabilities:
        severity = vuln.get("severity")
        if severity in severity_counts:
            severity_counts[severity] += 1

    state["critical_count"] = severity_counts[VulnerabilitySeverity.CRITICAL]
    state["high_count"] = severity_counts[VulnerabilitySeverity.HIGH]
    state["medium_count"] = severity_counts[VulnerabilitySeverity.MEDIUM]
    state["low_count"] = severity_counts[VulnerabilitySeverity.LOW]

    return state


# ============================================================================
# 6. State 검증 함수
# ============================================================================

def is_state_valid(state: SecurityAnalysisState) -> tuple[bool, List[str]]:
    """
    State의 타당성을 검증합니다.

    Args:
        state: 검증할 상태

    Returns:
        tuple[bool, List[str]]: (유효성 여부, 문제 사항 리스트)
    """
    issues = []

    # 1. 필수 필드 확인
    if not state.get("owner"):
        issues.append("owner가 설정되지 않았습니다.")

    if not state.get("repository"):
        issues.append("repository가 설정되지 않았습니다.")

    # 2. 불일치 확인
    if state["iteration"] > state["max_iterations"]:
        issues.append(f"반복 횟수({state['iteration']})가 최대값({state['max_iterations']})을 초과했습니다.")

    # 3. 카운트 일관성 확인
    if state["vulnerability_count"] != len(state["vulnerabilities"]):
        issues.append("취약점 수 불일치")

    expected_vuln_count = (
            state["critical_count"] + state["high_count"] +
            state["medium_count"] + state["low_count"]
    )
    if state["vulnerability_count"] != expected_vuln_count:
        issues.append("심각도별 취약점 수의 합이 일치하지 않습니다.")

    if state["dependency_count"] != len(state.get("dependencies", {}).get("all_dependencies", [])) if state.get(
            "dependencies") else False:
        issues.append("의존성 수 불일치")

    # 4. 완료 상태 확인
    if state["completed"] and state["final_result"] is None:
        issues.append("완료 상태이지만 final_result가 없습니다.")

    return len(issues) == 0, issues


# ============================================================================
# 7. State 직렬화 헬퍼 (로깅/저장용)
# ============================================================================

def serialize_state_for_logging(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    State를 로깅/저장 가능한 형태로 변환합니다.

    Args:
        state: 변환할 상태

    Returns:
        Dict[str, Any]: 직렬화된 상태
    """
    return {
        "owner": state["owner"],
        "repository": state["repository"],
        "current_step": state["current_step"].value,
        "iteration": state["iteration"],
        "completed": state["completed"],
        "dependency_count": state["dependency_count"],
        "vulnerability_count": state["vulnerability_count"],
        "security_grade": state["security_grade"].value,
        "risk_level": state["risk_level"].value,
        "error_count": state["error_count"],
        "warning_count": state["warning_count"],
        "human_intervention_count": state["human_intervention_count"],
        "message_count": len(state["messages"]),
    }


# ============================================================================
# 8. State 비교 함수 (검증용)
# ============================================================================

def get_state_diff(
        state_before: SecurityAnalysisState,
        state_after: SecurityAnalysisState,
) -> Dict[str, tuple[Any, Any]]:
    """
    두 State의 차이점을 찾습니다.

    Args:
        state_before: 이전 상태
        state_after: 이후 상태

    Returns:
        Dict: 변경된 필드 딕셔너리
    """
    changes = {}

    for key in state_before.keys():
        before_val = state_before.get(key)
        after_val = state_after.get(key)

        if before_val != after_val:
            changes[key] = (before_val, after_val)

    return changes
