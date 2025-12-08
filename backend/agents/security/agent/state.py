"""
Security Analysis Agent State Definition
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from operator import add


class SecurityAnalysisState(TypedDict, total=False):
    """보안 분석 에이전트의 상태"""

    # 입력 정보
    owner: str
    repository: str
    github_token: Optional[str]

    # 진행 상태
    current_step: str  # "initializing", "planning", "executing", "reporting", "completed"
    iteration: int
    max_iterations: int

    # 계획
    plan: List[str]  # 작업 계획 리스트
    plan_valid: bool
    plan_feedback: str

    # 메시지 (ReAct 대화)
    messages: Annotated[List[str], add]  # 메시지 누적

    # 분석 결과
    dependencies: Optional[Dict[str, Any]]  # 의존성 분석 결과
    dependency_count: int
    lock_files_found: List[str]

    # 취약점 정보 (향후 확장)
    vulnerabilities: List[Dict[str, Any]]
    vulnerability_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

    # CPE 매핑 (향후 확장)
    cpe_mappings: Dict[str, List[str]]  # {package_name: [cpe_ids]}

    # 보안 평가
    security_score: Optional[Dict[str, Any]]
    security_grade: str  # A, B, C, D, F
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"

    # 레포트
    report: Optional[str]
    recommendations: List[str]

    # 에이전트 판단
    needs_human_input: bool
    human_question: Optional[str]
    human_response: Optional[str]

    # 에러 및 로그
    errors: Annotated[List[str], add]
    warnings: Annotated[List[str], add]

    # 완료 여부
    completed: bool
    final_result: Optional[Dict[str, Any]]


def create_initial_state(
    owner: str,
    repository: str,
    github_token: Optional[str] = None,
    max_iterations: int = 10
) -> SecurityAnalysisState:
    """초기 State 생성"""
    return SecurityAnalysisState(
        owner=owner,
        repository=repository,
        github_token=github_token,
        current_step="initializing",
        iteration=0,
        max_iterations=max_iterations,
        plan=[],
        plan_valid=False,
        plan_feedback="",
        messages=[],
        dependency_count=0,
        lock_files_found=[],
        vulnerabilities=[],
        vulnerability_count=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        cpe_mappings={},
        security_grade="",
        risk_level="",
        recommendations=[],
        needs_human_input=False,
        errors=[],
        warnings=[],
        completed=False,
    )
