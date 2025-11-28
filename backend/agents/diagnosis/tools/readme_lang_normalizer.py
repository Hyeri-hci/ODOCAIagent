
from __future__ import annotations

from typing import List, Tuple
import json
import logging
import re
import textwrap

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

logger = logging.getLogger(__name__)


def _strip_code_blocks(markdown_text: str) -> str:
    """fenced code block (``` ... ``` / ~~~ ... ~~~) 제거"""
    text = markdown_text or ""

    fenced_pattern_backtick = re.compile(
        r"```.*?\n.*?```",
        re.DOTALL,
    )
    text = re.sub(fenced_pattern_backtick, "", text)

    fenced_pattern_tilde = re.compile(
        r"~~~.*?\n.*?~~~",
        re.DOTALL,
    )
    text = re.sub(fenced_pattern_tilde, "", text)

    return text


def _trim_for_llm_sample(text: str, max_lines: int = 80) -> str:
    """LLM에 넘길 샘플: 상단 일부 라인만 사용"""
    lines = text.splitlines()
    trimmed = "\n".join(lines[:max_lines])
    return trimmed


def _detect_language(sample_text: str) -> str:
    """샘플 텍스트 기반 언어 감지"""
    if not sample_text.strip():
        return "unknown"

    system_prompt = (
        "You are a language detection assistant. "
        "Return only a JSON object with a single key 'language' "
        "whose value is a BCP-47 language code such as 'en', 'ko', 'ja'."
    )

    user_prompt = textwrap.dedent(
        f"""
        Detect the main language of the following GitHub README content.

        README content:
        {sample_text}
        """
    ).strip()

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    try:
        client = fetch_llm_client()
        request = ChatRequest(messages=messages, max_tokens=128, temperature=0.0)
        response = client.chat(request)
        raw = response.content.strip()
        data = json.loads(raw)
        lang = data.get("language") or "unknown"
    except Exception as exc:
        logger.warning("Language detection failed: %s", exc)
        lang = "unknown"

    return lang


def _translate_chunk_to_english(text_chunk: str) -> str:
    """단일 텍스트 청크를 영어로 번역"""
    if not text_chunk.strip():
        return ""

    system_prompt = (
        "You are a translation assistant for GitHub README content. "
        "Translate the given text into natural English. "
        "Do not include code blocks or Markdown formatting artifacts. "
        "Return only the translated English text."
    )

    user_prompt = textwrap.dedent(
        f"""
        Translate the following README content into English.

        Source text:
        {text_chunk}
        """
    ).strip()

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    try:
        client = fetch_llm_client()
        request = ChatRequest(messages=messages, max_tokens=800, temperature=0.2)
        response = client.chat(request)
        return response.content.strip()
    except Exception as exc:
        logger.warning("Translation request failed: %s", exc)
        return text_chunk


def detect_readme_language(markdown_text: str) -> str:
    """
    README 전체에서 코드 블록을 제거한 뒤,
    상단 일부만 사용해서 언어를 한 번 감지한다.
    """
    original = markdown_text or ""
    if not original.strip():
        return "unknown"

    without_code = _strip_code_blocks(original)
    sample = _trim_for_llm_sample(without_code, max_lines=120)
    lang = _detect_language(sample)
    return lang


def translate_section_to_english_for_rules(
    section_text: str,
    lang_code: str,
    max_chars: int = 2000,
) -> str:
    """
    섹션 하나를 rule-based 분류용 영어 텍스트로 변환한다.

    - 영어 README(lang_code가 en*)면 코드 블록만 제거하고 그대로 사용
    - 비영어 README면 코드 블록 제거 후 max_chars까지만 잘라서 번역
    - 번역 실패 시 원문(코드 블록 제거 버전)을 그대로 반환
    """
    text = section_text or ""
    if not text.strip():
        return ""

    # 섹션 내부 코드 블록 제거
    text_no_code = _strip_code_blocks(text)
    # 너무 긴 섹션은 앞부분만 사용
    text_no_code = text_no_code[:max_chars]

    # 이미 영어인 경우 번역 없이 사용
    if lang_code.lower().startswith("en"):
        return text_no_code

    # 영어가 아닌 경우만 번역 시도
    try:
        translated = _translate_chunk_to_english(text_no_code)
        if translated.strip():
            return translated
        return text_no_code
    except Exception:
        return text_no_code
