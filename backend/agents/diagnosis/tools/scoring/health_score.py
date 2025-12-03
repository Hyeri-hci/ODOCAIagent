"""Health Score v2.0 - 프로젝트 건강도 및 온보딩 점수 + docs_effective + sustainability_gate."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional


@dataclass
class HealthScore:
    # 기존 필드 (v1 호환)
    documentation_quality: int           # D (0-100, README 8카테고리 기반) = docs_quality_raw
    activity_maintainability: int        # A (0-100, CHAOSS 기반)
    health_score: int                    # 모델 2: 0.3*D + 0.7*A
    onboarding_score: int                # 모델 1: 0.6*D + 0.4*A
    overall_score: int                   # = health_score (backward compat)
    is_healthy: bool                     # 모델 3: D >= 60 AND A >= 50
    
    # v2 신규 필드
    docs_quality_raw: int = 0            # 형식 기반 문서 점수 (= documentation_quality)
    docs_effective: int = 0              # 유효 문서 점수 (tech - marketing + consilience)
    tech_score: int = 0                  # 기술 신호 점수
    marketing_penalty: int = 0           # 마케팅 페널티
    consilience_score: int = 0           # 교차검증 점수
    
    # Sustainability Gate
    sustainability_score: int = 0        # 지속가능성 점수 (0-100)
    gate_level: str = "unknown"          # active | maintained | stale | abandoned
    is_sustainable: bool = True          # 게이트 통과 여부
    
    # 플래그
    is_marketing_heavy: bool = False     # 마케팅 과다 README
    has_broken_refs: bool = False        # 교차검증 실패 항목 존재

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    """D, A 점수로 HealthScore 생성 (v1 호환)"""
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
        docs_quality_raw=doc,
    )


def create_health_score_v2(
    doc: int,
    activity: int,
    docs_effective: int = 0,
    tech_score: int = 0,
    marketing_penalty: int = 0,
    consilience_score: int = 0,
    sustainability_score: int = 0,
    gate_level: str = "unknown",
    is_sustainable: bool = True,
    is_marketing_heavy: bool = False,
    has_broken_refs: bool = False,
) -> HealthScore:
    """v2: 확장 필드 포함 HealthScore 생성."""
    health = compute_health_score(doc, activity)
    
    # v2: onboarding은 docs_effective 기반으로 계산
    effective_doc = docs_effective if docs_effective > 0 else doc
    onboarding = compute_onboarding_score(effective_doc, activity)
    
    # v2: is_healthy는 sustainability gate도 고려
    is_healthy = compute_is_healthy(doc, activity) and is_sustainable

    return HealthScore(
        documentation_quality=doc,
        activity_maintainability=activity,
        health_score=health,
        onboarding_score=onboarding,
        overall_score=health,
        is_healthy=is_healthy,
        docs_quality_raw=doc,
        docs_effective=docs_effective,
        tech_score=tech_score,
        marketing_penalty=marketing_penalty,
        consilience_score=consilience_score,
        sustainability_score=sustainability_score,
        gate_level=gate_level,
        is_sustainable=is_sustainable,
        is_marketing_heavy=is_marketing_heavy,
        has_broken_refs=has_broken_refs,
    )
