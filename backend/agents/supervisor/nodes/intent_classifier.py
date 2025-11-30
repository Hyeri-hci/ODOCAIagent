"""
Intent 분류 노드

사용자 자연어 쿼리를 분석하여 Supervisor task_type을 추론한다.
멀티턴 대화에서 이전 컨텍스트를 참조하는 follow-up 질의도 처리한다.
Agent별 task_type은 여기서 설정하지 않으며, 이후 매핑 노드에서 처리한다.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

logger = logging.getLogger(__name__)

from ..models import SupervisorState, SupervisorTaskType, RepoInfo, UserContext
from ..intent_config import validate_followup_type


INTENT_SYSTEM_PROMPT = """
당신은 OSS 온보딩 플랫폼 ODOC의 Supervisor Agent입니다.

역할:
1) 사용자의 한국어/영어 질의를 읽고, 아래 Supervisor task_type 중 하나로 분류합니다.
2) 질의 안에 포함된 GitHub 저장소 URL이 있다면 추출합니다.
3) 사용자의 수준(level), 목표(goal), 사용 가능 시간(time_budget_hours), 선호 언어(preferred_language)를 추론합니다.
4) 이전 대화 컨텍스트가 있다면, 현재 질의가 이전 결과를 참조하는지 판단합니다.

Supervisor task_type 후보:
- "diagnose_repo_health": 저장소 건강 상태 분석
- "diagnose_repo_onboarding": 온보딩 Task 추천
- "compare_two_repos": 두 저장소 비교
- "refine_onboarding_tasks": 기존 Task 목록 재필터링 (더 쉬운/어려운 Task 요청)
- "explain_scores": 점수 계산 방식 설명

## 중요: GitHub URL 파싱 규칙
- URL 형식: https://github.com/{owner}/{repo}
- 예시: https://github.com/facebook/react → owner="facebook", repo="react"
- 저장소 이름은 URL에 있는 그대로 정확히 추출하세요. 절대 축약하거나 변경하지 마세요.
- owner/repo 형식(예: facebook/react)도 동일하게 처리합니다.

## 멀티턴 대화 처리 (중요!)

### is_followup 판단 기준:
1. **새로운 저장소 URL이 명시됨** → is_followup=false (새로운 분석 시작)
2. **저장소 URL 없음 + 이전 대화 컨텍스트 있음** → is_followup=true (이전 결과 참조)
3. **아래와 같은 표현이 있으면 거의 확실히 follow-up:**
   - 지시대명사: "그거", "이거", "그 저장소", "아까 그", "위에서"
   - 추가 요청: "더", "다른", "또", "그 외에", "나머지"
   - 비교/변경: "대신", "말고", "바꿔서"
   - 설명 요청: "왜", "어떻게", "무슨 뜻", "자세히"
   - 후속 질문: "그러면", "그럼", "근데", "참고로"

### is_followup=true일 때 task_type 분류:
- "더 쉬운 거 없어?", "좀 더 어려운 Task는?" → refine_onboarding_tasks
- "다른 점수도 설명해줘", "왜 이런 점수가?" → explain_scores
- "이 repo 말고 비슷한 거 추천해줘" → compare_two_repos
- "건강 상태는?", "전체적으로 어때?" → diagnose_repo_health

followup_type 후보 (is_followup이 true일 때만):
- "refine_easier": 더 쉬운 Task 요청
- "refine_harder": 더 어려운 Task 요청  
- "refine_different": 다른 종류의 Task 요청
- "ask_detail": 상세 설명 요청 (점수, 결과 등)
- "compare_similar": 비슷한 저장소 비교 요청
- "continue_same": 같은 저장소에 대한 추가 질문

반드시 아래 JSON 형식만으로 답변하세요.

{
  "task_type": "<위 task_type 중 하나>",
  "repo_url": "<주 대상 repo URL 또는 null>",
  "compare_repo_url": "<비교 대상 repo URL 또는 null>",
  "is_followup": <true|false>,
  "followup_type": "<위 followup_type 중 하나 또는 null>",
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


def _extract_repo_from_query(query: str) -> RepoInfo | None:
    """
    사용자 쿼리에서 GitHub URL을 직접 정규식으로 추출.
    LLM 파싱 실패 시 fallback으로 사용.
    """
    # URL 형식: https://github.com/owner/repo
    url_pattern = r"https?://github\.com/([^/\s]+)/([^/\s?#]+)"
    match = re.search(url_pattern, query)
    if match:
        owner = match.group(1)
        name = match.group(2)
        # .git 접미사 제거 (rstrip 대신 endswith 사용)
        if name.endswith(".git"):
            name = name[:-4]
        return {
            "owner": owner,
            "name": name,
            "url": f"https://github.com/{owner}/{name}",
        }
    
    # owner/repo 형식 (한글 등 유니코드 문자와 붙어 있어도 매칭)
    short_pattern = r"([a-zA-Z][a-zA-Z0-9_-]*)/([a-zA-Z0-9_.-]+)"
    match = re.search(short_pattern, query)
    if match:
        owner = match.group(1)
        name = match.group(2)
        return {
            "owner": owner,
            "name": name,
            "url": f"https://github.com/{owner}/{name}",
        }
    
    return None


def _extract_all_repos_from_query(query: str) -> list[RepoInfo]:
    """
    사용자 쿼리에서 모든 GitHub 저장소를 추출.
    비교 질의에서 두 개의 저장소를 찾을 때 사용.
    """
    repos = []
    
    # URL 형식: https://github.com/owner/repo
    url_pattern = r"https?://github\.com/([^/\s]+)/([^/\s?#]+)"
    for match in re.finditer(url_pattern, query):
        owner = match.group(1)
        name = match.group(2)
        if name.endswith(".git"):
            name = name[:-4]
        repos.append({
            "owner": owner,
            "name": name,
            "url": f"https://github.com/{owner}/{name}",
        })
    
    # owner/repo 형식
    if not repos:
        short_pattern = r"([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)"
        for match in re.finditer(short_pattern, query):
            owner = match.group(1)
            name = match.group(2)
            repos.append({
                "owner": owner,
                "name": name,
                "url": f"https://github.com/{owner}/{name}",
            })
    
    return repos


def classify_intent_node(state: SupervisorState) -> SupervisorState:
    """
    사용자 쿼리에서 intent와 task_type을 추론하는 노드
    
    LLM을 호출하여 자연어 쿼리를 분석하고,
    전역 task_type만 설정한다. Agent별 task_type은 설정하지 않는다.
    
    멀티턴 대화에서는:
    - 이전 컨텍스트(last_repo, last_task_list)를 참조하여 follow-up 질의 처리
    - is_followup, followup_type 필드 설정
    """
    user_query = state.get("user_query", "")
    if not user_query:
        raise ValueError("SupervisorState.user_query가 비어 있습니다.")

    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")
    if progress_cb:
        progress_cb("질문 분석 중", "의도와 저장소 정보 추출...")

    # 먼저 쿼리에서 직접 repo 추출 (LLM 파싱 오류 대비 fallback)
    fallback_repo = _extract_repo_from_query(user_query)
    
    # 이전 컨텍스트 확인
    last_repo = state.get("last_repo")
    last_intent = state.get("last_intent")
    history = state.get("history", [])

    # LLM 호출 (이전 컨텍스트 포함)
    llm_response = _call_intent_llm_with_context(user_query, history, last_repo)
    parsed = _parse_llm_response(llm_response)

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    task_type = parsed.get("task_type", DEFAULT_TASK_TYPE)
    if not _is_valid_task_type(task_type):
        task_type = DEFAULT_TASK_TYPE

    new_state["task_type"] = task_type
    new_state["intent"] = task_type
    
    # Follow-up 정보 설정
    is_followup = parsed.get("is_followup", False)
    followup_type = validate_followup_type(parsed.get("followup_type"))
    
    new_state["is_followup"] = is_followup
    new_state["followup_type"] = followup_type

    # LLM이 파싱한 repo 정보
    repo_info = _parse_repo_url(parsed.get("repo_url"))
    
    # LLM 결과 vs 정규식 fallback 비교
    if repo_info and fallback_repo:
        # LLM이 repo 이름을 잘못 파싱했으면 fallback 사용
        if repo_info["name"] != fallback_repo["name"]:
            logger.warning(
                "[classify_intent_node] LLM 파싱 오류 감지: %s -> %s (fallback 사용)",
                repo_info["name"],
                fallback_repo["name"],
            )
            repo_info = fallback_repo
    elif not repo_info and fallback_repo:
        # LLM이 repo를 못 찾았으면 fallback 사용
        repo_info = fallback_repo
    
    # repo가 없고 이전 컨텍스트가 있으면 자동으로 follow-up 처리
    if not repo_info and last_repo:
        # LLM이 follow-up을 감지 못해도 강제로 follow-up 처리
        if not is_followup:
            logger.info(
                "[classify_intent_node] repo 없음 + last_repo 있음 → follow-up으로 자동 처리"
            )
            is_followup = True
            new_state["is_followup"] = True
        
        repo_info = last_repo
        logger.info(
            "[classify_intent_node] Follow-up: last_repo 사용 (%s/%s)",
            last_repo.get("owner"),
            last_repo.get("name"),
        )
    elif is_followup and not repo_info and last_repo:
        # 기존 로직 유지
        repo_info = last_repo
        logger.info(
            "[classify_intent_node] Follow-up: last_repo 사용 (%s/%s)",
            last_repo.get("owner"),
            last_repo.get("name"),
        )

    if repo_info:
        new_state["repo"] = repo_info

    compare_repo_info = _parse_repo_url(parsed.get("compare_repo_url"))
    if compare_repo_info:
        new_state["compare_repo"] = compare_repo_info

    # 비교 모드일 때 fallback: LLM이 두 저장소를 못 파싱했으면 정규식으로 추출
    if task_type == "compare_two_repos":
        if not new_state.get("repo") or not new_state.get("compare_repo"):
            all_repos = _extract_all_repos_from_query(user_query)
            if len(all_repos) >= 2:
                logger.info(
                    "[classify_intent_node] 비교 모드 fallback: %s vs %s",
                    all_repos[0]["name"],
                    all_repos[1]["name"],
                )
                new_state["repo"] = all_repos[0]
                new_state["compare_repo"] = all_repos[1]
            elif len(all_repos) == 1 and not new_state.get("repo"):
                # 하나만 추출된 경우 repo에만 설정
                new_state["repo"] = all_repos[0]

    user_context = _parse_user_context(parsed.get("user_context", {}))
    if user_context:
        new_state["user_context"] = user_context

    history = list(state.get("history", []))
    history.append({"role": "user", "content": user_query})
    new_state["history"] = history

    logger.info(
        "[classify_intent_node] task_type=%s, repo=%s, user_context=%s, is_followup=%s, followup_type=%s",
        new_state.get("task_type"),
        new_state.get("repo"),
        new_state.get("user_context"),
        new_state.get("is_followup"),
        new_state.get("followup_type"),
    )

    return new_state


def _call_intent_llm_with_context(
    user_query: str, 
    history: list[dict], 
    last_repo: RepoInfo | None
) -> str:
    """LLM을 호출하여 intent 분류 결과를 얻는다 (컨텍스트 포함)"""
    
    # 컨텍스트 정보 구성
    context_info = ""
    if last_repo:
        context_info += f"\n\n## 이전 대화 컨텍스트\n"
        context_info += f"- 마지막으로 분석한 저장소: {last_repo.get('owner')}/{last_repo.get('name')}\n"
    
    if history:
        # 최근 2턴만 포함 (너무 길면 토큰 낭비)
        recent_history = history[-4:] if len(history) > 4 else history
        context_info += "\n## 최근 대화 히스토리\n"
        for turn in recent_history:
            role = "사용자" if turn.get("role") == "user" else "어시스턴트"
            content = turn.get("content", "")[:200]  # 너무 길면 자르기
            context_info += f"- {role}: {content}\n"
    
    user_prompt = f"사용자 질의:\n{user_query}{context_info}"

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


def _call_intent_llm(user_query: str) -> str:
    """LLM을 호출하여 intent 분류 결과를 얻는다 (단순 버전, 하위 호환)"""
    return _call_intent_llm_with_context(user_query, [], None)


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
    name = match.group(2)
    # .git 접미사 제거 (rstrip 대신 endswith 사용)
    if name.endswith(".git"):
        name = name[:-4]

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
