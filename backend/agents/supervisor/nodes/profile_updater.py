"""Profile Updater: 사용자 프로필 추론 및 세션 기억 업데이트."""
from __future__ import annotations

import re
import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState, UserProfile

logger = logging.getLogger(__name__)

# 기술 수준 감지용 키워드
BEGINNER_KEYWORDS = re.compile(
    r"(초보|입문|처음|배우|시작|newbie|beginner|starter|learning|easy|쉬운)",
    re.IGNORECASE
)
ADVANCED_KEYWORDS = re.compile(
    r"(실무|현업|고급|심화|전문|프로|시니어|expert|advanced|deep|senior|professional)",
    re.IGNORECASE
)

# 관심사 감지용 키워드 사전
INTEREST_KEYWORDS = [
    "react", "vue", "angular", "svelte", "nextjs", "nuxt",
    "python", "javascript", "typescript", "java", "kotlin", "go", "rust",
    "security", "보안", "cicd", "devops", "docker", "kubernetes", "k8s",
    "ai", "ml", "machine learning", "llm", "gpt",
    "backend", "frontend", "fullstack", "api", "database", "db",
    "testing", "test", "테스트", "tdd",
]

# 답변 스타일 감지용 키워드
SIMPLE_STYLE_KEYWORDS = re.compile(
    r"(간단|요약|짧게|핵심|summary|brief|short|concise)",
    re.IGNORECASE
)
DETAILED_STYLE_KEYWORDS = re.compile(
    r"(자세히|구체적|상세|코드|예시|detail|code|example|verbose)",
    re.IGNORECASE
)


def update_profile_node(state: SupervisorState) -> Dict[str, Any]:
    """
    현재 턴의 대화를 분석하여 user_profile을 업데이트.
    
    DB 없이 State 갱신만으로 세션 기억을 유지합니다.
    규칙 기반(Heuristic)으로 빠르게 처리합니다.
    """
    query = state.get("user_query", "")
    query_lower = query.lower()
    
    current_profile = state.get("user_profile") or {}
    new_profile: Dict[str, Any] = dict(current_profile)  # 기존 값 보존
    
    # 1. 기술 수준 추론 (명시적 언급 시에만 업데이트)
    if BEGINNER_KEYWORDS.search(query):
        new_profile["level"] = "beginner"
        logger.debug("[profile_updater] Detected level: beginner")
    elif ADVANCED_KEYWORDS.search(query):
        new_profile["level"] = "advanced"
        logger.debug("[profile_updater] Detected level: advanced")
    
    # 2. 관심사 추출 (누적 방식)
    current_interests = set(new_profile.get("interests", []))
    for kw in INTEREST_KEYWORDS:
        if kw in query_lower:
            current_interests.add(kw)
    
    if current_interests:
        new_profile["interests"] = sorted(current_interests)
        logger.debug("[profile_updater] Updated interests: %s", new_profile["interests"])
    
    # 3. 답변 스타일 추론
    if SIMPLE_STYLE_KEYWORDS.search(query):
        new_profile["persona"] = "simple"
        logger.debug("[profile_updater] Detected persona: simple")
    elif DETAILED_STYLE_KEYWORDS.search(query):
        new_profile["persona"] = "detailed"
        logger.debug("[profile_updater] Detected persona: detailed")
    
    # 진단 결과에서 추가 힌트 추출 (저장소의 주 언어)
    diagnosis_result = state.get("diagnosis_result", {})
    if diagnosis_result:
        details = diagnosis_result.get("details", {})
        repo_info = details.get("repo_info", {})
        primary_language = repo_info.get("primaryLanguage", "")
        
        if primary_language:
            lang_lower = primary_language.lower()
            current_interests = set(new_profile.get("interests", []))
            current_interests.add(lang_lower)
            new_profile["interests"] = sorted(current_interests)
    
    # 프로필 변경 여부 로깅
    if new_profile != current_profile:
        logger.info(
            "[profile_updater] Profile updated: level=%s, interests=%s, persona=%s",
            new_profile.get("level"),
            new_profile.get("interests"),
            new_profile.get("persona"),
        )
    
    return {"user_profile": new_profile}
