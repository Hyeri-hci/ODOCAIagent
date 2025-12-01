"""Intent classifier node for Supervisor V1."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Tuple

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.common.events import EventType, emit_event
from backend.agents.shared.contracts import safe_get

from ..models import (
    SupervisorState, 
    SupervisorIntent,
    SubIntent,
    RepoInfo, 
    UserContext,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
)
from ..intent_config import validate_intent, validate_sub_intent

logger = logging.getLogger(__name__)


# Heuristic patterns
GREETING_KEYWORDS = {"안녕", "하이", "hi", "hello", "hey", "반가워", "헬로"}
CHITCHAT_KEYWORDS = {"고마워", "감사", "thanks", "ㅋㅋ", "ㅎㅎ", "좋아", "굿", "ok", "알겠어"}
IDENTITY_PATTERNS = [r"(누구|뭐하는|정체|역할)", r"(who are you)", r"(너는|넌)\s*(뭐|누구)"]
HELP_PATTERNS = [r"뭘?\s*할\s*수\s*있", r"도와", r"help", r"기능", r"사용법"]
ANALYSIS_KEYWORDS = {"분석", "진단", "건강", "온보딩", "기여", "점수", "상태", "어때", "analyze", "health"}
FOLLOWUP_PATTERNS = [r"(왜|어떻게|자세히)", r"(더\s*(쉬운|어려운|다른))", r"(그러면|그럼)"]

FastResult = Tuple[SupervisorIntent, SubIntent, Optional[RepoInfo], float]


def _has_repo(query: str) -> bool:
    """Check if query contains owner/repo pattern."""
    return bool(re.search(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+", query))


def _fast_classify(query: str) -> Optional[FastResult]:
    """Tier-1: Rule-based classification (no LLM)."""
    q = query.lower().strip()
    tokens = q.split()
    
    # Identity questions
    for p in IDENTITY_PATTERNS:
        if re.search(p, q):
            return ("smalltalk", "greeting", None, 1.0)
    
    # Help patterns
    for p in HELP_PATTERNS:
        if re.search(p, q):
            return ("help", "getting_started", None, 1.0)
    
    # Analysis with repo -> let LLM classify sub_intent
    if any(kw in q for kw in ANALYSIS_KEYWORDS) and _has_repo(query):
        return None
    
    # Short greetings/chitchat
    if len(tokens) <= 6:
        for kw in GREETING_KEYWORDS:
            if kw in q:
                return ("smalltalk", "greeting", None, 1.0)
        for kw in CHITCHAT_KEYWORDS:
            if kw in q:
                return ("smalltalk", "chitchat", None, 1.0)
    
    return None


def _extract_repo(query: str) -> Optional[RepoInfo]:
    """Extract GitHub repo from query."""
    # URL format
    url_match = re.search(r"https?://github\.com/([^/\s]+)/([^/\s?#]+)", query)
    if url_match:
        owner, name = url_match.groups()
        if name.endswith(".git"):
            name = name[:-4]
        return {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}"}
    
    # owner/repo format
    short_match = re.search(r"([a-zA-Z][a-zA-Z0-9_-]*)/([a-zA-Z0-9_.-]+)", query)
    if short_match:
        owner, name = short_match.groups()
        return {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}"}
    
    return None


INTENT_SYSTEM_PROMPT = """당신은 OSS 온보딩 플랫폼 ODOC의 Intent 분류기입니다.

## Intent 분류
- analyze: 저장소 분석 요청 (health, onboarding)
- followup: 이전 분석 결과에 대한 후속 질문 (explain)
- general_qa: 개념/일반 질문 (concept, chat)

## SubIntent
- health: 저장소 건강 분석
- onboarding: 온보딩/기여 Task 추천
- explain: 점수/결과 상세 설명
- concept: 지표 개념 설명
- chat: 일반 대화

## 출력 형식 (JSON만)
{
  "intent": "analyze|followup|general_qa",
  "sub_intent": "health|onboarding|explain|concept|chat",
  "repo_url": "<GitHub URL 또는 null>",
  "user_context": {"level": "beginner|intermediate|advanced 또는 null"}
}
"""


def _call_llm(query: str, history: list[dict]) -> str:
    """Call LLM for intent classification."""
    context = ""
    if history:
        recent = history[-4:] if len(history) > 4 else history
        context = "\n\n최근 대화:\n" + "\n".join(
            f"- {'사용자' if h.get('role')=='user' else 'AI'}: {h.get('content', '')[:150]}"
            for h in recent
        )
    
    client = fetch_llm_client()
    response = client.chat(ChatRequest(
        messages=[
            ChatMessage(role="system", content=INTENT_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"질의: {query}{context}"),
        ],
        max_tokens=256,
        temperature=0.0,
    ))
    return response.content


def _parse_response(raw: str) -> dict[str, Any]:
    """Parse LLM JSON response."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}


def _parse_repo_url(url: str | None) -> Optional[RepoInfo]:
    """Parse repo URL to RepoInfo."""
    if not url:
        return None
    match = re.search(r"github\.com[/:]([^/]+)/([^/\s]+)", url)
    if not match:
        return None
    owner, name = match.groups()
    if name.endswith(".git"):
        name = name[:-4]
    return {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}"}


def _parse_user_context(raw: dict | None) -> Optional[UserContext]:
    """Parse user context from LLM response."""
    if not raw:
        return None
    ctx: UserContext = {}
    if raw.get("level") in ("beginner", "intermediate", "advanced"):
        ctx["level"] = raw["level"]
    return ctx if ctx else None


def classify_intent_node(state: SupervisorState) -> SupervisorState:
    """Classify user intent (Heuristic first, then LLM). Null-safe."""
    query = safe_get(state, "user_query", "")
    if not query:
        raise ValueError("user_query is empty")
    
    new_state: SupervisorState = dict(state)  # type: ignore
    classification_method = "unknown"
    
    # 1) Heuristic classification
    fast = _fast_classify(query)
    if fast and fast[3] >= 0.9:
        intent, sub_intent, repo, conf = fast
        new_state["intent"] = intent
        new_state["sub_intent"] = sub_intent
        if repo:
            new_state["repo"] = repo
        classification_method = "heuristic"
        
        # Emit INTENT_DETECTED event
        emit_event(
            event_type=EventType.SUPERVISOR_INTENT_DETECTED,
            actor="intent_classifier",
            inputs={"query": query[:200]},
            outputs={
                "intent": intent,
                "sub_intent": sub_intent,
                "method": classification_method,
                "confidence": conf,
                "repo": f"{repo['owner']}/{repo['name']}" if repo else None,
            },
        )
        
        logger.info("[classify] Heuristic: %s.%s", intent, sub_intent)
        return new_state
    
    # 2) Fallback repo extraction
    fallback_repo = _extract_repo(query)
    
    # 3) LLM classification (Null-safe history access)
    history = safe_get(state, "history", [])
    if not isinstance(history, list):
        history = []
    
    raw = _call_llm(query, history)
    parsed = _parse_response(raw)
    
    intent = validate_intent(safe_get(parsed, "intent"))
    sub_intent = validate_sub_intent(safe_get(parsed, "sub_intent"))
    
    new_state["intent"] = intent
    new_state["sub_intent"] = sub_intent
    classification_method = "llm"
    
    # Repo info (LLM result or fallback)
    repo = _parse_repo_url(safe_get(parsed, "repo_url")) or fallback_repo
    if repo:
        new_state["repo"] = repo
    
    # User context
    ctx = _parse_user_context(safe_get(parsed, "user_context"))
    if ctx:
        new_state["user_context"] = ctx
    
    # Update history (Null-safe)
    hist = list(safe_get(state, "history", []) or [])
    hist.append({"role": "user", "content": query})
    new_state["history"] = hist
    
    # Emit INTENT_DETECTED event
    emit_event(
        event_type=EventType.SUPERVISOR_INTENT_DETECTED,
        actor="intent_classifier",
        inputs={"query": query[:200]},
        outputs={
            "intent": intent,
            "sub_intent": sub_intent,
            "method": classification_method,
            "confidence": 0.8,  # LLM default confidence
            "repo": f"{repo['owner']}/{repo['name']}" if repo else None,
        },
    )
    
    logger.info("[classify] LLM: %s.%s, repo=%s", intent, sub_intent, repo)
    return new_state
