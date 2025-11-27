from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple

import re

from .readme_sections import ReadmeSection, extract_sections

CATEGORIES: List[str] = [
  "what",
  "why",
  "how",
  "when",
  "who",
  "references",
  "contribution",
  "other",
]

@dataclass
class ReadmeCategory:
    category: str
    present: bool
    confidence: float # 0.0 ~ 1.0
    examples: List[str]

def _init_categories() -> Dict[str, ReadmeCategory]:
    return {
        cat: ReadmeCategory(
            category=cat,
            present=False,
            confidence=0.0,
            examples=[],
        ) for cat in CATEGORIES
    }

def _update_category(
        presences: Dict[str, ReadmeCategory],
        cat: str,
        conf: float,
        section: ReadmeSection
) -> None:
    p = presences[cat]
    if conf > p.confidence:
        p.present = True
        p.confidence = conf
        p.examples = [section.content] if section.content else []

def _classify_section(section: ReadmeSection, presences: Dict[str, ReadmeCategory]) -> None:
    title = (section.title or "").lower()
    content = (section.content or "").lower()

    text = title + "\n" + content

    # WHAT: 소개, 설명 (프로젝트가 무엇인지) – "intro", "about", "overview" 등:contentReference[oaicite:4]{index=4}
    if re.search(r"\b(what|intro(duction)?|about|overview|description)\b", text):
        _update_category(presences, "what", 0.8, section)

    # WHY: 목적, 동기, 장점 비교 – "why", "motivation", "advantages" 등:contentReference[oaicite:5]{index=5}
    if re.search(r"\bwhy\b|\b(motivation|rationale|benefits?|advantages?)\b", text):
        _update_category(presences, "why", 0.7, section)

    # HOW: 사용법, 설치, 설정, 예제 – "install", "usage", "getting started" 등 (가장 흔한 카테고리)
    if re.search(
        r"\b(install(ation)?|setup|configure|configuration|usage|use|"
        r"getting[-_ ]started|quick[-_ ]start|example(s)?|run|build)\b",
        text,
    ):
        _update_category(presences, "how", 0.9, section)

    # WHEN: 릴리스, 버전, 로드맵, 상태 – "changelog", "roadmap", "status", "release" 등:contentReference[oaicite:7]{index=7}
    if re.search(
        r"\b(changelog|change\s*log|release(s)?|roadmap|status|version(s)?|history)\b",
        text,
    ):
        _update_category(presences, "when", 0.8, section)

    # WHO: 기여자/팀/라이선스/연락 – "author", "maintainer", "license", "credits" 등
    if re.search(
        r"\b(author(s)?|maintain(er|ers)|team|credit(s)?|acknowledg(e|ment)s?|"
        r"contact|license|licence|code\s+of\s+conduct)\b",
        text,
    ):
        _update_category(presences, "who", 0.8, section)

    # REFERENCES: 추가 문서/지원/관련 프로젝트 링크 – "documentation", "support", "see also" 등
    if re.search(
        r"\b(doc(s|umentation)?|api\s+reference|support|help|faq|"
        r"see\s+also|more\s+info|related\s+project(s)?)\b",
        text,
    ):
        _update_category(presences, "references", 0.7, section)

    # CONTRIBUTION: 기여 방법 – "contributing", "how to contribute", "pull request" 등:contentReference[oaicite:10]{index=10}
    if re.search(
        r"\b(contribut(e|ing|ion)s?|how\s+to\s+contribute|pull\s+request(s)?|"
        r"issues?|bug\s+report(s)?)\b",
        text,
    ):
        _update_category(presences, "contribution", 0.9, section)

    # OTHER: 위 아무 것도 매칭 안 되고, 텍스트가 거의 없는 highlight 섹션 등:contentReference[oaicite:11]{index=11}
    if not any(
        presences[cat].present and section.title in presences[cat].examples
        for cat in CATEGORIES
        if cat != "other"
    ):
        stripped = section.content.strip()
        if len(stripped) < 20:
            _update_category(presences, "other", 0.6, section)

def classify_readme_sections(
        markdown_text: str
) -> Tuple[Dict[str, dict], int]:
    """
      README 섹션별 카테고리 분류
      반환값: (카테고리별 존재 여부 및 예시, 전체 섹션 수, 0~100 문서 점수)
    """
    sections = extract_sections(markdown_text)
    presences = _init_categories()

    for section in sections:
        _classify_section(section, presences)

    categories_dict = {k: asdict(v) for k, v in presences.items()}
    score = _compute_readme_section_score(presences)
    return categories_dict, score

def _compute_readme_section_score(
        presences: Dict[str, ReadmeCategory]
) -> int:
    """
      README 섹션 카테고리 점수 산출
      - 각 카테고리별로 존재 여부에 따라 점수 부여
      - 최대 100점 만점
    """
    score = 0
    weights = {
        "what": 2,
        "why": 1,
        "how": 3,
        "when": 1,
        "who": 2,
        "references": 2,
        "contribution": 2,
        "other": 0,
    }

    # 최대 점수="존재 여부" * 10 * "가중치"
    max_raw = sum(weights.values()) * 10
    raw_score = 0

    for name, presences in presences.items():
        if presences.present:
            raw_score += weights.get(name, 0) * 10
    
    if max_raw == 0:
        return 0
    
    score = int(round(raw_score / max_raw * 100))
    return max(min(score, 100), 0)