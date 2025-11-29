"""
Supervisor Agent 서비스

사용자 쿼리를 받아 적절한 하위 Agent를 호출하고,
결과를 종합하여 최종 응답을 생성한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from backend.agents.diagnosis.service import run_diagnosis
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

from .models import SupervisorState, UserContext


UserLevel = Literal["beginner", "intermediate", "advanced"]


@dataclass
class SupervisorInput:
    """Supervisor 입력 데이터"""
    user_query: str
    user_level: UserLevel = "beginner"
    language: str = "ko"
    owner: str | None = None
    repo: str | None = None
    advanced_analysis: bool = False


@dataclass
class SupervisorOutput:
    """Supervisor 출력 데이터"""
    answer: str
    route: str
    intermediate: dict[str, Any]


def call_diagnosis_agent(
    owner: str,
    repo: str,
    user_level: UserLevel,
    advanced_analysis: bool = False,
) -> dict[str, Any]:
    """진단 에이전트 호출"""
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
    """LLM을 사용하여 진단 결과를 사용자 친화적으로 요약"""
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
    """언어별 시스템 프롬프트 생성"""
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
    """사용자 프롬프트 생성"""
    return (
        f"사용자 수준: {user_level}\n\n"
        "다음은 Diagnosis Agent가 생성한 진단 결과입니다.\n"
        "이 결과를 바탕으로 최종 사용자에게 보여줄 답변을 작성해 주세요.\n\n"
        f"{diagnosis_result}"
    )


def run_supervisor(input_data: SupervisorInput) -> SupervisorOutput:
    """Supervisor 에이전트 실행"""
    if not input_data.owner or not input_data.repo:
        raise ValueError("owner 및 repo 정보를 입력해야 합니다.")

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
    """
    SupervisorState 초기화
    
    LangGraph 워크플로우 시작 시 사용하는 헬퍼 함수.
    task_type은 이후 LLM 라우팅 노드에서 추론된다.
    """
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