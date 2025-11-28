"""
간단한 인메모리 캐시 + TTL 지원.

LangGraph 전환 시에도 그대로 사용 가능.
Redis 등으로 교체 시 이 파일만 수정하면 됨.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, TypeVar
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# 기본 TTL: 5분 (같은 repo 재분석 시 캐시 사용)
DEFAULT_TTL_SECONDS = 300

T = TypeVar("T")


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    value: Any
    expires_at: float  # timestamp


class SimpleCache:
    """
    간단한 인메모리 TTL 캐시.
    
    사용 예:
        cache = SimpleCache(ttl=300)
        cache.set("key", value)
        cached = cache.get("key")
    """
    
    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS):
        self._store: Dict[str, CacheEntry] = {}
        self._ttl = ttl
    
    def _make_key(self, *args, **kwargs) -> str:
        """인자들로 캐시 키 생성"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회 (만료되었으면 None)"""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """캐시에 값 저장"""
        expires_at = time.time() + (ttl or self._ttl)
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def delete(self, key: str) -> None:
        """캐시에서 삭제"""
        self._store.pop(key, None)
    
    def clear(self) -> None:
        """전체 캐시 삭제"""
        self._store.clear()
    
    def cleanup_expired(self) -> int:
        """만료된 엔트리 정리, 삭제된 개수 반환"""
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)


# 전역 캐시 인스턴스 (GitHub API용)
github_cache = SimpleCache(ttl=DEFAULT_TTL_SECONDS)


def cached(cache: SimpleCache = github_cache, ttl: Optional[int] = None):
    """
    함수 결과를 캐싱하는 데코레이터.
    
    사용 예:
        @cached()
        def fetch_repo_info(owner, repo):
            ...
    """
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
