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
VALID_SUB_INTENTS: list[str] = [
    "health", "onboarding", "compare", "onepager",  # analyze
    "explain", "evidence", "refine",                 # followup
    "chat", "concept",                                # general_qa
    "greeting", "chitchat",                           # smalltalk
    "getting_started",                                # help
    "repo",                                           # overview
]


# Confidence thresholds for hierarchical routing (Step 8: 의도별 임계)
# 비용에 맞춘 전환 기준: 고비용 intent는 높은 임계, 저비용은 낮은 임계
CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "smalltalk": 0.3,      # 경량: 가장 낮은 임계
    "help": 0.4,           # 경량: 낮은 임계
    "overview": 0.4,       # 저비용: 낮은 임계
    "general_qa": 0.5,     # 저비용: 중간 임계
    "followup": 0.5,       # 중비용: 중간 임계
    "recommendation": 0.5, # 중비용: 중간 임계
    "analyze": 0.6,        # 고비용: 높은 임계
    "compare": 0.6,        # 고비용: 높은 임계
}

# Disambiguation 임계 (이 미만이면 사용자에게 명확화 요청)
DISAMBIGUATION_THRESHOLDS: dict[str, float] = {
    "smalltalk": 0.15,
    "help": 0.2,
    "overview": 0.25,
    "general_qa": 0.3,
    "followup": 0.3,
    "recommendation": 0.3,
    "analyze": 0.4,
    "compare": 0.4,
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_DISAMBIGUATION_THRESHOLD = 0.3


def get_confidence_threshold(intent: str) -> float:
    """Get required confidence threshold for an intent."""
    return CONFIDENCE_THRESHOLDS.get(intent, DEFAULT_CONFIDENCE_THRESHOLD)


def get_disambiguation_threshold(intent: str) -> float:
    """Get disambiguation threshold for an intent."""
    return DISAMBIGUATION_THRESHOLDS.get(intent, DEFAULT_DISAMBIGUATION_THRESHOLD)


def should_degrade_to_help(intent: str, confidence: float) -> bool:
    """Check if low confidence should degrade to help.getting_started."""
    threshold = get_confidence_threshold(intent)
    return confidence < threshold


def should_disambiguate(intent: str, confidence: float) -> bool:
    """Check if confidence is too low and requires disambiguation."""
    threshold = get_disambiguation_threshold(intent)
    return confidence < threshold


# V1 Supported Intent combinations
V1_SUPPORTED_INTENTS: Set[Tuple[str, str]] = {
    ("analyze", "health"),
    ("analyze", "onboarding"),
    ("analyze", "compare"),
    ("analyze", "onepager"),
    ("followup", "explain"),
    ("followup", "evidence"),
    ("followup", "refine"),
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
    ("analyze", "compare"): {"requires_repo": True, "runs_diagnosis": False},  # expert_node
    ("analyze", "onepager"): {"requires_repo": True, "runs_diagnosis": False},  # expert_node
    ("followup", "explain"): {"requires_repo": True, "runs_diagnosis": True},
    ("followup", "evidence"): {"requires_repo": False, "runs_diagnosis": False},
    ("followup", "refine"): {"requires_repo": False, "runs_diagnosis": False},
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
    ("analyze", "compare"): "compare",
    ("analyze", "onepager"): "onepager",
    ("followup", "explain"): "explain",
    ("followup", "evidence"): "explain",
    ("followup", "refine"): "refine",
    ("general_qa", "concept"): "concept",
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
