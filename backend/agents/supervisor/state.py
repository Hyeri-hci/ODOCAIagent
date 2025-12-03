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
    session_guidelines: Optional[UserGuidelines]
    
    # Control Flow
    task_type: Literal["diagnosis", "security", "diagnosis_and_security", "recommendation", "explain"]
    run_security: bool
    run_recommendation: bool
    run_recommendation: bool
    last_answer_kind: Optional[Literal["diagnosis", "security", "recommendation", "explain"]]

    # Error
    error_message: Optional[str]
