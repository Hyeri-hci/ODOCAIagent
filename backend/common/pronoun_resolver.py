"""
대명사 및 지시어 해결 유틸리티
"그거", "더 자세히", "다시 만들어줘" 등의 표현을 세션 컨텍스트 기반으로 해결
"""

import re
from typing import Dict, Any, Optional, List
from backend.common.session import ConversationTurn, AccumulatedContext
import logging

logger = logging.getLogger(__name__)


class PronounResolver:
    """대명사/지시어 해결기"""
    
    # 패턴 정의
    PRONOUN_PATTERNS = [
        (r"(그거|이거|그\s*결과|이\s*결과)", "direct_reference"),
        (r"(더|좀\s*더)\s*(자세히|상세하게|구체적으로)", "add_detail"),
        (r"(다시|새로)\s*(만들어|생성해|작성해)", "regenerate"),
        (r"(바꿔|변경해|수정해)", "modify"),
        (r"(요약해|간단하게)", "summarize"),
        (r"(처음|맨\s*처음|첫\s*번째)", "first_reference"),
        (r"(아까|방금|직전)", "previous_reference")
    ]
    
    @staticmethod
    def resolve(
        user_message: str,
        conversation_history: List[ConversationTurn],
        accumulated_context: AccumulatedContext
    ) -> Dict[str, Any]:
        """
        대명사/지시어 해결
        
        Returns:
            {
                "resolved": True/False,
                "pattern": "direct_reference" | "add_detail" | etc.,
                "refers_to": "diagnosis_result" | "onboarding_plan" | None,
                "action": "view" | "refine" | "regenerate" | "summarize",
                "context_needed": {...},
                "confidence": 0.0 ~ 1.0
            }
        """
        
        # 패턴 매칭
        matched_pattern = None
        for pattern, pattern_type in PronounResolver.PRONOUN_PATTERNS:
            if re.search(pattern, user_message):
                matched_pattern = pattern_type
                break
        
        if not matched_pattern:
            return {
                "resolved": False,
                "pattern": None,
                "refers_to": None,
                "action": None,
                "context_needed": None,
                "confidence": 0.0
            }
        
        # 직전 턴 참조
        last_turn = conversation_history[-1] if conversation_history else None
        last_topic = accumulated_context.get("last_topic")
        last_data_key = accumulated_context.get("last_generated_data")
        
        result = {
            "resolved": True,
            "pattern": matched_pattern,
            "refers_to": None,
            "action": None,
            "context_needed": None,
            "confidence": 0.0
        }
        
        # 패턴별 처리
        if matched_pattern == "direct_reference":
            # "그거", "그 결과"
            if last_data_key and last_data_key in accumulated_context:
                result["refers_to"] = last_data_key
                result["action"] = "view"
                result["context_needed"] = accumulated_context.get(last_data_key)
                result["confidence"] = 0.9
                logger.debug(f"Resolved pronoun to: {last_data_key}")
            else:
                result["confidence"] = 0.3
        
        elif matched_pattern == "add_detail":
            # "더 자세히"
            if last_data_key and last_data_key in accumulated_context:
                result["refers_to"] = last_data_key
                result["action"] = "refine"
                result["refinement_type"] = "add_detail"
                result["context_needed"] = accumulated_context.get(last_data_key)
                result["confidence"] = 0.85
                logger.debug(f"Resolved 'add detail' to: {last_data_key}")
            else:
                result["confidence"] = 0.4
        
        elif matched_pattern == "regenerate":
            # "다시 만들어줘"
            if last_data_key and last_data_key in accumulated_context:
                result["refers_to"] = last_data_key
                result["action"] = "regenerate"
                result["context_needed"] = accumulated_context.get(last_data_key)
                result["confidence"] = 0.8
                logger.debug(f"Resolved 'regenerate' to: {last_data_key}")
            else:
                result["confidence"] = 0.3
        
        elif matched_pattern == "modify":
            # "수정해줘"
            if last_data_key and last_data_key in accumulated_context:
                result["refers_to"] = last_data_key
                result["action"] = "modify"
                result["context_needed"] = accumulated_context.get(last_data_key)
                result["confidence"] = 0.75
                logger.debug(f"Resolved 'modify' to: {last_data_key}")
            else:
                result["confidence"] = 0.3
        
        elif matched_pattern == "summarize":
            # "요약해줘"
            if last_data_key and last_data_key in accumulated_context:
                result["refers_to"] = last_data_key
                result["action"] = "summarize"
                result["context_needed"] = accumulated_context.get(last_data_key)
                result["confidence"] = 0.8
                logger.debug(f"Resolved 'summarize' to: {last_data_key}")
            else:
                result["confidence"] = 0.4
        
        elif matched_pattern == "first_reference":
            # "처음 것"
            if conversation_history:
                first_turn = conversation_history[0]
                first_data = first_turn.get("data_generated", [])
                if first_data:
                    first_key = first_data[0]
                    result["refers_to"] = first_key
                    result["action"] = "view"
                    result["context_needed"] = accumulated_context.get(first_key)
                    result["confidence"] = 0.7
                    logger.debug(f"Resolved to first turn: {first_key}")
        
        elif matched_pattern == "previous_reference":
            # "아까", "방금"
            if last_data_key and last_data_key in accumulated_context:
                result["refers_to"] = last_data_key
                result["action"] = "view"
                result["context_needed"] = accumulated_context.get(last_data_key)
                result["confidence"] = 0.85
                logger.debug(f"Resolved 'previous' to: {last_data_key}")
        
        return result
    
    @staticmethod
    def detect_implicit_context(
        user_message: str,
        accumulated_context: AccumulatedContext
    ) -> Dict[str, Any]:
        """
        암묵적 컨텍스트 감지
        예: "온보딩 가이드" (owner/repo는 세션에서)
        """
        
        # 명시적 owner/repo가 없는지 체크
        has_explicit_repo = bool(re.search(r"[\w-]+/[\w-]+", user_message))
        
        if has_explicit_repo:
            return {"implicit": False}
        
        # 온보딩, 진단 등의 키워드가 있는지
        keywords = {
            "온보딩": "onboarding",
            "가이드": "onboarding",
            "진단": "diagnosis",
            "분석": "diagnosis",
            "보안": "security",
            "취약점": "security",
            "비슷한": "recommendation",
        }
        
        detected_intent = None
        for keyword, intent in keywords.items():
            if keyword in user_message:
                detected_intent = intent
                break
        
        if detected_intent:
            return {
                "implicit": True,
                "detected_intent": detected_intent,
                "reason": "owner/repo not explicitly mentioned, assuming from session"
            }
        
        return {"implicit": False}


def resolve_pronoun(
    user_message: str,
    conversation_history: List[ConversationTurn],
    accumulated_context: AccumulatedContext
) -> Dict[str, Any]:
    """편의 함수"""
    return PronounResolver.resolve(user_message, conversation_history, accumulated_context)


def detect_implicit_context(
    user_message: str,
    accumulated_context: AccumulatedContext
) -> Dict[str, Any]:
    """편의 함수"""
    return PronounResolver.detect_implicit_context(user_message, accumulated_context)
