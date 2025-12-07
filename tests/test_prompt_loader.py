"""
프롬프트 로더 테스트.
"""
import pytest
import os

# 테스트 환경 설정  
os.environ.setdefault("GITHUB_TOKEN", "test_token")


class TestPromptLoader:
    """프롬프트 로더 테스트."""
    
    def test_load_diagnosis_summary(self):
        """diagnosis_summary 프롬프트 로드."""
        from backend.prompts.loader import load_prompt
        
        prompt = load_prompt("diagnosis_summary")
        
        assert prompt["name"] == "diagnosis_summary"
        assert prompt["version"] == "1.0"
        assert "system_prompt" in prompt
        assert "user_prompt_template" in prompt
        assert "parameters" in prompt
    
    def test_load_chat_system(self):
        """chat_system 프롬프트 로드."""
        from backend.prompts.loader import load_prompt
        
        prompt = load_prompt("chat_system")
        
        assert prompt["name"] == "chat_system"
        assert "system_prompt" in prompt
        assert "context_template" in prompt
        assert "guidelines" in prompt
    
    def test_get_system_prompt(self):
        """시스템 프롬프트 반환."""
        from backend.prompts.loader import get_system_prompt
        
        prompt = get_system_prompt("diagnosis_summary")
        
        assert "전문 소프트웨어 엔지니어링 컨설턴트" in prompt
        assert "마크다운" in prompt
    
    def test_get_parameters(self):
        """파라미터 반환."""
        from backend.prompts.loader import get_parameters
        
        params = get_parameters("diagnosis_summary")
        
        assert params["temperature"] == 0.2
        assert params["max_tokens"] == 1024
    
    def test_render_prompt(self):
        """프롬프트 렌더링."""
        from backend.prompts.loader import render_prompt
        
        rendered = render_prompt(
            "diagnosis_summary",
            "user_prompt_template",
            repo_id="test/repo",
            health_score=85,
            health_level="good",
            documentation_quality=90,
            activity_maintainability=75,
            onboarding_score=60,
            onboarding_level="basic",
            docs_issues="없음",
            activity_issues="없음",
        )
        
        assert "test/repo" in rendered
        assert "85점" in rendered or "85" in rendered
        assert "good" in rendered
    
    def test_list_prompts(self):
        """프롬프트 목록 반환."""
        from backend.prompts.loader import list_prompts
        
        prompts = list_prompts()
        
        assert "diagnosis_summary" in prompts
        assert "chat_system" in prompts
    
    def test_cache(self):
        """캐시 동작 확인."""
        from backend.prompts.loader import load_prompt, clear_cache
        
        clear_cache()
        
        # 첫 로드
        prompt1 = load_prompt("diagnosis_summary")
        # 캐시에서 로드
        prompt2 = load_prompt("diagnosis_summary")
        
        assert prompt1 is prompt2
        
        clear_cache()
    
    def test_file_not_found(self):
        """존재하지 않는 파일 에러."""
        from backend.prompts.loader import load_prompt
        
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt")


class TestPromptPackage:
    """prompts 패키지 테스트."""
    
    def test_package_import(self):
        """패키지 임포트."""
        from backend.prompts import load_prompt, render_prompt, get_system_prompt
        
        assert callable(load_prompt)
        assert callable(render_prompt)
        assert callable(get_system_prompt)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
