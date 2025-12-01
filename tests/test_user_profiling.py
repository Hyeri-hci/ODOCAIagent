"""User Profiling 기능 단위 테스트."""
import pytest
from typing import cast
from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.profile_updater import update_profile_node
from backend.agents.supervisor.nodes.summarize_node import _build_persona_instruction


class TestProfileUpdater:
    """프로필 업데이트 노드 테스트."""
    
    def test_detect_beginner_level(self):
        """초보자 키워드 감지 테스트."""
        state = cast(SupervisorState, {"user_query": "나 React 배우기 시작한 초보 개발자야"})
        result = update_profile_node(state)
        
        assert result["user_profile"]["level"] == "beginner"
        assert "react" in result["user_profile"]["interests"]
    
    def test_detect_advanced_level(self):
        """고급 사용자 키워드 감지 테스트."""
        state = cast(SupervisorState, {"user_query": "실무에서 사용할 고급 분석이 필요해"})
        result = update_profile_node(state)
        
        assert result["user_profile"]["level"] == "advanced"
    
    def test_accumulate_interests(self):
        """관심사 누적 테스트."""
        state = cast(SupervisorState, {
            "user_query": "python과 security에 관심있어",
            "user_profile": {"interests": ["react"]},
        })
        result = update_profile_node(state)
        
        interests = result["user_profile"]["interests"]
        assert "python" in interests
        assert "security" in interests
        assert "react" in interests  # 기존 값 유지
    
    def test_detect_simple_persona(self):
        """간결한 답변 스타일 감지 테스트."""
        state = cast(SupervisorState, {"user_query": "간단하게 요약해줘"})
        result = update_profile_node(state)
        
        assert result["user_profile"]["persona"] == "simple"
    
    def test_detect_detailed_persona(self):
        """상세한 답변 스타일 감지 테스트."""
        state = cast(SupervisorState, {"user_query": "자세히 코드와 함께 설명해줘"})
        result = update_profile_node(state)
        
        assert result["user_profile"]["persona"] == "detailed"
    
    def test_preserve_existing_profile(self):
        """기존 프로필 유지 테스트."""
        state = cast(SupervisorState, {
            "user_query": "이 레포 분석해줘",  # 레벨 키워드 없음
            "user_profile": {"level": "beginner", "persona": "simple"},
        })
        result = update_profile_node(state)
        
        # 기존 값 유지
        assert result["user_profile"]["level"] == "beginner"
        assert result["user_profile"]["persona"] == "simple"


class TestPersonaInstruction:
    """페르소나 프롬프트 생성 테스트."""
    
    def test_empty_profile(self):
        """빈 프로필은 빈 문자열 반환."""
        assert _build_persona_instruction(None) == ""
        assert _build_persona_instruction({}) == ""
    
    def test_beginner_instruction(self):
        """초보자 프로필 지시문 생성."""
        profile = {"level": "beginner"}
        result = _build_persona_instruction(profile)
        
        assert "초보자" in result
        assert "쉽게 설명" in result
    
    def test_advanced_instruction(self):
        """전문가 프로필 지시문 생성."""
        profile = {"level": "advanced"}
        result = _build_persona_instruction(profile)
        
        assert "전문가" in result
        assert "기술적인 깊이" in result
    
    def test_interests_instruction(self):
        """관심사 기반 지시문 생성."""
        profile = {"interests": ["react", "typescript"]}
        result = _build_persona_instruction(profile)
        
        assert "react" in result
        assert "typescript" in result
        assert "관심사" in result
    
    def test_simple_persona_instruction(self):
        """간결 스타일 지시문 생성."""
        profile = {"persona": "simple"}
        result = _build_persona_instruction(profile)
        
        assert "간결한" in result
        assert "핵심만" in result
    
    def test_combined_profile(self):
        """복합 프로필 지시문 생성."""
        profile = {
            "level": "beginner",
            "interests": ["python", "security"],
            "persona": "detailed",
        }
        result = _build_persona_instruction(profile)
        
        assert "초보자" in result
        assert "python" in result
        assert "상세한" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
