from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import json
import logging

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

logger = logging.getLogger(__name__)


@dataclass
class ReadmeUnifiedSummary:
    """README 통합 요약 결과"""
    summary_en: str  # 임베딩용 영어 요약
    summary_ko: str  # 사용자용 한국어 요약


def summarize_diagnosis_repository(
    diagnosis_result: Dict[str, Any],
    user_level: str = "beginner",
    language: str = "ko",
) -> str:
    """Diagnosis Agent 전체 결과를 요약하는 LLM 호출"""

    try:
        diagnosis_json_str = json.dumps(
            diagnosis_result,
            ensure_ascii=False,
            indent=2,
        )
    except Exception:
        diagnosis_json_str = str(diagnosis_result)

    scores = diagnosis_result.get("scores", {}) or {}
    details = diagnosis_result.get("details", {}) or {}
    docs_block = details.get("docs", {}) or {}

    overall_score = scores.get("overall_score")
    docs_score = scores.get("documentation_quality")
    activity_score = scores.get("activity_maintainability")
    readme_dsa = docs_block.get("readme_category_score")

    if language == "ko":
        system_prompt = (
            "너는 오픈소스 프로젝트 진단 결과를 바탕으로 "
            "초보 개발자에게 프로젝트 상태를 설명하는 전문가이다. "
            "입력 JSON 안의 숫자 점수는 임의로 바꾸거나 새로 만들지 말고 "
            "그대로 사용해라. "
            "문장이 중간에 끊기지 않도록 완결된 문장으로 답변해라."
        )

        user_prompt = (
            f"사용자 수준: {user_level}\n\n"
            "다음은 한 GitHub 저장소에 대한 진단 결과 JSON이다.\n"
            "전체 Health Score, 문서 품질, 활동성, README 카테고리 분석이 포함될 수 있다.\n\n"
            "주요 점수 요약은 다음과 같다. 값이 없으면 None이다.\n"
            f"- overall_score: {overall_score}\n"
            f"- documentation_quality: {docs_score}\n"
            f"- activity_maintainability: {activity_score}\n"
            f"- readme_category_score(DSA): {readme_dsa}\n\n"
            "아래 JSON 전체를 참고해서, 다음 구조로 한국어로 답변해라.\n\n"
            "[프로젝트 상태 개요]\n"
            "전체 Health Score와 핵심 지표를 바탕으로 전반적인 상태를 한 문단 정도로 설명해라.\n\n"
            "[문서 품질 및 온보딩 관점]\n"
            "README와 관련 문서 구조, DSA 점수를 기반으로 문서 품질과 온보딩 난이도를 설명해라.\n\n"
            "[활동성 및 유지보수성]\n"
            "커밋과 이슈 관련 지표를 바탕으로 활동성과 유지보수 상태를 설명해라.\n\n"
            "[개선이 필요한 점]\n"
            "가장 중요한 개선 포인트를 여러 개 bullet 형태로 제시하되, "
            "각 bullet은 한두 문장 정도로 이유와 방향을 함께 설명해라.\n\n"
            "[초보 기여자를 위한 온보딩 제안]\n"
            "초보 개발자가 이 프로젝트에 기여를 시작할 때 어떤 순서로 문서와 이슈를 보면 좋은지 "
            "간단한 단계형 가이드로 제안해라.\n\n"
            "진단 결과 JSON:\n"
            f"{diagnosis_json_str}"
        )
    else:
        system_prompt = (
            "You explain open source diagnosis results to help new contributors. "
            "Use only numeric scores from the input JSON. "
            "Write complete sentences."
        )
        user_prompt = (
            f"User level: {user_level}\n\n"
            f"Diagnosis JSON:\n{diagnosis_json_str}"
        )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(
        messages=messages,
        max_tokens=1200,
        temperature=0.2,
    )
    response = client.chat(request)
    return response.content


def summarize_readme_category_for_embedding(
    category: str,
    text: str,
) -> Optional[str]:
    """README 카테고리 영어 텍스트를 임베딩용 의미 요약으로 변환"""

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

    client = fetch_llm_client()
    request = ChatRequest(
        messages=messages,
        max_tokens=300,
        temperature=0.2,
    )
    response = client.chat(request)
    return response.content.strip() or None


def generate_readme_unified_summary(
    category_raw_texts: Dict[str, str],
) -> ReadmeUnifiedSummary:
    """
    카테고리별 raw_text를 합쳐 통합 README 요약 생성.
    
    LLM 1회 호출로 영어(임베딩용) + 한국어(사용자용) 동시 생성.
    기존 카테고리별 semantic_summary 4회 호출 → 1회로 통합하여 성능 최적화.
    
    Args:
        category_raw_texts: {카테고리명: raw_text} 딕셔너리
        
    Returns:
        ReadmeUnifiedSummary(summary_en, summary_ko)
    """
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
        "1. 'en': English summary for semantic search/embedding (3-5 sentences, focus on project purpose, features, usage)\n"
        "2. 'ko': Korean summary for users (4-6 sentences, friendly tone, explain what the project does)\n\n"
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
