from typing import Literal, Dict, Any, Optional, List
from pydantic import BaseModel
from backend.core.models import RepoSnapshot

# 1. TaskType Definition (Hero Scenarios Only)
TaskType = Literal[
    "diagnose_repo",
    "build_onboarding_plan",
]

# 2. SupervisorInput Definition
class SupervisorInput(BaseModel):
    task_type: TaskType
    owner: str  # Required
    repo: str   # Required
    user_context: Dict[str, Any] = {}

# 3. SupervisorState Definition
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
    diagnosis_result: Optional[Dict[str, Any]] = None  # DiagnosisOutput.to_dict()
    repo_snapshot: Optional[RepoSnapshot] = None

    # 4) 온보딩 관련 산출물
    candidate_issues: List[Dict[str, Any]] = []  # good first issue 등
    onboarding_plan: Optional[List[Dict[str, Any]]] = None # OnboardingStep list
    onboarding_progress_index: int = 0  # interactive tutor용
    onboarding_summary: Optional[str] = None # 온보딩 플랜 요약 텍스트

    # 5) 대화/요약 컨텍스트
    last_answer_kind: AnswerKind = "none"        # "report" / "plan" / "explain"
    last_explain_target: Optional[str] = None    # "metric" / "plan" 등
    messages: List[Any] = [] # LangGraph message history

    # 6) 에러
    error: Optional[str] = None
