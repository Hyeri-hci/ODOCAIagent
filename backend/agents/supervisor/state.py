"""SupervisorState - LangGraph 상태 정의."""
from __future__ import annotations

from typing import Annotated, Any, List, Literal, Optional, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

from backend.core.models import (
    RepoSnapshot,
    DiagnosisCoreResult,
    DependencySnapshot,
    DocsCoreResult,
    ActivityCoreResult,
    ProjectRules,
    UserGuidelines,
)


class SupervisorState(TypedDict):
    """Supervisor State Definition."""
    
    # Messages
    messages: Annotated[List[AnyMessage], add_messages]
    
    # Repository Info
    owner: str
    repo: str
    repo_ref: str
    repo_id: str
    
    # Snapshots & Results
    repo_snapshot: Optional[RepoSnapshot]
    dependency_snapshot: Optional[DependencySnapshot]
    diagnosis_result: Optional[DiagnosisCoreResult]
    security_result: Optional[Any]  # SecurityResult placeholder
    docs_result: Optional[DocsCoreResult]
    activity_result: Optional[ActivityCoreResult]
    
    # Context
    project_rules: Optional[ProjectRules]
    # 리포지토리 단위로 장기 적용되는 규칙 (예: "프론트엔드 이슈 우선", "문서 먼저 개선")
    
    session_guidelines: Optional[UserGuidelines]
    # 이번 진단/추천 세션에만 적용되는 일시적인 지침 (예: "초보자 기여 위주로만 알려줘")
    
    # Control Flow
    task_type: Literal["diagnosis", "security", "diagnosis_and_security", "recommendation", "explain"]
    run_security: bool
    run_security: bool
    run_recommendation: bool
    use_llm_summary: bool  # LLM 요약 사용 여부 (False면 Core 결과만 단순 요약)

    last_answer_kind: Optional[Literal["diagnosis", "security", "recommendation", "explain"]]

    # Error
    error_message: Optional[str]
