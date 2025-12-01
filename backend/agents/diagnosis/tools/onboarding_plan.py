"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .onboarding.onboarding_plan import *
from .onboarding.onboarding_plan import (
    _compute_difficulty,
    _compute_recommended,
    _generate_first_steps_rule_based,
    _generate_risks_rule_based,
    _estimate_setup_time,
)
