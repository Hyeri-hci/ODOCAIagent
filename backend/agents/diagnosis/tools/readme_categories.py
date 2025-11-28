from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Tuple
import json
import logging
import re
import textwrap

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

from .readme_sections import ReadmeSection, split_readme_into_sections
from .llm_summarizer import (
    generate_readme_unified_summary,
    generate_readme_advanced_summary,
    ReadmeUnifiedSummary,
    ReadmeAdvancedSummary,
)

logger = logging.getLogger(__name__)


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


@dataclass
class CategoryInfo:
    present: bool
    coverage_score: float
    summary: str               # 디버깅/간단 표시용
    example_snippets: List[str]
    raw_text: str              # 원문 텍스트 일부 (다국어 가능)
    semantic_summary_en: str   # LLM이 만든 의미 중심 영어 요약


@dataclass
class SectionClassification:
    category: ReadmeCategory
    score: float  # rule-based confidence (0.0 ~ 1.0)


# 가중치 상수
WEIGHT_HEADING = 3.0
WEIGHT_BODY = 1.5
WEIGHT_POSITION_FIRST = 2.0
WEIGHT_STRUCT_HOW = 2.0

# 카테고리 우선순위 (동점일 때 우선 적용)
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

# 카테고리별 제목 키워드 (영어 + 한국어)
HEADING_KEYWORDS: Dict[ReadmeCategory, List[str]] = {
    ReadmeCategory.WHAT: [
        "overview",
        "introduction",
        "about",
        "project description",
        "project overview",
        "소개",
        "개요",
        "프로젝트 소개",
        "프로젝트 개요",
        "프로젝트 설명",
    ],
    ReadmeCategory.WHY: [
        "motivation",
        "why",
        "background",
        "goals",
        "objectives",
        "problem statement",
        "배경",
        "동기",
        "목표",
        "문제 정의",
        "왜 이 프로젝트인가",
    ],
    ReadmeCategory.HOW: [
        "installation",
        "install",
        "getting started",
        "quick start",
        "usage",
        "how to use",
        "setup",
        "examples",
        "예제",
        "사용법",
        "사용 방법",
        "시작하기",
        "빠른 시작",
        "설치",
        "실행 방법",
        "예시 코드",
    ],
    ReadmeCategory.WHEN: [
        "changelog",
        "release notes",
        "releases",
        "roadmap",
        "version history",
        "변경 로그",
        "업데이트 내역",
        "릴리스 노트",
        "로드맵",
        "버전 기록",
    ],
    ReadmeCategory.WHO: [
        "authors",
        "maintainers",
        "contributors",
        "team",
        "license",
        "credits",
        "people",
        "작성자",
        "기여자",
        "관리자",
        "팀",
        "라이선스",
        "저작권",
        "문의",
        "연락처",
    ],
    ReadmeCategory.REFERENCES: [
        "references",
        "documentation",
        "docs",
        "further reading",
        "related work",
        "참고 문헌",
        "참고 자료",
        "추가 문서",
        "관련 자료",
        "인용",
    ],
    ReadmeCategory.CONTRIBUTING: [
        "contributing",
        "how to contribute",
        "contributing guidelines",
        "code of conduct",
        "development",
        "기여",
        "기여 방법",
        "기여 가이드",
        "기여하기",
        "개발 가이드",
        "참여 방법",
        "이슈 등록",
        "풀 리퀘스트",
        "pull request",
        "pull requests",
        "pr 가이드",
    ],
    ReadmeCategory.OTHER: [],
}

# 카테고리별 본문 키워드 (영어 + 한국어)
BODY_KEYWORDS: Dict[ReadmeCategory, List[str]] = {
    ReadmeCategory.WHAT: [
        "is a library",
        "is a framework",
        "provides",
        "allows you to",
        "used for",
        "라이브러리입니다",
        "프레임워크입니다",
        "제공합니다",
        "위해 사용됩니다",
        "도와줍니다",
    ],
    ReadmeCategory.WHY: [
        "we aim to",
        "the goal is",
        "we want to",
        "in order to",
        "to solve this problem",
        "designed to",
        "목표는",
        "우리는",
        "문제를 해결하기 위해",
        "위해 설계되었습니다",
        "필요성이 있습니다",
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
        "다음 명령을 실행",
        "예제",
        "사용 예시",
        "설치",
        "실행",
        "환경 설정",
        "순서대로",
        "단계별",
    ],
    ReadmeCategory.WHEN: [
        "released on",
        "since version",
        "this release",
        "upcoming",
        "milestone",
        "version",
        "릴리스",
        "버전",
        "업데이트",
        "다음과 같이 변경",
    ],
    ReadmeCategory.WHO: [
        "maintained by",
        "developed by",
        "thanks to",
        "contact",
        "email",
        "slack",
        "discord",
        "문의는",
        "연락처",
        "개발자",
        "기여자",
        "작성자",
    ],
    ReadmeCategory.REFERENCES: [
        "see also",
        "documentation",
        "wiki",
        "read the docs",
        "arxiv",
        "doi",
        "bibtex",
        "citation",
        "참고",
        "문서",
        "위키",
        "인용",
    ],
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
        "기여하려면",
        "이슈를 생성",
        "버그 리포트",
        "기능 요청",
        "PR을 보내주세요",
    ],
    ReadmeCategory.OTHER: [],
}


EMBED_SUMMARY_TARGET_CATEGORIES = {
    ReadmeCategory.WHAT,
    ReadmeCategory.WHY,
    ReadmeCategory.HOW,
    ReadmeCategory.CONTRIBUTING,
}

MAX_RAW_CHARS_PER_CAT = 2000  # LLM에 넘길 때 카테고리별 최대 길이


def _classify_section_rule_based(section: ReadmeSection) -> SectionClassification:
    """헤딩/본문 키워드 기반 섹션 분류."""
    heading = (section.heading or "").strip()
    body = section.content or ""

    heading_lower = heading.lower()
    body_lower = body.lower()

    scores: Dict[ReadmeCategory, float] = {cat: 0.0 for cat in ReadmeCategory}

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

    # 3) HOW에 자주 등장하는 구조적인 패턴
    if re.search(r"```", body) or re.search(r"\binstall\b", body_lower):
        scores[ReadmeCategory.HOW] += WEIGHT_STRUCT_HOW

    # 4) 첫 번째 섹션 위치 보정
    if section.index == 0:
        scores[ReadmeCategory.WHAT] += WEIGHT_POSITION_FIRST
        scores[ReadmeCategory.WHY] += WEIGHT_POSITION_FIRST * 0.7

    max_score = max(scores.values()) if scores else 0.0
    if max_score <= 0.0:
        # 아무 키워드도 못 찾은 경우: 위치 기반 기본값
        if section.index == 0:
            base_cat = ReadmeCategory.WHAT
        elif section.index == 1:
            base_cat = ReadmeCategory.HOW
        else:
            base_cat = ReadmeCategory.OTHER
        return SectionClassification(category=base_cat, score=0.0)

    best_cat = ReadmeCategory.OTHER
    best_raw_score = -1.0
    for cat in CATEGORY_PRIORITY:
        sc = scores[cat]
        if sc > best_raw_score:
            best_raw_score = sc
            best_cat = cat

    # 규칙 기반 confidence를 대략 0~1 범위로 정규화 (경험적 파라미터)
    norm_score = min(best_raw_score / 10.0, 1.0)
    return SectionClassification(category=best_cat, score=norm_score)


def _apply_last_section_bias(category: ReadmeCategory, section: ReadmeSection) -> ReadmeCategory:
    """마지막 섹션 키워드 기반 보정."""
    text = ((section.heading or "") + "\n" + (section.content or "")).lower()

    if "contributing" in text or "기여" in text or "pull request" in text:
        return ReadmeCategory.CONTRIBUTING
    if "license" in text or "licence" in text or "mit license" in text or "apache license" in text:
        return ReadmeCategory.WHO
    if "reference" in text or "참고" in text or "citation" in text or "인용" in text:
        return ReadmeCategory.REFERENCES
    if "contact" in text or "문의" in text or "이메일" in text or "email" in text:
        return ReadmeCategory.WHO

    return category

def _safe_json_loads(text: str):
    if not isinstance(text, str):
        raise ValueError("text must be str")

    cleaned = text.strip()

    # 코드블록 형태일 때 ```json ... ``` 제거
    if cleaned.startswith("```"):
        # 첫 줄: ``` 또는 ```json 같은 것 제거
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n", "", cleaned)
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3].strip()

    # 문자열 안에서 JSON 배열 부분만 추출
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    return json.loads(cleaned)



def _refine_with_llm(
    sections: List[ReadmeSection],
    initial: List[SectionClassification],
    score_threshold: float = 0.3,
) -> List[ReadmeCategory]:
    """confidence 낮은 섹션들만 LLM으로 재분류."""
    indices = [i for i, cls in enumerate(initial) if cls.score < score_threshold]
    if not indices:
        return [cls.category for cls in initial]

    payload = []
    for i in indices:
        sec = sections[i]
        cls = initial[i]
        payload.append(
            {
                "index": sec.index,
                "heading": sec.heading or "",
                "content": (sec.content or "")[:1200],
                "initial_category": cls.category.value,
                "initial_score": cls.score,
            }
        )

    system_prompt = (
        "You classify GitHub README sections into one of 8 categories: "
        "WHAT, WHY, HOW, WHEN, WHO, REFERENCES, CONTRIBUTING, OTHER.\n"
        "You are given a JSON array of sections with their index, heading, content, "
        "and an initial_category suggestion.\n"
        "For each item, choose the most appropriate category and return a JSON array "
        "of objects with fields 'index' and 'category' (one of the 8 labels). "
        "Return ONLY the JSON output, no explanation."
    )

    user_prompt = textwrap.dedent(
        f"""
        Sections to classify (JSON):
        {json.dumps(payload, ensure_ascii=False, indent=2)}

        Return a JSON array with the same length as input.
        """
    ).strip()

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    try:
        client = fetch_llm_client()
        request = ChatRequest(messages=messages, max_tokens=1024, temperature=0.0)
        response = client.chat(request)
        text = response.content.strip()
        
        if len(text) > 3000:
            logger.warning(
                "LLM classification response may be truncated (length: %d chars). "
                "Consider reducing section count or increasing max_tokens.",
                len(text),
            )
        
        data = _safe_json_loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "LLM-based README section classification failed - invalid JSON: %s. Response was: %s",
            exc,
            text[:300] if 'text' in locals() else "(no response)",
        )
        return [cls.category for cls in initial]
    except Exception as exc:
        logger.warning("LLM-based README section classification failed: %s", exc)
        return [cls.category for cls in initial]

    category_map: Dict[int, ReadmeCategory] = {}
    if isinstance(data, list):
        for item in data:
            try:
                idx = int(item.get("index"))
                cat_str = str(item.get("category") or "").upper()
                cat_enum = ReadmeCategory[cat_str]
            except Exception:
                continue
            category_map[idx] = cat_enum

    final_categories: List[ReadmeCategory] = []
    for sec, cls in zip(sections, initial):
        if sec.index in category_map:
            final_categories.append(category_map[sec.index])
        else:
            final_categories.append(cls.category)

    return final_categories


def _summarize_category_sections(
    category: ReadmeCategory,
    sections: List[ReadmeSection],
    total_chars: int,
    enable_semantic_summary: bool = True,
) -> CategoryInfo:
    """카테고리별 섹션 요약 생성."""
    if not sections:
        return CategoryInfo(
            present=False,
            coverage_score=0.0,
            summary="",
            example_snippets=[],
            raw_text="",
            semantic_summary_en="",
        )

    cat_chars = sum(len(s.content) for s in sections)
    coverage = cat_chars / total_chars if total_chars > 0 else 0.0

    # 간단 summary / example_snippet: 첫 섹션 앞부분만 사용
    first_lines = sections[0].content.strip().splitlines()
    meaningful_lines: List[str] = []
    for line in first_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("![](") or line.startswith("!["):
            continue
        if "<img " in line:
            continue
        if "shields.io" in line:
            continue
        if set(line) <= {"#", "=", "-", "_", "*"}:
            continue
        meaningful_lines.append(line)
        if len(meaningful_lines) >= 3:
            break

    if meaningful_lines:
        summary_text = "\n".join(meaningful_lines)
    else:
        summary_text = "\n".join(first_lines[:3])

    summary_snippet = summary_text[:1000]
    example_snippet = summary_snippet[:500]

    # 원문 raw_text는 길이 제한 후 그대로 저장
    full_text = "\n\n".join(s.content.strip() for s in sections)
    if len(full_text) > MAX_RAW_CHARS_PER_CAT:
        full_text = full_text[:MAX_RAW_CHARS_PER_CAT]

    raw_text = full_text
    # 카테고리별 LLM 요약은 비활성화 (통합 요약에서 1회 처리로 최적화)
    semantic_summary_en = ""

    return CategoryInfo(
        present=True,
        coverage_score=coverage,
        summary=summary_snippet,
        example_snippets=[example_snippet] if example_snippet else [],
        raw_text=raw_text,
        semantic_summary_en=semantic_summary_en,
    )


def _compute_documentation_score(
    grouped: Dict[ReadmeCategory, List[ReadmeSection]],
    total_chars: int,
) -> int:
    """coverage + diversity 기반 문서 품질 점수 (0~100)."""
    if total_chars <= 0:
        return 0

    present_categories = 0
    coverage_total = 0.0

    for cat, sections in grouped.items():
        if not sections:
            continue
        present_categories += 1
        coverage_total += min(
            1.0, sum(len(sec.content) for sec in sections) / float(total_chars)
        )

    diversity = present_categories / float(len(ReadmeCategory))
    score = int(round((coverage_total * 60.0) + (diversity * 40.0)))
    return max(0, min(score, 100))


def classify_readme_sections(
    markdown_text: str,
    use_llm_refine: bool = True,
    enable_semantic_summary: bool = True,
    advanced_mode: bool = False,
) -> Tuple[Dict[str, Dict], int, ReadmeUnifiedSummary]:
    """
    README 분류 및 요약.
    - advanced_mode=False: 통합 요약만 (LLM 1회)
    - advanced_mode=True: 카테고리별 + 통합 (LLM 5회)
    """
    empty_summary = ReadmeUnifiedSummary(summary_en="", summary_ko="")
    
    original_text = markdown_text or ""
    if not original_text.strip():
        return {}, 0, empty_summary

    sections = split_readme_into_sections(original_text)
    if not sections:
        return {}, 0, empty_summary

    # 1) 규칙 기반 1차 분류
    initial: List[SectionClassification] = [
        _classify_section_rule_based(sec) for sec in sections
    ]

    # 2) LLM으로 애매한 섹션만 재분류
    if use_llm_refine:
        categories: List[ReadmeCategory] = _refine_with_llm(sections, initial)
    else:
        categories = [cls.category for cls in initial]

    # 3) 마지막 섹션 bias
    if categories:
        last_idx = len(categories) - 1
        categories[last_idx] = _apply_last_section_bias(
            categories[last_idx],
            sections[last_idx],
        )

    # 4) 카테고리별 섹션 묶기
    grouped: Dict[ReadmeCategory, List[ReadmeSection]] = defaultdict(list)
    for sec, cat in zip(sections, categories):
        grouped[cat].append(sec)

    total_chars = sum(len(sec.content) for sec in sections) or 1

    # 5) 카테고리별 요약/점수 구성
    cat_infos: Dict[str, CategoryInfo] = {}
    for cat in ReadmeCategory:
        info = _summarize_category_sections(
            category=cat,
            sections=grouped.get(cat, []),
            total_chars=total_chars,
            enable_semantic_summary=enable_semantic_summary,
        )
        cat_infos[cat.value] = info

    score = _compute_documentation_score(grouped, total_chars)
    
    # 6) 요약 생성 (모드에 따라 분기)
    unified_summary = empty_summary
    if enable_semantic_summary:
        category_raw_texts = {
            name: info.raw_text
            for name, info in cat_infos.items()
            if info.raw_text and name in ["WHAT", "WHY", "HOW", "CONTRIBUTING"]
        }
        if category_raw_texts:
            if advanced_mode:
                # 고급 분석: 카테고리별 요약 + 통합 요약 (LLM 5회)
                advanced = generate_readme_advanced_summary(category_raw_texts)
                unified_summary = advanced.unified
                # 카테고리별 semantic_summary_en 채우기
                for cat_name, cat_summary in advanced.category_summaries.items():
                    if cat_name in cat_infos:
                        cat_infos[cat_name] = CategoryInfo(
                            present=cat_infos[cat_name].present,
                            coverage_score=cat_infos[cat_name].coverage_score,
                            summary=cat_infos[cat_name].summary,
                            example_snippets=cat_infos[cat_name].example_snippets,
                            raw_text=cat_infos[cat_name].raw_text,
                            semantic_summary_en=cat_summary,
                        )
            else:
                # 기본 모드: 통합 요약만 (LLM 1회, 빠름)
                unified_summary = generate_readme_unified_summary(category_raw_texts)
    
    return {name: asdict(info) for name, info in cat_infos.items()}, score, unified_summary
