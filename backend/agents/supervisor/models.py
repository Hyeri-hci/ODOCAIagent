"""
Supervisor 상태 및 타입 정의

Supervisor는 사용자 자연어 쿼리를 받아 적절한 Agent로 라우팅하고,
결과를 종합하여 최종 응답을 생성하는 역할을 담당한다.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict


# Supervisor가 처리하는 전역 태스크 타입
SupervisorTaskType = Literal[
    "diagnose_repo_health",
    "diagnose_repo_onboarding",
    "compare_two_repos",
    "refine_onboarding_tasks",
    "explain_scores",
]

# Agent별 태스크 타입 (각 Agent 모듈에서 구체화)
DiagnosisTaskType = str
SecurityTaskType = str
RecommendTaskType = str


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
    task_type은 UI에서 직접 지정하지 않고, LLM이 user_query를 분석하여 추론한다.
    """
    # 입력
    user_query: str
    task_type: SupervisorTaskType

    # 의도 및 저장소 정보
    intent: SupervisorTaskType
    repo: RepoInfo
    compare_repo: RepoInfo

    # 사용자 맥락
    user_context: UserContext

    # Agent별 태스크 타입 (Supervisor 매핑 노드에서 설정)
    diagnosis_task_type: DiagnosisTaskType
    security_task_type: SecurityTaskType
    recommend_task_type: RecommendTaskType

    # Agent 실행 결과
    diagnosis_result: dict[str, Any]
    compare_diagnosis_result: dict[str, Any]

    # 최종 응답
    llm_summary: str

    # 대화 히스토리
    history: list[Turn]

    # ========================================
    # 멀티턴 상태 관리 필드
    # ========================================
    
    # 이전 턴 메타데이터 (follow-up 처리용)
    last_repo: RepoInfo              # 마지막으로 분석한 저장소
    last_intent: SupervisorTaskType  # 마지막 intent
    last_task_list: list[dict]       # 마지막 온보딩 Task 목록 (리랭킹용)
    
    # 현재 턴 분류 결과
    is_followup: bool                # 이전 턴 컨텍스트 참조 여부
    followup_type: Literal[          # follow-up 유형
        "refine_easier",             # "더 쉬운 거 없어?"
        "refine_harder",             # "더 어려운 거?"
        "refine_different",          # "다른 종류는?"
        "ask_detail",                # "이거 더 자세히"
        "compare_similar",           # "비슷한 repo는?"
        "continue_same",             # 같은 repo 계속 분석
        None
    ]
