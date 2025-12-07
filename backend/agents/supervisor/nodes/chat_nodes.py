"""채팅 응답 노드."""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
    """채팅 응답 생성."""
    from backend.llm.factory import fetch_llm_client
    from backend.llm.base import ChatRequest, ChatMessage
    from backend.common.config import LLM_MODEL_NAME

    intent = state.detected_intent
    message = state.chat_message or ""
    context = state.chat_context or {}
    diagnosis = state.diagnosis_result or {}

    logger.info(f"Chat response: intent={intent}, message={message[:50]}...")

    try:
        client = fetch_llm_client()

        if intent == "explain" and (context or diagnosis):
            system_prompt = _build_explain_prompt(context, diagnosis)
        else:
            system_prompt = _build_chat_prompt(context, diagnosis)

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=message),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.7,
        )

        response = client.chat(request, timeout=30)
        chat_response = response.content

    except Exception as e:
        logger.warning(f"LLM chat failed: {e}")
        chat_response = _generate_fallback(intent, message, context, diagnosis)

    return {
        "chat_response": chat_response,
        "step": state.step + 1,
    }


def _build_explain_prompt(context: Dict, diagnosis: Dict) -> str:
    """분석 결과 기반 설명 프롬프트."""
    health = diagnosis.get("health_score", context.get("health_score", "N/A"))
    docs = diagnosis.get("documentation_quality", context.get("documentation_quality", "N/A"))
    activity = diagnosis.get("activity_maintainability", context.get("activity_maintainability", "N/A"))
    onboard = diagnosis.get("onboarding_score", context.get("onboarding_score", "N/A"))

    return f"""당신은 오픈소스 프로젝트 분석 전문가입니다.
아래 분석 결과를 바탕으로 사용자 질문에 답변하세요.

분석 결과:
- 건강 점수: {health}점
- 문서 품질: {docs}점
- 활동성: {activity}점
- 온보딩 점수: {onboard}점

간결하고 명확하게 답변하세요."""


def _build_chat_prompt(context: Dict, diagnosis: Dict) -> str:
    """일반 채팅 프롬프트."""
    if context or diagnosis:
        health = diagnosis.get("health_score", context.get("health_score", ""))
        repo = diagnosis.get("repo_id", context.get("repo_id", ""))
        if health and repo:
            return f"""당신은 오픈소스 프로젝트 분석 도우미입니다.
현재 분석 중인 저장소: {repo}
건강 점수: {health}점

사용자를 도와주세요. 간결하게 답변하세요."""

    return """당신은 오픈소스 프로젝트 분석 도우미입니다.
사용자를 도와주세요. 간결하게 답변하세요."""


def _generate_fallback(intent: str, message: str, context: Dict, diagnosis: Dict) -> str:
    """LLM 실패 시 폴백 응답."""
    if intent == "explain":
        health = diagnosis.get("health_score", context.get("health_score"))
        if health:
            return f"현재 프로젝트의 건강 점수는 {health}점입니다. 구체적인 분석 결과는 리포트를 참고해주세요."
        return "분석 결과가 없습니다. 먼저 저장소를 분석해주세요."

    return "요청을 처리하는 중 문제가 발생했습니다. 다시 시도해주세요."


def route_after_chat(state: SupervisorState) -> str:
    """채팅 노드 후 라우팅."""
    return "__end__"

