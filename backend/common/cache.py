"""TTL 기반 인메모리 캐시."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable, TypeVar
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300

T = TypeVar("T")


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class SimpleCache:
    """인메모리 TTL 캐시."""
    
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
    """함수 결과 캐싱 데코레이터."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 캐시 키 생성
            key = f"{func.__module__}.{func.__name__}:" + cache._make_key(*args, **kwargs)
            
            # 캐시 히트 확인
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug("Cache HIT: %s", key[:50])
                return cached_value
            
            # 캐시 미스: 실제 함수 호출
            logger.debug("Cache MISS: %s", key[:50])
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            cache.set(key, result, ttl)
            return result
        
        # 캐시 무효화 헬퍼 추가
        def invalidate(*args, **kwargs) -> None:
            key = f"{func.__module__}.{func.__name__}:" + cache._make_key(*args, **kwargs)
            cache.delete(key)
        
        wrapper.invalidate = invalidate  # type: ignore
        wrapper.cache = cache  # type: ignore
        return wrapper
    
    return decorator
