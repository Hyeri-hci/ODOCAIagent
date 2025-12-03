"""라벨 분류 상수 및 라벨 기반 판단 함수."""
from __future__ import annotations

from typing import List

from .models import Difficulty, TaskKind


# 라벨 분류
BEGINNER_LABELS = {
    "good first issue", "good-first-issue", "beginner", "beginner-friendly",
    "first-timers-only", "first-time-contributor", "easy", "starter",
    "newbie", "hacktoberfest",
}
INTERMEDIATE_LABELS = {
    "help wanted", "help-wanted", "documentation", "docs", "tests",
    "testing", "enhancement", "feature", "improvement",
}
ADVANCED_LABELS = {
    "bug", "critical", "security", "performance", "refactor",
    "breaking-change", "architecture", "core",
}
PRIORITY_LABELS = [
    "good first issue", "good-first-issue", "beginner", "beginner-friendly",
    "first-timers-only", "help wanted", "help-wanted", "documentation",
    "docs", "hacktoberfest",
]

# Level → 예상 시간 매핑 (시간 단위)
LEVEL_HOURS_MAP = {
    1: 1.0,
    2: 2.0,
    3: 4.0,
    4: 8.0,
    5: 16.0,
    6: 24.0,
}

# 라벨 → 기술 키워드 매핑
LABEL_SKILL_MAP = {
    "react": ["React", "JavaScript"],
    "typescript": ["TypeScript"],
    "python": ["Python"],
    "java": ["Java"],
    "rust": ["Rust"],
    "go": ["Go"],
    "c++": ["C++"],
    "frontend": ["Frontend", "HTML", "CSS"],
    "backend": ["Backend"],
    "api": ["API", "REST"],
    "graphql": ["GraphQL"],
    "database": ["Database", "SQL"],
    "docker": ["Docker"],
    "kubernetes": ["Kubernetes"],
    "testing": ["Testing"],
    "ci/cd": ["CI/CD"],
    "documentation": ["Documentation", "Technical Writing"],
    "docs": ["Documentation"],
}


def get_estimated_hours_from_level(level: int) -> float:
    """레벨에서 예상 소요 시간 추정."""
    return LEVEL_HOURS_MAP.get(level, 4.0)


def extract_skills_from_labels(labels: List[str]) -> List[str]:
    """라벨에서 필요 기술 추론."""
    skills = []
    for label in labels:
        label_lower = label.lower()
        for key, skill_list in LABEL_SKILL_MAP.items():
            if key in label_lower:
                for skill in skill_list:
                    if skill not in skills:
                        skills.append(skill)
    return skills


def determine_difficulty_from_labels(labels: List[str]) -> Difficulty:
    """라벨 목록에서 난이도 결정."""
    labels_lower = {label.lower() for label in labels}
    if labels_lower & BEGINNER_LABELS:
        return "beginner"
    if labels_lower & ADVANCED_LABELS:
        return "advanced"
    return "intermediate"


def determine_level(difficulty: Difficulty, labels: List[str], comment_count: int = 0) -> int:
    """난이도/메타데이터 기반 레벨 결정 (1-6)."""
    labels_lower = {label.lower() for label in labels}

    if difficulty == "beginner":
        if labels_lower & {"good first issue", "good-first-issue", "first-timers-only"}:
            return 1
        return 2
    elif difficulty == "intermediate":
        if labels_lower & {"documentation", "docs", "tests", "testing"}:
            return 3
        return 4
    else:
        return 6 if comment_count > 10 else 5


def determine_kind_from_labels(labels: List[str]) -> TaskKind:
    """라벨에서 Task 종류 결정."""
    labels_lower = {label.lower() for label in labels}
    if labels_lower & {"documentation", "docs"}:
        return "doc"
    if labels_lower & {"tests", "testing", "test"}:
        return "test"
    if labels_lower & {"refactor", "refactoring", "cleanup"}:
        return "refactor"
    return "issue"
