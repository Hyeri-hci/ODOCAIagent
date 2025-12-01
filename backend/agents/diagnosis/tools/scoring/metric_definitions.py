"""
Metric Definitions - Single Source of Truth

모든 지표에 대한 정의, 수식, 해석을 한 곳에서 관리합니다.
Concept QA, Explain Scores, UI 도움말 등에서 이 정의를 참조합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricDefinition:
    """지표 정의 구조체"""
    key: str
    name_ko: str
    name_en: str
    aliases: list[str] = field(default_factory=list)
    formula_md: str = ""
    interpretation: str = ""
    range_hint: str = ""
    example: str = ""


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "health_score": MetricDefinition(
        key="health_score",
        name_ko="전체 건강 점수",
        name_en="Health Score",
        aliases=[
            "건강 점수",
            "건강도",
            "프로젝트 건강",
            "health",
            "헬스 스코어",
            "전체 점수",
            "전체 건강",
            "종합 점수",
            "overall",
            "이 리포 어때",
            "전반적으로",
            "종합적으로",
            "전체적으로"
        ],
        formula_md="health_score = 0.3 × 문서 품질(D) + 0.7 × 활동성(A)",
        interpretation="프로젝트의 전반적인 유지보수 가능성과 활력을 종합적으로 평가합니다. "
                       "문서화보다 실제 개발 활동(커밋, 이슈, PR)에 더 큰 가중치를 둡니다.",
        range_hint="90-100: 매우 우수 | 80-89: 우수 | 70-79: 양호 | 60-69: 보통 | 60 미만: 개선 필요",
        example="예: 문서 품질 80점, 활동성 90점이면 → 0.3×80 + 0.7×90 = 24 + 63 = 87점(우수)",
    ),
    "onboarding_score": MetricDefinition(
        key="onboarding_score",
        name_ko="온보딩 용이성",
        name_en="Onboarding Score",
        aliases=[
            "온보딩 점수",
            "진입장벽",
            "진입 장벽",
            "초보자 점수",
            "기여 난이도",
            "onboarding",
            "진입 난이도",
            "온보딩",
            "초보자",
            "입문",
            "처음 기여",
            "신규 기여자",
            "시작하기",
            "쉽게 참여"
        ],
        formula_md="onboarding_score = 0.6 × 문서 품질(D) + 0.4 × 활동성(A)",
        interpretation="신규 기여자가 프로젝트에 참여하기 얼마나 쉬운지를 평가합니다. "
                       "문서화(README, CONTRIBUTING 등)에 더 큰 가중치를 두어 초보자 관점을 반영합니다.",
        range_hint="90-100: 매우 쉬움 | 80-89: 쉬움 | 70-79: 보통 | 60-69: 약간 어려움 | 60 미만: 어려움",
        example="예: 문서 품질 90점, 활동성 70점이면 → 0.6×90 + 0.4×70 = 54 + 28 = 82점(쉬움)",
    ),
    "activity_maintainability": MetricDefinition(
        key="activity_maintainability",
        name_ko="활동성/유지보수성",
        name_en="Activity & Maintainability",
        aliases=[
            "활동성",
            "활동 점수",
            "유지보수성",
            "activity",
            "개발 활동",
            "커밋 활동",
            "activity maintainability",
            "유지보수",
            "커밋",
            "이슈",
            "pr",
            "관리",
            "업데이트",
            "최근 활동",
            "살아있"
        ],
        formula_md="activity = 0.4 × 커밋 점수 + 0.3 × 이슈 점수 + 0.3 × PR 점수",
        interpretation="최근 90일간의 개발 활동을 종합 평가합니다. "
                       "커밋 빈도, 이슈 해결률, PR 병합률을 함께 고려하여 프로젝트가 얼마나 활발히 유지되는지 측정합니다.",
        range_hint="90-100: 매우 활발 | 80-89: 활발 | 70-79: 보통 | 60-69: 저조 | 60 미만: 비활성",
        example="예: 커밋 85점, 이슈 70점, PR 80점이면 → 0.4×85 + 0.3×70 + 0.3×80 = 34 + 21 + 24 = 79점(보통)",
    ),
    "documentation_quality": MetricDefinition(
        key="documentation_quality",
        name_ko="문서 품질",
        name_en="Documentation Quality",
        aliases=[
            "문서 점수",
            "문서화",
            "docs",
            "readme 점수",
            "문서화 수준",
            "문서",
            "리드미",
            "readme",
            "설명서",
            "가이드"
        ],
        formula_md="documentation = (존재하는 필수 섹션 수 / 8) × 100",
        interpretation="README 파일의 필수 섹션(설명, 설치, 사용법, 기여 가이드, 라이선스 등) 존재 여부를 평가합니다. "
                       "8개 필수 섹션 중 몇 개가 있는지를 백분율로 환산합니다.",
        range_hint="100: 완벽 | 87.5: 7개 섹션 | 75: 6개 섹션 | 62.5: 5개 섹션 | 50 이하: 문서 보강 필요",
        example="예: README에 6개 섹션이 있으면 → 6/8 × 100 = 75점(양호, 2개 섹션 추가 권장)",
    ),
}


def get_metric_by_key(key: str) -> Optional[MetricDefinition]:
    """키로 지표 정의 조회"""
    return METRIC_DEFINITIONS.get(key)


def get_metric_by_alias(alias: str) -> Optional[MetricDefinition]:
    """별칭(한글/영문)으로 지표 정의 조회"""
    alias_lower = alias.lower().strip()
    
    for metric in METRIC_DEFINITIONS.values():
        if alias_lower == metric.name_ko.lower():
            return metric
        if alias_lower == metric.name_en.lower():
            return metric
        if alias_lower == metric.key.lower():
            return metric
        for a in metric.aliases:
            if alias_lower == a.lower():
                return metric
    return None


def get_all_metric_keys() -> list[str]:
    """모든 지표 키 목록 반환"""
    return list(METRIC_DEFINITIONS.keys())


def get_all_aliases() -> dict[str, str]:
    """모든 별칭 → 키 매핑 반환"""
    mapping = {}
    for key, metric in METRIC_DEFINITIONS.items():
        mapping[metric.name_ko.lower()] = key
        mapping[metric.name_en.lower()] = key
        mapping[key.lower()] = key
        for alias in metric.aliases:
            mapping[alias.lower()] = key
    return mapping


def format_metric_for_concept_qa(metric: MetricDefinition) -> str:
    """Concept QA용 지표 설명 포맷팅"""
    return f"""### {metric.name_ko} ({metric.name_en})

**수식**: `{metric.formula_md}`

**해석**: {metric.interpretation}

**점수 구간**: {metric.range_hint}

**{metric.example}**"""


def format_metric_for_explain(metric: MetricDefinition, score: float) -> str:
    """Explain 모드용 지표 + 현재 점수 포맷팅"""
    return f"""### {metric.name_ko} ({metric.name_en}): {score:.1f}점

**수식**: `{metric.formula_md}`

**해석**: {metric.interpretation}

**점수 구간**: {metric.range_hint}"""
