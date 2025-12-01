"""
Health Formulas - 점수 공식 및 설명 단일 소스.

모든 점수 공식과 설명을 한 곳에서 관리합니다.
summarize_node에서 explain 모드 시 이 모듈을 import하여 사용합니다.
"""
from __future__ import annotations

# 점수 공식 (사람이 읽을 수 있는 형태)
HEALTH_SCORE_FORMULA = "health_score = 0.3 × documentation_quality + 0.7 × activity_maintainability"
ONBOARDING_SCORE_FORMULA = "onboarding_score = 0.6 × documentation_quality + 0.4 × activity_maintainability"
ACTIVITY_SCORE_FORMULA = "activity = 0.4 × commit + 0.3 × issue + 0.3 × pr"
IS_HEALTHY_FORMULA = "is_healthy = (documentation_quality >= 60) AND (activity_maintainability >= 50)"

# 세부 점수 공식
COMMIT_SCORE_FORMULA = "commit = 0.5 × frequency + 0.3 × recency + 0.2 × diversity"
ISSUE_SCORE_FORMULA = "issue = 0.5 × closure_ratio + 0.5 × resolution_speed"
PR_SCORE_FORMULA = "pr = 0.4 × merge_ratio + 0.6 × merge_speed"

# 공식별 가중치 설명
FORMULA_WEIGHTS = {
    "health_score": {"documentation_quality": 0.3, "activity_maintainability": 0.7},
    "onboarding_score": {"documentation_quality": 0.6, "activity_maintainability": 0.4},
    "activity_maintainability": {"commit": 0.4, "issue": 0.3, "pr": 0.3},
    "commit": {"frequency": 0.5, "recency": 0.3, "diversity": 0.2},
    "issue": {"closure_ratio": 0.5, "resolution_speed": 0.5},
    "pr": {"merge_ratio": 0.4, "merge_speed": 0.6},
}

# 메트릭별 한 줄 설명
METRIC_EXPLANATION = {
    "health_score": "저장소 전반의 건강 상태를 0~100점으로 나타낸 종합 지표",
    "documentation_quality": "README 및 문서 구조의 완성도 (8개 필수 섹션 기준)",
    "activity_maintainability": "최근 90일간 커밋/이슈/PR 처리 속도와 꾸준함",
    "onboarding_score": "신규 기여자가 프로젝트에 진입하기 쉬운 정도",
    "is_healthy": "문서 60점 이상 + 활동성 50점 이상이면 건강한 프로젝트",
}

# 공식 설명 딕셔너리 (explain 모드에서 사용)
SCORE_FORMULA_DESC = {
    "health_score": {
        "formula": HEALTH_SCORE_FORMULA,
        "explanation": METRIC_EXPLANATION["health_score"],
        "weights": FORMULA_WEIGHTS["health_score"],
        "interpretation": {
            "90-100": "매우 우수 - 활발하게 유지보수되는 건강한 프로젝트",
            "80-89": "우수 - 대부분의 지표가 양호함",
            "70-79": "양호 - 기본적인 유지보수가 이루어짐",
            "60-69": "보통 - 일부 개선이 필요함",
            "0-59": "개선 필요 - 문서화 또는 활동성에 주의 필요",
        },
    },
    "documentation_quality": {
        "formula": "8개 필수 섹션 존재 여부 기반 점수 (섹션당 12.5점)",
        "explanation": METRIC_EXPLANATION["documentation_quality"],
        "required_sections": [
            "소개/설명", "설치 방법", "사용법", "기여 가이드",
            "라이선스", "연락처/유지보수자", "배지/상태", "예제 코드"
        ],
    },
    "activity_maintainability": {
        "formula": ACTIVITY_SCORE_FORMULA,
        "explanation": METRIC_EXPLANATION["activity_maintainability"],
        "weights": FORMULA_WEIGHTS["activity_maintainability"],
        "sub_formulas": {
            "commit": COMMIT_SCORE_FORMULA,
            "issue": ISSUE_SCORE_FORMULA,
            "pr": PR_SCORE_FORMULA,
        },
    },
    "onboarding_score": {
        "formula": ONBOARDING_SCORE_FORMULA,
        "explanation": METRIC_EXPLANATION["onboarding_score"],
        "weights": FORMULA_WEIGHTS["onboarding_score"],
        "factors": [
            "문서 품질 (60% 비중)",
            "활동성 - 이슈/PR 응답 속도 (40% 비중)",
            "good first issue 라벨 존재 여부",
            "CONTRIBUTING.md 존재 여부",
        ],
    },
}


def get_formula_desc(metric: str) -> dict | None:
    """메트릭에 대한 공식 설명 반환"""
    return SCORE_FORMULA_DESC.get(metric)


def get_metric_explanation(metric: str) -> str:
    """메트릭에 대한 한 줄 설명 반환"""
    return METRIC_EXPLANATION.get(metric, f"{metric}에 대한 설명이 없습니다.")
