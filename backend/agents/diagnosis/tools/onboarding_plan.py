"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .onboarding.onboarding_plan import (
    OnboardingPlan,
    create_onboarding_plan,
    create_onboarding_plan_v0,
    create_onboarding_plan_v1,
)
# Internal functions for testing
from .onboarding.onboarding_plan import (
    _compute_difficulty,
    _compute_recommended,
    _generate_first_steps_rule_based,
    _generate_risks_rule_based,
    _estimate_setup_time,
)

__all__ = [
    "OnboardingPlan",
    "create_onboarding_plan",
    "create_onboarding_plan_v0",
    "create_onboarding_plan_v1",
]
