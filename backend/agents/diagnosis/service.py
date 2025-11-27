from backend.common.models import DiagnosisResult
from .tools.repo_parser import build_repo_metrics
from .tools.health_score import calculate_health_score

def diagnose_repo(full_name: str) -> DiagnosisResult:
    """
      Diagnoses a repository and returns a DiagnosisResult.
      1. Builds repo metrics.
      2. Calculates health score.
      3. Labeling for each diagnosis item.
    """
    metrics = build_repo_metrics(full_name)
    health_score = calculate_health_score(metrics)

    if health_score >= 80:
        activity_level = "high"
        maintenance_level = "good"
        issue_responsiveness = "fast"
        recommendations = "건강한 프로젝트로 보입니다."
    elif health_score >= 50:
        activity_level = "medium"
        maintenance_level = "average"
        issue_responsiveness = "moderate"
        recommendations = "일반적인 수준의 활동성을 보입니다."
    else:
        activity_level = "low"
        maintenance_level = "poor"
        issue_responsiveness = "slow"
        recommendations = "프로젝트의 활동성이 낮아 주의가 필요합니다."



    diagnosis = DiagnosisResult(
        repo_full_name=metrics.repo_full_name,
        health_score=health_score,
        activity_level=activity_level,
        maintenance_level=maintenance_level,
        issue_responsiveness=issue_responsiveness,
        recommendations=recommendations
    )
    return diagnosis