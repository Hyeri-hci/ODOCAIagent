"""
Health Score v1.0 - 프로젝트 건강도 및 온보딩 점수

Scores:
  - health_score: 운영/유지보수 중심 (doc 30% + activity 70%)
  - onboarding_score: 초보자 친화도 (doc 60% + activity 40%)
  - is_healthy: 임계값 기반 플래그 (doc >= 60 AND activity >= 50)

Spec: docs/CHAOSS_ACTIVITY_SCORE_v1.md
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class HealthScore:
    documentation_quality: int           # D (0-100, README 8카테고리 기반)
    activity_maintainability: int        # A (0-100, CHAOSS 기반)
    health_score: int                    # 모델 2: 0.3*D + 0.7*A
    onboarding_score: int                # 모델 1: 0.6*D + 0.4*A
    overall_score: int                   # = health_score (backward compat)
    is_healthy: bool                     # 모델 3: D >= 60 AND A >= 50

    def to_dict(self):
        return asdict(self)


# === Score Computation ===

def compute_health_score(doc: int, activity: int) -> int:
    """모델 2: 운영/유지보수 Health (doc 30% + activity 70%)"""
    return round(0.3 * doc + 0.7 * activity)


def compute_onboarding_score(doc: int, activity: int) -> int:
    """모델 1: 온보딩 친화도 (doc 60% + activity 40%)"""
    return round(0.6 * doc + 0.4 * activity)


def compute_is_healthy(doc: int, activity: int) -> bool:
    """모델 3: 임계값 기반 건강 플래그"""
    return doc >= 60 and activity >= 50


def create_health_score(doc: int, activity: int) -> HealthScore:
    """D, A 점수로 HealthScore 생성"""
    health = compute_health_score(doc, activity)
    onboarding = compute_onboarding_score(doc, activity)
    is_healthy = compute_is_healthy(doc, activity)

    return HealthScore(
        documentation_quality=doc,
        activity_maintainability=activity,
        health_score=health,
        onboarding_score=onboarding,
        overall_score=health,  # backward compat
        is_healthy=is_healthy,
    )
