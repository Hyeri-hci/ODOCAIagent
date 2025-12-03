"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .scoring.health_score import (
    HealthScore,
    compute_health_score,
    compute_onboarding_score,
    compute_is_healthy,
    create_health_score,
    create_health_score_v2,
)

__all__ = [
    "HealthScore",
    "compute_health_score",
    "compute_onboarding_score",
    "compute_is_healthy",
    "create_health_score",
    "create_health_score_v2",
]
