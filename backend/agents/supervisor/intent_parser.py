"""Global Intent Parser - LLM 기반 의도/엔터티 추출.

사용자 자연어 입력을 구조화된 ParsedChatIntent로 변환하고,
repo_hint를 기반으로 캐시에서 실제 레포를 매칭합니다.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

# Intent 종류 정의
IntentType = Literal["diagnose", "compare", "explain", "onboard", "chat", "help", "unknown"]

# 대상 메트릭 종류
TargetMetricType = Literal["health", "onboarding", "docs", "activity", "structure", "all", None]


@dataclass
class ParsedChatIntent:
    """LLM에서 파싱된 사용자 의도."""
    
    intent: IntentType = "chat"
    repo_hint: Optional[str] = None  # 사용자가 말한 레포 이름/별칭 (raw)
    target_metric: Optional[str] = None  # health, onboarding, docs 등
    options: Dict[str, Any] = field(default_factory=dict)  # no_llm, depth, language 등
    follow_up: bool = False  # 이전 답변에 대한 후속 질문 여부
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "repo_hint": self.repo_hint,
            "target_metric": self.target_metric,
            "options": self.options,
            "follow_up": self.follow_up,
            "confidence": self.confidence,
        }


# 간단한 명령어 패턴 (LLM 호출 불필요)
SIMPLE_COMMANDS = {
    "/help": "help",
    "/reset": "help",
    "/version": "help",
    "도움말": "help",
    "도움": "help",
}


def is_simple_command(message: str) -> bool:
    """간단한 명령어인지 확인."""
    if not message:
        return False
    msg_lower = message.strip().lower()
    return msg_lower in SIMPLE_COMMANDS or msg_lower.startswith("/")


def handle_simple_command(message: str) -> ParsedChatIntent:
    """간단한 명령어를 ParsedChatIntent로 변환."""
    msg_lower = message.strip().lower()
    intent = SIMPLE_COMMANDS.get(msg_lower, "help")
    return ParsedChatIntent(intent=intent, confidence=1.0)


def _build_parser_prompt(
    message: str,
    analyzed_repos: List[str],
    last_context: Optional[Dict[str, Any]] = None,
) -> str:
    """LLM 파서용 시스템 프롬프트 생성."""
    
    repos_str = ", ".join(analyzed_repos[:10]) if analyzed_repos else "없음"
    
    context_info = ""
    if last_context:
        last_repo = last_context.get("repo_id") or last_context.get("repo_url", "")
        if last_repo:
            context_info = f"\n[이전 대화 컨텍스트]\n- 마지막 분석 저장소: {last_repo}"
    
    return f"""당신은 ODOC 시스템의 Intent 파서입니다.
사용자 메시지를 분석하여 JSON 형식으로만 응답하세요.

[가능한 intent 값]
- diagnose: 저장소 분석/진단 요청
- compare: 여러 저장소 비교 요청
- explain: 분석 결과 설명 요청
- onboard: 기여/온보딩 방법 문의
- chat: 일반 대화
- help: 도움말 요청

[가능한 target_metric 값]
- health: 건강 점수
- onboarding: 온보딩 점수
- docs: 문서 품질
- activity: 활동성
- structure: 구조 점수
- all: 전체 분석
- null: 특정 메트릭 없음

[분석 완료된 저장소 목록]
{repos_str}
{context_info}

[응답 형식 - 반드시 이 JSON만 출력]
{{
  "intent": "diagnose|compare|explain|onboard|chat|help",
  "repo_hint": "사용자가 언급한 저장소 이름 또는 null",
  "target_metric": "health|onboarding|docs|activity|structure|all|null",
  "options": {{}},
  "follow_up": true/false,
  "confidence": 0.0-1.0
}}

주의사항:
- JSON 외 다른 텍스트 절대 출력 금지
- repo_hint는 사용자가 말한 그대로 추출 (예: "react", "저번 레포", "vscode")
- follow_up은 이전 대화 결과에 대한 후속 질문인지 여부
- confidence는 의도 분류 확신도"""


def llm_parse_chat_intent(
    message: str,
    analyzed_repos: List[str],
    last_context: Optional[Dict[str, Any]] = None,
) -> Optional[ParsedChatIntent]:
    """
    LLM을 사용하여 사용자 메시지를 ParsedChatIntent로 파싱.
    
    Args:
        message: 사용자 입력 메시지
        analyzed_repos: 현재 캐시에 있는 분석된 레포 목록
        last_context: 이전 대화 컨텍스트 (선택)
    
    Returns:
        ParsedChatIntent 또는 파싱 실패 시 None
    """
    if not message or len(message.strip()) < 2:
        return None
    
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME
        
        client = fetch_llm_client()
        
        system_prompt = _build_parser_prompt(message, analyzed_repos, last_context)
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=message),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.1,  # 낮은 temperature로 일관성 확보
        )
        
        response = client.chat(request, timeout=15)
        raw_content = response.content.strip()
        
        # JSON 추출 (코드 블록 안에 있을 수 있음)
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
            raw_content = raw_content.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(raw_content)
        
        # 필드 검증 및 기본값 설정
        intent = parsed.get("intent", "chat")
        if intent not in ["diagnose", "compare", "explain", "onboard", "chat", "help"]:
            intent = "chat"
        
        return ParsedChatIntent(
            intent=intent,
            repo_hint=parsed.get("repo_hint"),
            target_metric=parsed.get("target_metric"),
            options=parsed.get("options", {}),
            follow_up=parsed.get("follow_up", False),
            confidence=float(parsed.get("confidence", 0.7)),
        )
        
    except json.JSONDecodeError as e:
        logger.warning(f"LLM parser JSON decode error: {e}")
        return None
    except Exception as e:
        logger.warning(f"LLM parser failed: {e}")
        return None


def resolve_repo(
    repo_hint: Optional[str],
    analyzed_repos: List[str],
    message: str,
) -> Optional[str]:
    """
    repo_hint와 메시지를 기반으로 캐시에서 실제 레포를 찾음.
    
    하이브리드 매칭:
    1. LLM이 준 repo_hint 기준으로 먼저 매칭 시도
    2. 실패하면 기존 regex 패턴으로 전체 message 기반 매칭
    3. 그래도 없으면 None
    
    Args:
        repo_hint: LLM에서 추출한 레포 힌트 (None 가능)
        analyzed_repos: 분석 완료된 레포 목록 (예: ["facebook/react", "microsoft/vscode"])
        message: 원본 사용자 메시지
    
    Returns:
        매칭된 레포 ID (예: "facebook/react") 또는 None
    """
    if not analyzed_repos:
        return None
    
    # 1. repo_hint가 있으면 우선 매칭
    if repo_hint:
        matched = _match_by_hint(repo_hint, analyzed_repos)
        if matched:
            logger.info(f"Resolved repo from hint '{repo_hint}' -> '{matched}'")
            return matched
    
    # 2. 메시지에서 직접 레포 이름 추출 시도
    matched = _match_from_message(message, analyzed_repos)
    if matched:
        logger.info(f"Resolved repo from message -> '{matched}'")
        return matched
    
    return None


def _match_by_hint(hint: str, repos: List[str]) -> Optional[str]:
    """repo_hint를 기반으로 캐시에서 레포 찾기."""
    hint_lower = hint.lower().strip()
    
    # 정확히 일치
    for repo in repos:
        if hint_lower == repo.lower():
            return repo
    
    # 레포 이름만 일치 (owner 무시)
    for repo in repos:
        parts = repo.split("/")
        if len(parts) >= 2:
            repo_name = parts[-1].lower()
            if hint_lower == repo_name:
                return repo
    
    # 부분 일치 (hint가 repo 이름에 포함)
    for repo in repos:
        if hint_lower in repo.lower():
            return repo
    
    # 레포 이름이 hint에 포함
    for repo in repos:
        parts = repo.split("/")
        if len(parts) >= 2:
            repo_name = parts[-1].lower()
            if repo_name in hint_lower:
                return repo
    
    return None


def _match_from_message(message: str, repos: List[str]) -> Optional[str]:
    """메시지에서 레포 이름을 직접 찾기."""
    import re
    
    msg_lower = message.lower()
    
    # GitHub URL 패턴
    url_match = re.search(r"github\.com/([^/]+)/([^/\s]+)", message)
    if url_match:
        owner, repo = url_match.group(1), url_match.group(2).rstrip("/")
        full_id = f"{owner}/{repo}"
        for cached_repo in repos:
            if cached_repo.lower() == full_id.lower():
                return cached_repo
    
    # 레포 이름이 메시지에 직접 언급됨
    for repo in repos:
        parts = repo.split("/")
        if len(parts) >= 2:
            repo_name = parts[-1].lower()
            # 단어 경계로 찾기
            if re.search(rf"\b{re.escape(repo_name)}\b", msg_lower):
                return repo
    
    return None


def get_analyzed_repos() -> List[str]:
    """현재 캐시에 있는 분석 완료된 레포 목록 반환."""
    try:
        from backend.common.cache import analysis_cache
        
        if hasattr(analysis_cache, '_analyses'):
            # 캐시 키에서 레포 ID 추출 (예: "owner/repo@branch" -> "owner/repo")
            repos = []
            for key in analysis_cache._analyses.keys():
                # "owner/repo@branch" 형식에서 "owner/repo" 추출
                repo_id = key.split("@")[0] if "@" in key else key
                if repo_id and repo_id not in repos:
                    repos.append(repo_id)
            return repos
        return []
    except Exception as e:
        logger.warning(f"Failed to get analyzed repos: {e}")
        return []
