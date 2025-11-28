from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Tuple

import re

from .readme_sections import ReadmeSection, split_readme_into_sections

# README 카테고리 정의 및 분류 로직
class ReadmeCategory(Enum):
    """8가지 README 카테고리."""

    WHAT = "WHAT"
    WHY = "WHY"
    HOW = "HOW"
    WHEN = "WHEN"
    WHO = "WHO"
    REFERENCES = "REFERENCES"
    CONTRIBUTING = "CONTRIBUTING"
    OTHER = "OTHER"

# 카테고리 정보 데이터 클래스
@dataclass
class CategoryInfo:
    present: bool                   # 해당 카테고리 존재 여부
    coverage_score: float           # 해당 카테고리 커버리지 점수 (0.0 ~ 1.0)
    summary: str                    # 해당 카테고리 요약
    example_snippets: List[str]     # 해당 카테고리 예제 코드 조각


# 가중치 상수
WEIGHT_HEADING = 3.0
WEIGHT_BODY = 1.5
WEIGHT_POSITION_FIRST = 2.0
WEIGHT_STRUCT_HOW = 2.0

# 카테고리 우선순위 리스트
CATEGORY_PRIORITY: List[ReadmeCategory] = [
    ReadmeCategory.WHAT,
    ReadmeCategory.HOW,
    ReadmeCategory.WHY,
    ReadmeCategory.CONTRIBUTING,
    ReadmeCategory.WHO,
    ReadmeCategory.WHEN,
    ReadmeCategory.REFERENCES,
    ReadmeCategory.OTHER,
]

# 카테고리별 제목 키워드 매핑
HEADING_KEYWORDS: Dict[ReadmeCategory, List[str]] = {
    ReadmeCategory.WHAT: ["overview", "introduction", "about", "project description"],
    ReadmeCategory.WHY: ["motivation", "why", "background", "goals", "objectives"],
    ReadmeCategory.HOW: [
        "installation",
        "install",
        "getting started",
        "quick start",
        "usage",
        "how to use",
        "setup",
    ],
    ReadmeCategory.WHEN: ["changelog", "release notes", "releases", "roadmap", "version history"],
    ReadmeCategory.WHO: ["authors", "maintainers", "contributors", "team", "license", "credits"],
    ReadmeCategory.REFERENCES: ["references", "documentation", "docs", "further reading"],
    ReadmeCategory.CONTRIBUTING: [
        "contributing",
        "how to contribute",
        "CONTRIBUTING guidelines",
        "code of conduct",
        "development",
    ],
    ReadmeCategory.OTHER: [],
}

# 카테고리별 본문 키워드 매핑
BODY_KEYWORDS: Dict[ReadmeCategory, List[str]] = {
    ReadmeCategory.WHAT: ["is a library", "is a framework", "provides", "allows you to"],
    ReadmeCategory.WHY: [
        "we aim to",
        "the goal is",
        "we want to",
        "in order to",
        "to solve this problem",
        "designed to",
    ],
    ReadmeCategory.HOW: [
        "run the following command",
        "example",
        "examples",
        "install",
        "pip install",
        "npm install",
        "usage",
        "usage examples",
        "sample",
        "configuration",
        "clone the repository",
        "build",
        "execute",
        "step",
    ],
    ReadmeCategory.WHEN: ["released on", "since version", "this release", "upcoming", "milestone"],
    ReadmeCategory.WHO: ["maintained by", "developed by", "thanks to", "contact", "email", "slack"],
    ReadmeCategory.REFERENCES: ["see also", "documentation", "wiki", "read the docs", "arxiv", "doi", "bibtex", "citation"],
    ReadmeCategory.CONTRIBUTING: [
        "pull request",
        "pull requests",
        "issue",
        "issues",
        "bug report",
        "feature request",
        "open an issue",
        "fork the repo",
        "submit code",
        "fork",
        "clone",
        "create a pull request",
        "development environment",
    ],
    ReadmeCategory.OTHER: [],
}


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _count_matches(text: str, keywords: List[str]) -> int:
    return sum(text.count(kw) for kw in keywords)


def _looks_like_code_block(text: str | None) -> bool:
    body = text or ""
    if not body:
        return False
    if "```" in body or "$ " in body:
        return True
    return bool(re.search(r"^\s*[-*+]\s+`?.+`?", body, re.MULTILINE))


def _looks_like_list(text: str | None) -> bool:
    body = (text or "").strip()
    if not body:
        return False
    return bool(re.search(r"(^|\n)\s*[-*+]\s+", body))


def _apply_last_section_bias(category: ReadmeCategory, section: ReadmeSection) -> ReadmeCategory:
    text = _normalize(section.heading) + "\n" + _normalize(section.content)
    if any(token in text for token in ["license", "copyright"]):
        return ReadmeCategory.WHO
    if any(token in text for token in ["reference", "see also", "documentation"]):
        return ReadmeCategory.REFERENCES
    if any(token in text for token in ["contributing", "pull request", "issues"]):
        return ReadmeCategory.CONTRIBUTING
    return category


def classify_section_rule_based(section: ReadmeSection) -> ReadmeCategory:
    heading_norm = _normalize(section.heading)
    body_norm = _normalize(section.content)
    combined = (heading_norm + "\n" + body_norm).strip()
    if not combined:
        return ReadmeCategory.OTHER

    scores: Dict[ReadmeCategory, float] = {cat: 0.0 for cat in ReadmeCategory}

    for cat, keywords in HEADING_KEYWORDS.items():
        matches = _count_matches(heading_norm, keywords)
        if matches:
            scores[cat] += matches * WEIGHT_HEADING

    for cat, keywords in BODY_KEYWORDS.items():
        matches = _count_matches(body_norm, keywords)
        if matches:
            scores[cat] += matches * WEIGHT_BODY

    if _looks_like_code_block(section.content) or _looks_like_list(section.content):
        scores[ReadmeCategory.HOW] += WEIGHT_STRUCT_HOW

    if section.index == 0:
        scores[ReadmeCategory.WHAT] += WEIGHT_POSITION_FIRST
        scores[ReadmeCategory.WHY] += WEIGHT_POSITION_FIRST * 0.7

    max_score = max(scores.values()) if scores else 0.0
    if max_score <= 0:
        if section.index == 0:
            return ReadmeCategory.WHAT
        if section.index == 1:
            return ReadmeCategory.HOW
        return ReadmeCategory.OTHER

    best_cat = ReadmeCategory.OTHER
    best_score = -1.0
    for cat in CATEGORY_PRIORITY:
        score = scores.get(cat, 0.0)
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat


def _summarize_category_sections(sections: List[ReadmeSection], total_chars: int) -> CategoryInfo:
    if not sections:
        return CategoryInfo(False, 0.0, "", [])

    char_sum = sum(len(sec.content) for sec in sections)
    coverage = min(1.0, char_sum / max(total_chars, 1))
    snippet_lines = sections[0].content.strip().splitlines()
    snippet = "\n".join(snippet_lines[:3]).strip()[:500]

    return CategoryInfo(
        present=True,
        coverage_score=coverage,
        summary=snippet,
        example_snippets=[snippet[:200]] if snippet else [],
    )


def _compute_documentation_score(category_map: Dict[ReadmeCategory, List[ReadmeSection]], total_chars: int) -> int:
    if not total_chars:
        return 0

    coverage_total = 0.0
    present_categories = 0

    for cat in ReadmeCategory:
        sections = category_map.get(cat, [])
        if not sections:
            continue
        present_categories += 1
        coverage_total += min(1.0, sum(len(sec.content) for sec in sections) / total_chars)

    diversity = present_categories / len(ReadmeCategory)
    score = int(round((coverage_total * 60) + (diversity * 40)))
    return max(0, min(score, 100))


def classify_readme_sections(markdown_text: str) -> Tuple[Dict[str, dict], int]:
    text = markdown_text or ""
    sections = split_readme_into_sections(text)
    if not sections:
        return {}, 0

    classified: List[Tuple[ReadmeSection, ReadmeCategory]] = []
    for section in sections:
        classified.append((section, classify_section_rule_based(section)))

    if classified:
        last_section, last_cat = classified[-1]
        classified[-1] = (last_section, _apply_last_section_bias(last_cat, last_section))

    grouped: Dict[ReadmeCategory, List[ReadmeSection]] = defaultdict(list)
    for section, category in classified:
        grouped[category].append(section)

    total_chars = sum(len(sec.content) for sec, _ in classified) or 1
    categories: Dict[str, CategoryInfo] = {}
    for cat in ReadmeCategory:
        categories[cat.value] = _summarize_category_sections(grouped.get(cat, []), total_chars)

    score = _compute_documentation_score(grouped, total_chars)
    return {name: asdict(info) for name, info in categories.items()}, score