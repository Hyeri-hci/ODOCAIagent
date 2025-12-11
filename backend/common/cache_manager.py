"""
캐시 관리 시스템
진단 결과, 온보딩 플랜 등을 캐싱
"""

from typing import Dict, Any, Optional, Callable, TypeVar
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib
import json
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300  # 5분

T = TypeVar("T")


# === Simple TTL Cache ===

@dataclass
class SimpleCacheEntry:
    """간단한 캐시 엔트리"""
    value: Any
    expires_at: float


class SimpleCache:
    """간단한 TTL 기반 인메모리 캐시"""
    
    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS):
        self._store: Dict[str, SimpleCacheEntry] = {}
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
        self._store[key] = SimpleCacheEntry(value=value, expires_at=expires_at)
    
    def delete(self, key: str) -> None:
        self._store.pop(key, None)
    
    def clear(self) -> None:
        self._store.clear()


# GitHub API 전용 캐시
github_cache = SimpleCache(ttl=DEFAULT_TTL_SECONDS)


def cached(cache: SimpleCache = github_cache, ttl: Optional[int] = None):
    """함수 결과를 캐싱하는 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            key = f"{func.__module__}.{func.__name__}:" + cache._make_key(*args, **kwargs)
            
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug("Cache HIT: %s", key[:50])
                return cached_value
            
            logger.debug("Cache MISS: %s", key[:50])
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        def invalidate(*args, **kwargs) -> None:
            key = f"{func.__module__}.{func.__name__}:" + cache._make_key(*args, **kwargs)
            cache.delete(key)
        
        wrapper.invalidate = invalidate  # type: ignore
        return wrapper
    return decorator


# === CacheManager ===


@dataclass
class CacheEntry:
    """캐시 항목"""
    key: str
    data: Dict[str, Any]
    cached_at: datetime
    ttl_hours: int
    access_count: int = 0
    
    def is_expired(self) -> bool:
        """만료 여부"""
        return datetime.now() - self.cached_at > timedelta(hours=self.ttl_hours)
    
    def access(self):
        """접근 카운트 증가"""
        self.access_count += 1


class CacheManager:
    """캐시 관리자"""
    
    def __init__(self, default_ttl_hours: int = 6):
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl_hours
        logger.info(f"CacheManager initialized (TTL: {default_ttl_hours}h)")
    
    def make_cache_key(
        self,
        owner: str,
        repo: str,
        ref: str,
        analysis_type: str,
        analysis_depth: str = "standard",
        additional_params: Optional[Dict] = None
    ) -> str:
        """
        캐시 키 생성
        
        형식: {owner}/{repo}@{ref}:{analysis_type}:{depth}:{params_hash}
        예시: facebook/react@main:diagnosis:standard:a1b2c3
        """
        base_key = f"{owner}/{repo}@{ref}:{analysis_type}:{analysis_depth}"
        
        if additional_params:
            # 추가 파라미터 해시 (정렬 보장)
            params_str = json.dumps(additional_params, sort_keys=True)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:6]
            base_key += f":{params_hash}"
        
        return base_key
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """캐시 조회"""
        entry = self._cache.get(key)
        
        if entry is None:
            logger.debug(f"Cache miss: {key}")
            return None
        
        # 만료 체크
        if entry.is_expired():
            logger.info(f"Cache expired: {key}")
            del self._cache[key]
            return None
        
        # 접근 카운트 증가
        entry.access()
        logger.debug(f"Cache hit: {key} (access_count: {entry.access_count})")
        
        return entry.data
    
    def set(
        self,
        key: str,
        data: Dict[str, Any],
        ttl_hours: Optional[int] = None
    ):
        """캐시 저장"""
        ttl = ttl_hours if ttl_hours is not None else self._default_ttl
        
        entry = CacheEntry(
            key=key,
            data=data,
            cached_at=datetime.now(),
            ttl_hours=ttl
        )
        
        self._cache[key] = entry
        logger.info(f"Cache set: {key} (TTL: {ttl}h)")
    
    def invalidate(self, key: str):
        """캐시 무효화"""
        if key in self._cache:
            del self._cache[key]
            logger.info(f"Cache invalidated: {key}")
    
    def invalidate_repo(self, owner: str, repo: str):
        """특정 저장소의 모든 캐시 무효화"""
        prefix = f"{owner}/{repo}@"
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        
        for key in keys_to_delete:
            del self._cache[key]
        
        if keys_to_delete:
            logger.info(f"Invalidated {len(keys_to_delete)} cache entries for {owner}/{repo}")
    
    def cleanup_expired(self):
        """만료된 캐시 정리"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        total_entries = len(self._cache)
        total_accesses = sum(entry.access_count for entry in self._cache.values())
        
        return {
            "total_entries": total_entries,
            "total_accesses": total_accesses,
            "avg_access_per_entry": total_accesses / total_entries if total_entries > 0 else 0
        }
    
    def clear_all(self):
        """모든 캐시 삭제 (테스트용)"""
        self._cache.clear()
        logger.warning("All cache cleared")
    
    
    def make_repo_key(self, owner: str, repo: str, ref: str = "main") -> str:
        """저장소 기반 캐시 키 생성 (AnalysisCache 호환)"""
        return f"analysis:{owner.lower()}/{repo.lower()}:{ref}"
    
    def get_analysis(
        self, 
        owner: str, 
        repo: str, 
        ref: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """분석 결과 조회 (AnalysisCache 호환)"""
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
        ttl_hours: Optional[int] = None
    ) -> None:
        """분석 결과 저장 (AnalysisCache 호환)"""
        key = self.make_repo_key(owner, repo, ref)
        self.set(key, result, ttl_hours)
        logger.info(f"Analysis cache SET: {owner}/{repo}@{ref}")
    
    def invalidate_analysis(self, owner: str, repo: str, ref: str = "main") -> bool:
        """특정 저장소 캐시 무효화 (AnalysisCache 호환)"""
        key = self.make_repo_key(owner, repo, ref)
        existed = key in self._cache
        self.invalidate(key)
        if existed:
            logger.info(f"Analysis cache INVALIDATED: {owner}/{repo}@{ref}")
        return existed
    
    def invalidate_all_refs(self, owner: str, repo: str) -> int:
        """특정 저장소의 모든 ref 캐시 무효화 (AnalysisCache 호환)"""
        prefix = f"analysis:{owner.lower()}/{repo.lower()}:"
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
        if keys_to_delete:
            logger.info(f"Analysis cache INVALIDATED ALL: {owner}/{repo} ({len(keys_to_delete)} entries)")
        return len(keys_to_delete)
    
    def clear(self):
        """캐시 전체 삭제 (AnalysisCache 호환)"""
        self.clear_all()


# === 싱글톤 인스턴스 ===
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """캐시 관리자 싱글톤 인스턴스 반환"""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager(default_ttl_hours=24)  # AnalysisCache 기본 TTL과 동일
    return _cache_manager_instance

analysis_cache = get_cache_manager()


# === Auto-Invalidation Trigger ===

class CacheInvalidationTrigger:
    """
    캐시 자동 무효화 트리거.
    
    GitHub webhook 이벤트나 주기적 검사를 통해
    캐시를 자동으로 무효화합니다.
    """
    
    def __init__(self, cache: CacheManager):
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
        """
        key = self._cache.make_repo_key(owner, repo, ref)
        entry = self._cache._cache.get(key)
        
        if entry is None:
            return False
        
        # pushed_at이 캐시 생성 시간 이후면 무효화
        if pushed_at:
            import time
            cache_created_at = entry.cached_at.timestamp()
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
        """주기적 캐시 검사 및 무효화."""
        import time
        key = f"{owner}/{repo}@{ref}"
        now = time.time()
        
        if not force and key in self._last_check:
            if now - self._last_check[key] < self._check_interval:
                return False
        
        self._last_check[key] = now
        
        # 향후: github_client.fetch_repo_overview()로 pushed_at 비교 가능
        # 현재는 캐시가 있으면 유지
        return False


# Global invalidation trigger
cache_invalidation_trigger = CacheInvalidationTrigger(analysis_cache)
