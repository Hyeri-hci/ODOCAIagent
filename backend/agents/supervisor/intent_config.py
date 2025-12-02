"""Intent configuration for Supervisor V1 with hierarchical routing."""
from __future__ import annotations

from typing import Literal, TypedDict, Set, Tuple

from .models import (
    SupervisorIntent, 
    SubIntent,
    AnswerKind,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)


VALID_INTENTS: list[str] = ["analyze", "followup", "general_qa", "smalltalk", "help", "overview"]
VALID_SUB_INTENTS: list[str] = ["health", "onboarding", "explain", "chat", "greeting", "chitchat", "getting_started", "concept", "repo"]


# Confidence thresholds for hierarchical routing
CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "smalltalk": 0.3,      # Low bar for greetings
    "help": 0.4,           # Low bar for help requests
    "overview": 0.4,       # Low bar for repo introductions
    "general_qa": 0.5,     # Medium bar for general questions
    "followup": 0.5,       # Medium bar for follow-ups
    "analyze": 0.6,        # High bar for diagnosis (expensive operation)
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.5


def get_confidence_threshold(intent: str) -> float:
    """Get required confidence threshold for an intent."""
    return CONFIDENCE_THRESHOLDS.get(intent, DEFAULT_CONFIDENCE_THRESHOLD)


def should_degrade_to_help(intent: str, confidence: float) -> bool:
    """Check if low confidence should degrade to help.getting_started."""
    threshold = get_confidence_threshold(intent)
    return confidence < threshold


# V1 Supported Intent combinations
V1_SUPPORTED_INTENTS: Set[Tuple[str, str]] = {
    ("analyze", "health"),
    ("analyze", "onboarding"),
    ("followup", "explain"),
    ("general_qa", "chat"),
    ("general_qa", "concept"),
    ("smalltalk", "greeting"),
    ("smalltalk", "chitchat"),
    ("help", "getting_started"),
    ("overview", "repo"),
}


def is_v1_supported(intent: str, sub_intent: str) -> bool:
    """Check if (intent, sub_intent) is supported in V1."""
    return (intent, sub_intent) in V1_SUPPORTED_INTENTS


class IntentMeta(TypedDict):
    """Routing metadata for (intent, sub_intent)."""
    requires_repo: bool
    runs_diagnosis: bool


INTENT_META: dict[Tuple[str, str], IntentMeta] = {
    ("analyze", "health"): {"requires_repo": True, "runs_diagnosis": True},
    ("analyze", "onboarding"): {"requires_repo": True, "runs_diagnosis": True},
    ("followup", "explain"): {"requires_repo": True, "runs_diagnosis": True},
    ("general_qa", "concept"): {"requires_repo": False, "runs_diagnosis": False},
    ("general_qa", "chat"): {"requires_repo": False, "runs_diagnosis": False},
    ("smalltalk", "greeting"): {"requires_repo": False, "runs_diagnosis": False},
    ("smalltalk", "chitchat"): {"requires_repo": False, "runs_diagnosis": False},
    ("help", "getting_started"): {"requires_repo": False, "runs_diagnosis": False},
    ("overview", "repo"): {"requires_repo": True, "runs_diagnosis": False},
}

DEFAULT_INTENT_META: IntentMeta = {"requires_repo": False, "runs_diagnosis": False}


ANSWER_KIND_MAP: dict[tuple[str, str], AnswerKind] = {
    ("analyze", "health"): "report",
    ("analyze", "onboarding"): "report",
    ("followup", "explain"): "explain",
    ("general_qa", "concept"): "chat",
    ("general_qa", "chat"): "chat",
    ("smalltalk", "greeting"): "greeting",
    ("smalltalk", "chitchat"): "greeting",
    ("help", "getting_started"): "chat",
    ("overview", "repo"): "chat",
}

DEFAULT_ANSWER_KIND: AnswerKind = "chat"


def get_intent_meta(intent: str, sub_intent: str | None = None) -> IntentMeta:
    """Get routing metadata for (intent, sub_intent)."""
    sub_intent = sub_intent or DEFAULT_SUB_INTENT
    return INTENT_META.get((intent, sub_intent), DEFAULT_INTENT_META)


def get_answer_kind(intent: str, sub_intent: str | None = None) -> AnswerKind:
    """Get AnswerKind for UI badges."""
    sub_intent = sub_intent or DEFAULT_SUB_INTENT
    return ANSWER_KIND_MAP.get((intent, sub_intent), DEFAULT_ANSWER_KIND)


def validate_intent(intent: str | None) -> SupervisorIntent:
    """Validate intent, return default if invalid."""
    if intent in VALID_INTENTS:
        return intent  # type: ignore
    return DEFAULT_INTENT


def validate_sub_intent(sub_intent: str | None) -> SubIntent:
    """Validate sub_intent, return default if invalid."""
    if sub_intent in VALID_SUB_INTENTS:
        return sub_intent  # type: ignore
    return DEFAULT_SUB_INTENT


def validate_followup_type(followup_type: str | None) -> str | None:
    """V1: Returns None (followup types not used)."""
    return None
