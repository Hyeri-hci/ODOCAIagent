from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Union
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

def to_summary_dto(repo_id: str, res: Union[DiagnosisCoreResult, Dict[str, Any]]) -> DiagnosisSummaryDTO:
    """DiagnosisCoreResult 또는 dict를 DiagnosisSummaryDTO로 변환합니다.
    
    Note: dict는 다음 형식 중 하나를 지원합니다:
    - DiagnosisCoreResult.to_dict(): 네스트된 scores/labels/complexity 구조
    - DiagnosisOutput.to_dict(): 플랫한 구조
    """
    
    # dict인 경우 구조 분석
    if isinstance(res, dict):
        # 네스트된 구조 체크 (DiagnosisCoreResult.to_dict() 형식)
        if "scores" in res:
            scores = res.get("scores", {})
            labels = res.get("labels", {})
            complexity = res.get("complexity", {})
            
            documentation_quality = scores.get("documentation_quality", 0)
            activity_maintainability = scores.get("activity_maintainability", 0)
            health_score = scores.get("health_score", 0)
            onboarding_score = scores.get("onboarding_score", 0)
            health_level = labels.get("health_level", "bad")
            onboarding_level = labels.get("onboarding_level", "hard")
            dependency_complexity_score = complexity.get("dependency_complexity_score", 0)
            dependency_flags = labels.get("dependency_flags", [])
            docs_issues = labels.get("docs_issues", [])
            activity_issues = labels.get("activity_issues", [])
        else:
            # 플랫한 구조 (DiagnosisOutput.to_dict() 형식)
            documentation_quality = res.get("docs", {}).get("total_score", 0)
            activity_maintainability = res.get("activity", {}).get("total_score", 0)
            health_score = int(res.get("health_score", 0))
            onboarding_score = int(res.get("onboarding_score", 0))
            health_level = res.get("health_level", "bad")
            onboarding_level = res.get("onboarding_level", "hard")
            dependency_complexity_score = res.get("dependency_complexity_score", 0)
            dependency_flags = res.get("dependency_flags", [])
            # DiagnosisOutput에서 docs_issues는 raw_metrics에 있을 수 있음
            raw_metrics = res.get("raw_metrics", {})
            if "labels" in raw_metrics:
                docs_issues = raw_metrics.get("labels", {}).get("docs_issues", [])
                activity_issues = raw_metrics.get("labels", {}).get("activity_issues", [])
            else:
                docs_issues = []
                activity_issues = []
    else:
        # DiagnosisCoreResult 객체인 경우
        documentation_quality = res.documentation_quality
        activity_maintainability = res.activity_maintainability
        health_score = res.health_score
        onboarding_score = res.onboarding_score
        health_level = res.health_level
        onboarding_level = res.onboarding_level
        dependency_complexity_score = res.dependency_complexity_score
        dependency_flags = res.dependency_flags
        docs_issues = res.docs_issues
        activity_issues = res.activity_issues
    
    # 의존성 복잡도 레벨 계산
    if dependency_complexity_score < 30:
        dep_level = "low"
    elif dependency_complexity_score < 70:
        dep_level = "medium"
    else:
        dep_level = "high"

    return DiagnosisSummaryDTO(
        repo_id=repo_id,
        documentation_quality=documentation_quality,
        activity_maintainability=activity_maintainability,
        health_score=health_score,
        health_level=health_level,
        onboarding_score=onboarding_score,
        onboarding_level=onboarding_level,
        dependency_complexity_score=dependency_complexity_score,
        dependency_complexity_level=dep_level,
        dependency_flags=list(dependency_flags),
        docs_issues_count=len(docs_issues),
        activity_issues_count=len(activity_issues),
    )
