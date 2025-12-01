"""Intent 분류 노드. LLM으로 Intent/SubIntent 추론."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Tuple

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

logger = logging.getLogger(__name__)

from ..models import (
    SupervisorState, 
    SupervisorIntent,
    SubIntent,
    RepoInfo, 
    UserContext,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
    VALID_INTENTS,
    VALID_SUB_INTENTS,
    convert_legacy_task_type,
)
from ..intent_config import validate_followup_type, validate_intent, validate_sub_intent


# 경량 분류용 키워드 (LLM 호출 전 빠른 경로)
GREETING_KEYWORDS = {
    "안녕", "하이", "hi", "hello", "hey", "안뇽", "헬로", "반가워", "반갑",
}
CHITCHAT_KEYWORDS = {
    "고마워", "감사", "thanks", "thank you", "ㅋㅋ", "ㅎㅎ", "좋아", "굿", "good",
    "오케이", "okay", "ok", "알겠어", "네", "응", "ㅇㅇ",
}
HELP_PATTERNS = [
    r"뭘?\s*할\s*수\s*있",
    r"도와",
    r"help",
    r"무엇을?\s*(할|도와)",
    r"뭐\s*해",
    r"어떻게\s*써",
    r"사용법",
    r"기능",
]
# 개요 패턴: "facebook/react가 뭐야?", "react 알려줘"
OVERVIEW_PATTERNS = [
    r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)(가|이|는|은)?\s*(뭐|뭔|무엇|what)",
    r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)\s*알려",
    r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)\s*(소개|개요)",
]
# 분석/진단 관련 키워드 (있으면 Expert Tool 경로)
ANALYSIS_KEYWORDS = {
    "분석", "진단", "비교", "추천", "건강", "온보딩", "기여",
    "analyze", "diagnose", "compare", "health", "onboarding",
}


def _fast_classify_smalltalk(query: str) -> Optional[Tuple[SupervisorIntent, SubIntent]]:
    """
    경량 분류: Fast Chat 경로 빠른 판별 (LLM 호출 없이).
    
    규칙 (우선순위 순):
    1. 도움 요청 패턴 → help.getting_started
    2. 분석/진단 키워드 → None (Expert Tool)
    3. 개요 패턴 (owner/repo가 뭐야?) → overview.repo
    4. 짧은 인사 (≤8 토큰) → smalltalk.greeting
    5. 짧은 잡담 (≤8 토큰) → smalltalk.chitchat
    
    Returns:
        (intent, sub_intent) 튜플 또는 None (LLM 분류 필요)
    """
    query_lower = query.lower().strip()
    tokens = query_lower.split()
    token_count = len(tokens)
    
    # 1) 도움말 패턴 먼저 체크 (최우선)
    for pattern in HELP_PATTERNS:
        if re.search(pattern, query_lower):
            logger.info("[fast_classify] help.getting_started: %s", query[:50])
            return ("help", "getting_started")
    
    # 2) 분석/진단 관련 키워드가 있으면 Expert Tool 경로
    for kw in ANALYSIS_KEYWORDS:
        if kw in query_lower:
            return None
    
    # 3) 개요 패턴 체크 (owner/repo가 뭐야?)
    for pattern in OVERVIEW_PATTERNS:
        if re.search(pattern, query_lower):
            logger.info("[fast_classify] overview.repo: %s", query[:50])
            return ("overview", "repo")
    
    # 4) 짧은 쿼리 (≤ 8 토큰)에서만 인사/잡담 체크
    if token_count <= 8:
        # 인사 키워드 체크
        for kw in GREETING_KEYWORDS:
            if kw in query_lower:
                logger.info("[fast_classify] smalltalk.greeting: %s", query[:50])
                return ("smalltalk", "greeting")
        
        # 잡담 키워드 체크
        for kw in CHITCHAT_KEYWORDS:
            if kw in query_lower:
                logger.info("[fast_classify] smalltalk.chitchat: %s", query[:50])
                return ("smalltalk", "chitchat")
    
    # 5) 경량 분류 불가 → LLM 분류 필요
    return None


def _normalize_history(history: Any) -> list[dict]:
    """비정상 history 입력을 list[dict]로 정규화."""
    if history is None:
        return []
    
    if isinstance(history, str):
        logger.warning("[_normalize_history] history가 문자열입니다: %s", history[:100])
        return []
    
    if not isinstance(history, list):
        logger.warning("[_normalize_history] history가 list가 아닙니다: %s", type(history))
        return []
    
    normalized = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            normalized.append(item)
        else:
            logger.warning("[_normalize_history] 잘못된 history 항목: %s", item)
    
    return normalized


INTENT_SYSTEM_PROMPT = """
당신은 OSS 온보딩 플랫폼 ODOC의 Supervisor Agent입니다.

## 역할
1) 사용자의 한국어/영어 질의를 읽고, Intent와 SubIntent를 분류합니다.
2) 질의 안에 포함된 GitHub 저장소 URL이 있다면 추출합니다.
3) 사용자의 수준(level), 목표(goal) 등을 추론합니다.

## Intent 분류 (3가지)

### analyze
- **정의**: 새로운 저장소 분석이 필요한 요청
- **조건**: GitHub URL이 있거나, 새로운 저장소/비교를 요청할 때
- **sub_intent**: health, onboarding, compare

### followup
- **정의**: 이전 분석 결과에 대한 후속 질문
- **조건**: 이전 대화 컨텍스트를 참조하여 더 자세히 묻거나, 결과를 조정할 때
- **sub_intent**: explain, refine

### general_qa
- **정의**: 특정 저장소 없이 개념, 프로세스, 일반 질문
- **조건**: 저장소 분석 없이 답변 가능한 질문
- **sub_intent**: concept, chat

## SubIntent 분류 (7가지)

| SubIntent | 설명 | 예시 |
|-----------|------|------|
| health | 저장소 건강 상태 분석 | "react 상태 분석해줘" |
| onboarding | 온보딩 Task 추천 | "초보자인데 이 프로젝트에 기여하고 싶어" |
| compare | 두 저장소 비교 | "react랑 vue 비교해줘" |
| explain | 이전 결과 상세 설명 | "4단계 테스트를 더 자세히 설명해줘" |
| refine | Task 재필터링 | "더 쉬운 이슈는 없을까?" |
| concept | 지표/개념 설명 | "health_score가 정확히 뭐야?" |
| chat | 일반 대화/인사 | "안녕? 뭐 하는 에이전트야?" |

## 분류 규칙 (중요!)

1. **새 repo/새 비교 요청 → analyze**
   - 새로운 저장소 URL이 있으면 무조건 analyze
   - "A랑 B 비교해줘" → analyze + compare

2. **이전 결과 확대 설명/리랭킹 → followup**
   - 저장소 URL 없음 + 이전 대화 컨텍스트 참조
   - "더 쉬운 거", "왜 이런 점수가?", "자세히" → followup

3. **지표 개념/진단 기준 → general_qa + concept**
   - 저장소 없이 답변 가능한 개념 질문
   - "온보딩 용이성이 뭐야?", "PR은 어떻게 보내?"

4. **잡담/인사 → general_qa + chat**
   - OSS와 직접 관련 없는 인사, 질문
   - "안녕", "고마워", "뭐 하는 에이전트야?"

## 분류 예시

| 질의 | intent | sub_intent |
|------|--------|------------|
| "react 상태 분석해줘" | analyze | health |
| "https://github.com/facebook/react 분석해줘" | analyze | health |
| "초보자인데 이 프로젝트에 기여하고 싶어" | analyze | onboarding |
| "그럼 vue랑 비교해줘" | analyze | compare |
| "점수 설명해줘" | followup | explain |
| "왜 이런 점수가 나왔어?" | followup | explain |
| "4단계 테스트를 더 자세히 설명해줘" | followup | explain |
| "더 쉬운 이슈는 없을까?" | followup | refine |
| "더 쉬운 거 추천해줘" | followup | refine |
| "다른 종류의 Task 보여줘" | followup | refine |
| "health_score가 정확히 뭐야?" | general_qa | concept |
| "온보딩 용이성이 무슨 뜻이야?" | general_qa | concept |
| "안녕? 뭐 하는 에이전트야?" | general_qa | chat |
| "고마워!" | general_qa | chat |

## followup vs analyze 구분 핵심

**followup (explain, refine):**
- 이전 대화 컨텍스트를 참조하여 "설명", "재필터링"을 요청
- 새로운 저장소 URL이 없음 (이전에 분석한 저장소를 기준으로)
- 예: "점수 왜 이래?", "더 쉬운 거", "자세히 설명해줘"

**analyze (health, onboarding, compare):**
- 새로운 저장소 URL이 명시되거나 새 분석을 요청
- 예: "react 분석해줘", "이 프로젝트 기여하고 싶어"

## GitHub URL 파싱 규칙
- URL 형식: https://github.com/{owner}/{repo}
- 예시: https://github.com/facebook/react → owner="facebook", repo="react"
- 저장소 이름은 URL에 있는 그대로 정확히 추출하세요.

## 후속 질문 감지 (followup 판단용)
아래와 같은 표현이 있으면 followup일 가능성 높음:
- 지시대명사: "그거", "이거", "그 저장소", "아까 그"
- 추가 요청: "더", "다른", "또", "그 외에"
- 설명 요청: "왜", "어떻게", "무슨 뜻", "자세히"
- 후속 질문: "그러면", "그럼", "근데"

## 출력 형식

반드시 아래 JSON 형식만으로 답변하세요.

{
  "intent": "analyze|followup|general_qa",
  "sub_intent": "health|onboarding|compare|explain|refine|concept|chat",
  "repo_url": "<GitHub URL 또는 null>",
  "compare_repo_url": "<비교 대상 repo URL 또는 null>",
  "user_context": {
    "level": "beginner|intermediate|advanced 또는 null",
    "goal": "<사용자 목표 요약 또는 null>",
    "time_budget_hours": <숫자 또는 null>,
    "preferred_language": "ko|en 등 또는 null"
  }
}

추가 설명이나 자연어 문장은 절대 포함하지 마세요.
""".strip()


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
    사용자 쿼리에서 intent와 sub_intent를 추론하는 노드
    
    1) 경량 분류 시도 (인사/잡담/도움말 → LLM 호출 없이 즉시 응답)
    2) LLM 호출하여 자연어 쿼리 분석
    3) Intent(analyze/followup/general_qa/smalltalk/help)와 SubIntent 설정
    
    멀티턴 대화에서는:
    - 이전 컨텍스트(last_repo, last_task_list)를 참조하여 follow-up 질의 처리
    - is_followup 필드 설정
    """
    user_query = state.get("user_query", "")
    if not user_query:
        raise ValueError("SupervisorState.user_query가 비어 있습니다.")

    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")
    if progress_cb:
        progress_cb("질문 분석 중", "의도와 저장소 정보 추출...")

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]
    
    # 1) 경량 분류 먼저 시도 (LLM 호출 없이 빠른 경로)
    fast_result = _fast_classify_smalltalk(user_query)
    if fast_result:
        intent, sub_intent = fast_result
        new_state["intent"] = intent
        new_state["sub_intent"] = sub_intent
        new_state["task_type"] = f"{intent}_{sub_intent}"
        new_state["is_followup"] = False
        new_state["followup_type"] = None
        new_state["repo"] = None
        new_state["_fast_classified"] = True  # 경량 분류 플래그
        logger.info("[classify_intent_node] Fast classified: %s.%s", intent, sub_intent)
        return new_state

    # 2) 일반 분류 (LLM 호출)
    # 먼저 쿼리에서 직접 repo 추출 (LLM 파싱 오류 대비 fallback)
    fallback_repo = _extract_repo_from_query(user_query)
    
    # 이전 컨텍스트 확인
    last_repo = state.get("last_repo")
    last_intent = state.get("last_intent")
    
    # history 정규화 (str이 들어오는 등의 에러 방지)
    raw_history = state.get("history", [])
    history = _normalize_history(raw_history)

    # LLM 호출 (이전 컨텍스트 포함)
    llm_response = _call_intent_llm_with_context(user_query, history, last_repo)
    parsed = _parse_llm_response(llm_response)

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    # ========================================
    # 새 구조: intent + sub_intent 설정
    # ========================================
    intent = parsed.get("intent", DEFAULT_INTENT)
    sub_intent = parsed.get("sub_intent", DEFAULT_SUB_INTENT)
    
    # 유효성 검사
    intent = validate_intent(intent)
    sub_intent = validate_sub_intent(sub_intent)
    
    new_state["intent"] = intent
    new_state["sub_intent"] = sub_intent
    
    # 레거시 호환: task_type도 설정 (기존 코드 호환)
    new_state["task_type"] = _convert_to_legacy_task_type(intent, sub_intent)
    
    # Follow-up 판단 (intent가 followup이면 True)
    is_followup = (intent == "followup")
    new_state["is_followup"] = is_followup
    
    # followup_type 설정 (refine → refine_easier/harder 등으로 매핑)
    followup_type = _infer_followup_type(sub_intent, user_query) if is_followup else None
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
    
    # followup인데 repo_info도 없고 last_repo도 없는 경우 → 에러 메시지 설정
    # (graph.py에서 처리하지만, 여기서 더 명확한 안내 가능)
    if is_followup and not repo_info and not last_repo:
        logger.warning(
            "[classify_intent_node] followup 요청이지만 분석할 저장소가 없습니다"
        )
        # 에러 메시지는 graph.py의 route_after_mapping에서 설정되므로 여기선 로깅만
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
    if sub_intent == "compare":
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
                # repos 리스트도 설정 (나중 확장용)
                new_state["repos"] = all_repos[:2]
            elif len(all_repos) == 1 and not new_state.get("repo"):
                new_state["repo"] = all_repos[0]

    user_context = _parse_user_context(parsed.get("user_context", {}))
    if user_context:
        new_state["user_context"] = user_context

    # history에 현재 쿼리 추가 (dict 형태로 통일)
    history = list(state.get("history", []))
    history.append({"role": "user", "content": user_query})
    new_state["history"] = history

    logger.info(
        "[classify_intent_node] intent=%s, sub_intent=%s, repo=%s, is_followup=%s",
        new_state.get("intent"),
        new_state.get("sub_intent"),
        new_state.get("repo"),
        new_state.get("is_followup"),
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


def _is_valid_intent(value: str) -> bool:
    """유효한 SupervisorIntent인지 확인 (새 구조)"""
    return value in VALID_INTENTS


def _is_valid_sub_intent(value: str) -> bool:
    """유효한 SubIntent인지 확인"""
    return value in VALID_SUB_INTENTS


def _convert_to_legacy_task_type(intent: str, sub_intent: str) -> str:
    """
    새 (intent, sub_intent) 구조를 레거시 task_type으로 변환.
    기존 코드와의 호환성을 위해 사용.
    """
    mapping = {
        ("analyze", "health"): "diagnose_repo_health",
        ("analyze", "onboarding"): "diagnose_repo_onboarding",
        ("analyze", "compare"): "compare_two_repos",
        ("followup", "explain"): "explain_scores",
        ("followup", "refine"): "refine_onboarding_tasks",
        ("general_qa", "concept"): "concept_qa_metric",
        ("general_qa", "chat"): "concept_qa_process",  # chat도 일반 응답으로 처리
    }
    return mapping.get((intent, sub_intent), "diagnose_repo_health")


def _infer_followup_type(sub_intent: str, user_query: str) -> str | None:
    """
    sub_intent와 쿼리 내용으로 followup_type 추론.
    """
    query_lower = user_query.lower()
    
    if sub_intent == "refine":
        if any(kw in query_lower for kw in ["쉬운", "쉽", "easy", "easier", "simple"]):
            return "refine_easier"
        elif any(kw in query_lower for kw in ["어려운", "어렵", "hard", "harder", "difficult", "challenge"]):
            return "refine_harder"
        elif any(kw in query_lower for kw in ["다른", "다르", "different", "another", "other"]):
            return "refine_different"
        return "refine_easier"  # 기본값
    
    if sub_intent == "explain":
        return "ask_detail"
    
    return None


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
