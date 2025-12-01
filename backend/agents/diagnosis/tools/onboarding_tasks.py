"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .onboarding.onboarding_tasks import *
from .onboarding.onboarding_tasks import (
    _fetch_issues_rest,
    _estimate_hours_from_level,
    _calculate_skill_match_score,
    _calculate_time_fit_score,
)
