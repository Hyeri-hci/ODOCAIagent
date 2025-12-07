"""ConversationMemory 테스트."""
import pytest
import time
from backend.agents.supervisor.memory import (
    ConversationMemory,
    ConversationTurn,
    ConversationContext,
    InMemoryConversationBackend,
    RedisConversationBackend,
)


class TestConversationTurn:
    """ConversationTurn 데이터 클래스 테스트."""

    def test_create_turn(self):
        turn = ConversationTurn(
            user_message="Hello",
            assistant_message="Hi there!"
        )
        assert turn.user_message == "Hello"
        assert turn.assistant_message == "Hi there!"
        assert turn.timestamp > 0

    def test_to_dict(self):
        turn = ConversationTurn(
            user_message="Test",
            assistant_message="Response",
            metadata={"key": "value"}
        )
        data = turn.to_dict()
        assert data["user_message"] == "Test"
        assert data["assistant_message"] == "Response"
        assert data["metadata"] == {"key": "value"}

    def test_from_dict(self):
        data = {
            "user_message": "Test",
            "assistant_message": "Response",
            "timestamp": 12345.0,
            "metadata": {}
        }
        turn = ConversationTurn.from_dict(data)
        assert turn.user_message == "Test"
        assert turn.timestamp == 12345.0


class TestConversationContext:
    """ConversationContext 데이터 클래스 테스트."""

    def test_create_context(self):
        context = ConversationContext(session_id="test-session")
        assert context.session_id == "test-session"
        assert context.recent_turns == []
        assert context.summary is None

    def test_to_dict_from_dict(self):
        turn = ConversationTurn(
            user_message="Hello",
            assistant_message="Hi"
        )
        context = ConversationContext(
            session_id="test",
            recent_turns=[turn],
            summary="Test summary",
            preferences={"lang": "ko"}
        )
        data = context.to_dict()
        restored = ConversationContext.from_dict(data)
        assert restored.session_id == "test"
        assert len(restored.recent_turns) == 1
        assert restored.summary == "Test summary"


class TestInMemoryBackend:
    """InMemoryConversationBackend 테스트."""

    def test_add_and_get_turns(self):
        backend = InMemoryConversationBackend(max_turns=5)
        turn = ConversationTurn(
            user_message="Hello",
            assistant_message="Hi"
        )
        backend.add_turn("session1", turn)
        turns = backend.get_turns("session1")
        assert len(turns) == 1
        assert turns[0].user_message == "Hello"

    def test_max_turns_limit(self):
        backend = InMemoryConversationBackend(max_turns=3)
        for i in range(5):
            turn = ConversationTurn(
                user_message=f"msg{i}",
                assistant_message=f"resp{i}"
            )
            backend.add_turn("session1", turn)
        turns = backend.get_turns("session1")
        assert len(turns) == 3
        assert turns[0].user_message == "msg2"

    def test_summary_operations(self):
        backend = InMemoryConversationBackend()
        assert backend.get_summary("session1") is None
        backend.set_summary("session1", "Test summary")
        assert backend.get_summary("session1") == "Test summary"

    def test_preferences_operations(self):
        backend = InMemoryConversationBackend()
        assert backend.get_preferences("session1") == {}
        backend.set_preferences("session1", {"lang": "ko"})
        assert backend.get_preferences("session1") == {"lang": "ko"}

    def test_clear_session(self):
        backend = InMemoryConversationBackend()
        turn = ConversationTurn(
            user_message="Hello",
            assistant_message="Hi"
        )
        backend.add_turn("session1", turn)
        backend.set_summary("session1", "Summary")
        backend.set_preferences("session1", {"key": "value"})
        
        backend.clear_session("session1")
        
        assert backend.get_turns("session1") == []
        assert backend.get_summary("session1") is None
        assert backend.get_preferences("session1") == {}

    def test_is_available(self):
        backend = InMemoryConversationBackend()
        assert backend.is_available() is True


class TestRedisBackendFallback:
    """RedisConversationBackend Fallback 테스트."""

    def test_unavailable_redis(self):
        backend = RedisConversationBackend(
            redis_url="redis://invalid-host:9999",
            turn_ttl=60,
            summary_ttl=120,
        )
        assert backend.is_available() is False
        assert backend.get_turns("session1") == []
        assert backend.get_summary("session1") is None


class TestConversationMemory:
    """ConversationMemory 통합 테스트."""

    def setup_method(self):
        ConversationMemory.reset_instance()

    def test_memory_with_fallback(self):
        memory = ConversationMemory(redis_url=None)
        assert memory.backend_type == "memory"
        assert memory.is_redis_available() is False

    def test_add_and_get_context(self):
        memory = ConversationMemory(redis_url=None)
        memory.add_turn("session1", "Hello", "Hi there!")
        context = memory.get_context("session1")
        assert len(context.recent_turns) == 1
        assert context.recent_turns[0].user_message == "Hello"

    def test_summary_operations(self):
        memory = ConversationMemory(redis_url=None)
        assert memory.get_summary("session1") is None
        memory.set_summary("session1", "Conversation about testing")
        assert memory.get_summary("session1") == "Conversation about testing"

    def test_preferences_operations(self):
        memory = ConversationMemory(redis_url=None)
        memory.set_preferences("session1", {"language": "ko"})
        assert memory.get_preferences("session1") == {"language": "ko"}
        
        memory.update_preferences("session1", {"theme": "dark"})
        prefs = memory.get_preferences("session1")
        assert prefs["language"] == "ko"
        assert prefs["theme"] == "dark"

    def test_get_recent_messages_for_prompt(self):
        memory = ConversationMemory(redis_url=None)
        memory.add_turn("session1", "Question 1", "Answer 1")
        memory.add_turn("session1", "Question 2", "Answer 2")
        
        messages = memory.get_recent_messages_for_prompt("session1")
        assert len(messages) == 4
        assert messages[0] == {"role": "user", "content": "Question 1"}
        assert messages[1] == {"role": "assistant", "content": "Answer 1"}
        assert messages[2] == {"role": "user", "content": "Question 2"}
        assert messages[3] == {"role": "assistant", "content": "Answer 2"}

    def test_get_recent_messages_with_limit(self):
        memory = ConversationMemory(redis_url=None)
        for i in range(5):
            memory.add_turn("session1", f"Q{i}", f"A{i}")
        
        messages = memory.get_recent_messages_for_prompt("session1", max_turns=2)
        assert len(messages) == 4
        assert messages[0]["content"] == "Q3"

    def test_clear_session(self):
        memory = ConversationMemory(redis_url=None)
        memory.add_turn("session1", "Hello", "Hi")
        memory.set_summary("session1", "Test")
        memory.clear_session("session1")
        
        context = memory.get_context("session1")
        assert len(context.recent_turns) == 0
        assert context.summary is None


class TestServiceIntegration:
    """service.py 통합 테스트."""

    def setup_method(self):
        ConversationMemory.reset_instance()

    def test_check_memory_status(self):
        from backend.agents.supervisor.service import check_memory_status
        status = check_memory_status()
        assert "backend_type" in status
        assert "redis_available" in status

    def test_save_and_get_conversation(self):
        from backend.agents.supervisor.service import (
            save_conversation_turn,
            get_conversation_context,
        )
        save_conversation_turn("test-session", "Hello", "Hi there!")
        context = get_conversation_context("test-session")
        assert context["session_id"] == "test-session"
        assert len(context["recent_turns"]) == 1

