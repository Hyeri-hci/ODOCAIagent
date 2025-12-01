"""Onboarding Agent v0 - 스코어링 엔진 (건강+온보딩+스택 매칭)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import logging

from .models import UserContext, RepoRecommendation

logger = logging.getLogger(__name__)


# 스택 매칭

# 언어/프레임워크 정규화 맵
LANGUAGE_ALIASES = {
    # Python
    "python": ["python", "py", "django", "flask", "fastapi", "pytorch", "tensorflow"],
    "django": ["python", "django"],
    "flask": ["python", "flask"],
    "fastapi": ["python", "fastapi"],
    
    # JavaScript/TypeScript
    "javascript": ["javascript", "js", "node", "nodejs", "express", "react", "vue", "angular"],
    "typescript": ["typescript", "ts", "react", "vue", "angular", "node"],
    "react": ["javascript", "typescript", "react", "jsx", "tsx"],
    "vue": ["javascript", "typescript", "vue"],
    "node": ["javascript", "typescript", "node", "nodejs", "express"],
    
    # Java/Kotlin
    "java": ["java", "spring", "springboot", "kotlin", "android"],
    "kotlin": ["kotlin", "java", "android"],
    "spring": ["java", "spring", "springboot"],
    
    # Go
    "go": ["go", "golang"],
    
    # Rust
    "rust": ["rust"],
    
    # C/C++
    "c": ["c", "cpp", "c++"],
    "cpp": ["c", "cpp", "c++"],
    
    # Others
    "ruby": ["ruby", "rails"],
    "php": ["php", "laravel"],
    "swift": ["swift", "ios"],
}


def normalize_language(lang: str) -> List[str]:
    """언어/프레임워크를 정규화된 목록으로 변환."""
    lang_lower = lang.lower().strip()
    
    # 직접 매칭
    if lang_lower in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[lang_lower]
    
    # 부분 매칭 시도
    for key, values in LANGUAGE_ALIASES.items():
        if lang_lower in values:
            return values
    
    # 매칭 없으면 원본 반환
    return [lang_lower]


def compute_stack_match_score(
    preferred_stack: List[str],
    repo_language: Optional[str],
    repo_topics: Optional[List[str]] = None,
) -> Tuple[int, List[str]]:
    """
    기술 스택 매칭 점수 계산.
    
    Returns:
        (점수 0-30, 매칭된 스택 리스트)
    """
    if not preferred_stack:
        # 선호 스택이 없으면 기본 점수
        return 10, []
    
    matched: List[str] = []
    repo_langs: List[str] = []
    
    # repo 언어 정규화
    if repo_language:
        repo_langs.extend(normalize_language(repo_language))
    
    # repo topics 정규화
    if repo_topics:
        for topic in repo_topics:
            repo_langs.extend(normalize_language(topic))
    
    repo_langs_set = set(repo_langs)
    
    # 선호 스택과 매칭
    for pref in preferred_stack:
        pref_variants = set(normalize_language(pref))
        if pref_variants & repo_langs_set:
            matched.append(pref)
    
    # 점수 계산 (최대 30점)
    if not matched:
        return 0, []
    
    # 매칭 비율에 따른 점수
    match_ratio = len(matched) / len(preferred_stack)
    score = int(min(30, match_ratio * 30 + len(matched) * 5))
    
    return score, matched


# 경험 레벨 매칭

def compute_level_match_score(
    experience_level: str,
    onboarding_level: str,
    health_level: str,
) -> int:
    """
    사용자 경험 레벨과 프로젝트 난이도 매칭 점수.
    
    Returns:
        점수 0-25
    """
    # 레벨 매칭 테이블
    # experience_level: beginner → easy 프로젝트 선호
    # experience_level: intermediate → normal 프로젝트 선호
    # experience_level: advanced → hard도 OK
    
    level_preference = {
        "beginner": {"easy": 25, "normal": 15, "hard": 5},
        "intermediate": {"easy": 20, "normal": 25, "hard": 15},
        "advanced": {"easy": 15, "normal": 20, "hard": 25},
    }
    
    exp = experience_level.lower()
    onb = onboarding_level.lower()
    
    base_score = level_preference.get(exp, {}).get(onb, 15)
    
    # 건강한 프로젝트 보너스
    if health_level == "good":
        base_score += 5
    elif health_level == "bad":
        base_score -= 10
    
    return max(0, min(25, base_score))


# 목표 매칭

def compute_goal_match_score(
    goal: str,
    is_healthy: bool,
    onboarding_score: int,
    activity_score: int,
) -> int:
    """
    사용자 목표와 프로젝트 특성 매칭 점수.
    
    Returns:
        점수 0-20
    """
    goal_lower = goal.lower()
    score = 10  # 기본 점수
    
    if "첫" in goal_lower or "pr" in goal_lower or "처음" in goal_lower:
        # 첫 PR 경험: 온보딩 점수 중요
        if onboarding_score >= 70:
            score += 10
        elif onboarding_score >= 50:
            score += 5
    
    elif "장기" in goal_lower or "기여" in goal_lower:
        # 장기 기여: 활동성 중요
        if activity_score >= 70 and is_healthy:
            score += 10
        elif activity_score >= 50:
            score += 5
    
    elif "학습" in goal_lower:
        # 학습 목적: 문서화 중요 (onboarding_score는 문서 가중치 높음)
        if onboarding_score >= 60:
            score += 10
    
    return min(20, score)


# 종합 점수 계산

def compute_recommendation_score(
    user_context: UserContext,
    diagnosis_result: Dict[str, Any],
) -> Tuple[int, List[str], str]:
    """
    종합 추천 점수 계산.
    
    Returns:
        (총점 0-100, 매칭된 스택, 추천 이유)
    """
    scores = diagnosis_result.get("scores", {})
    labels = diagnosis_result.get("labels", {})
    repo_info = diagnosis_result.get("details", {}).get("repo_info", {})
    
    # 개별 점수 계산
    health_score = scores.get("health_score", 0)
    onboarding_score = scores.get("onboarding_score", 0)
    activity_score = scores.get("activity_maintainability", 0)
    is_healthy = scores.get("is_healthy", False)
    
    health_level = labels.get("health_level", "warning")
    onboarding_level = labels.get("onboarding_level", "normal")
    
    repo_language = repo_info.get("primary_language")
    repo_topics = repo_info.get("topics", [])
    
    # 1. 기본 점수 (건강도 기반) - 25점
    base_score = 0
    if is_healthy:
        base_score = 20
    elif health_level == "warning":
        base_score = 10
    else:
        base_score = 0
    
    # 온보딩 점수 보너스
    if onboarding_score >= 70:
        base_score += 5
    
    # 2. 스택 매칭 점수 - 30점
    stack_score, matched_stack = compute_stack_match_score(
        preferred_stack=user_context.preferred_stack,
        repo_language=repo_language,
        repo_topics=repo_topics,
    )
    
    # 3. 레벨 매칭 점수 - 25점
    level_score = compute_level_match_score(
        experience_level=user_context.experience_level,
        onboarding_level=onboarding_level,
        health_level=health_level,
    )
    
    # 4. 목표 매칭 점수 - 20점
    goal_score = compute_goal_match_score(
        goal=user_context.goal,
        is_healthy=is_healthy,
        onboarding_score=onboarding_score,
        activity_score=activity_score,
    )
    
    # 총점 계산
    total_score = base_score + stack_score + level_score + goal_score
    total_score = min(100, max(0, total_score))
    
    # 추천 이유 생성
    reason = generate_recommendation_reason(
        user_context=user_context,
        health_level=health_level,
        onboarding_level=onboarding_level,
        matched_stack=matched_stack,
        repo_language=repo_language,
        is_healthy=is_healthy,
    )
    
    return total_score, matched_stack, reason


def generate_recommendation_reason(
    user_context: UserContext,
    health_level: str,
    onboarding_level: str,
    matched_stack: List[str],
    repo_language: Optional[str],
    is_healthy: bool,
) -> str:
    """추천 이유 문자열 생성."""
    parts: List[str] = []
    
    # 언어/스택 매칭
    if matched_stack:
        parts.append(f"{', '.join(matched_stack)} 기반")
    elif repo_language:
        parts.append(f"{repo_language} 기반")
    
    # 건강 상태
    if is_healthy:
        parts.append("건강한 프로젝트")
    elif health_level == "warning":
        parts.append("활동 중인 프로젝트")
    
    # 온보딩 난이도
    level_desc = {
        "easy": "초보자 친화적",
        "normal": "적당한 난이도",
        "hard": "도전적인 프로젝트",
    }
    parts.append(level_desc.get(onboarding_level, ""))
    
    # 사용자 목표 반영
    if "첫" in user_context.goal or "pr" in user_context.goal.lower():
        if onboarding_level == "easy":
            parts.append("첫 PR에 적합")
    
    return ", ".join(p for p in parts if p)


# 추천 결과 생성

def create_recommendation_from_diagnosis(
    repo_full_name: str,
    diagnosis_result: Dict[str, Any],
    user_context: UserContext,
    include_full_diagnosis: bool = False,
) -> RepoRecommendation:
    """
    진단 결과로부터 추천 결과 생성.
    """
    # 점수 계산
    match_score, matched_stack, reason = compute_recommendation_score(
        user_context=user_context,
        diagnosis_result=diagnosis_result,
    )
    
    labels = diagnosis_result.get("labels", {})
    onboarding_plan = diagnosis_result.get("onboarding_plan", {})
    
    # 진단 요약 (옵션)
    diagnosis_summary = None
    if include_full_diagnosis:
        diagnosis_summary = {
            "scores": diagnosis_result.get("scores"),
            "labels": labels,
            "natural_language_summary": diagnosis_result.get("natural_language_summary_for_user", ""),
        }
    
    return RepoRecommendation(
        repo=repo_full_name,
        reason=reason,
        match_score=match_score,
        matched_stack=matched_stack,
        health_level=labels.get("health_level", "warning"),
        onboarding_level=labels.get("onboarding_level", "normal"),
        onboarding_plan=onboarding_plan,
        diagnosis_summary=diagnosis_summary,
    )
