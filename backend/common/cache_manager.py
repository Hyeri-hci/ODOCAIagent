"""
캐시 관리 시스템
진단 결과, 온보딩 플랜 등을 캐싱
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


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


# === 싱글톤 인스턴스 ===
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """캐시 관리자 싱글톤 인스턴스 반환"""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
    return _cache_manager_instance
