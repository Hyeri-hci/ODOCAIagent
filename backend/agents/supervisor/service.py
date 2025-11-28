from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from backend.agents.diagnosis.service import run_diagnosis
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client


UserLevel = Literal["beginner", "intermediate", "advanced"]

@dataclass
class SupervisorInput:
    user_query: str
    user_level: UserLevel = "beginner"
    language: str = "ko"
    owner: Optional[str] = None
    repo: Optional[str] = None
    advanced_analysis: bool = False  # 고급 분석 모드 (카테고리별 상세 요약 포함)


@dataclass
class SupervisorOutput:
    answer: str
    route: str
    intermediate: Dict[str, Any]

def _call_diagnosis_agent(
    owner: str,
    repo: str,
    user_level: UserLevel,
    advanced_analysis: bool = False,
) -> Dict[str, Any]:
    """진단 에이전트 호출"""
    payload = {
        "owner": owner,
        "repo": repo,
        "task_type": "full_diagnosis",
        "focus": ["documentation", "activity"],
        "user_context": {
            "level": user_level,
        },
        "advanced_analysis": advanced_analysis,
    }
    result = run_diagnosis(payload)
    return result

def _summarize_with_llm(
    user_query: str,
    diagnosis_result: Dict[str, Any],
    user_level: UserLevel,
    language: str = "ko",
) -> str:
    """Supervisor 차원의 최종 답변 포맷팅 (Kanana 사용)."""
    if language == "ko":
        system_prompt = (
            "당신은 오픈소스 온보딩을 돕는 AI 에이전트의 Supervisor입니다. "
            "입력으로 GitHub 저장소 진단 결과(JSON)가 주어지면, "
            "초보 개발자가 이해하기 쉬운 한국어로 핵심만 정리해 주세요. "
            "1) 프로젝트의 현재 상태 요약, 2) 지금 당장 할 수 있는 개선 행동 3가지를 제시하세요."
        )
    else:
        system_prompt = (
            "You are a supervisor agent explaining open-source project diagnosis results "
            "for beginner contributors. Summarize the current status and suggest 3 concrete actions."
        )

    user_prompt = (
        f"사용자 수준: {user_level}\n\n"
        "다음은 Diagnosis Agent가 생성한 진단 결과입니다.\n"
        "이 결과를 바탕으로 최종 사용자에게 보여줄 답변을 작성해 주세요.\n\n"
        f"{diagnosis_result}"
    )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    req = ChatRequest(messages=messages, max_tokens=384, temperature=0.25, top_p=0.9)
    resp = client.chat(req)
    return resp.content

def run_supervisor(input_data: SupervisorInput) -> SupervisorOutput:
    """Supervisor 에이전트 실행"""
    if not input_data.owner or not input_data.repo:
        raise ValueError("owner 및 repo 정보를 입력해야 합니다.")
    
    # 1. 진단 에이전트 호출
    diagnosis_result = _call_diagnosis_agent(
        owner=input_data.owner,
        repo=input_data.repo,
        user_level=input_data.user_level,
        advanced_analysis=input_data.advanced_analysis,
    )

    # 2. LLM을 사용해 최종 요약 생성 (Supervisor 역할)
    answer_text = _summarize_with_llm(
        user_query=input_data.user_query,
        diagnosis_result=diagnosis_result,
        user_level=input_data.user_level,
        language=input_data.language,
    )
    output = SupervisorOutput(
        answer=answer_text,
        route="diagnosis/full",
        intermediate={
            "diagnosis": diagnosis_result,
        },
    )
    return output