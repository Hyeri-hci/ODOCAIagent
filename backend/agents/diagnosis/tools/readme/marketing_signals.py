"""README 마케팅 신호 추출기: 마케팅 키워드, 템플릿 유사도 등."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Set

from backend.agents.diagnosis.config import get_marketing_keywords


@dataclass
class MarketingSignals:
    """마케팅 신호 데이터."""
    # 마케팅 키워드 카운트 (언어별)
    marketing_keywords: Dict[str, int] = field(default_factory=dict)
    marketing_keyword_total: int = 0
    
    # 밀도 (per 1k tokens)
    marketing_density: float = 0.0
    
    # 코드 연결 없는 기능 불릿
    unlinked_feature_bullets: int = 0
    total_bullets: int = 0
    
    # 배지 비율
    badge_counts: Dict[str, int] = field(default_factory=dict)
    badge_urls: List[str] = field(default_factory=list)  # 배지 URL 목록
    promo_badge_ratio: float = 0.0
    
    # 템플릿 유사도 (3-gram Jaccard)
    template_similarity: float = 0.0
    
    # 집계
    marketing_signal_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 배지 패턴
BADGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# 기술 배지 키워드 (GitHub Actions, Coverage 등)
TECH_BADGE_KEYWORDS = {
    "actions", "workflow", "build", "test", "coverage", "codecov",
    "ci", "cd", "travis", "circleci", "github", "npm", "pypi",
    "docs", "documentation", "license", "version", "release"
}

# 홍보 배지 키워드
PROMO_BADGE_KEYWORDS = {
    "star", "sponsor", "donate", "patreon", "buymeacoffee", "kofi",
    "twitter", "discord", "slack", "gitter", "telegram", "reddit",
    "youtube", "linkedin", "follow", "subscribe"
}

# 불릿 패턴 (-, *, +)
BULLET_PATTERN = re.compile(r"^[\s]*[-*+]\s+(.+)$", re.MULTILINE)

# 코드 참조 패턴 (백틱, 코드블록 등)
CODE_REF_PATTERN = re.compile(r"`[^`]+`|```[\s\S]*?```")


def _get_ngrams(text: str, n: int = 3) -> Set[str]:
    """텍스트에서 n-gram 집합 추출."""
    # 소문자 변환 및 특수문자 제거
    text = re.sub(r"[^a-z0-9\s가-힣]", " ", text.lower())
    words = text.split()
    
    if len(words) < n:
        return set(words)
    
    ngrams = set()
    for i in range(len(words) - n + 1):
        ngram = " ".join(words[i:i+n])
        ngrams.add(ngram)
    
    return ngrams


def _jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """두 집합의 Jaccard 유사도 계산."""
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


# 공용 템플릿 패턴 (README 템플릿에서 자주 보이는 문구)
TEMPLATE_PHRASES = [
    # 영문 템플릿
    "about the project",
    "built with",
    "getting started",
    "prerequisites",
    "installation",
    "usage",
    "roadmap",
    "contributing",
    "license",
    "contact",
    "acknowledgments",
    # 표준 섹션
    "table of contents",
    "features",
    "quick start",
    "documentation",
    "support",
    "authors",
]


def _estimate_template_similarity(readme_content: str) -> float:
    """
    템플릿 유사도 추정 (공용 템플릿 패턴 기반).
    
    Returns:
        float: 0.0 ~ 1.0 (높을수록 템플릿 의심)
    """
    readme_lower = readme_content.lower()
    
    # 템플릿 문구 매칭 카운트
    matches = 0
    for phrase in TEMPLATE_PHRASES:
        if phrase in readme_lower:
            matches += 1
    
    # 매칭 비율 (최대 1.0)
    similarity = min(matches / len(TEMPLATE_PHRASES), 1.0)
    
    # 추가 신호: "[Project Name]", "Lorem ipsum" 등 플레이스홀더
    placeholders = [
        r"\[project.?name\]",
        r"\[your.?name\]",
        r"lorem ipsum",
        r"<!-- .* -->",  # HTML 주석
    ]
    for pattern in placeholders:
        if re.search(pattern, readme_lower):
            similarity += 0.1
    
    return min(similarity, 1.0)


def extract_marketing_signals(readme_content: str, token_count: int = 0) -> MarketingSignals:
    """
    README에서 마케팅 신호 추출.
    
    Args:
        readme_content: README 마크다운 내용
        token_count: 토큰 수 (밀도 계산용, 없으면 자체 계산)
        
    Returns:
        MarketingSignals: 추출된 마케팅 신호
    """
    if not readme_content:
        return MarketingSignals()
    
    signals = MarketingSignals()
    
    # 토큰 수 (전달받지 않으면 자체 계산)
    if token_count <= 0:
        token_count = len(readme_content.split())
    
    # 1. 마케팅 키워드 카운트
    keywords = get_marketing_keywords()
    keyword_counts: Dict[str, int] = {"en": 0, "ko": 0}
    
    readme_lower = readme_content.lower()
    
    for lang, keyword_list in keywords.items():
        for keyword in keyword_list:
            count = len(re.findall(re.escape(keyword.lower()), readme_lower))
            keyword_counts[lang] = keyword_counts.get(lang, 0) + count
    
    signals.marketing_keywords = keyword_counts
    signals.marketing_keyword_total = sum(keyword_counts.values())
    
    # 2. 마케팅 밀도 (per 1k tokens)
    if token_count > 0:
        signals.marketing_density = round(
            signals.marketing_keyword_total / (token_count / 1000), 2
        )
    
    # 3. 코드 연결 없는 불릿 카운트
    bullets = BULLET_PATTERN.findall(readme_content)
    signals.total_bullets = len(bullets)
    
    unlinked = 0
    for bullet in bullets:
        # 코드 참조가 없는 불릿
        if not CODE_REF_PATTERN.search(bullet):
            # 기능 설명처럼 보이는 불릿 (동사로 시작하지 않음)
            if not re.match(r"^(install|run|build|test|use|see|check|read)", bullet.lower()):
                unlinked += 1
    
    signals.unlinked_feature_bullets = unlinked
    
    # 4. 배지 분석
    badges = BADGE_PATTERN.findall(readme_content)
    tech_count = 0
    promo_count = 0
    badge_urls = []
    
    for alt_text, url in badges:
        badge_urls.append(url)
        combined = (alt_text + " " + url).lower()
        
        is_tech = any(kw in combined for kw in TECH_BADGE_KEYWORDS)
        is_promo = any(kw in combined for kw in PROMO_BADGE_KEYWORDS)
        
        if is_tech:
            tech_count += 1
        elif is_promo:
            promo_count += 1
    
    signals.badge_counts = {"tech": tech_count, "promo": promo_count, "total": len(badges)}
    signals.badge_urls = badge_urls
    
    total_badges = tech_count + promo_count
    if total_badges > 0:
        signals.promo_badge_ratio = round(promo_count / total_badges, 2)
    
    # 5. 템플릿 유사도
    signals.template_similarity = round(_estimate_template_similarity(readme_content), 2)
    
    # 6. 마케팅 신호 집계
    marketing_signal_count = (
        signals.marketing_keyword_total * 2 +  # 키워드는 가중치 2배
        signals.unlinked_feature_bullets +
        promo_count * 3 +  # 홍보 배지는 가중치 3배
        int(signals.template_similarity * 10)  # 템플릿 유사도 반영
    )
    signals.marketing_signal_count = marketing_signal_count
    
    return signals
