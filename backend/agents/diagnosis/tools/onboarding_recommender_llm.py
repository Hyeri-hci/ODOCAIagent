"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .onboarding.onboarding_recommender_llm import *
from .onboarding.onboarding_recommender_llm import (
    _create_fallback_enrichment,
    _create_fallback_scenario,
    _extract_json,
    _estimate_time_from_level,
    _parse_enrichment_response,
    _parse_scenario_response,
)
