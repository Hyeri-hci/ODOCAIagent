"""
벤치마크 설정 및 테스트 저장소 정의

저장소 카테고리:
- very_active: 매우 활발한 대형 프로젝트 (vscode, react 등)
- active: 활발한 중형 프로젝트 (langchain 등)
- small: 소규모 개인/학습 프로젝트
- archived: 아카이브된 프로젝트
- deprecated: 더 이상 유지보수되지 않는 프로젝트
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any


class RepoCategory(Enum):
    """저장소 카테고리"""
    VERY_ACTIVE = "very_active"
    ACTIVE = "active"
    SMALL = "small"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


@dataclass
class RepoInfo:
    """벤치마크용 저장소 정보"""
    owner: str
    repo: str
    category: RepoCategory
    expected_health: str = "good"  # good | warning | bad
    expected_onboarding: str = "easy"  # easy | normal | hard
    notes: str = ""


# 벤치마크 저장소 목록 (Ground Truth)
BENCHMARK_REPOS: List[RepoInfo] = [
    # Very Active (대형 활발 프로젝트)
    RepoInfo("microsoft", "vscode", RepoCategory.VERY_ACTIVE,
             expected_health="good", expected_onboarding="normal",
             notes="매우 큰 코드베이스, 활발한 커뮤니티"),
    RepoInfo("facebook", "react", RepoCategory.VERY_ACTIVE,
             expected_health="good", expected_onboarding="normal",
             notes="잘 정리된 문서, 많은 기여자"),
    RepoInfo("vercel", "next.js", RepoCategory.VERY_ACTIVE,
             expected_health="good", expected_onboarding="easy",
             notes="good-first-issue 라벨 활용"),
    RepoInfo("astral-sh", "ruff", RepoCategory.VERY_ACTIVE,
             expected_health="good", expected_onboarding="easy",
             notes="Rust 기반, 빠른 응답"),

    # Active (중형 활발 프로젝트)
    RepoInfo("langchain-ai", "langchain", RepoCategory.ACTIVE,
             expected_health="good", expected_onboarding="normal",
             notes="빠르게 성장, 문서 개선 중"),
    RepoInfo("pydantic", "pydantic", RepoCategory.ACTIVE,
             expected_health="good", expected_onboarding="easy",
             notes="잘 정리된 기여 가이드"),
    RepoInfo("pallets", "flask", RepoCategory.ACTIVE,
             expected_health="good", expected_onboarding="easy",
             notes="안정적인 프로젝트"),
    RepoInfo("psf", "requests", RepoCategory.ACTIVE,
             expected_health="warning", expected_onboarding="normal",
             notes="성숙한 프로젝트, 느린 변화"),

    # Small (소규모 프로젝트)
    RepoInfo("Hyeri-hci", "OSSDoctor", RepoCategory.SMALL,
             expected_health="warning", expected_onboarding="hard",
             notes="개발 초기 단계"),
    RepoInfo("tiangolo", "typer", RepoCategory.SMALL,
             expected_health="good", expected_onboarding="easy",
             notes="소규모지만 잘 관리됨"),

    # Archived (아카이브)
    RepoInfo("facebookarchive", "flux", RepoCategory.ARCHIVED,
             expected_health="bad", expected_onboarding="hard",
             notes="공식 아카이브"),

    # Deprecated (더 이상 유지보수 안 함)
    RepoInfo("request", "request", RepoCategory.DEPRECATED,
             expected_health="bad", expected_onboarding="hard",
             notes="deprecated 선언됨"),
]


def get_repos_by_category(category: RepoCategory) -> List[RepoInfo]:
    """카테고리별 저장소 필터링"""
    return [r for r in BENCHMARK_REPOS if r.category == category]


def get_active_repos() -> List[RepoInfo]:
    """활성 저장소만 (very_active + active + small)"""
    active_cats = {RepoCategory.VERY_ACTIVE, RepoCategory.ACTIVE, RepoCategory.SMALL}
    return [r for r in BENCHMARK_REPOS if r.category in active_cats]


def get_inactive_repos() -> List[RepoInfo]:
    """비활성 저장소만 (archived + deprecated)"""
    inactive_cats = {RepoCategory.ARCHIVED, RepoCategory.DEPRECATED}
    return [r for r in BENCHMARK_REPOS if r.category in inactive_cats]


@dataclass
class BenchmarkConfig:
    """벤치마크 실행 설정"""
    
    # 실행 설정
    use_cache: bool = True
    cache_ttl_hours: int = 24
    max_retries: int = 3
    timeout_seconds: int = 60
    
    # LLM 설정
    enable_llm: bool = True
    llm_temperature: float = 0.0  # 재현성을 위해 0
    llm_max_tokens: int = 2000
    
    # 출력 설정
    output_dir: str = "test/benchmark_results"
    save_raw_responses: bool = True
    verbose: bool = True
    
    # 평가 설정
    llm_eval_enabled: bool = True
    llm_eval_model: str = "same"  # same | gpt-4 | etc
    repetitions: int = 1  # 재현성 테스트용


# 기대 패턴 정의 (검증용)
EXPECTED_PATTERNS = {
    # 카테고리별 health_score 범위
    "health_score_range": {
        RepoCategory.VERY_ACTIVE: (70, 100),
        RepoCategory.ACTIVE: (60, 100),
        RepoCategory.SMALL: (40, 80),
        RepoCategory.ARCHIVED: (0, 40),
        RepoCategory.DEPRECATED: (0, 30),
    },
    
    # 카테고리별 onboarding_score 범위
    "onboarding_score_range": {
        RepoCategory.VERY_ACTIVE: (60, 100),
        RepoCategory.ACTIVE: (50, 90),
        RepoCategory.SMALL: (30, 70),
        RepoCategory.ARCHIVED: (0, 40),
        RepoCategory.DEPRECATED: (0, 30),
    },
    
    # 비활성 프로젝트에서 study intent 최소 비율
    "inactive_study_intent_min_ratio": 0.3,
    
    # beginner 레벨에서 docs/test kind 최소 비율
    "beginner_docs_test_min_ratio": 0.4,
    
    # archived 프로젝트에서 is_healthy=False 비율
    "archived_unhealthy_min_ratio": 0.8,
}
