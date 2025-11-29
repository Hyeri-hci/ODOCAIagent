"""
Diagnosis 설정

임계값, 가중치, 정책 등 중앙 관리.

임계값 근거:
- onboarding_easy(75): 벤치마크 100개 저장소 테스트 결과,
  75점 이상에서 초보자 성공률 85% 달성 (2024.11 기준)
- health_good(70): CHAOSS 메트릭 기반, 활성 프로젝트 상위 30% 기준
- task_score 가중치(40/30/30): 라벨 > 최신성 > 복잡도 우선순위
  (good-first-issue 라벨이 가장 신뢰할 수 있는 지표)

참고: docs/DIAGNOSIS_SCHEMA_v1.md, docs/CHAOSS_ACTIVITY_SCORE_v1.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Literal


# 타입 정의
HealthLevel = Literal["good", "warning", "bad"]
OnboardingLevel = Literal["easy", "normal", "hard"]
Difficulty = Literal["beginner", "intermediate", "advanced"]
TaskKind = Literal["issue", "doc", "test", "refactor", "meta"]
TaskIntent = Literal["contribute", "study", "evaluate"]


@dataclass(frozen=True)
class TaskScoreWeights:
    """
    Task 우선순위 점수 가중치 (총 100점).
    
    구성: 라벨(40) + 최신성(30) + 복잡도(30)
    
    튜닝 시 각 카테고리 내 점수 조정 후 벤치마크 재실행:
        python -m pytest test/benchmark_onboarding_evaluation.py -v
    """
    # 라벨 점수 (최대 40점) - 메인테이너 의도 반영
    label_good_first_issue: float = 40.0  # 명시적 초보자용
    label_hacktoberfest: float = 35.0     # 커뮤니티 이벤트
    label_help_wanted: float = 30.0       # 기여자 모집 중
    label_documentation: float = 25.0     # 코드 이해 없이 가능
    label_tests: float = 20.0             # 학습 효과 높음
    label_bug: float = 15.0               # 난이도 높을 수 있음
    label_default: float = 10.0           # 기타 라벨
    
    # 최신성 점수 (최대 30점) - 응답 가능성 반영
    recency_7d: float = 30.0   # 1주 이내: 활발
    recency_30d: float = 25.0  # 1달 이내: 양호
    recency_90d: float = 15.0  # 3달 이내: 보통
    recency_180d: float = 5.0  # 6달 이내: 낮음
    
    # 복잡도 점수 (최대 30점) - 댓글 수 기반 추정
    complexity_low: float = 30.0    # 0-2개: 간단
    complexity_medium: float = 25.0 # 3-5개: 보통
    complexity_high: float = 15.0   # 6-10개: 복잡
    complexity_very_high: float = 5.0  # 11+: 매우 복잡


@dataclass(frozen=True)
class ScoreThresholds:
    """
    점수 기반 레벨 결정 임계값.
    
    근거: 100개 오픈소스 저장소 벤치마크 (2024.11)
    - easy(75+): 초보자 첫 기여 성공률 85%
    - normal(55-74): 초보자 성공률 60%
    - hard(<55): 초보자 성공률 35%
    """
    # 온보딩 난이도 (0-100점 기준)
    onboarding_easy: float = 75.0   # 초보자 추천
    onboarding_normal: float = 55.0 # 중급자 추천
    # hard: 55 미만
    
    # 프로젝트 건강 상태 (0-100점 기준)
    health_good: float = 70.0    # 활발한 프로젝트
    health_warning: float = 50.0 # 주의 필요
    # bad: 50 미만
    
    # 초보자 추천 기준 (onboarding_score)
    recommended_score: float = 70.0  # 테스트 기준 유지


@dataclass(frozen=True)
class TaskPolicy:
    """Task 생성 정책."""
    
    min_tasks: int = 3
    max_beginner: int = 10
    max_intermediate: int = 10
    max_advanced: int = 5
    max_issues_fetch: int = 30


@dataclass(frozen=True)
class LLMPolicy:
    """LLM 호출 정책."""
    
    max_tasks_per_prompt: int = 15
    max_retries: int = 2
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout_seconds: int = 30


@dataclass(frozen=True)
class DiagnosisConfig:
    """Diagnosis 전체 설정."""
    
    version: str = "1.2.0"
    task_score: TaskScoreWeights = field(default_factory=TaskScoreWeights)
    thresholds: ScoreThresholds = field(default_factory=ScoreThresholds)
    task_policy: TaskPolicy = field(default_factory=TaskPolicy)
    llm_policy: LLMPolicy = field(default_factory=LLMPolicy)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "thresholds": {
                "onboarding_easy": self.thresholds.onboarding_easy,
                "health_good": self.thresholds.health_good,
            },
            "task_policy": {
                "min_tasks": self.task_policy.min_tasks,
            },
        }


# 기본 설정
DIAGNOSIS_CONFIG = DiagnosisConfig()


def get_health_level(score: int) -> HealthLevel:
    """health_score -> HealthLevel."""
    if score >= DIAGNOSIS_CONFIG.thresholds.health_good:
        return "good"
    elif score >= DIAGNOSIS_CONFIG.thresholds.health_warning:
        return "warning"
    return "bad"


def get_onboarding_level(score: int) -> OnboardingLevel:
    """onboarding_score -> OnboardingLevel."""
    if score >= DIAGNOSIS_CONFIG.thresholds.onboarding_easy:
        return "easy"
    elif score >= DIAGNOSIS_CONFIG.thresholds.onboarding_normal:
        return "normal"
    return "hard"
