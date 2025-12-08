"""Agentic Decision Maker - LLM 기반 의사결정.

Supervisor의 핵심 의사결정을 LLM으로 수행합니다.
- 다음 행동 결정
- 실행 계획 수립
- 결과 검증 및 반성
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

# 가능한 액션 정의
ActionType = Literal[
    "run_diagnosis",      # 저장소 분석 실행
    "use_cache",          # 캐시된 결과 사용
    "respond_to_chat",    # 채팅 응답 생성
    "compare_repos",      # 여러 저장소 비교
    "fetch_issues",       # 이슈 목록 가져오기
    "plan_onboarding",    # 온보딩 계획 수립
    "end",                # 작업 완료
]


@dataclass
class AgentDecision:
    """LLM에서 생성된 에이전트 의사결정."""
    
    action: ActionType
    reasoning: str  # LLM의 추론 과정
    plan: List[str] = field(default_factory=list)  # 실행 계획 (단계별)
    context_updates: Dict[str, Any] = field(default_factory=dict)  # 상태 업데이트
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reasoning": self.reasoning,
            "plan": self.plan,
            "context_updates": self.context_updates,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


def _build_decision_prompt(
    intent: str,
    owner: str,
    repo: str,
    has_cache: bool,
    has_diagnosis: bool,
    chat_message: Optional[str],
    user_context: Dict[str, Any],
) -> str:
    """의사결정을 위한 LLM 프롬프트 생성."""
    
    context_info = f"""
[현재 상태]
- 사용자 의도: {intent}
- 대상 저장소: {owner}/{repo}
- 캐시된 분석 결과 존재: {has_cache}
- 진단 결과 완료: {has_diagnosis}
- 사용자 메시지: {chat_message or '없음'}
- 사용자 컨텍스트: {json.dumps(user_context, ensure_ascii=False)}
"""

    return f"""당신은 ODOC 시스템의 Supervisor Agent입니다.
현재 상태를 분석하고 다음 행동을 결정하세요.

{context_info}

[가능한 액션]
- run_diagnosis: 저장소 분석 실행 (캐시가 없거나 새로운 분석 필요시)
- use_cache: 캐시된 분석 결과 사용 (캐시가 있고 최신일 때)
- respond_to_chat: 사용자 질문에 답변 생성 (설명/채팅 요청시)
- compare_repos: 여러 저장소 비교 분석
- fetch_issues: 이슈 목록 조회 (온보딩 시작시)
- plan_onboarding: 기여 온보딩 계획 수립
- end: 작업 완료

[의사결정 규칙]
1. diagnose 의도 + 캐시 없음 → run_diagnosis
2. diagnose 의도 + 캐시 있음 → use_cache
3. explain/chat 의도 + 진단 완료 → respond_to_chat
4. onboard 의도 → 진단 필요시 run_diagnosis, 있으면 fetch_issues
5. compare 의도 → compare_repos

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "action": "run_diagnosis|use_cache|respond_to_chat|compare_repos|fetch_issues|plan_onboarding|end",
  "reasoning": "이 결정을 내린 이유 (한국어)",
  "plan": ["1단계", "2단계", ...],
  "warnings": ["주의사항1", ...],
  "confidence": 0.0-1.0
}}"""


def llm_make_decision(
    intent: str,
    owner: str,
    repo: str,
    has_cache: bool,
    has_diagnosis: bool,
    chat_message: Optional[str] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> Optional[AgentDecision]:
    """
    LLM을 사용하여 다음 행동을 결정.
    
    Args:
        intent: 감지된 사용자 의도
        owner: 저장소 소유자
        repo: 저장소 이름
        has_cache: 캐시된 분석 결과 존재 여부
        has_diagnosis: 진단 완료 여부
        chat_message: 사용자 채팅 메시지
        user_context: 사용자 컨텍스트
    
    Returns:
        AgentDecision 또는 실패 시 None
    """
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME
        
        client = fetch_llm_client()
        
        prompt = _build_decision_prompt(
            intent=intent,
            owner=owner,
            repo=repo,
            has_cache=has_cache,
            has_diagnosis=has_diagnosis,
            chat_message=chat_message,
            user_context=user_context or {},
        )
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content=prompt),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.2,  # 낮은 temperature로 일관성 확보
        )
        
        response = client.chat(request, timeout=15)
        raw_content = response.content.strip()
        
        # JSON 추출
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
            raw_content = raw_content.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(raw_content)
        
        # 액션 검증
        action = parsed.get("action", "end")
        valid_actions = [
            "run_diagnosis", "use_cache", "respond_to_chat",
            "compare_repos", "fetch_issues", "plan_onboarding", "end"
        ]
        if action not in valid_actions:
            action = "end"
        
        return AgentDecision(
            action=action,
            reasoning=parsed.get("reasoning", "LLM 응답에서 추론 과정 없음"),
            plan=parsed.get("plan", []),
            warnings=parsed.get("warnings", []),
            confidence=float(parsed.get("confidence", 0.7)),
        )
        
    except json.JSONDecodeError as e:
        logger.warning(f"LLM decision JSON decode error: {e}")
        return None
    except Exception as e:
        logger.warning(f"LLM decision failed: {e}")
        return None


# 액션 → 노드 매핑
ACTION_TO_NODE = {
    "run_diagnosis": "run_diagnosis_node",
    "use_cache": "use_cached_result_node",
    "respond_to_chat": "chat_response_node",
    "compare_repos": "batch_diagnosis_node",
    "fetch_issues": "fetch_issues_node",
    "plan_onboarding": "plan_onboarding_node",
    "end": "__end__",
}


def get_node_from_action(action: str) -> str:
    """액션을 노드 이름으로 변환."""
    return ACTION_TO_NODE.get(action, "__end__")
