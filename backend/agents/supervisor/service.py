"""Supervisor Agent Service: LangGraph workflow and legacy compatibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Dict

from backend.agents.diagnosis.service import run_diagnosis
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

from .models import SupervisorState, UserContext


UserLevel = Literal["beginner", "intermediate", "advanced"]


@dataclass
class SupervisorInput:
    user_query: str
    user_level: UserLevel = "beginner"
    language: str = "ko"
    owner: str | None = None
    repo: str | None = None
    advanced_analysis: bool = False


@dataclass
class SupervisorOutput:
    answer: str
    route: str
    intermediate: dict[str, Any]


def call_diagnosis_agent(
    owner: str,
    repo: str,
    user_level: UserLevel,
    advanced_analysis: bool = False,
) -> dict[str, Any]:
    """Calls the Diagnosis Agent."""
    payload = {
        "owner": owner,
        "repo": repo,
        "task_type": "full_diagnosis",
        "focus": ["documentation", "activity"],
        "user_context": {"level": user_level},
        "advanced_analysis": advanced_analysis,
    }
    return run_diagnosis(payload)


def summarize_with_llm(
    user_query: str,
    diagnosis_result: dict[str, Any],
    user_level: UserLevel,
    language: str = "ko",
) -> str:
    """Summarizes the diagnosis result into a user-friendly response using an LLM."""
    system_prompt = _build_system_prompt(language)
    user_prompt = _build_user_prompt(user_level, diagnosis_result)

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    req = ChatRequest(messages=messages, max_tokens=384, temperature=0.25, top_p=0.9)
    return client.chat(req).content


def _build_system_prompt(language: str) -> str:
    """Builds a system prompt for the given language."""
    if language == "ko":
        return (
            "당신은 오픈소스 온보딩을 돕는 AI 에이전트의 Supervisor입니다. "
            "입력으로 GitHub 저장소 진단 결과(JSON)가 주어지면, "
            "초보 개발자가 이해하기 쉬운 한국어로 핵심만 정리해 주세요. "
            "프로젝트의 현재 상태 요약과 지금 당장 할 수 있는 개선 행동 3가지를 제시하세요."
        )
    return (
        "You are a supervisor agent explaining open-source project diagnosis results "
        "for beginner contributors. Summarize the current status and suggest 3 concrete actions."
    )


def _build_user_prompt(user_level: UserLevel, diagnosis_result: dict[str, Any]) -> str:
    """Builds the user prompt."""
    return (
        f"User level: {user_level}\n\n"
        "The following is the diagnosis result from the Diagnosis Agent.\n"
        "Based on this result, please write a response for the end-user.\n\n"
        f"{diagnosis_result}"
    )


def run_supervisor(input_data: SupervisorInput) -> SupervisorOutput:
    """Runs the Supervisor agent."""
    if not input_data.owner or not input_data.repo:
        raise ValueError("owner and repo information must be provided.")

    diagnosis_result = call_diagnosis_agent(
        owner=input_data.owner,
        repo=input_data.repo,
        user_level=input_data.user_level,
        advanced_analysis=input_data.advanced_analysis,
    )

    answer_text = summarize_with_llm(
        user_query=input_data.user_query,
        diagnosis_result=diagnosis_result,
        user_level=input_data.user_level,
        language=input_data.language,
    )

    return SupervisorOutput(
        answer=answer_text,
        route="diagnosis/full",
        intermediate={"diagnosis": diagnosis_result},
    )


def build_initial_state(
    user_query: str,
    owner: str,
    repo: str,
    user_context: UserContext | None = None,
) -> SupervisorState:
    """Initializes the SupervisorState for a LangGraph workflow."""
    state: SupervisorState = {
        "user_query": user_query,
        "repo": {
            "owner": owner,
            "name": repo,
            "url": f"https://github.com/{owner}/{repo}",
        },
    }

    if user_context:
        state["user_context"] = user_context

    return state