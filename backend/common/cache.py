"""A simple TTL-based in-memory cache with idempotency support."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, TypeVar, Tuple
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


# Idempotency Store

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


# === Analysis Cache ===

ANALYSIS_CACHE_TTL = 86400  # 24시간 (초)


class AnalysisCache(SimpleCache):
    """
    분석 결과 전용 캐시.
    
    - 24시간 TTL (기본)
    - 저장소 기반 키 생성
    - 자동 무효화 트리거 지원
    """
    
    def __init__(self, ttl: int = ANALYSIS_CACHE_TTL):
        super().__init__(ttl=ttl)
        self._invalidation_callbacks: List[Callable[[str, str, str], None]] = []
    
    def make_repo_key(self, owner: str, repo: str, ref: str = "main") -> str:
        """저장소 기반 캐시 키 생성."""
        return f"analysis:{owner.lower()}/{repo.lower()}:{ref}"
    
    def get_analysis(
        self, 
        owner: str, 
        repo: str, 
        ref: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """분석 결과 조회."""
        key = self.make_repo_key(owner, repo, ref)
        result = self.get(key)
        if result:
            logger.info(f"Analysis cache HIT: {owner}/{repo}@{ref}")
        else:
            logger.debug(f"Analysis cache MISS: {owner}/{repo}@{ref}")
        return result
    
    def set_analysis(
        self, 
        owner: str, 
        repo: str, 
        ref: str, 
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """분석 결과 저장."""
        key = self.make_repo_key(owner, repo, ref)
        self.set(key, result, ttl)
        logger.info(f"Analysis cache SET: {owner}/{repo}@{ref}")
    
    def invalidate_analysis(self, owner: str, repo: str, ref: str = "main") -> bool:
        """특정 저장소 캐시 무효화."""
        key = self.make_repo_key(owner, repo, ref)
        existed = self.get(key) is not None
        self.delete(key)
        
        # 무효화 콜백 실행
        for callback in self._invalidation_callbacks:
            try:
                callback(owner, repo, ref)
            except Exception as e:
                logger.warning(f"Invalidation callback failed: {e}")
        
        if existed:
            logger.info(f"Analysis cache INVALIDATED: {owner}/{repo}@{ref}")
        return existed
    
    def invalidate_all_refs(self, owner: str, repo: str) -> int:
        """특정 저장소의 모든 ref 캐시 무효화."""
        prefix = f"analysis:{owner.lower()}/{repo.lower()}:"
        count = 0
        keys_to_delete = [k for k in self._store.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            self.delete(key)
            count += 1
        if count > 0:
            logger.info(f"Analysis cache INVALIDATED ALL: {owner}/{repo} ({count} entries)")
        return count
    
    def register_invalidation_callback(
        self, 
        callback: Callable[[str, str, str], None]
    ) -> None:
        """무효화 시 호출될 콜백 등록."""
        self._invalidation_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환."""
        now = time.time()
        active_entries = sum(1 for v in self._store.values() if now <= v.expires_at)
        expired_entries = len(self._store) - active_entries
        
        return {
            "total_entries": len(self._store),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "ttl_seconds": self._ttl,
        }


# Global analysis cache
analysis_cache = AnalysisCache()


# === Auto-Invalidation Triggers ===

class CacheInvalidationTrigger:
    """
    캐시 자동 무효화 트리거.
    
    GitHub webhook 이벤트나 주기적 검사를 통해
    캐시를 자동으로 무효화합니다.
    """
    
    def __init__(self, cache: AnalysisCache):
        self._cache = cache
        self._last_check: Dict[str, float] = {}
        self._check_interval = 3600  # 1시간
    
    def should_invalidate_on_push(
        self, 
        owner: str, 
        repo: str, 
        ref: str,
        pushed_at: Optional[float] = None
    ) -> bool:
        """
        Push 이벤트 시 캐시 무효화 여부 결정.
        
        Args:
            owner: 저장소 소유자
            repo: 저장소 이름
            ref: 브랜치/태그
            pushed_at: Push 시간 (Unix timestamp)
        
        Returns:
            무효화가 필요하면 True
        """
        key = self._cache.make_repo_key(owner, repo, ref)
        entry = self._cache._store.get(key)
        
        if entry is None:
            return False
        
        # pushed_at이 캐시 생성 시간 이후면 무효화
        if pushed_at:
            cache_created_at = entry.expires_at - self._cache._ttl
            if pushed_at > cache_created_at:
                return True
        
        return False
    
    def trigger_push_invalidation(
        self, 
        owner: str, 
        repo: str, 
        ref: str = "main",
        pushed_at: Optional[float] = None
    ) -> bool:
        """Push 이벤트로 인한 캐시 무효화 실행."""
        if self.should_invalidate_on_push(owner, repo, ref, pushed_at):
            return self._cache.invalidate_analysis(owner, repo, ref)
        return False
    
    def trigger_periodic_check(
        self, 
        owner: str, 
        repo: str,
        ref: str = "main",
        force: bool = False
    ) -> bool:
        """
        주기적 캐시 검사 및 무효화.
        
        check_interval 이후에만 실제로 GitHub API를 호출하여
        저장소 업데이트 여부를 확인합니다.
        """
        key = f"{owner}/{repo}@{ref}"
        now = time.time()
        
        if not force and key in self._last_check:
            if now - self._last_check[key] < self._check_interval:
                return False
        
        self._last_check[key] = now
        
        # TODO: GitHub API로 최신 커밋 시간 확인
        # 현재는 단순히 캐시가 있으면 유지
        return False


# Global invalidation trigger
cache_invalidation_trigger = CacheInvalidationTrigger(analysis_cache)
