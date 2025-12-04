from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from backend.core.models import DiagnosisCoreResult

@dataclass
class DiagnosisSummaryDTO:
    """프론트엔드 및 CLI에서 공통으로 사용할 진단 결과 요약 DTO."""
    repo_id: str
    documentation_quality: int
    activity_maintainability: int
    health_score: int
    health_level: str
    onboarding_score: int
    onboarding_level: str
    dependency_complexity_score: int
    dependency_complexity_level: str
    dependency_flags: List[str]
    docs_issues_count: int
    activity_issues_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def to_summary_dto(repo_id: str, res: DiagnosisCoreResult) -> DiagnosisSummaryDTO:
    """DiagnosisCoreResult를 DiagnosisSummaryDTO로 변환합니다."""
    
    # 의존성 복잡도 레벨 계산
    score = res.dependency_complexity_score
    if score < 30:
        dep_level = "low"
    elif score < 70:
        dep_level = "medium"
    else:
        dep_level = "high"

    return DiagnosisSummaryDTO(
        repo_id=repo_id,
        documentation_quality=res.documentation_quality,
        activity_maintainability=res.activity_maintainability,
        health_score=res.health_score,
        health_level=res.health_level,
        onboarding_score=res.onboarding_score,
        onboarding_level=res.onboarding_level,
        dependency_complexity_score=res.dependency_complexity_score,
        dependency_complexity_level=dep_level,
        dependency_flags=list(res.dependency_flags),
        docs_issues_count=len(res.docs_issues),
        activity_issues_count=len(res.activity_issues),
    )
