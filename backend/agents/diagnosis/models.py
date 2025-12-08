from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel
from backend.agents.shared.agent_mode import AgentMode, AgentModeLiteral

# 분석 깊이 타입 정의
AnalysisDepth = Literal["deep", "standard", "quick"]

class DiagnosisInput(BaseModel):
    owner: str
    repo: str
    ref: str = "main"
    use_llm_summary: bool = True
    analysis_depth: AnalysisDepth = "standard"
    mode: AgentModeLiteral = AgentMode.AUTO  # 분석 깊이 (deep/standard/quick)


class DiagnosisOutput(BaseModel):
    repo_id: str
    health_score: float
    health_level: str
    onboarding_score: float
    onboarding_level: str
    
    # 상세 결과
    docs: Dict[str, Any]
    activity: Dict[str, Any]
    structure: Dict[str, Any] # 추가된 필드
    dependency_complexity_score: int
    dependency_flags: List[str]
    
    # 저장소 메타데이터
    stars: int = 0
    forks: int = 0
    
    # 요약
    summary_for_user: str
    
    # 원본 메트릭 (선택적)
    raw_metrics: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# Diagnosis LangGraph 상태 모델
class DiagnosisState(BaseModel):
    """Diagnosis LangGraph 상태 모델."""
    # 입력값
    owner: str
    repo: str
    ref: str = "main"
    analysis_depth: AnalysisDepth = "standard"
    use_llm_summary: bool = True
    
    # 진행 상태
    step: int = 0
    max_step: int = 10
    
    # GitHub 스냅샷 (첫 단계에서 수집)
    repo_snapshot: Optional[Dict[str, Any]] = None
    
    # 개별 분석 결과 (각 노드에서 설정)
    docs_result: Optional[Dict[str, Any]] = None
    activity_result: Optional[Dict[str, Any]] = None
    structure_result: Optional[Dict[str, Any]] = None
    deps_result: Optional[Dict[str, Any]] = None
    
    # 점수 계산 결과
    scoring_result: Optional[Dict[str, Any]] = None
    
    # 요약
    summary_text: Optional[str] = None
    
    # 최종 결과
    diagnosis_output: Optional[Dict[str, Any]] = None
    
    # 에러 및 복구
    error: Optional[str] = None
    failed_step: Optional[str] = None
    retry_count: int = 0
    max_retry: int = 2
    
    # 타이밍 정보
    timings: Dict[str, float] = {}
    
    # 스킵할 컴포넌트
    skip_components: List[str] = []
    
    def get_partial_result(self) -> Dict[str, Any]:
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

