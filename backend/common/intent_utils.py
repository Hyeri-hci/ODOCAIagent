"""
Intent Parser 공통 유틸리티
여러 Intent Parser에서 공통으로 사용하는 헬퍼 함수들
"""

from typing import Dict, Any, Optional, List
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class IntentParserBase:
    """Intent Parser 기본 클래스"""
    
    def __init__(self):
        from backend.llm.factory import fetch_llm_client
        self.llm = fetch_llm_client()
    
    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        LLM 호출 공통 로직
        
        Args:
            prompt: LLM에 전달할 프롬프트
            
        Returns:
            파싱된 JSON 응답
        """
        try:
            from backend.llm.base import ChatRequest, ChatMessage
            
            request = ChatRequest(
                messages=[ChatMessage(role="user", content=prompt)]
            )
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.llm.chat, request)
            return json.loads(response.content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


def extract_experience_level(user_message: str) -> Optional[str]:
    """
    사용자 메시지에서 경험 수준 추출
    
    Args:
        user_message: 사용자 메시지
        
    Returns:
        "beginner", "intermediate", "advanced" 또는 None
    """
    message_lower = user_message.lower()
    
    # 입문자/초보자 키워드
    beginner_keywords = [
        "입문", "초보", "초심", "beginner", "novice", "처음", "시작", 
        "입문자", "초보자", "막 시작"
    ]
    
    # 중급자 키워드
    intermediate_keywords = [
        "중급", "중간", "intermediate", "일반", "평범", "중급자",
        "어느정도", "조금", "기본"
    ]
    
    # 숙련자/고급 키워드
    advanced_keywords = [
        "숙련", "고급", "전문", "advanced", "expert", "senior", 
        "숙련자", "고급자", "전문가", "경험", "많은"
    ]
    
    # 키워드 매칭
    for keyword in beginner_keywords:
        if keyword in message_lower:
            return "beginner"
    
    for keyword in advanced_keywords:
        if keyword in message_lower:
            return "advanced"
            
    for keyword in intermediate_keywords:
        if keyword in message_lower:
            return "intermediate"
    
    return None


def summarize_session_context(session_context: Dict[str, Any]) -> str:
    """
    세션 컨텍스트 요약
    
    Args:
        session_context: 세션 컨텍스트 딕셔너리
        
    Returns:
        요약된 컨텍스트 문자열
    """
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
    
    # 최근 언급된 저장소 (멀티턴 컨텍스트)
    last_mentioned_repo = accumulated.get("last_mentioned_repo")
    if last_mentioned_repo:
        summary_parts.append(
            f"📌 Last mentioned repo: {last_mentioned_repo.get('full_name', 'unknown')}"
        )
    
    # 마지막 주제
    last_topic = accumulated.get("last_topic")
    if last_topic:
        summary_parts.append(f"Last topic: {last_topic}")
    
    return "\n".join(summary_parts) if summary_parts else "없음"


def detect_force_refresh(user_message: str) -> bool:
    """
    메시지에서 강제 새로고침 의도 감지
    
    Args:
        user_message: 사용자 메시지
        
    Returns:
        강제 새로고침 여부
    """
    keywords = ["최신", "다시", "업데이트", "refresh", "reload", "새로"]
    return any(keyword in user_message.lower() for keyword in keywords)


def detect_detail_level(user_message: str) -> str:
    """
    메시지에서 상세도 수준 감지
    
    Args:
        user_message: 사용자 메시지
        
    Returns:
        "brief", "standard", "detailed"
    """
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ["간단", "간략", "요약", "brief", "summary"]):
        return "brief"
    
    if any(word in message_lower for word in ["자세", "상세", "구체", "detailed", "thorough"]):
        return "detailed"
    
    return "standard"
