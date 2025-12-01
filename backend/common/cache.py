"""A simple TTL-based in-memory cache with idempotency support."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, TypeVar, Tuple
from functools import wraps
import hashlib
import json
import logging
from threading import Lock
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300
IDEMPOTENCY_TTL_SECONDS = 60  # 1분 (동일 요청 중복 방지)

T = TypeVar("T")


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class SimpleCache:
    """A simple in-memory cache with Time-To-Live (TTL) support."""
    
    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS):
        self._store: Dict[str, CacheEntry] = {}
        self._ttl = ttl
    
    def _make_key(self, *args, **kwargs) -> str:
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expires_at = time.time() + (ttl or self._ttl)
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def delete(self, key: str) -> None:
        self._store.pop(key, None)
    
    def clear(self) -> None:
        self._store.clear()
    
    def size(self) -> int:
        return len(self._store)
    
    def cleanup_expired(self) -> int:
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)


github_cache = SimpleCache(ttl=DEFAULT_TTL_SECONDS)


def cached(cache: SimpleCache = github_cache, ttl: Optional[int] = None):
    """Decorator to cache the result of a function."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Create a cache key from the function and its arguments.
            key = f"{func.__module__}.{func.__name__}:" + cache._make_key(*args, **kwargs)
            
            # Check for a cache hit.
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug("Cache HIT: %s", key[:50])
                return cached_value
            
            # On a cache miss, call the actual function.
            logger.debug("Cache MISS: %s", key[:50])
            result = func(*args, **kwargs)
            
            # Store the result in the cache.
            cache.set(key, result, ttl)
            return result
        
        # Add a helper to invalidate the cache for a specific call.
        def invalidate(*args, **kwargs) -> None:
            key = f"{func.__module__}.{func.__name__}:" + cache._make_key(*args, **kwargs)
            cache.delete(key)
        
        wrapper.invalidate = invalidate  # type: ignore
        wrapper.cache = cache  # type: ignore
        return wrapper
    
    return decorator


# =============================================================================
# Idempotency: 턴ID×스텝ID 실행 잠금 + 캐시
# =============================================================================

@dataclass
class ExecutionResult:
    """Stores the result of an idempotent execution."""
    answer_id: str
    result: Any
    created_at: float = field(default_factory=time.time)
    execution_count: int = 1


class IdempotencyStore:
    """
    Manages idempotent execution using turn_id × step_id locking.
    
    Ensures:
    - Same turn+step combination returns cached result
    - Generates unique answer_id per execution
    - Thread-safe operations
    """
    
    def __init__(self, ttl: int = IDEMPOTENCY_TTL_SECONDS):
        self._store: Dict[str, ExecutionResult] = {}
        self._locks: Dict[str, Lock] = {}
        self._global_lock = Lock()
        self._ttl = ttl
        self._enabled = True  # 롤백용 플래그
    
    def _make_key(self, session_id: str, turn_id: str, step_id: str) -> str:
        """Creates a unique key from session, turn, and step IDs."""
        return f"{session_id}:{turn_id}:{step_id}"
    
    def _generate_answer_id(self, session_id: str) -> str:
        """Generates a unique answer_id within the session."""
        short_uuid = uuid.uuid4().hex[:8]
        timestamp = int(time.time() * 1000) % 100000
        return f"ans_{session_id[-8:]}_{timestamp}_{short_uuid}"
    
    def _get_lock(self, key: str) -> Lock:
        """Gets or creates a lock for the given key."""
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]
    
    def _cleanup_expired(self) -> None:
        """Removes expired entries."""
        now = time.time()
        expired_keys = [
            k for k, v in self._store.items() 
            if now - v.created_at > self._ttl
        ]
        for key in expired_keys:
            self._store.pop(key, None)
            self._locks.pop(key, None)
    
    def get_cached(
        self, 
        session_id: str, 
        turn_id: str, 
        step_id: str
    ) -> Optional[ExecutionResult]:
        """Returns cached result if exists and not expired."""
        if not self._enabled:
            return None
        
        key = self._make_key(session_id, turn_id, step_id)
        entry = self._store.get(key)
        
        if entry is None:
            return None
        
        # Check TTL
        if time.time() - entry.created_at > self._ttl:
            self._store.pop(key, None)
            return None
        
        # Increment execution count (for debugging)
        entry.execution_count += 1
        logger.debug(f"Idempotency HIT: {key} (count={entry.execution_count})")
        return entry
    
    def store_result(
        self,
        session_id: str,
        turn_id: str,
        step_id: str,
        result: Any,
        answer_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Stores execution result with generated answer_id."""
        if not self._enabled:
            aid = answer_id or self._generate_answer_id(session_id)
            return ExecutionResult(answer_id=aid, result=result)
        
        key = self._make_key(session_id, turn_id, step_id)
        aid = answer_id or self._generate_answer_id(session_id)
        
        entry = ExecutionResult(answer_id=aid, result=result)
        self._store[key] = entry
        
        # Periodic cleanup
        if len(self._store) > 100:
            self._cleanup_expired()
        
        logger.debug(f"Idempotency STORE: {key} -> {aid}")
        return entry
    
    @contextmanager
    def acquire_lock(self, session_id: str, turn_id: str, step_id: str):
        """Context manager for acquiring execution lock."""
        if not self._enabled:
            yield
            return
        
        key = self._make_key(session_id, turn_id, step_id)
        lock = self._get_lock(key)
        
        acquired = lock.acquire(timeout=5.0)  # 5초 타임아웃
        try:
            if not acquired:
                logger.warning(f"Lock acquisition timeout: {key}")
            yield
        finally:
            if acquired:
                lock.release()
    
    def disable(self) -> None:
        """Disables idempotency (rollback mode)."""
        self._enabled = False
        logger.warning("Idempotency store DISABLED")
    
    def enable(self) -> None:
        """Enables idempotency."""
        self._enabled = True
        logger.info("Idempotency store ENABLED")
    
    def clear(self) -> None:
        """Clears all cached results."""
        self._store.clear()
        self._locks.clear()
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled


# Global idempotency store
idempotency_store = IdempotencyStore()
