"""문서 분석 Core 레이어 - README 구조 분석 및 8-카테고리 스코어 (Pure Python)"""
from __future__ import annotations

import re
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Any

from .models import DocsCoreResult, RepoSnapshot

logger = logging.getLogger(__name__)


# 1. Data Structures

class ReadmeCategory(Enum):
    WHAT = "WHAT"
    WHY = "WHY"
    HOW = "HOW"
    WHEN = "WHEN"
    WHO = "WHO"
    REFERENCES = "REFERENCES"
    CONTRIBUTING = "CONTRIBUTING"
    OTHER = "OTHER"


@dataclass
class ReadmeSection:
    index: int
    heading: Optional[str]
    content: str


@dataclass
class CategoryInfo:
    present: bool
    coverage_score: float
    summary: str
    example_snippets: list[str]
    raw_text: str


@dataclass
class SectionClassification:
    category: ReadmeCategory
    score: float


# 2. Constants & Keywords

REQUIRED_SECTIONS = ["WHAT", "WHY", "HOW", "CONTRIBUTING", "REFERENCES", "WHEN", "WHO", "OTHER"]

ESSENTIAL_CATEGORIES = {ReadmeCategory.WHAT, ReadmeCategory.WHY, ReadmeCategory.HOW, ReadmeCategory.CONTRIBUTING}
OPTIONAL_CATEGORIES = {ReadmeCategory.WHO, ReadmeCategory.WHEN, ReadmeCategory.REFERENCES, ReadmeCategory.OTHER}

ESSENTIAL_WEIGHT = 0.7
OPTIONAL_WEIGHT = 0.3

WEIGHT_HEADING = 3.0
WEIGHT_BODY = 1.5
WEIGHT_POSITION_FIRST = 2.0
WEIGHT_STRUCT_HOW = 2.0

CATEGORY_PRIORITY: list[ReadmeCategory] = [
    ReadmeCategory.WHAT,
    ReadmeCategory.HOW,
    ReadmeCategory.WHY,
    ReadmeCategory.CONTRIBUTING,
    ReadmeCategory.WHO,
    ReadmeCategory.WHEN,
    ReadmeCategory.REFERENCES,
    ReadmeCategory.OTHER,
]

HEADING_KEYWORDS: dict[ReadmeCategory, list[str]] = {
    ReadmeCategory.WHAT: [
        "overview", "introduction", "about", "project description", "project overview",
        "소개", "개요", "프로젝트 소개", "프로젝트 개요", "프로젝트 설명",
    ],
    ReadmeCategory.WHY: [
        "motivation", "why", "background", "goals", "objectives", "problem statement",
        "배경", "동기", "목표", "문제 정의", "왜 이 프로젝트인가",
    ],
    ReadmeCategory.HOW: [
        "installation", "install", "getting started", "quick start", "usage", "how to use",
        "setup", "examples", "예제", "사용법", "사용 방법", "시작하기", "빠른 시작", "설치", "실행 방법",
    ],
    ReadmeCategory.WHEN: [
        "changelog", "release notes", "releases", "roadmap", "version history",
        "변경 로그", "업데이트 내역", "릴리스 노트", "로드맵", "버전 기록",
    ],
    ReadmeCategory.WHO: [
        "authors", "maintainers", "contributors", "team", "license", "credits", "people",
        "작성자", "기여자", "관리자", "팀", "라이선스", "저작권", "문의", "연락처",
    ],
    ReadmeCategory.REFERENCES: [
        "references", "documentation", "docs", "further reading", "related work",
        "참고 문헌", "참고 자료", "추가 문서", "관련 자료", "인용",
    ],
    ReadmeCategory.CONTRIBUTING: [
        "contributing", "how to contribute", "contributing guidelines", "code of conduct", "development",
        "기여", "기여 방법", "기여 가이드", "기여하기", "개발 가이드", "참여 방법", "이슈 등록", "풀 리퀘스트",
    ],
    ReadmeCategory.OTHER: [],
}

BODY_KEYWORDS: dict[ReadmeCategory, list[str]] = {
    ReadmeCategory.WHAT: [
        "is a library", "is a framework", "provides", "allows you to", "used for",
        "라이브러리입니다", "프레임워크입니다", "제공합니다", "위해 사용됩니다", "도와줍니다",
    ],
    ReadmeCategory.WHY: [
        "we aim to", "the goal is", "we want to", "in order to", "to solve this problem", "designed to",
        "목표는", "우리는", "문제를 해결하기 위해", "위해 설계되었습니다", "필요성이 있습니다",
    ],
    ReadmeCategory.HOW: [
        "run the following command", "example", "examples", "install", "pip install", "npm install",
        "usage", "usage examples", "sample", "configuration", "clone the repository", "build", "execute",
        "다음 명령을 실행", "예제", "사용 예시", "설치", "실행", "환경 설정",
    ],
    ReadmeCategory.WHEN: [
        "released on", "since version", "this release", "upcoming", "milestone", "version",
        "릴리스", "버전", "업데이트", "다음과 같이 변경",
    ],
    ReadmeCategory.WHO: [
        "maintained by", "developed by", "thanks to", "contact", "email", "slack", "discord",
        "문의는", "연락처", "개발자", "기여자", "작성자",
    ],
    ReadmeCategory.REFERENCES: [
        "see also", "documentation", "wiki", "read the docs", "arxiv", "doi", "bibtex", "citation",
        "참고", "문서", "위키", "인용",
    ],
    ReadmeCategory.CONTRIBUTING: [
        "pull request", "pull requests", "issue", "issues", "bug report", "feature request",
        "open an issue", "fork the repo", "submit code", "fork", "clone", "create a pull request",
        "기여하려면", "이슈를 생성", "버그 리포트", "기능 요청", "PR을 보내주세요",
    ],
    ReadmeCategory.OTHER: [],
}

MARKETING_KEYWORDS = [
    "revolutionary", "game-changing", "world's best", "best-in-class", "award-winning",
    "cutting-edge", "state-of-the-art", "unrivaled", "unmatched", "superior",
    "혁신적인", "세계 최고", "최고의", "혁명적", "압도적", "최첨단", "수상 경력",
]


# 3. Helper Functions

def split_readme_into_sections(markdown_text: str) -> list[ReadmeSection]:
    """마크다운 텍스트를 헤딩 기준으로 섹션 분리"""
    lines = markdown_text.splitlines()
    sections: list[ReadmeSection] = []
    
    current_heading = None
    current_content = []
    index = 0

    # 정규식: #, ##, ### ... (최대 6개)
    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)")

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            # 이전 섹션 저장
            if current_heading is not None or current_content:
                sections.append(ReadmeSection(
                    index=index,
                    heading=current_heading,
                    content="\n".join(current_content).strip()
                ))
                index += 1
            
            current_heading = match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)

    # 마지막 섹션 저장
    if current_heading is not None or current_content:
        sections.append(ReadmeSection(
            index=index,
            heading=current_heading,
            content="\n".join(current_content).strip()
        ))

    return sections


def _classify_section_rule_based(section: ReadmeSection) -> SectionClassification:
    """헤딩/본문 키워드 기반 섹션 분류"""
    heading = (section.heading or "").strip()
    body = section.content or ""

    heading_lower = heading.lower()
    body_lower = body.lower()

    scores: dict[ReadmeCategory, float] = {cat: 0.0 for cat in ReadmeCategory}

    # 1) 제목 키워드
    for cat, keywords in HEADING_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in heading_lower:
                scores[cat] += WEIGHT_HEADING

    # 2) 본문 키워드
    for cat, keywords in BODY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in body_lower:
                scores[cat] += WEIGHT_BODY

    # 3) HOW 구조적 패턴
    if "```" in body or "install" in body_lower:
        scores[ReadmeCategory.HOW] += WEIGHT_STRUCT_HOW

    # 4) 첫 번째 섹션 위치 보정
    if section.index == 0:
        scores[ReadmeCategory.WHAT] += WEIGHT_POSITION_FIRST
        scores[ReadmeCategory.WHY] += WEIGHT_POSITION_FIRST * 0.7

    max_score = max(scores.values()) if scores else 0.0
    
    # 점수가 없으면 위치 기반 추론
    if max_score <= 0.0:
        if section.index == 0:
            return SectionClassification(ReadmeCategory.WHAT, 0.0)
        elif section.index == 1:
            return SectionClassification(ReadmeCategory.HOW, 0.0)
        else:
            return SectionClassification(ReadmeCategory.OTHER, 0.0)

    # 최고 점수 카테고리 선정 (우선순위 적용)
    best_cat = ReadmeCategory.OTHER
    best_raw_score = -1.0
    for cat in CATEGORY_PRIORITY:
        sc = scores[cat]
        if sc > best_raw_score:
            best_raw_score = sc
            best_cat = cat

    return SectionClassification(category=best_cat, score=min(best_raw_score / 10.0, 1.0))







def _apply_last_section_bias(category: ReadmeCategory, section: ReadmeSection) -> ReadmeCategory:
    """마지막 섹션 키워드 기반 보정."""
    text = ((section.heading or "") + "\n" + (section.content or "")).lower()

    if "contributing" in text or "기여" in text:
        return ReadmeCategory.CONTRIBUTING
    if "license" in text or "licence" in text:
        return ReadmeCategory.WHO
    if "reference" in text or "참고" in text:
        return ReadmeCategory.REFERENCES
    if "contact" in text or "문의" in text:
        return ReadmeCategory.WHO

    return category


def _summarize_category_sections(
    category: ReadmeCategory,
    sections: list[ReadmeSection],
    total_chars: int,
) -> CategoryInfo:
    """카테고리별 섹션 요약 생성."""
    if not sections:
        return CategoryInfo(False, 0.0, "", [], "")

    cat_chars = sum(len(s.content) for s in sections)
    coverage = cat_chars / total_chars if total_chars > 0 else 0.0

    # 간단 요약 (첫 섹션의 앞부분)
    first_lines = sections[0].content.strip().splitlines()
    meaningful_lines = []
    for line in first_lines:
        line = line.strip()
        if not line or line.startswith("!") or line.startswith("<img") or set(line) <= {"#", "=", "-", "_"}:
            continue
        meaningful_lines.append(line)
        if len(meaningful_lines) >= 3:
            break
    
    summary_text = "\n".join(meaningful_lines) if meaningful_lines else ""
    raw_text = "\n\n".join(s.content.strip() for s in sections)[:2000]

    return CategoryInfo(
        present=True,
        coverage_score=coverage,
        summary=summary_text[:500],
        example_snippets=[summary_text[:200]] if summary_text else [],
        raw_text=raw_text,
    )


def _compute_documentation_score(
    grouped: dict[ReadmeCategory, list[ReadmeSection]],
    total_chars: int,
) -> int:
    """문서 품질 점수 (0~100) - 가중치 및 구조 보너스 적용."""
    if total_chars <= 0:
        return 0

    essential_cov = 0.0
    optional_cov = 0.0

    # 1. Coverage Score Calculation (Presence-based)
    # 텍스트 비중(fraction) 사용 시 카테고리 수로 나눌 때 점수가 너무 낮아짐
    # "존재 여부(Presence)" 기준으로 가중치 적용
    
    for cat in ReadmeCategory:
        sections = grouped.get(cat, [])
        is_present = 1.0 if sections else 0.0
        
        if cat in ESSENTIAL_CATEGORIES:
            essential_cov += is_present
        else:
            optional_cov += is_present

    # 카테고리 수로 Normalize (Presence Ratio)
    if ESSENTIAL_CATEGORIES:
        essential_cov /= float(len(ESSENTIAL_CATEGORIES))
    if OPTIONAL_CATEGORIES:
        optional_cov /= float(len(OPTIONAL_CATEGORIES))

    # Base Score (Weighted)
    base_score = (
        ESSENTIAL_WEIGHT * essential_cov +
        OPTIONAL_WEIGHT * optional_cov
    ) * 100.0

    # 2. Structure Bonus Calculation
    bonus = 0.0
    target_sections = grouped.get(ReadmeCategory.HOW, []) + grouped.get(ReadmeCategory.WHAT, [])
    
    has_code_block = False
    has_usage_keyword = False
    
    for sec in target_sections:
        content_lower = sec.content.lower()
        heading_lower = (sec.heading or "").lower()
        
        if "```" in sec.content:
            has_code_block = True
        
        usage_keywords = ["quickstart", "usage", "example", "예제", "사용 예시", "사용법", "시작하기"]
        if any(k in content_lower or k in heading_lower for k in usage_keywords):
            has_usage_keyword = True

    if has_code_block and has_usage_keyword:
        bonus = 10.0
    elif has_code_block:
        bonus = 5.0
    
    final_score = base_score + bonus
    
    # Scale adjustment: 커버리지가 낮으면 점수가 너무 낮게 나올 수 있음
    # 필수 카테고리 존재 시 기본 점수 보장 로직 추가 가능하나, 현재 요구사항에 따라 단순 클램핑만 수행
    
    # 커버리지 기반 점수는 텍스트 양이 적으면 매우 낮게 나올 수 있음
    # 카테고리 존재 여부 자체에 대한 기본 점수 부여가 일반적임
    # 요구사항("필수/옵션 coverage 기준으로만 계산")을 따르되, 커버리지 값이 너무 작아지는 것 방지 위해 Normalize 방식 유지
    
    return max(0, min(int(round(final_score)), 100))


def _calculate_marketing_ratio(readme_content: str) -> float:
    """마케팅 텍스트 비중 계산 (0~1)"""
    if not readme_content:
        return 0.0
        
    sentences = re.split(r'[.!?\n]', readme_content)
    total_sentences = len([s for s in sentences if s.strip()])
    if total_sentences == 0:
        return 0.0
        
    marketing_sentences = 0
    for sentence in sentences:
        if not sentence.strip():
            continue
        sentence_lower = sentence.lower()
        if any(kw in sentence_lower for kw in MARKETING_KEYWORDS):
            marketing_sentences += 1
            
    return min(1.0, marketing_sentences / float(total_sentences))


# 4. Main Analysis Function

def analyze_documentation(
    readme_content: Optional[str],
    custom_required_sections: Optional[list[str]] = None
) -> DocsCoreResult:
    """README 기반 문서 품질 분석 (Pure Python)"""
    
    target_required = custom_required_sections if custom_required_sections else REQUIRED_SECTIONS
    
    if not readme_content or not readme_content.strip():
        return DocsCoreResult(
            readme_present=False,
            readme_word_count=0,
            category_scores={},
            total_score=0,
            missing_sections=target_required.copy(),
            present_sections=[],
            marketing_ratio=0.0,
        )

    sections = split_readme_into_sections(readme_content)
    
    # 1) 분류
    categories = []
    for sec in sections:
        cls = _classify_section_rule_based(sec)
        categories.append(cls.category)

    # 2) 마지막 섹션 보정
    if categories:
        last_idx = len(categories) - 1
        categories[last_idx] = _apply_last_section_bias(categories[last_idx], sections[last_idx])

    # 3) 그룹화
    grouped = defaultdict(list)
    for sec, cat in zip(sections, categories):
        grouped[cat].append(sec)

    total_chars = len(readme_content)
    
    # 4) 카테고리별 점수/요약
    cat_infos = {}
    for cat in ReadmeCategory:
        info = _summarize_category_sections(cat, grouped.get(cat, []), total_chars)
        cat_infos[cat.value] = asdict(info)

    # 5) 전체 점수 및 마케팅 비율
    total_score = _compute_documentation_score(grouped, total_chars)
    marketing_ratio = _calculate_marketing_ratio(readme_content)

    present_sections = [k for k, v in cat_infos.items() if v["present"]]
    
    # Missing Sections 계산 (Custom Rule 적용)
    # Note: ReadmeCategory Enum 값과 target_required 문자열 일치해야 함
    # target_required가 ["WHAT", "HOW"] 형태라고 가정
    missing_sections = [req for req in target_required if req not in present_sections]

    return DocsCoreResult(
        readme_present=True,
        readme_word_count=len(readme_content.split()),
        category_scores=cat_infos,
        total_score=total_score,
        missing_sections=missing_sections,
        present_sections=present_sections,
        marketing_ratio=marketing_ratio,
    )


def analyze_docs(
    snapshot: "RepoSnapshot",
    custom_required_sections: Optional[list[str]] = None
) -> DocsCoreResult:
    """Wrapper for analyze_documentation using RepoSnapshot"""
    return analyze_documentation(snapshot.readme_content, custom_required_sections)
