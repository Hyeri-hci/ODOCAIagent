from __future__ import annotations

from typing import Any, Dict

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

def summarize_diagnosis_repository(
    diagnosis_result: Dict[str, Any],
    user_level: str = "beginner",
    language: str = "ko",
) -> str:
    """
        LLM을 사용하여 진단 결과 요약 생성
    """

    # system prompt
    if language == "ko":
        system_prompt = (
            "당신은 오픈소스 온보딩을 돕는 진단 전문가입니다. "
            "입력으로 GitHub 저장소 진단 결과(JSON)가 주어지면, "
            "초보 개발자가 이해하기 쉬운 한국어 요약을 만들어 주세요. "
            "점수(0~100)와 의미, 개선이 필요한 부분을 간단히 설명하세요."
        )
    else:
        system_prompt = (
            "You are an expert who explains open-source project diagnosis results. "
            "Given a JSON result, generate an easy-to-understand summary for a beginner developer."
        )

    user_prompt = (
        f"사용자 수준: {user_level}\n\n"
        "다음은 한 GitHub 저장소에 대한 진단 결과입니다.\n"
        "이 결과를 바탕으로, 한 단락으로 요약하고, "
        "그 다음에 개선이 필요한 점 3가지를 bullet로 정리해 주세요.\n\n"
        "진단 결과(JSON):\n"
        f"{diagnosis_result}"
    )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(messages=messages, max_tokens=512, temperature=0.2)
    response = client.chat(request)

    return response.content