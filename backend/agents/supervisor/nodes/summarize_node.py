from __future__ import annotations

import logging
from typing import Any

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

from ..models import SupervisorState

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """
당신은 오픈소스 프로젝트 분석 결과를 요약하는 전문가입니다.
진단 결과, 보안 분석, 추천 정보 등을 사용자가 이해하기 쉽게 한국어로 요약해 주세요.

다음 원칙을 따르세요:
1. 핵심 정보를 간결하게 전달
2. 수치가 있으면 명확히 언급
3. 사용자의 원래 질문에 맞는 답변 제공
4. 마크다운 형식 사용 가능
"""


def summarize_node(state: SupervisorState) -> SupervisorState:
    """
    모든 Agent 결과를 종합하여 사용자에게 최종 응답을 생성합니다.
    """
    diagnosis_result = state.get("diagnosis_result")
    security_result = state.get("security_result")
    recommend_result = state.get("recommend_result")
    history = state.get("history", [])

    # 마지막 사용자 질문 추출
    user_query = ""
    for turn in reversed(history):
        if turn.get("role") == "user":
            user_query = turn.get("content", "")
            break

    # 결과 조합
    context_parts = []

    if diagnosis_result:
        context_parts.append(f"## 진단 결과\n{_format_diagnosis(diagnosis_result)}")

    if security_result:
        context_parts.append(f"## 보안 분석\n{_format_result(security_result)}")

    if recommend_result:
        context_parts.append(f"## 추천 정보\n{_format_result(recommend_result)}")

    if not context_parts:
        summary = "분석 결과가 없습니다. 다시 시도해 주세요."
    else:
        context = "\n\n".join(context_parts)
        summary = _generate_summary_with_llm(user_query, context)

    logger.debug("[summarize_node] summary_length=%d", len(summary))

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    # history에 assistant 응답 추가
    new_history = list(history)
    new_history.append({"role": "assistant", "content": summary})
    new_state["history"] = new_history
    new_state["final_response"] = summary

    return new_state


def _format_diagnosis(result: Any) -> str:
    """진단 결과를 문자열로 포맷팅"""
    if isinstance(result, dict):
        parts = []
        if "health_score" in result:
            parts.append(f"- 건강 점수: {result['health_score']}")
        if "grade" in result:
            parts.append(f"- 등급: {result['grade']}")
        if "summary" in result:
            parts.append(f"- 요약: {result['summary']}")
        if parts:
            return "\n".join(parts)
    return str(result)


def _format_result(result: Any) -> str:
    """일반 결과를 문자열로 포맷팅"""
    if isinstance(result, dict):
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


def _generate_summary_with_llm(user_query: str, context: str) -> str:
    """LLM을 사용하여 최종 요약 생성"""
    try:
        llm_client = fetch_llm_client()

        user_message = f"""
사용자 질문: {user_query}

분석 결과:
{context}

위 결과를 바탕으로 사용자 질문에 답변해 주세요.
"""

        request = ChatRequest(
            model="gpt-4o-mini",
            messages=[
                ChatMessage(role="system", content=SUMMARIZE_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_message),
            ],
            temperature=0.7,
        )

        response = llm_client.chat(request)
        return response.content

    except Exception as e:
        logger.error("[summarize_node] LLM 호출 실패: %s", e)
        return f"요약 생성 중 오류가 발생했습니다: {e}"
