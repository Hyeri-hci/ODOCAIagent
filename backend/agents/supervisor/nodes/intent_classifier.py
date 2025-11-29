"""
Intent 분류 노드

사용자 자연어 쿼리를 분석하여 Supervisor task_type을 추론한다.
Agent별 task_type은 여기서 설정하지 않으며, 이후 매핑 노드에서 처리한다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

from ..models import SupervisorState, SupervisorTaskType, RepoInfo, UserContext


INTENT_SYSTEM_PROMPT = """
당신은 OSS 온보딩 플랫폼 ODOC의 Supervisor Agent입니다.

역할:
1) 사용자의 한국어/영어 질의를 읽고, 아래 Supervisor task_type 중 하나로 분류합니다.
2) 질의 안에 포함된 GitHub 저장소 URL이 있다면 추출합니다.
3) 사용자의 수준(level), 목표(goal), 사용 가능 시간(time_budget_hours), 선호 언어(preferred_language)를 추론합니다.

Supervisor task_type 후보:
- "diagnose_repo_health"
- "diagnose_repo_onboarding"
- "compare_two_repos"
- "refine_onboarding_tasks"
- "explain_scores"

반드시 아래 JSON 형식만으로 답변하세요.

{
  "task_type": "<위 task_type 중 하나>",
  "repo_url": "<주 대상 repo URL 또는 null>",
  "compare_repo_url": "<비교 대상 repo URL 또는 null>",
  "user_context": {
    "level": "<beginner|intermediate|advanced 또는 null>",
    "goal": "<사용자 목표 요약 또는 null>",
    "time_budget_hours": <숫자 또는 null>,
    "preferred_language": "<ko|en 등 또는 null>"
  }
}

추가 설명이나 자연어 문장은 절대 포함하지 마세요.
""".strip()

DEFAULT_TASK_TYPE: SupervisorTaskType = "diagnose_repo_health"


def classify_intent_node(state: SupervisorState) -> SupervisorState:
    """
    사용자 쿼리에서 intent와 task_type을 추론하는 노드
    
    LLM을 호출하여 자연어 쿼리를 분석하고,
    전역 task_type만 설정한다. Agent별 task_type은 설정하지 않는다.
    """
    user_query = state.get("user_query", "")
    if not user_query:
        raise ValueError("SupervisorState.user_query가 비어 있습니다.")

    llm_response = _call_intent_llm(user_query)
    parsed = _parse_llm_response(llm_response)

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    task_type = parsed.get("task_type", DEFAULT_TASK_TYPE)
    if not _is_valid_task_type(task_type):
        task_type = DEFAULT_TASK_TYPE

    new_state["task_type"] = task_type
    new_state["intent"] = task_type

    repo_info = _parse_repo_url(parsed.get("repo_url"))
    if repo_info:
        new_state["repo"] = repo_info

    compare_repo_info = _parse_repo_url(parsed.get("compare_repo_url"))
    if compare_repo_info:
        new_state["compare_repo"] = compare_repo_info

    user_context = _parse_user_context(parsed.get("user_context", {}))
    if user_context:
        new_state["user_context"] = user_context

    history = list(state.get("history", []))
    history.append({"role": "user", "content": user_query})
    new_state["history"] = history

    return new_state


def _call_intent_llm(user_query: str) -> str:
    """LLM을 호출하여 intent 분류 결과를 얻는다"""
    user_prompt = f"사용자 질의:\n{user_query}"

    messages = [
        ChatMessage(role="system", content=INTENT_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(
        messages=messages,
        max_tokens=512,
        temperature=0.0,
        top_p=1.0,
    )

    response = client.chat(request)
    return response.content


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """LLM 응답을 JSON으로 파싱"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}


def _is_valid_task_type(value: str) -> bool:
    """유효한 SupervisorTaskType인지 확인"""
    valid_types = {
        "diagnose_repo_health",
        "diagnose_repo_onboarding",
        "compare_two_repos",
        "refine_onboarding_tasks",
        "explain_scores",
    }
    return value in valid_types


def _parse_repo_url(url: str | None) -> RepoInfo | None:
    """GitHub URL에서 owner/name 추출"""
    if not url:
        return None

    pattern = r"github\.com[/:]([^/]+)/([^/\s]+)"
    match = re.search(pattern, url)
    if not match:
        return None

    owner = match.group(1)
    name = match.group(2).rstrip(".git")

    return {
        "owner": owner,
        "name": name,
        "url": f"https://github.com/{owner}/{name}",
    }


def _parse_user_context(raw: dict[str, Any] | None) -> UserContext | None:
    """LLM 응답에서 user_context 파싱"""
    if not raw:
        return None

    context: UserContext = {}

    level = raw.get("level")
    if level in ("beginner", "intermediate", "advanced"):
        context["level"] = level

    goal = raw.get("goal")
    if goal and isinstance(goal, str):
        context["goal"] = goal

    time_budget = raw.get("time_budget_hours")
    if isinstance(time_budget, (int, float)) and time_budget > 0:
        context["time_budget_hours"] = float(time_budget)

    language = raw.get("preferred_language")
    if language and isinstance(language, str):
        context["preferred_language"] = language

    return context if context else None
