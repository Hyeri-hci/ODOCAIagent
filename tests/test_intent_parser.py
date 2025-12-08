"""Intent Parser 유닛 테스트.

ParsedChatIntent 모델, LLM 파서, resolve_repo 하이브리드 매칭 테스트.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.agents.supervisor.intent_parser import (
    ParsedChatIntent,
    is_simple_command,
    handle_simple_command,
    llm_parse_chat_intent,
    resolve_repo,
    get_analyzed_repos,
    _match_by_hint,
    _match_from_message,
)


class TestParsedChatIntent:
    """ParsedChatIntent 모델 테스트."""
    
    def test_default_values(self):
        """기본값 테스트."""
        intent = ParsedChatIntent()
        assert intent.intent == "chat"
        assert intent.repo_hint is None
        assert intent.target_metric is None
        assert intent.options == {}
        assert intent.follow_up is False
        assert intent.confidence == 0.0
    
    def test_to_dict(self):
        """dict 변환 테스트."""
        intent = ParsedChatIntent(
            intent="diagnose",
            repo_hint="react",
            confidence=0.9,
        )
        d = intent.to_dict()
        assert d["intent"] == "diagnose"
        assert d["repo_hint"] == "react"
        assert d["confidence"] == 0.9


class TestSimpleCommand:
    """간단한 명령어 감지 테스트."""
    
    def test_is_simple_command_slash(self):
        """슬래시 명령어 감지."""
        assert is_simple_command("/help") is True
        assert is_simple_command("/reset") is True
        assert is_simple_command("/version") is True
        assert is_simple_command("/unknown") is True  # 모든 슬래시 명령어
    
    def test_is_simple_command_korean(self):
        """한글 명령어 감지."""
        assert is_simple_command("도움말") is True
        assert is_simple_command("도움") is True
    
    def test_is_not_simple_command(self):
        """일반 메시지는 간단한 명령어 아님."""
        assert is_simple_command("react 레포 분석해줘") is False
        assert is_simple_command("") is False
        assert is_simple_command(None) is False
    
    def test_handle_simple_command(self):
        """간단한 명령어 처리."""
        result = handle_simple_command("/help")
        assert result.intent == "help"
        assert result.confidence == 1.0


class TestResolveRepo:
    """하이브리드 레포 매칭 테스트."""
    
    @pytest.fixture
    def sample_repos(self):
        return ["facebook/react", "microsoft/vscode", "pallets/flask"]
    
    def test_exact_match(self, sample_repos):
        """정확히 일치하는 경우."""
        result = resolve_repo("facebook/react", sample_repos, "")
        assert result == "facebook/react"
    
    def test_repo_name_only(self, sample_repos):
        """레포 이름만 주어진 경우."""
        result = resolve_repo("react", sample_repos, "")
        assert result == "facebook/react"
        
        result = resolve_repo("vscode", sample_repos, "")
        assert result == "microsoft/vscode"
    
    def test_partial_match(self, sample_repos):
        """부분 일치."""
        result = resolve_repo("face", sample_repos, "")
        assert result == "facebook/react"
    
    def test_no_match(self, sample_repos):
        """매칭 없음."""
        result = resolve_repo("django", sample_repos, "")
        assert result is None
    
    def test_message_fallback(self, sample_repos):
        """메시지에서 레포 추출."""
        result = resolve_repo(None, sample_repos, "flask 레포 분석해줘")
        assert result == "pallets/flask"
    
    def test_github_url_in_message(self, sample_repos):
        """메시지에 GitHub URL 포함."""
        result = resolve_repo(None, sample_repos, "https://github.com/microsoft/vscode 분석해줘")
        assert result == "microsoft/vscode"
    
    def test_empty_repos(self):
        """빈 레포 목록."""
        result = resolve_repo("react", [], "")
        assert result is None


class TestMatchByHint:
    """_match_by_hint 헬퍼 함수 테스트."""
    
    def test_case_insensitive(self):
        """대소문자 구분 없음."""
        repos = ["Facebook/React"]
        assert _match_by_hint("facebook/react", repos) == "Facebook/React"
        assert _match_by_hint("REACT", repos) == "Facebook/React"
    
    def test_repo_name_in_hint(self):
        """힌트에 레포 이름 포함."""
        repos = ["facebook/react"]
        assert _match_by_hint("저번에 react 분석했던 거", repos) == "facebook/react"


class TestMatchFromMessage:
    """_match_from_message 헬퍼 함수 테스트."""
    
    def test_word_boundary(self):
        """단어 경계로 정확히 매칭."""
        repos = ["facebook/react", "vercel/next.js"]
        # react는 매칭
        assert _match_from_message("react 분석", repos) == "facebook/react"
        # reactor는 매칭 안 됨 (단어 경계)
        assert _match_from_message("reactor 패턴", repos) is None


class TestLLMParseIntent:
    """LLM 파서 테스트 (모킹)."""
    
    @patch("backend.llm.factory.LLMClientProvider.get")
    def test_successful_parse(self, mock_fetch_client):
        """성공적인 LLM 파싱."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '''{"intent": "diagnose", "repo_hint": "react", "target_metric": "health", "options": {}, "follow_up": false, "confidence": 0.95}'''
        mock_client.chat.return_value = mock_response
        mock_fetch_client.return_value = mock_client
        
        result = llm_parse_chat_intent("react 레포 분석해줘", ["facebook/react"], {})
        
        assert result is not None
        assert result.intent == "diagnose"
        assert result.repo_hint == "react"
        assert result.confidence == 0.95
    
    @patch("backend.llm.factory.LLMClientProvider.get")
    def test_json_in_code_block(self, mock_fetch_client):
        """JSON이 코드 블록 안에 있는 경우."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '''```json
{"intent": "compare", "repo_hint": null, "target_metric": null, "options": {}, "follow_up": false, "confidence": 0.8}
```'''
        mock_client.chat.return_value = mock_response
        mock_fetch_client.return_value = mock_client
        
        result = llm_parse_chat_intent("react랑 vue 비교해줘", [], {})
        
        assert result is not None
        assert result.intent == "compare"
    
    @patch("backend.llm.factory.LLMClientProvider.get")
    def test_invalid_json_returns_none(self, mock_fetch_client):
        """잘못된 JSON은 None 반환."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "이건 JSON이 아닙니다"
        mock_client.chat.return_value = mock_response
        mock_fetch_client.return_value = mock_client
        
        result = llm_parse_chat_intent("테스트 메시지", [], {})
        assert result is None
    
    @patch("backend.llm.factory.LLMClientProvider.get")
    def test_llm_exception_returns_none(self, mock_fetch_client):
        """LLM 예외 발생 시 None 반환."""
        mock_fetch_client.side_effect = Exception("API 에러")
        
        result = llm_parse_chat_intent("테스트 메시지", [], {})
        assert result is None
    
    def test_short_message_returns_none(self):
        """너무 짧은 메시지는 파싱하지 않음."""
        result = llm_parse_chat_intent("a", [], {})
        assert result is None
    
    def test_empty_message_returns_none(self):
        """빈 메시지는 파싱하지 않음."""
        result = llm_parse_chat_intent("", [], {})
        assert result is None
        
        result = llm_parse_chat_intent(None, [], {})
        assert result is None


class TestGetAnalyzedRepos:
    """get_analyzed_repos 함수 테스트."""
    
    @patch("backend.common.cache.analysis_cache")
    def test_extracts_repo_ids(self, mock_cache):
        """캐시에서 레포 ID 추출."""
        mock_cache._analyses = {
            "facebook/react@main": {"data": {}},
            "microsoft/vscode@main": {"data": {}},
        }
        
        result = get_analyzed_repos()
        assert "facebook/react" in result
        assert "microsoft/vscode" in result
    
    @patch("backend.common.cache.analysis_cache")
    def test_handles_missing_analyses(self, mock_cache):
        """_analyses 속성 없는 경우."""
        del mock_cache._analyses
        
        result = get_analyzed_repos()
        assert result == []
