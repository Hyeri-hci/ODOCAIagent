"""
Supervisor Intent Parser V2
최상위 의도 파싱 - 어느 agent로 라우팅할지, 명확화가 필요한지 결정
세션 기반 대화 지원
"""

from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class SupervisorIntentV2(BaseModel):
    """Supervisor 수준 의도 (세션 기반)"""
    
    task_type: Literal[
        "diagnosis",      # 진단 관련
        "onboarding",     # 온보딩 관련
        "security",       # 보안 관련
        "general_chat",   # 일반 대화
        "clarification"   # 명확화 필요
    ]
    
    target_agent: Literal["diagnosis", "onboarding", "security", "chat", "none"]
    
    # Agentic 기능
    needs_clarification: bool = Field(
        default=False,
        description="명확화 필요 여부"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="되물을 질문들"
    )
    
    # 세션 컨텍스트 활용
    uses_previous_context: bool = Field(
        default=False,
        description="이전 컨텍스트 활용 여부"
    )
    referenced_data: List[str] = Field(
        default_factory=list,
        description="참조할 데이터 키들 (예: ['diagnosis_result'])"
    )
    
    # 디버깅
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="의도 파악 신뢰도"
    )
    reasoning: str = Field(
        default="",
        description="의도 파악 근거"
    )
    
    # 추가 메타데이터
    detected_repo: Optional[str] = Field(
        default=None,
        description="메시지에서 감지된 저장소 (owner/repo)"
    )
    implicit_context: bool = Field(
        default=False,
        description="암묵적 컨텍스트 사용 여부"
    )


class SupervisorIntentParserV2:
    """Supervisor 의도 파싱기 V2 (세션 지원)"""
    
    def __init__(self):
        from backend.llm.factory import fetch_llm_client
        self.llm = fetch_llm_client()
        logger.info("SupervisorIntentParserV2 initialized")
    
    async def parse(
        self,
        user_message: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> SupervisorIntentV2:
        """
        사용자 메시지를 Supervisor 의도로 파싱
        
        Args:
            user_message: 사용자 메시지
            session_context: 세션 컨텍스트 (있으면)
                {
                    "owner": "facebook",
                    "repo": "react",
                    "conversation_history": [...],
                    "accumulated_context": {...}
                }
        """
        
        # 컨텍스트 요약
        context_summary = self._summarize_context(session_context) if session_context else "없음"
        
        prompt = f"""당신은 GitHub 저장소 분석 시스템의 의도 파악 전문가입니다.

=== 사용자 메시지 ===
{user_message}

=== 세션 컨텍스트 ===
{context_summary}

=== 지시사항 ===
사용자의 의도를 파악하여 다음 JSON 형식으로 반환하세요:

{{
    "task_type": "diagnosis" | "onboarding" | "security" | "general_chat" | "clarification",
    "target_agent": "diagnosis" | "onboarding" | "security" | "chat" | "none",
    "needs_clarification": true | false,
    "clarification_questions": ["질문1", "질문2"],
    "uses_previous_context": true | false,
    "referenced_data": ["diagnosis_result", "onboarding_plan"],
    "confidence": 0.0 ~ 1.0,
    "reasoning": "의도 파악 근거",
    "detected_repo": "owner/repo" | null,
    "implicit_context": true | false
}}

=== 판단 기준 ===

1. task_type 결정:
   - "분석", "진단", "건강도", "점수" → diagnosis
   - "온보딩", "가이드", "기여", "시작" → onboarding
   - "보안", "취약점", "CVE" → security
   - "비교해줘", "알려줘", "설명해줘" → general_chat
   - 정보가 부족하면 → clarification

2. needs_clarification:
   - 저장소가 명시되지 않고 세션에도 없으면 → true
   - 요청이 모호하면 → true
   - 예: "분석해줘" (어떤 저장소?)
   - ⚠️ 단, 대명사가 감지되고 컨텍스트에 데이터가 있으면 → false

3. uses_previous_context:
   - "그거", "더 자세히", "다시", "아까" 등 → true
   - 세션에 이미 데이터가 있고 참조 가능 → true
   - ⚠️ 대명사 감지 시 referenced_data에 해당 데이터 명시

4. implicit_context:
   - owner/repo가 명시되지 않았지만 세션에서 추론 가능 → true

5. confidence:
   - 명확한 요청 (저장소 명시, 구체적 동작) → 0.9+
   - 대명사 참조가 명확한 경우 → 0.8+
   - 일반적 요청 → 0.7~0.8
   - 모호한 요청 → 0.5 이하

=== 대명사 처리 예시 ===

입력: "그거 초보자 관점에서 다시 설명해줘"
컨텍스트: diagnosis_result 있음
→ {{"task_type": "diagnosis", "target_agent": "diagnosis", "uses_previous_context": true, "referenced_data": ["diagnosis_result"]}}

입력: "더 자세히 알려줘"
컨텍스트: 이전에 onboarding_plan 생성
→ {{"task_type": "onboarding", "target_agent": "onboarding", "uses_previous_context": true}}
"""

        try:
            from backend.llm.base import ChatRequest, ChatMessage
            
            request = ChatRequest(
                messages=[ChatMessage(role="user", content=prompt)]
            )
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.llm.chat, request)
            intent_data = json.loads(response.content)
            intent = SupervisorIntentV2(**intent_data)
            
            logger.info(
                f"Parsed intent: task_type={intent.task_type}, "
                f"target_agent={intent.target_agent}, "
                f"confidence={intent.confidence}"
            )
            
            return intent
            
        except Exception as e:
            logger.error(f"Failed to parse intent: {e}")
            # Fallback: 기본 의도 반환
            return SupervisorIntentV2(
                task_type="clarification",
                target_agent="none",
                needs_clarification=True,
                clarification_questions=["무엇을 도와드릴까요?"],
                confidence=0.0,
                reasoning=f"파싱 실패: {str(e)}"
            )
    
    def _summarize_context(self, session_context: Dict[str, Any]) -> str:
        """세션 컨텍스트 요약"""
        summary_parts = []
        
        # 저장소 정보
        if "owner" in session_context and "repo" in session_context:
            summary_parts.append(
                f"Repository: {session_context['owner']}/{session_context['repo']}"
            )
        
        # 대명사 해결 정보
        if session_context.get("pronoun_detected"):
            accumulated = session_context.get("accumulated_context", {})
            pronoun_ref = accumulated.get("last_pronoun_reference", {})
            if pronoun_ref.get("resolved"):
                summary_parts.append(
                    f"⚠️ 대명사 감지: '{pronoun_ref.get('pattern')}' → 참조: {pronoun_ref.get('refers_to')}"
                )
        
        # 대화 히스토리
        history = session_context.get("conversation_history", [])
        if history:
            recent = history[-3:]  # 최근 3턴
            summary_parts.append(f"Recent turns: {len(recent)}")
            for turn in recent:
                msg = turn.get('user_message', '')
                agent_resp = turn.get('agent_response', '')
                summary_parts.append(
                    f"  Turn {turn.get('turn', '?')}: User: {msg[:40]}... → Agent: {agent_resp[:40]}..."
                )
        
        # 누적 컨텍스트
        accumulated = session_context.get("accumulated_context", {})
        available_data = []
        if accumulated.get("diagnosis_result"):
            available_data.append("diagnosis_result")
        if accumulated.get("onboarding_plan"):
            available_data.append("onboarding_plan")
        if accumulated.get("security_scan"):
            available_data.append("security_scan")
        
        if available_data:
            summary_parts.append(f"✅ Available data: {', '.join(available_data)}")
        
        # 마지막 주제
        last_topic = accumulated.get("last_topic")
        if last_topic:
            summary_parts.append(f"Last topic: {last_topic}")
        
        return "\n".join(summary_parts) if summary_parts else "없음"
