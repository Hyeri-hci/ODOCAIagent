"""Onboarding Task 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional

Difficulty = Literal["beginner", "intermediate", "advanced"]
TaskKind = Literal["issue", "doc", "test", "refactor", "meta"]
TaskIntent = Literal["contribute", "study", "evaluate"]


@dataclass
class TaskSuggestion:
    """개별 Task 제안."""
    kind: TaskKind
    difficulty: Difficulty
    level: int  # 1-6 (게임식 레벨)
    id: str  # "issue#123", "meta:improve_contributing"
    title: str
    url: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    reason_tags: List[str] = field(default_factory=list)
    meta_flags: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    intent: TaskIntent = "contribute"
    task_score: float = 0.0  # 0-100
    recency_days: Optional[int] = None
    comment_count: int = 0
    estimated_hours: Optional[float] = None
    required_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OnboardingTasks:
    """난이도별 Task 모음."""
    beginner: List[TaskSuggestion] = field(default_factory=list)
    intermediate: List[TaskSuggestion] = field(default_factory=list)
    advanced: List[TaskSuggestion] = field(default_factory=list)
    total_count: int = 0
    issue_count: int = 0
    meta_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beginner": [t.to_dict() for t in self.beginner],
            "intermediate": [t.to_dict() for t in self.intermediate],
            "advanced": [t.to_dict() for t in self.advanced],
            "meta": {
                "total_count": self.total_count,
                "issue_count": self.issue_count,
                "meta_count": self.meta_count,
            },
        }


@dataclass
class UserTaskContext:
    """사용자 컨텍스트 기반 Task 필터링용."""
    level: str = "beginner"
    preferred_skills: List[str] = field(default_factory=list)
    max_hours: Optional[float] = None
    intent: TaskIntent = "contribute"
