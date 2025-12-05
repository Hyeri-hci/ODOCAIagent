from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class DiagnosisInput(BaseModel):
    owner: str
    repo: str
    ref: str = "main"
    use_llm_summary: bool = True

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
    
    # 요약
    summary_for_user: str
    
    # 원본 메트릭 (선택적)
    raw_metrics: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
