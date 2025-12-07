"""
Chat 서비스 테스트.

ChatService 클래스의 단위 테스트 및 통합 테스트.
"""
import pytest
import os
from unittest.mock import patch, MagicMock

# 테스트 환경 설정
os.environ.setdefault("GITHUB_TOKEN", "test_token")


class TestChatServiceModels:
    """ChatService 모델 테스트."""
    
    def test_chat_message_defaults(self):
        """ChatMessage 기본값 테스트."""
        from backend.api.chat_service import ChatMessage
        
        msg = ChatMessage(content="안녕하세요")
        assert msg.role == "user"
        assert msg.content == "안녕하세요"
    
    def test_chat_service_request(self):
        """ChatServiceRequest 테스트."""
        from backend.api.chat_service import ChatServiceRequest, ChatMessage
        
        request = ChatServiceRequest(
            message="테스트 메시지",
            repo_url="https://github.com/test/repo",
            analysis_context={"health_score": 75},
            conversation_history=[
                ChatMessage(role="user", content="이전 질문"),
                ChatMessage(role="assistant", content="이전 답변"),
            ]
        )
        
        assert request.message == "테스트 메시지"
        assert request.repo_url == "https://github.com/test/repo"
        assert request.analysis_context["health_score"] == 75
        assert len(request.conversation_history) == 2
    
    def test_chat_service_response(self):
        """ChatServiceResponse 테스트."""
        from backend.api.chat_service import ChatServiceResponse
        
        response = ChatServiceResponse(
            ok=True,
            message="응답 메시지",
            error=None,
            is_fallback=False
        )
        
        assert response.ok is True
        assert response.message == "응답 메시지"
        assert response.error is None
        assert response.is_fallback is False


class TestChatServiceBuildSystemPrompt:
    """시스템 프롬프트 빌드 테스트."""
    
    def test_basic_prompt(self):
        """기본 프롬프트 생성."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        prompt = service.build_system_prompt(None, None)
        
        assert "ODOC AI Agent" in prompt
        assert "한글" in prompt
    
    def test_prompt_with_repo_url(self):
        """저장소 URL 포함 프롬프트."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        prompt = service.build_system_prompt("https://github.com/test/repo", None)
        
        assert "https://github.com/test/repo" in prompt
    
    def test_prompt_with_context(self):
        """분석 컨텍스트 포함 프롬프트."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        context = {
            "health_score": 85,
            "documentation_quality": 90,
            "activity_maintainability": 75,
            "stars": 1500,
            "forks": 200,
        }
        prompt = service.build_system_prompt(None, context)
        
        assert "85점" in prompt
        assert "90점" in prompt
        assert "75점" in prompt
        assert "1,500" in prompt  # 천 단위 구분
        assert "200" in prompt


class TestChatServiceFallback:
    """Fallback 응답 테스트."""
    
    def test_fallback_contribution(self):
        """기여 관련 fallback 응답."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        response = service.generate_fallback_response("어떻게 기여하나요?", None)
        
        assert "Fork" in response
        assert "Clone" in response
        assert "Pull Request" in response
    
    def test_fallback_security(self):
        """보안 관련 fallback 응답."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        response = service.generate_fallback_response("보안 취약점이 있나요?", None)
        
        assert "의존성" in response or "보안" in response
    
    def test_fallback_documentation(self):
        """문서 관련 fallback 응답."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        response = service.generate_fallback_response("README를 어떻게 작성하나요?", None)
        
        # README 또는 문서 관련 키워드 확인
        assert "README" in response or "프로젝트" in response or "문서" in response
    
    def test_fallback_score_with_context(self):
        """점수 관련 fallback 응답 (컨텍스트 포함)."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        context = {"health_score": 85}
        response = service.generate_fallback_response("점수가 무슨 의미인가요?", context)
        
        assert "85점" in response
        assert "상위" in response  # 높은 점수이므로
    
    def test_fallback_default(self):
        """기본 fallback 응답."""
        from backend.api.chat_service import ChatService
        
        service = ChatService()
        response = service.generate_fallback_response("랜덤한 질문입니다", None)
        
        assert "기여 방법" in response
        assert "문서화" in response


class TestChatServiceWithMock:
    """LLM 모킹 테스트."""
    
    def test_chat_success_with_mock_llm(self):
        """LLM 성공 응답 모킹."""
        from backend.api.chat_service import ChatService, ChatServiceRequest
        
        # Mock LLM 클라이언트
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "LLM 테스트 응답입니다."
        mock_client.chat.return_value = mock_response
        
        service = ChatService(llm_client=mock_client, model_name="test-model")
        
        request = ChatServiceRequest(message="테스트 질문")
        response = service.chat(request)
        
        assert response.ok is True
        assert response.message == "LLM 테스트 응답입니다."
        assert response.is_fallback is False
        mock_client.chat.assert_called_once()
    
    def test_chat_fallback_on_llm_error(self):
        """LLM 실패 시 fallback 응답."""
        from backend.api.chat_service import ChatService, ChatServiceRequest
        
        # Mock LLM 클라이언트 (예외 발생)
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("LLM timeout")
        
        service = ChatService(llm_client=mock_client, model_name="test-model")
        
        request = ChatServiceRequest(message="어떻게 기여하나요?")
        response = service.chat(request)
        
        assert response.ok is True
        assert response.is_fallback is True
        assert "Fork" in response.message  # 기여 관련 fallback


class TestChatServiceIntegration:
    """통합 테스트 (실제 LLM 호출)."""
    
    @pytest.mark.skipif(
        not os.environ.get("KANANA_API_KEY"),
        reason="KANANA_API_KEY not set"
    )
    def test_real_llm_chat(self):
        """실제 LLM 호출 테스트."""
        from backend.api.chat_service import ChatService, ChatServiceRequest
        
        service = ChatService()
        
        request = ChatServiceRequest(
            message="오픈소스 프로젝트에 처음 기여하려면 어떻게 해야 하나요? 간단히 설명해주세요.",
            repo_url=None,
            analysis_context=None
        )
        
        response = service.chat(request, timeout=30)
        
        print(f"응답: {response.message[:200]}...")
        
        assert response.ok is True
        assert len(response.message) > 50  # 충분한 길이의 응답


class TestGetChatService:
    """get_chat_service 함수 테스트."""
    
    def test_singleton_pattern(self):
        """싱글톤 패턴 확인."""
        from backend.api.chat_service import get_chat_service
        
        service1 = get_chat_service()
        service2 = get_chat_service()
        
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
