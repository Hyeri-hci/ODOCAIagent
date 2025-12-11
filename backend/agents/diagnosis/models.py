from __future__ import annotations

from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
from backend.agents.shared.agent_mode import AgentMode, AgentModeLiteral

# 분석 깊이 타입 정의
AnalysisDepth = Literal["deep", "standard", "quick"]

class DiagnosisInput(BaseModel):
    """진단 에이전트 입력 모델."""
    owner: str = Field(..., description="저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    ref: str = Field(default="main", description="브랜치/태그 참조")
    use_llm_summary: bool = Field(default=True, description="LLM 요약 사용 여부")
    analysis_depth: AnalysisDepth = Field(default="standard", description="분석 깊이")
    mode: AgentModeLiteral = Field(default="auto", description="분석 모드")


class DiagnosisOutput(BaseModel):
    """진단 에이전트 출력 모델."""
    repo_id: str = Field(..., description="저장소 식별자 (owner/repo)")
    health_score: float = Field(..., ge=0, le=100, description="건강 점수 (0-100)")
    health_level: str = Field(..., description="건강 수준 (Good/Fair/Poor)")
    onboarding_score: float = Field(..., ge=0, le=100, description="온보딩 점수 (0-100)")
    onboarding_level: str = Field(..., description="온보딩 수준")
    
    # 상세 결과
    docs: dict[str, Any] = Field(default_factory=dict, description="문서 분석 결과")
    activity: dict[str, Any] = Field(default_factory=dict, description="활동 분석 결과")
    structure: dict[str, Any] = Field(default_factory=dict, description="구조 분석 결과")
    dependency_complexity_score: int = Field(default=0, description="의존성 복잡도 점수")
    dependency_flags: list[str] = Field(default_factory=list, description="의존성 플래그")
    
    # 저장소 메타데이터
    stars: int = Field(default=0, ge=0, description="스타 수")
    forks: int = Field(default=0, ge=0, description="포크 수")
    
    # 요약
    summary_for_user: str = Field(default="", description="사용자용 요약")
    
    # 원본 메트릭
    raw_metrics: dict[str, Any] = Field(default_factory=dict, description="원본 메트릭")

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return self.model_dump()


class DiagnosisState(BaseModel):
    """Diagnosis LangGraph 상태 모델."""
    
    # 입력값
    owner: str = Field(..., description="저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    ref: str = Field(default="main", description="브랜치/태그 참조")
    analysis_depth: AnalysisDepth = Field(default="standard", description="분석 깊이")
    use_llm_summary: bool = Field(default=True, description="LLM 요약 사용 여부")
    
    # 진행 상태
    step: int = Field(default=0, ge=0, description="현재 단계")
    max_step: int = Field(default=10, ge=1, description="최대 단계")
    
    # GitHub 스냅샷
    repo_snapshot: Optional[dict[str, Any]] = Field(default=None, description="GitHub 스냅샷")
    
    # 개별 분석 결과
    docs_result: Optional[dict[str, Any]] = Field(default=None, description="문서 분석 결과")
    activity_result: Optional[dict[str, Any]] = Field(default=None, description="활동 분석 결과")
    structure_result: Optional[dict[str, Any]] = Field(default=None, description="구조 분석 결과")
    deps_result: Optional[dict[str, Any]] = Field(default=None, description="의존성 분석 결과")
    
    # 점수 계산 결과
    scoring_result: Optional[dict[str, Any]] = Field(default=None, description="점수 계산 결과")
    
    # 요약
    summary_text: Optional[str] = Field(default=None, description="요약 텍스트")
    
    # 최종 결과
    diagnosis_output: Optional[dict[str, Any]] = Field(default=None, description="최종 진단 결과")
    
    # 에러 및 복구
    error: Optional[str] = Field(default=None, description="에러 메시지")
    failed_step: Optional[str] = Field(default=None, description="실패한 단계")
    retry_count: int = Field(default=0, ge=0, description="재시도 횟수")
    max_retry: int = Field(default=2, ge=0, description="최대 재시도 횟수")
    
    # 타이밍 정보
    timings: dict[str, float] = Field(default_factory=dict, description="단계별 소요 시간")
    
    # 스킵할 컴포넌트
    skip_components: list[str] = Field(default_factory=list, description="스킵할 컴포넌트 목록")
    
    # 헬퍼 메서드
    def update_docs_result(self, result: dict[str, Any]) -> "DiagnosisState":
        """문서 분석 결과 업데이트."""
        return self.model_copy(update={"docs_result": result, "step": self.step + 1})
    
    def update_activity_result(self, result: dict[str, Any]) -> "DiagnosisState":
        """활동 분석 결과 업데이트."""
        return self.model_copy(update={"activity_result": result, "step": self.step + 1})
    
    def update_structure_result(self, result: dict[str, Any]) -> "DiagnosisState":
        """구조 분석 결과 업데이트."""
        return self.model_copy(update={"structure_result": result, "step": self.step + 1})
    
    def update_deps_result(self, result: dict[str, Any]) -> "DiagnosisState":
        """의존성 분석 결과 업데이트."""
        return self.model_copy(update={"deps_result": result, "step": self.step + 1})
    
    def update_scoring_result(self, result: dict[str, Any]) -> "DiagnosisState":
        """점수 계산 결과 업데이트."""
        return self.model_copy(update={"scoring_result": result, "step": self.step + 1})
    
    def set_error(self, error: str, failed_step: str) -> "DiagnosisState":
        """에러 설정."""
        return self.model_copy(update={
            "error": error, 
            "failed_step": failed_step,
            "retry_count": self.retry_count + 1,
        })
    
    def add_timing(self, step_name: str, duration: float) -> "DiagnosisState":
        """타이밍 정보 추가."""
        new_timings = {**self.timings, step_name: duration}
        return self.model_copy(update={"timings": new_timings})
    
    def get_partial_result(self) -> dict[str, Any]:
        """현재까지의 부분 결과 반환."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "docs": self.docs_result,
            "activity": self.activity_result,
            "structure": self.structure_result,
            "deps": self.deps_result,
            "scoring": self.scoring_result,
            "summary": self.summary_text,
            "timings": self.timings,
            "error": self.error,
            "failed_step": self.failed_step,
        }
    
    class Config:
        """Pydantic 설정."""
        validate_assignment = True

