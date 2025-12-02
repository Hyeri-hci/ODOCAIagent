"""Intent classifier with hierarchical routing (Heuristic → LLM)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Tuple
from dataclasses import dataclass

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
from ..intent_config import (
    validate_intent, 
    validate_sub_intent,
    get_confidence_threshold,
    should_degrade_to_help,
)

logger = logging.getLogger(__name__)


# Tier-1 Heuristic Patterns
GREETING_PATTERNS = [
    r"^(안녕|하이|헬로|hi|hello|hey)[\s!?.]*$",
    r"^(반가워|반갑습니다)[\s!?.]*$",
]

HELP_PATTERNS = [
    r"(뭘?\s*할\s*수\s*있|어떤\s*기능)",
    r"(도와|도움|help)",
    r"(사용법|사용\s*방법|how\s*to)",
    r"(설치|업데이트|오류|에러|안\s*됨|안됨)",
    r"^(기능|메뉴|명령어)[\s!?.]*$",
]

OVERVIEW_PATTERNS = [
    r"(뭐야|뭔가요|소개|정의|설명).*(저장소|레포|repo)",
    r"(저장소|레포|repo).*(뭐야|뭔가요|소개|정의|설명)",
    r"^([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)\s*(뭐야|뭔가요|소개|정의|설명해|알려줘)[\s!?.]*$",
    r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)\s*(가|이)\s*(뭐야|뭔가요|뭐|뭔)",
    r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+).*(어떤|무슨).*(프로젝트|저장소|레포)",
]

IDENTITY_PATTERNS = [
    r"(누구|뭐하는|정체|역할)",
    r"(who\s*are\s*you)",
    r"(너는|넌)\s*(뭐|누구)",
]

# Follow-up 패턴 (직전 턴 참조)
FOLLOWUP_PATTERNS = [
    r"(그|그거|이거|저거|그것|이것)\s*(결과|점수|근거|이유|왜|어디서|출처)",
    r"(왜|어떻게|어디서).*(나왔|계산|판단)",
    r"(근거|이유|출처).*(뭐|알려|설명)",
    r"^(왜|어떻게|어디서)[요?\s]*$",
    r"(좀더|더)\s*(자세히|설명|알려)",
    r"(방금|아까|위에|이전).*(결과|분석|점수)",
]

# Follow-up 키워드 (부분 매칭)
FOLLOWUP_KEYWORDS = {"근거", "이유", "왜", "출처", "어디서", "자세히", "더 설명", "방금"}

# Compare 패턴 (두 개의 repo 비교)
COMPARE_PATTERNS = [
    r"(.+)(랑|와|과|vs|versus|compared?\s*to)\s*(.+)\s*(비교|compare)",
    r"(비교|compare)\s*(.+)(랑|와|과|vs)\s*(.+)",
    r"(.+)(이랑|하고)\s*(.+)\s*(비교)",
]

# One-pager/요약 패턴
ONEPAGER_PATTERNS = [
    r"(한\s*장|원페이저|one.?pager|요약|정리).*(만들어|생성|줘|해줘)",
    r"(발표|보고|브리핑).*(자료|요약)",
    r"(정리|요약).*(한\s*장|간단히)",
]

# Refine 패턴 (Task 재필터링)
REFINE_PATTERNS = [
    r"(급한|중요한|쉬운|어려운).*(것|거).*(정리|추려|골라|다시)",
    r"(\d+)개.*(만|정리|다시|추려)",
    r"(우선순위|priority).*(정렬|순서)",
]

ANALYSIS_KEYWORDS = {"분석", "진단", "건강", "온보딩", "기여", "점수", "상태", "어때", "analyze", "health"}
CHITCHAT_KEYWORDS = {"고마워", "감사", "thanks", "ㅋㅋ", "ㅎㅎ", "좋아", "굿", "ok", "알겠어", "ㅇㅋ"}


@dataclass
class ClassifyResult:
    """Result of intent classification."""
    intent: SupervisorIntent
    sub_intent: SubIntent
    repo: Optional[RepoInfo]
    confidence: float
    method: str  # "heuristic" | "llm" | "degrade"
    compare_repo: Optional[RepoInfo] = None  # Second repo for compare


def _has_repo_pattern(query: str) -> bool:
    """Check if query contains owner/repo pattern."""
    return bool(re.search(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+", query))


def _detect_followup(query: str, has_prev_artifacts: bool) -> bool:
    """Detect follow-up intent from query patterns."""
    if not has_prev_artifacts:
        return False
    
    q = query.lower().strip()
    
    # Pattern matching
    for p in FOLLOWUP_PATTERNS:
        if re.search(p, q):
            return True
    
    # Keyword matching (short queries)
    if len(q) <= 20:
        for kw in FOLLOWUP_KEYWORDS:
            if kw in q:
                return True
    
    return False


def _is_short_or_emoji(query: str) -> bool:
    """Check if query is too short or mostly emoji."""
    stripped = query.strip()
    if len(stripped) <= 3:
        return True
    emoji_pattern = re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]")
    emoji_count = len(emoji_pattern.findall(stripped))
    return emoji_count > len(stripped) / 3


def _tier1_heuristic(query: str, has_prev_artifacts: bool = False) -> Optional[ClassifyResult]:
    """Tier-1: Rule-based classification (no LLM, high confidence)."""
    q = query.lower().strip()
    
    # Compare detection (두 개의 repo 비교)
    is_compare, repo_a, repo_b = _detect_compare(query)
    if is_compare and repo_a and repo_b:
        result = ClassifyResult("analyze", "compare", repo_a, 1.0, "heuristic")
        result.compare_repo = repo_b  # type: ignore
        return result
    
    # Refine detection (직전 턴 아티팩트 있을 때만, one-pager보다 먼저 체크)
    if _detect_refine(query, has_prev_artifacts):
        return ClassifyResult("followup", "refine", None, 1.0, "heuristic")
    
    # One-pager detection
    if _detect_onepager(query):
        repo = _extract_repo(query)
        return ClassifyResult("analyze", "onepager", repo, 1.0, "heuristic")
    
    # Follow-up detection (직전 턴 아티팩트 있을 때만)
    if _detect_followup(query, has_prev_artifacts):
        return ClassifyResult("followup", "evidence", None, 1.0, "heuristic")
    
    # Identity questions → greeting (check first)
    for p in IDENTITY_PATTERNS:
        if re.search(p, q):
            return ClassifyResult("smalltalk", "greeting", None, 1.0, "heuristic")
    
    # Greeting patterns (exact match, check before short fallback)
    for p in GREETING_PATTERNS:
        if re.search(p, q):
            return ClassifyResult("smalltalk", "greeting", None, 1.0, "heuristic")
    
    # Short/emoji without greeting → help fallback
    if _is_short_or_emoji(query) and not _has_repo_pattern(query):
        return ClassifyResult("help", "getting_started", None, 1.0, "heuristic")
    
    # Help patterns
    for p in HELP_PATTERNS:
        if re.search(p, q):
            return ClassifyResult("help", "getting_started", None, 1.0, "heuristic")
    
    # Overview patterns (repo + intro keywords)
    repo = _extract_repo(query)
    for p in OVERVIEW_PATTERNS:
        if re.search(p, q):
            return ClassifyResult("overview", "repo", repo, 1.0, "heuristic")
    
    # Repo with question mark but no analysis keywords -> overview
    if repo and re.search(r"(뭐야|뭔가요|뭔데|뭐지|어때)[?\s]*$", q):
        if not any(kw in q for kw in ANALYSIS_KEYWORDS):
            return ClassifyResult("overview", "repo", repo, 0.9, "heuristic")
    
    # Analysis keywords → delegate to LLM for sub_intent classification
    if any(kw in q for kw in ANALYSIS_KEYWORDS):
        return None  # LLM will classify
    
    # Chitchat keywords (only for short queries without analysis)
    tokens = q.split()
    if len(tokens) <= 6:
        for kw in CHITCHAT_KEYWORDS:
            if kw in q:
                return ClassifyResult("smalltalk", "chitchat", None, 1.0, "heuristic")
    
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
    
    # owner/repo format (handle vue.js/core style - dots allowed in owner)
    # More permissive: allow dots in both owner and name
    short_match = re.search(r"([a-zA-Z][a-zA-Z0-9_.-]*)/([a-zA-Z0-9_.-]+)", query)
    if short_match:
        owner, name = short_match.groups()
        # Clean trailing punctuation from name
        name = re.sub(r'[\s,;:!?]+$', '', name)
        return {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}"}
    
    return None


def _extract_two_repos(query: str) -> Tuple[Optional[RepoInfo], Optional[RepoInfo]]:
    """Extract two GitHub repos from query for comparison."""
    repos = []
    
    # Find all owner/repo patterns (allow dots in owner like vue.js)
    patterns = re.findall(r"([a-zA-Z][a-zA-Z0-9_.-]*)/([a-zA-Z0-9_.-]+)", query)
    for owner, name in patterns:
        # Skip common false positives
        if owner.lower() in ("http", "https", "www", "github"):
            continue
        # Clean trailing punctuation
        name = re.sub(r'[\s,;:!?]+$', '', name)
        repos.append({"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}"})
    
    if len(repos) >= 2:
        return repos[0], repos[1]
    elif len(repos) == 1:
        return repos[0], None
    return None, None


def _detect_compare(query: str) -> Tuple[bool, Optional[RepoInfo], Optional[RepoInfo]]:
    """Detect compare intent and extract two repos."""
    q = query.lower().strip()
    
    for p in COMPARE_PATTERNS:
        if re.search(p, q, re.IGNORECASE):
            repo_a, repo_b = _extract_two_repos(query)
            if repo_a and repo_b:
                return True, repo_a, repo_b
    
    return False, None, None


def _detect_onepager(query: str) -> bool:
    """Detect one-pager/summary request."""
    q = query.lower().strip()
    for p in ONEPAGER_PATTERNS:
        if re.search(p, q, re.IGNORECASE):
            return True
    return False


def _detect_refine(query: str, has_prev_artifacts: bool) -> bool:
    """Detect refine/filter request for previous results."""
    if not has_prev_artifacts:
        return False
    q = query.lower().strip()
    for p in REFINE_PATTERNS:
        if re.search(p, q, re.IGNORECASE):
            return True
    return False


INTENT_SYSTEM_PROMPT = """당신은 OSS 온보딩 플랫폼 ODOC의 Intent 분류기입니다.

## Intent 분류 (6개)
- analyze: 저장소 분석 요청 (health, onboarding) - 비용이 큰 작업
- followup: 이전 분석 결과에 대한 후속 질문 (explain)
- overview: 저장소 간단 소개/정의 요청 (repo) - 분석 없이 즉답
- help: 플랫폼 사용법/기능 문의 (getting_started)
- smalltalk: 인사/잡담 (greeting, chitchat)
- general_qa: 개념/일반 질문 (concept, chat)

## SubIntent
- health: 저장소 건강 분석 (상세 지표 필요)
- onboarding: 온보딩/기여 Task 추천 (상세 분석 필요)
- explain: 점수/결과 상세 설명
- repo: 저장소 간단 소개 (분석 불필요)
- getting_started: 사용법/기능 안내
- greeting: 인사 응답
- chitchat: 일상 대화
- concept: 지표 개념 설명
- chat: 일반 대화

## 분류 기준
1. "뭐야", "소개", "설명해줘" + repo → overview.repo (분석 X)
2. "분석", "진단", "점수", "건강" + repo → analyze.health (분석 O)
3. "기여", "온보딩", "시작" + repo → analyze.onboarding (분석 O)
4. "도와줘", "사용법", "기능" → help.getting_started

## 출력 형식 (JSON만)
{
  "intent": "analyze|followup|overview|help|smalltalk|general_qa",
  "sub_intent": "health|onboarding|explain|repo|getting_started|greeting|chitchat|concept|chat",
  "confidence": 0.0~1.0,
  "repo_url": "<GitHub URL 또는 null>",
  "user_context": {"level": "beginner|intermediate|advanced 또는 null"}
}
"""


def _call_llm_classify(query: str, history: list[dict]) -> dict[str, Any]:
    """Tier-2: LLM classification with confidence score."""
    context = ""
    if history:
        recent = history[-4:] if len(history) > 4 else history
        context = "\n\n최근 대화:\n" + "\n".join(
            f"- {'사용자' if h.get('role')=='user' else 'AI'}: {h.get('content', '')[:150]}"
            for h in recent
        )
    
    try:
        client = fetch_llm_client()
        response = client.chat(ChatRequest(
            messages=[
                ChatMessage(role="system", content=INTENT_SYSTEM_PROMPT),
                ChatMessage(role="user", content=f"질의: {query}{context}"),
            ],
            max_tokens=256,
            temperature=0.0,
        ))
        return _parse_llm_response(response.content)
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return {}


def _parse_llm_response(raw: str) -> dict[str, Any]:
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


def _tier2_llm_classify(query: str, history: list[dict]) -> ClassifyResult:
    """Tier-2: LLM classification with confidence-based degradation."""
    parsed = _call_llm_classify(query, history)
    
    intent = validate_intent(safe_get(parsed, "intent"))
    sub_intent = validate_sub_intent(safe_get(parsed, "sub_intent"))
    confidence = float(safe_get(parsed, "confidence", 0.5))
    
    repo = _parse_repo_url(safe_get(parsed, "repo_url"))
    if not repo:
        repo = _extract_repo(query)
    
    # Confidence-based degradation
    if should_degrade_to_help(intent, confidence):
        logger.info(f"[classify] Degrading {intent} (conf={confidence:.2f}) to help.getting_started")
        return ClassifyResult("help", "getting_started", repo, confidence, "degrade")
    
    return ClassifyResult(intent, sub_intent, repo, confidence, "llm")


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
    """Hierarchical intent classification: Tier-1 Heuristic → Tier-2 LLM."""
    query = safe_get(state, "user_query", "")
    if not query:
        raise ValueError("user_query is empty")
    
    new_state: SupervisorState = dict(state)  # type: ignore
    
    # Check for previous artifacts (for follow-up detection)
    diagnosis_result = safe_get(state, "diagnosis_result")
    has_prev_artifacts = bool(diagnosis_result and isinstance(diagnosis_result, dict))
    
    # Tier-1: Heuristic (instant, no LLM)
    result = _tier1_heuristic(query, has_prev_artifacts)
    
    if result is None:
        # Tier-2: LLM classification
        history = safe_get(state, "history", [])
        if not isinstance(history, list):
            history = []
        result = _tier2_llm_classify(query, history)
    
    # Apply result to state
    new_state["intent"] = result.intent
    new_state["sub_intent"] = result.sub_intent
    if result.repo:
        new_state["repo"] = result.repo
    if result.compare_repo:
        new_state["compare_repo"] = result.compare_repo
    
    # Store confidence for routing decisions
    new_state["_classification_confidence"] = result.confidence  # type: ignore
    new_state["_classification_method"] = result.method  # type: ignore
    
    # Update history
    hist = list(safe_get(state, "history", []) or [])
    hist.append({"role": "user", "content": query})
    new_state["history"] = hist  # type: ignore
    
    # Emit INTENT_DETECTED event
    emit_event(
        event_type=EventType.SUPERVISOR_INTENT_DETECTED,
        actor="intent_classifier",
        inputs={"query": query[:200]},
        outputs={
            "intent": result.intent,
            "sub_intent": result.sub_intent,
            "method": result.method,
            "confidence": result.confidence,
            "repo": f"{result.repo['owner']}/{result.repo['name']}" if result.repo else None,
        },
    )
    
    logger.info(
        "[classify] %s: %s.%s (conf=%.2f, repo=%s)",
        result.method.upper(),
        result.intent,
        result.sub_intent,
        result.confidence,
        f"{result.repo['owner']}/{result.repo['name']}" if result.repo else None,
    )
    
    return new_state
