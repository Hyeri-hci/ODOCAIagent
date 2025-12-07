"""대화 컨텍스트 관리 - Redis 기반 (메모리 Fallback 지원)."""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """단일 대화 턴."""
    user_message: str
    assistant_message: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        return cls(**data)


@dataclass
class ConversationContext:
    """세션의 대화 컨텍스트."""
    session_id: str
    recent_turns: List[ConversationTurn] = field(default_factory=list)
    summary: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "recent_turns": [t.to_dict() for t in self.recent_turns],
            "summary": self.summary,
            "preferences": self.preferences,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        turns = [ConversationTurn.from_dict(t) for t in data.get("recent_turns", [])]
        return cls(
            session_id=data["session_id"],
            recent_turns=turns,
            summary=data.get("summary"),
            preferences=data.get("preferences", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class ConversationMemoryBackend(ABC):
    """대화 메모리 백엔드 인터페이스."""

    @abstractmethod
    def get_turns(self, session_id: str) -> List[ConversationTurn]:
        """세션의 대화 턴 목록 조회."""
        pass

    @abstractmethod
    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """대화 턴 추가."""
        pass

    @abstractmethod
    def get_summary(self, session_id: str) -> Optional[str]:
        """세션 요약 조회."""
        pass

    @abstractmethod
    def set_summary(self, session_id: str, summary: str) -> None:
        """세션 요약 저장."""
        pass

    @abstractmethod
    def get_preferences(self, session_id: str) -> Dict[str, Any]:
        """사용자 선호도 조회."""
        pass

    @abstractmethod
    def set_preferences(self, session_id: str, preferences: Dict[str, Any]) -> None:
        """사용자 선호도 저장."""
        pass

    @abstractmethod
    def clear_session(self, session_id: str) -> None:
        """세션 데이터 삭제."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """백엔드 사용 가능 여부."""
        pass


class RedisConversationBackend(ConversationMemoryBackend):
    """Redis 기반 대화 메모리 백엔드."""

    def __init__(
        self,
        redis_url: str,
        turn_ttl: int = 604800,
        summary_ttl: int = 2592000,
        max_turns: int = 20,
    ):
        self.redis_url = redis_url
        self.turn_ttl = turn_ttl
        self.summary_ttl = summary_ttl
        self.max_turns = max_turns
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        try:
            import redis
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            self._client.ping()
            self._available = True
            logger.info(f"Redis connected: {self.redis_url}")
        except ImportError:
            logger.warning("redis package not installed. Using fallback.")
            self._available = False
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using fallback.")
            self._available = False

    def _turns_key(self, session_id: str) -> str:
        return f"conv:turns:{session_id}"

    def _summary_key(self, session_id: str) -> str:
        return f"conv:summary:{session_id}"

    def _prefs_key(self, session_id: str) -> str:
        return f"conv:prefs:{session_id}"

    def is_available(self) -> bool:
        return self._available

    def get_turns(self, session_id: str) -> List[ConversationTurn]:
        if not self._available:
            return []
        try:
            key = self._turns_key(session_id)
            data = self._client.lrange(key, 0, -1)
            return [ConversationTurn.from_dict(json.loads(item)) for item in data]
        except Exception as e:
            logger.error(f"Failed to get turns: {e}")
            return []

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        if not self._available:
            return
        try:
            key = self._turns_key(session_id)
            self._client.rpush(key, json.dumps(turn.to_dict()))
            self._client.ltrim(key, -self.max_turns, -1)
            self._client.expire(key, self.turn_ttl)
        except Exception as e:
            logger.error(f"Failed to add turn: {e}")

    def get_summary(self, session_id: str) -> Optional[str]:
        if not self._available:
            return None
        try:
            return self._client.get(self._summary_key(session_id))
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return None

    def set_summary(self, session_id: str, summary: str) -> None:
        if not self._available:
            return
        try:
            self._client.setex(self._summary_key(session_id), self.summary_ttl, summary)
        except Exception as e:
            logger.error(f"Failed to set summary: {e}")

    def get_preferences(self, session_id: str) -> Dict[str, Any]:
        if not self._available:
            return {}
        try:
            data = self._client.get(self._prefs_key(session_id))
            return json.loads(data) if data else {}
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}

    def set_preferences(self, session_id: str, preferences: Dict[str, Any]) -> None:
        if not self._available:
            return
        try:
            self._client.setex(
                self._prefs_key(session_id),
                self.summary_ttl,
                json.dumps(preferences)
            )
        except Exception as e:
            logger.error(f"Failed to set preferences: {e}")

    def clear_session(self, session_id: str) -> None:
        if not self._available:
            return
        try:
            self._client.delete(
                self._turns_key(session_id),
                self._summary_key(session_id),
                self._prefs_key(session_id),
            )
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")


class InMemoryConversationBackend(ConversationMemoryBackend):
    """메모리 기반 대화 메모리 백엔드 (Fallback)."""

    def __init__(self, max_turns: int = 20, max_sessions: int = 1000):
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self._turns: Dict[str, List[ConversationTurn]] = {}
        self._summaries: Dict[str, str] = {}
        self._preferences: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = Lock()

    def _cleanup_if_needed(self) -> None:
        if len(self._turns) <= self.max_sessions:
            return
        sorted_sessions = sorted(self._access_times.items(), key=lambda x: x[1])
        to_remove = len(self._turns) - self.max_sessions + 100
        for session_id, _ in sorted_sessions[:to_remove]:
            self._turns.pop(session_id, None)
            self._summaries.pop(session_id, None)
            self._preferences.pop(session_id, None)
            self._access_times.pop(session_id, None)

    def is_available(self) -> bool:
        return True

    def get_turns(self, session_id: str) -> List[ConversationTurn]:
        with self._lock:
            self._access_times[session_id] = time.time()
            return self._turns.get(session_id, []).copy()

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        with self._lock:
            self._cleanup_if_needed()
            if session_id not in self._turns:
                self._turns[session_id] = []
            self._turns[session_id].append(turn)
            if len(self._turns[session_id]) > self.max_turns:
                self._turns[session_id] = self._turns[session_id][-self.max_turns:]
            self._access_times[session_id] = time.time()

    def get_summary(self, session_id: str) -> Optional[str]:
        with self._lock:
            self._access_times[session_id] = time.time()
            return self._summaries.get(session_id)

    def set_summary(self, session_id: str, summary: str) -> None:
        with self._lock:
            self._summaries[session_id] = summary
            self._access_times[session_id] = time.time()

    def get_preferences(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            self._access_times[session_id] = time.time()
            return self._preferences.get(session_id, {}).copy()

    def set_preferences(self, session_id: str, preferences: Dict[str, Any]) -> None:
        with self._lock:
            self._preferences[session_id] = preferences.copy()
            self._access_times[session_id] = time.time()

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._turns.pop(session_id, None)
            self._summaries.pop(session_id, None)
            self._preferences.pop(session_id, None)
            self._access_times.pop(session_id, None)


class ConversationMemory:
    """
    대화 컨텍스트 관리자.
    
    Redis 사용 가능 시 Redis 백엔드, 그렇지 않으면 메모리 백엔드 사용.
    """

    _instance: Optional["ConversationMemory"] = None

    def __init__(
        self,
        redis_url: Optional[str] = None,
        turn_ttl: int = 604800,
        summary_ttl: int = 2592000,
        max_turns: int = 20,
    ):
        self.max_turns = max_turns
        self._redis_backend: Optional[RedisConversationBackend] = None
        self._memory_backend = InMemoryConversationBackend(max_turns=max_turns)

        if redis_url:
            self._redis_backend = RedisConversationBackend(
                redis_url=redis_url,
                turn_ttl=turn_ttl,
                summary_ttl=summary_ttl,
                max_turns=max_turns,
            )

    @property
    def _backend(self) -> ConversationMemoryBackend:
        if self._redis_backend and self._redis_backend.is_available():
            return self._redis_backend
        return self._memory_backend

    @property
    def backend_type(self) -> str:
        if self._redis_backend and self._redis_backend.is_available():
            return "redis"
        return "memory"

    def is_redis_available(self) -> bool:
        return self._redis_backend is not None and self._redis_backend.is_available()

    def get_context(self, session_id: str) -> ConversationContext:
        """세션의 전체 컨텍스트 조회."""
        turns = self._backend.get_turns(session_id)
        summary = self._backend.get_summary(session_id)
        preferences = self._backend.get_preferences(session_id)
        return ConversationContext(
            session_id=session_id,
            recent_turns=turns,
            summary=summary,
            preferences=preferences,
        )

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """대화 턴 추가."""
        turn = ConversationTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            metadata=metadata or {},
        )
        self._backend.add_turn(session_id, turn)

    def get_summary(self, session_id: str) -> Optional[str]:
        """세션 요약 조회."""
        return self._backend.get_summary(session_id)

    def set_summary(self, session_id: str, summary: str) -> None:
        """세션 요약 저장."""
        self._backend.set_summary(session_id, summary)

    def get_preferences(self, session_id: str) -> Dict[str, Any]:
        """사용자 선호도 조회."""
        return self._backend.get_preferences(session_id)

    def set_preferences(self, session_id: str, preferences: Dict[str, Any]) -> None:
        """사용자 선호도 저장."""
        self._backend.set_preferences(session_id, preferences)

    def update_preferences(self, session_id: str, updates: Dict[str, Any]) -> None:
        """사용자 선호도 부분 업데이트."""
        current = self.get_preferences(session_id)
        current.update(updates)
        self.set_preferences(session_id, current)

    def clear_session(self, session_id: str) -> None:
        """세션 데이터 삭제."""
        self._backend.clear_session(session_id)

    def get_recent_messages_for_prompt(
        self,
        session_id: str,
        max_turns: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        LLM 프롬프트용 최근 메시지 목록 반환.
        
        Returns:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        turns = self._backend.get_turns(session_id)
        if max_turns:
            turns = turns[-max_turns:]
        
        messages = []
        for turn in turns:
            messages.append({"role": "user", "content": turn.user_message})
            messages.append({"role": "assistant", "content": turn.assistant_message})
        return messages

    @classmethod
    def get_instance(cls) -> "ConversationMemory":
        """싱글톤 인스턴스 반환."""
        if cls._instance is None:
            from backend.common.config import (
                REDIS_URL,
                REDIS_CONVERSATION_TTL,
                REDIS_SUMMARY_TTL,
            )
            cls._instance = cls(
                redis_url=REDIS_URL,
                turn_ttl=REDIS_CONVERSATION_TTL,
                summary_ttl=REDIS_SUMMARY_TTL,
            )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """싱글톤 인스턴스 초기화 (테스트용)."""
        cls._instance = None


def get_conversation_memory() -> ConversationMemory:
    """ConversationMemory 싱글톤 인스턴스 반환."""
    return ConversationMemory.get_instance()

