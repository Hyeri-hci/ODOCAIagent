"""Task 점수 및 Intent 결정 로직."""
from __future__ import annotations

from typing import List, Optional

from .models import Difficulty, TaskIntent


def compute_task_score(
    difficulty: Difficulty,
    labels: List[str],
    comment_count: int = 0,
    recency_days: Optional[int] = None,
) -> float:
    """Task 우선순위 점수 (0-100). 구성: 라벨(40) + 최신성(30) + 복잡도(30)."""
    from backend.agents.diagnosis.config import DIAGNOSIS_CONFIG
    w = DIAGNOSIS_CONFIG.task_score

    score = 0.0
    labels_lower = {label.lower() for label in labels}

    # 라벨 점수 (최대 40점)
    if labels_lower & {"good first issue", "good-first-issue"}:
        score += w.label_good_first_issue
    elif labels_lower & {"hacktoberfest"}:
        score += w.label_hacktoberfest
    elif labels_lower & {"help wanted", "help-wanted"}:
        score += w.label_help_wanted
    elif labels_lower & {"documentation", "docs"}:
        score += w.label_documentation
    elif labels_lower & {"tests", "testing"}:
        score += w.label_tests
    elif labels_lower & {"bug"}:
        score += w.label_bug
    else:
        score += w.label_default

    # 최신성 점수 (최대 30점)
    if recency_days is not None:
        if recency_days <= 7:
            score += w.recency_7d
        elif recency_days <= 30:
            score += w.recency_30d
        elif recency_days <= 90:
            score += w.recency_90d
        elif recency_days <= 180:
            score += w.recency_180d

    # 복잡도 점수 (댓글 적을수록 초보자 친화, 최대 30점)
    if comment_count <= 2:
        score += w.complexity_low
    elif comment_count <= 5:
        score += w.complexity_medium
    elif comment_count <= 10:
        score += w.complexity_high
    else:
        score += w.complexity_very_high

    return min(score, 100.0)


def determine_intent(difficulty: Difficulty, is_healthy: bool, is_active: bool) -> TaskIntent:
    """Task intent 결정. 정책: 건강+활성→contribute, 비활성→study."""
    if is_healthy and is_active:
        return "contribute"
    
    if not is_active:
        if difficulty == "advanced":
            return "evaluate"
        return "study"
    
    if difficulty == "beginner":
        return "study"
    return "contribute"


def generate_reason_tags(labels: List[str], difficulty: Difficulty) -> List[str]:
    """라벨에서 추천 이유 태그 생성."""
    tags: List[str] = []
    labels_lower = {label.lower() for label in labels}

    tag_map = {
        "good_first_issue": {"good first issue", "good-first-issue"},
        "help_wanted": {"help wanted", "help-wanted"},
        "docs_issue": {"documentation", "docs"},
        "test_issue": {"tests", "testing"},
        "hacktoberfest": {"hacktoberfest"},
        "bug_fix": {"bug"},
        "security_issue": {"security"},
        "feature_request": {"enhancement", "feature"},
        "refactoring": {"refactor", "refactoring"},
    }

    for tag, label_set in tag_map.items():
        if labels_lower & label_set:
            tags.append(tag)

    return tags or [f"difficulty_{difficulty}"]


def generate_fallback_reason(difficulty: Difficulty, reason_tags: List[str]) -> str:
    """태그 기반 기본 추천 이유 문장."""
    parts = []
    tag_reasons = {
        "good_first_issue": "메인테이너가 초보자용으로 표시한 이슈",
        "help_wanted": "기여자를 적극적으로 찾는 이슈",
        "docs_issue": "코드 이해 없이도 기여 가능",
        "test_issue": "코드베이스 학습에 도움",
        "hacktoberfest": "Hacktoberfest 참여 가능",
        "bug_fix": "버그 수정 이슈",
        "security_issue": "보안 관련 이슈",
    }

    for tag, reason in tag_reasons.items():
        if tag in reason_tags:
            parts.append(reason)

    if parts:
        return ", ".join(parts)

    difficulty_reasons = {
        "beginner": "초보자도 도전 가능한 난이도",
        "intermediate": "중급 수준의 기여 이슈",
        "advanced": "경험자에게 적합한 도전적인 이슈",
    }
    return difficulty_reasons.get(difficulty, "")
