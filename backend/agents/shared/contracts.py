"""
Agentic Orchestrator 계약 정의.

Phase 1: AnswerContract - LLM 응답에 출처 강제
Phase 2: PlanStep, SupervisorOutput - 계획 수립 및 추론 추적
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# Answer Contract (LLM 응답 출처 강제)

class AnswerContract(BaseModel):
    """LLM 응답 계약: 모든 답변은 출처를 명시해야 함."""
    text: str = Field(..., min_length=1, description="응답 텍스트")
    sources: List[str] = Field(
        default_factory=list, 
        description="참조한 artifact ID 목록"
    )
    source_kinds: List[str] = Field(
        default_factory=list,
        description="참조한 artifact 종류 (diagnosis_raw, python_metrics 등)"
    )
    
    @field_validator("sources", "source_kinds")
    @classmethod
    def validate_non_empty_lists(cls, v: List[str], info) -> List[str]:
        # 빈 리스트 허용하되, sources와 source_kinds 길이는 동일해야 함
        return v
    
    def validate_sources_match(self) -> bool:
        """sources와 source_kinds 길이가 일치하는지 검증."""
        return len(self.sources) == len(self.source_kinds)


# Plan Step & Supervisor Output

class AgentType(str, Enum):
    """사용 가능한 Agent 타입."""
    DIAGNOSIS = "diagnosis"
    SECURITY = "security"
    RECOMMENDATION = "recommendation"
    COMPARE = "compare"
    ONEPAGER = "onepager"


class ErrorAction(str, Enum):
    """에러 발생 시 정책."""
    RETRY = "retry"           # 재시도 (백오프/타임아웃 조정)
    FALLBACK = "fallback"     # 대체 파라미터/경로로 재실행
    ASK_USER = "ask_user"     # 사용자에게 확인 (disambiguation)
    ABORT = "abort"           # 중단


class PlanStep(BaseModel):
    """실행 계획의 단일 스텝."""
    id: str = Field(..., description="스텝 고유 ID (예: fetch_diag, calc_metrics)")
    agent: AgentType = Field(..., description="실행할 Agent 타입")
    params: Dict[str, Any] = Field(default_factory=dict, description="Agent 파라미터")
    needs: List[str] = Field(default_factory=list, description="선행 스텝 ID 목록")
    on_error: ErrorAction = Field(
        default=ErrorAction.FALLBACK, 
        description="에러 발생 시 정책"
    )


class SupervisorPlanOutput(BaseModel):
    """
    Supervisor의 계획 수립 결과.
    
    reasoning_trace는 내부 로그용으로만 사용 (사용자 응답에 포함 금지).
    """
    reasoning_trace: str = Field(
        default="",
        description="내부 추론 로그 (왜 이 계획/노드를 선택했는지)"
    )
    intent: Literal[
        "explain", 
        "task_recommendation", 
        "compare", 
        "onepager", 
        "disambiguation"
    ] = Field(..., description="최종 분류된 Intent")
    plan: List[PlanStep] = Field(
        default_factory=list, 
        description="실행할 스텝 목록"
    )
    artifacts_required: List[str] = Field(
        default_factory=list,
        description="참조해야 할 artifact kind/id 힌트"
    )
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0, 
        description="Intent 분류 신뢰도"
    )


# Error Policy & Inference Hints

class ErrorKind(str, Enum):
    """에러 종류."""
    PERMISSION = "permission"       # 권한 오류 (private repo 등)
    NOT_FOUND = "not_found"         # 저장소/리소스 없음
    NO_DATA = "no_data"             # 데이터 부족 (커밋 0개 등)
    TIMEOUT = "timeout"             # 네트워크 타임아웃
    RATE_LIMIT = "rate_limit"       # API 호출 제한
    INVALID_INPUT = "invalid_input" # 잘못된 입력
    UNKNOWN = "unknown"             # 알 수 없는 오류


# 에러 종류별 기본 정책
ERROR_POLICY: Dict[ErrorKind, ErrorAction] = {
    ErrorKind.PERMISSION: ErrorAction.ASK_USER,
    ErrorKind.NOT_FOUND: ErrorAction.ASK_USER,
    ErrorKind.NO_DATA: ErrorAction.FALLBACK,
    ErrorKind.TIMEOUT: ErrorAction.RETRY,
    ErrorKind.RATE_LIMIT: ErrorAction.RETRY,
    ErrorKind.INVALID_INPUT: ErrorAction.ASK_USER,
    ErrorKind.UNKNOWN: ErrorAction.ABORT,
}


class InferenceHints(BaseModel):
    """누락 옵션 추론 결과."""
    repo_guess: Optional[str] = Field(
        default=None, 
        description="추론된 저장소 (owner/repo 형식)"
    )
    owner: Optional[str] = None
    name: Optional[str] = None
    branch: str = Field(default="main", description="기본 브랜치")
    window_days: int = Field(default=90, description="활동성 분석 기간")
    confidence: float = Field(
        default=0.0, 
        ge=0.0, 
        le=1.0, 
        description="추론 신뢰도"
    )
    inferred_fields: List[str] = Field(
        default_factory=list,
        description="추론된 필드 목록"
    )


# Artifact 관련 타입

class ArtifactKind(str, Enum):
    """Artifact 종류."""
    DIAGNOSIS_RAW = "diagnosis_raw"
    PYTHON_METRICS = "python_metrics"
    README_ANALYSIS = "readme_analysis"
    ACTIVITY_METRICS = "activity_metrics"
    ONBOARDING_TASKS = "onboarding_tasks"
    SUMMARY = "summary"
    INFERENCE_HINTS = "inference_hints"
    PLOT = "plot"
    TABLE = "table"


class ArtifactRef(BaseModel):
    """Artifact 참조."""
    id: str = Field(..., description="Artifact 고유 ID (sha256 기반)")
    kind: ArtifactKind = Field(..., description="Artifact 종류")
    session_id: str = Field(..., description="세션 ID")
    turn_id: Optional[str] = Field(default=None, description="턴 ID")


# Agent Error

class AgentError(Exception):
    """Agent 실행 중 발생한 에러."""
    
    def __init__(
        self, 
        message: str, 
        kind: ErrorKind = ErrorKind.UNKNOWN,
        suggested_fallback: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.kind = kind
        self._suggested_fallback = suggested_fallback or {}
    
    def suggested_fallback(self) -> Dict[str, Any]:
        """대체 파라미터 제안."""
        return self._suggested_fallback
