"""README Summarizer - 카테고리별/통합 요약 생성. 임베딩/검색/분류에 활용."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import json
import logging

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

logger = logging.getLogger(__name__)


@dataclass
class ReadmeUnifiedSummary:
    summary_en: str
    summary_ko: str


@dataclass
class ReadmeAdvancedSummary:
    unified: ReadmeUnifiedSummary
    category_summaries: Dict[str, str]


def summarize_readme_category_for_embedding(
    category: str,
    text: str,
) -> Optional[str]:
    """카테고리 텍스트를 임베딩용 영어 요약으로 변환 (고급 모드용)."""

    text = (text or "").strip()
    if not text:
        return None

    system_prompt = (
        "You summarize sections of GitHub READMEs. "
        "Your goal is to produce a short English paragraph that captures "
        "the purpose and intent of the section, suitable for semantic embedding. "
        "Do not include Markdown syntax or code, only plain sentences."
    )

    user_prompt = (
        f"Category: {category}\n\n"
        "Section text:\n"
        f"{text}\n\n"
        "Write a concise English summary describing the purpose and intent "
        "of this section. Focus on meaning, not formatting."
    )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    try:
        client = fetch_llm_client()
        request = ChatRequest(
            messages=messages,
            max_tokens=300,
            temperature=0.2,
        )
        response = client.chat(request)
        return response.content.strip() or None
    except Exception as exc:
        logger.warning("Category summary failed for %s: %s", category, exc)
        return None


def generate_readme_category_summaries(
    category_raw_texts: Dict[str, str],
) -> Dict[str, str]:
    """카테고리별 영어 요약 생성 (고급 모드, LLM 4회)."""
    results: Dict[str, str] = {}
    target_categories = ["WHAT", "WHY", "HOW", "CONTRIBUTING"]
    
    for cat in target_categories:
        raw_text = category_raw_texts.get(cat, "")
        if not raw_text or not raw_text.strip():
            continue
            
        summary = summarize_readme_category_for_embedding(cat, raw_text)
        if summary:
            results[cat] = summary
            
    return results


def generate_readme_advanced_summary(
    category_raw_texts: Dict[str, str],
) -> ReadmeAdvancedSummary:
    """카테고리별 + 통합 요약 생성 (고급 모드, LLM 5회)."""
    # 1) 카테고리별 요약 (4회)
    category_summaries = generate_readme_category_summaries(category_raw_texts)
    
    # 2) 통합 요약 (1회)
    unified = generate_readme_unified_summary(category_raw_texts)
    
    return ReadmeAdvancedSummary(
        unified=unified,
        category_summaries=category_summaries,
    )


def generate_readme_unified_summary(
    category_raw_texts: Dict[str, str],
) -> ReadmeUnifiedSummary:
    """통합 README 요약 생성 (LLM 1회, en+ko 동시)."""
    # 카테고리별 원문 합치기 (중요 카테고리 우선, 길이 제한)
    parts = []
    priority_order = ["WHAT", "WHY", "HOW", "CONTRIBUTING"]
    max_chars_per_cat = 800
    
    for cat in priority_order:
        raw = category_raw_texts.get(cat, "")
        if raw and raw.strip():
            truncated = raw.strip()[:max_chars_per_cat]
            parts.append(f"[{cat}]\n{truncated}")
    
    if not parts:
        return ReadmeUnifiedSummary(summary_en="", summary_ko="")
    
    combined_text = "\n\n".join(parts)
    
    # 전체 입력 길이 제한 (LLM 토큰 절약)
    if len(combined_text) > 3500:
        combined_text = combined_text[:3500]
    
    system_prompt = (
        "You summarize GitHub README content into two formats:\n"
        "1. 'en': English summary for semantic search/embedding (3-5 sentences, 150-250 characters, focus on project purpose, features, usage)\n"
        "2. 'ko': Korean summary for users (4-6 sentences, 300-500 characters in Korean, friendly tone, explain what the project does)\n\n"
        "IMPORTANT: Keep 'ko' summary within 300-500 Korean characters. Do not exceed 500 characters.\n\n"
        "Return ONLY a JSON object: {\"en\": \"...\", \"ko\": \"...\"}. No markdown, no explanation."
    )
    
    user_prompt = (
        "Below is README content organized by category.\n"
        "Create a unified project summary.\n\n"
        f"{combined_text}\n\n"
        "Return JSON with 'en' and 'ko' keys."
    )
    
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]
    
    try:
        client = fetch_llm_client()
        request = ChatRequest(
            messages=messages,
            max_tokens=700,
            temperature=0.2,
        )
        response = client.chat(request)
        raw = response.content.strip()
        
        # JSON 파싱
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        data = json.loads(raw)
        summary_en = data.get("en", "").strip()
        summary_ko = data.get("ko", "").strip()
        
        return ReadmeUnifiedSummary(summary_en=summary_en, summary_ko=summary_ko)
        
    except Exception as exc:
        logger.warning("README unified summary generation failed: %s", exc)
        # 실패 시 간단 fallback
        fallback_en = " ".join(
            s.strip()[:200] for s in category_raw_texts.values() if s and s.strip()
        )[:500]
        return ReadmeUnifiedSummary(
            summary_en=fallback_en,
            summary_ko="README 요약을 생성하지 못했습니다.",
        )
