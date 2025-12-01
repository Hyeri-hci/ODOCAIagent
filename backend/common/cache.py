"""A simple TTL-based in-memory cache."""
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
