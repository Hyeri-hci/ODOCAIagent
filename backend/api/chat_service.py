"""
Chat 서비스 - LLM 기반 대화 처리.

http_router.py에서 분리된 채팅 로직을 담당합니다.
"""
import logging
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """채팅 메시지."""
    role: str = "user"
    content: str


class ChatServiceRequest(BaseModel):
    """채팅 서비스 요청."""
    message: str
    repo_url: Optional[str] = None
    analysis_context: Optional[Dict[str, Any]] = None
    conversation_history: List[ChatMessage] = Field(default_factory=list)


class ChatServiceResponse(BaseModel):
    """채팅 서비스 응답."""
    ok: bool
    message: str
    error: Optional[str] = None
    is_fallback: bool = False


class ChatService:
    """LLM 기반 채팅 서비스."""
    
    def __init__(self, llm_client=None, model_name: str = None):
        """
        Args:
            llm_client: LLM 클라이언트 (None이면 자동 생성)
            model_name: 사용할 모델 이름
        """
        self._llm_client = llm_client
        self._model_name = model_name
    
    @property
    def llm_client(self):
        """LLM 클라이언트 지연 로딩."""
        if self._llm_client is None:
            from backend.llm.factory import fetch_llm_client
            self._llm_client = fetch_llm_client()
        return self._llm_client
    
    @property
    def model_name(self) -> str:
        """모델 이름."""
        if self._model_name is None:
            from backend.common.config import LLM_MODEL_NAME
            self._model_name = LLM_MODEL_NAME
        return self._model_name
    
    def chat(self, request: ChatServiceRequest, timeout: int = 60) -> ChatServiceResponse:
        """
        LLM과 대화.
        
        Args:
            request: 채팅 요청
            timeout: LLM 호출 타임아웃 (초)
        
        Returns:
            채팅 응답 (성공 시 LLM 응답, 실패 시 fallback 응답)
        """
        try:
            from backend.llm.base import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage
            
            # 시스템 프롬프트 구성
            system_prompt = self.build_system_prompt(request.repo_url, request.analysis_context)
            
            # 대화 메시지 구성
            messages = [LLMChatMessage(role="system", content=system_prompt)]
            
            # 이전 대화 기록 추가
            for msg in request.conversation_history:
                messages.append(LLMChatMessage(role=msg.role, content=msg.content))
            
            # 현재 사용자 메시지 추가
            messages.append(LLMChatMessage(role="user", content=request.message))
            
            # LLM 호출
            llm_request = LLMChatRequest(
                messages=messages,
                model=self.model_name,
                temperature=0.7,
            )
            
            response = self.llm_client.chat(llm_request, timeout=timeout)
            
            return ChatServiceResponse(
                ok=True,
                message=response.content,
                is_fallback=False,
            )
            
        except Exception as e:
            logger.exception(f"Chat failed: {e}")
            # Fallback 응답
            fallback = self.generate_fallback_response(request.message, request.analysis_context)
            return ChatServiceResponse(
                ok=True,
                message=fallback,
                error=f"LLM 호출 실패, 기본 응답 사용: {str(e)}",
                is_fallback=True,
            )
    
    def build_system_prompt(self, repo_url: Optional[str], analysis_context: Optional[Dict]) -> str:
        """
        채팅용 시스템 프롬프트 구성.
        
        Args:
            repo_url: 분석 중인 저장소 URL
            analysis_context: 분석 결과 컨텍스트
        
        Returns:
            시스템 프롬프트 문자열
        """
        base_prompt = (
            "당신은 ODOC AI Agent입니다. 오픈소스 프로젝트 분석 및 기여 가이드 전문가입니다.\n"
            "사용자가 오픈소스 프로젝트에 대해 질문하면 친절하고 전문적으로 답변해주세요.\n"
            "답변은 항상 한글로 작성하고, 구체적이고 실행 가능한 조언을 제공하세요.\n"
        )
        
        if repo_url:
            base_prompt += f"\n현재 분석 중인 저장소: {repo_url}\n"
        
        if analysis_context:
            context_parts = []
            if "health_score" in analysis_context:
                context_parts.append(f"- 건강 점수: {analysis_context['health_score']}점")
            if "documentation_quality" in analysis_context:
                context_parts.append(f"- 문서 품질: {analysis_context['documentation_quality']}점")
            if "activity_maintainability" in analysis_context:
                context_parts.append(f"- 활동성: {analysis_context['activity_maintainability']}점")
            if "stars" in analysis_context:
                context_parts.append(f"- Stars: {analysis_context['stars']:,}")
            if "forks" in analysis_context:
                context_parts.append(f"- Forks: {analysis_context['forks']:,}")
            
            if context_parts:
                base_prompt += "\n분석 결과 요약:\n" + "\n".join(context_parts) + "\n"
        
        base_prompt += (
            "\n답변 시 다음 가이드라인을 따르세요:\n"
            "1. 질문에 직접적으로 답변하세요.\n"
            "2. 필요시 단계별 가이드를 제공하세요.\n"
            "3. 코드 예시가 필요하면 마크다운 코드 블록을 사용하세요.\n"
            "4. 불확실한 내용은 솔직하게 말하세요.\n"
            "5. 절대로 URL이나 링크를 생성하지 마세요. 실제로 존재하지 않는 페이지를 안내하면 안됩니다.\n"
            "6. CONTRIBUTING.md 등 기여 가이드가 있는지 확실하지 않으면 '기여 가이드가 있다면 확인하세요' 정도로 안내하세요.\n"
            "7. 특정 파일명(예: contribute.md, setup.py 등)을 직접 언급하지 마세요. 대신 'README 파일', '설정 파일', '기여 가이드 문서' 등 일반적인 용어를 사용하세요.\n"
            "8. 프로젝트 구조나 파일이 어디에 있는지 확실하지 않으면 '저장소를 확인해보세요' 정도로 안내하세요.\n"
        )
        
        return base_prompt
    
    def generate_fallback_response(self, message: str, context: Optional[Dict]) -> str:
        """
        LLM 실패 시 키워드 기반 fallback 응답.
        
        Args:
            message: 사용자 메시지
            context: 분석 컨텍스트
        
        Returns:
            Fallback 응답 문자열
        """
        message_lower = message.lower()
        
        if "기여" in message or "contribute" in message_lower or "어떻게" in message:
            return (
                "오픈소스 기여를 시작하는 방법을 안내해드릴게요:\n\n"
                "1. **저장소 Fork**: GitHub에서 저장소를 Fork합니다\n"
                "2. **로컬 Clone**: `git clone <your-fork-url>`\n"
                "3. **브랜치 생성**: `git checkout -b feature/your-feature`\n"
                "4. **변경 사항 작업**: 코드 수정 또는 문서 개선\n"
                "5. **커밋 & 푸시**: `git commit -m '설명'` 후 `git push`\n"
                "6. **PR 생성**: GitHub에서 Pull Request를 생성합니다\n\n"
                "처음이라면 'good first issue' 라벨이 붙은 이슈부터 시작하는 것을 추천드립니다!"
            )
        
        if "보안" in message or "security" in message_lower or "취약점" in message:
            return (
                "보안 관련 조언을 드릴게요:\n\n"
                "1. **의존성 업데이트**: `npm audit fix` 또는 `pip install --upgrade`로 취약점 패치\n"
                "2. **보안 스캐닝**: GitHub Security Advisories나 Dependabot 알림 확인\n"
                "3. **민감 정보 관리**: `.env` 파일 사용, 절대 커밋하지 않기\n"
                "4. **코드 리뷰**: 보안 관점에서 PR 리뷰 수행\n\n"
                "구체적인 취약점이 있다면 해당 라이브러리의 보안 권고사항을 확인하세요."
            )
        
        if "문서" in message or "readme" in message_lower or "documentation" in message_lower:
            return (
                "좋은 문서 작성을 위한 가이드입니다:\n\n"
                "**README.md 필수 섹션:**\n"
                "1. 프로젝트 소개 (WHAT) - 무엇을 하는 프로젝트인지\n"
                "2. 사용 이유 (WHY) - 왜 이 프로젝트가 필요한지\n"
                "3. 설치 방법 (HOW) - 어떻게 시작하는지\n"
                "4. 사용 예시 - 코드 예제\n"
                "5. 기여 가이드 - CONTRIBUTING.md 링크\n\n"
                "스크린샷이나 GIF를 추가하면 이해하기 쉬워집니다!"
            )
        
        if "점수" in message or "score" in message_lower or "평가" in message:
            score_info = ""
            if context and "health_score" in context:
                score = context["health_score"]
                if score >= 80:
                    score_info = f"현재 점수 {score}점은 상위 10% 수준으로 매우 건강한 프로젝트입니다."
                elif score >= 60:
                    score_info = f"현재 점수 {score}점은 평균 수준입니다. 문서화나 활동성 개선으로 점수를 높일 수 있습니다."
                else:
                    score_info = f"현재 점수 {score}점은 개선이 필요합니다. 문서 보완과 이슈 해결에 집중하세요."
            else:
                score_info = "분석 결과를 확인해주세요."
            
            return (
                f"점수 해석을 도와드릴게요:\n\n{score_info}\n\n"
                "**점수 구성 요소:**\n"
                "- 문서 품질: README 완성도, 기여 가이드 유무\n"
                "- 활동성: 최근 커밋, PR 병합 속도, 이슈 해결률\n"
                "- 온보딩 용이성: 신규 기여자가 시작하기 쉬운 정도"
            )
        
        # 기본 응답
        return (
            "궁금한 점에 대해 답변드릴게요. 다음과 같은 주제로 질문해주시면 더 구체적인 답변을 드릴 수 있습니다:\n\n"
            "- **기여 방법**: 오픈소스에 어떻게 기여하나요?\n"
            "- **문서화**: README를 어떻게 개선하나요?\n"
            "- **보안**: 취약점은 어떻게 해결하나요?\n"
            "- **점수 해석**: 분석 점수의 의미는 무엇인가요?\n\n"
            "자유롭게 질문해주세요!"
        )


# 기본 인스턴스 (싱글톤 패턴)
_default_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """기본 ChatService 인스턴스 반환."""
    global _default_service
    if _default_service is None:
        _default_service = ChatService()
    return _default_service
