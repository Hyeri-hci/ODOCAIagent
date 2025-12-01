from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE: str = os.getenv("GITHUB_API_BASE", "https://api.github.com")

DEFAULT_ACTIVITY_DAYS: int = 90

# LLM Settings
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai_compatible")
LLM_API_BASE: str | None = os.getenv("LLM_API_BASE", "http://localhost:8000/v1")
LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "kanana-1.5-8b-instruct-2505")


# =============================================================================
# Feature Toggles (V1)
# =============================================================================

# Agentic mode: True=full planning, False=simple routing
AGENTIC_MODE: bool = os.getenv("AGENTIC_MODE", "false").lower() == "true"

# Graceful degradation: fallback to simpler paths on error
DEGRADE_ENABLED: bool = os.getenv("DEGRADE_ENABLED", "true").lower() == "true"

# Intent confidence thresholds (per intent type)
INTENT_MIN_CONF_ANALYZE: float = float(os.getenv("INTENT_MIN_CONF_ANALYZE", "0.5"))
INTENT_MIN_CONF_FOLLOWUP: float = float(os.getenv("INTENT_MIN_CONF_FOLLOWUP", "0.5"))
INTENT_MIN_CONF_GENERAL: float = float(os.getenv("INTENT_MIN_CONF_GENERAL", "0.3"))

# Event logging toggle
EVENT_LOGGING_ENABLED: bool = os.getenv("EVENT_LOGGING_ENABLED", "true").lower() == "true"

# Contract enforcement: require non-empty sources
ENFORCE_ANSWER_CONTRACT: bool = os.getenv("ENFORCE_ANSWER_CONTRACT", "true").lower() == "true"

