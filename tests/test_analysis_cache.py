"""
분석 결과 캐싱 테스트.

AnalysisCache 클래스 및 캐시 무효화 트리거 테스트.
"""
import time
import pytest

from backend.common.cache import (
    AnalysisCache,
    CacheInvalidationTrigger,
    analysis_cache,
    ANALYSIS_CACHE_TTL,
)


class TestAnalysisCache:
    """AnalysisCache 테스트."""
    
    def setup_method(self):
        """각 테스트 전 캐시 초기화."""
        self.cache = AnalysisCache(ttl=60)  # 테스트용 짧은 TTL
        self.cache.clear()
    
    def test_make_repo_key(self):
        """저장소 키 생성 테스트."""
        key = self.cache.make_repo_key("Owner", "Repo", "main")
        assert key == "analysis:owner/repo:main"
        
        # 대소문자 정규화
        key2 = self.cache.make_repo_key("OWNER", "REPO", "main")
        assert key == key2
    
    def test_set_and_get_analysis(self):
        """분석 결과 저장/조회 테스트."""
        result = {"health_score": 85, "health_level": "good"}
        
        self.cache.set_analysis("owner", "repo", "main", result)
        
        cached = self.cache.get_analysis("owner", "repo", "main")
        assert cached is not None
        assert cached["health_score"] == 85
    
    def test_cache_miss(self):
        """캐시 미스 테스트."""
        cached = self.cache.get_analysis("nonexistent", "repo", "main")
        assert cached is None
    
    def test_invalidate_analysis(self):
        """캐시 무효화 테스트."""
        result = {"health_score": 85}
        self.cache.set_analysis("owner", "repo", "main", result)
        
        # 무효화 전 확인
        assert self.cache.get_analysis("owner", "repo", "main") is not None
        
        # 무효화
        existed = self.cache.invalidate_analysis("owner", "repo", "main")
        assert existed is True
        
        # 무효화 후 확인
        assert self.cache.get_analysis("owner", "repo", "main") is None
        
        # 이미 없는 캐시 무효화
        existed = self.cache.invalidate_analysis("owner", "repo", "main")
        assert existed is False
    
    def test_invalidate_all_refs(self):
        """모든 ref 무효화 테스트."""
        self.cache.set_analysis("owner", "repo", "main", {"branch": "main"})
        self.cache.set_analysis("owner", "repo", "develop", {"branch": "develop"})
        self.cache.set_analysis("owner", "repo", "feature", {"branch": "feature"})
        self.cache.set_analysis("other", "repo", "main", {"branch": "other"})
        
        count = self.cache.invalidate_all_refs("owner", "repo")
        assert count == 3
        
        # owner/repo 캐시 모두 삭제됨
        assert self.cache.get_analysis("owner", "repo", "main") is None
        assert self.cache.get_analysis("owner", "repo", "develop") is None
        
        # 다른 저장소는 유지
        assert self.cache.get_analysis("other", "repo", "main") is not None
    
    def test_ttl_expiration(self):
        """TTL 만료 테스트."""
        short_cache = AnalysisCache(ttl=1)  # 1초 TTL
        short_cache.set_analysis("owner", "repo", "main", {"test": True})
        
        # 즉시 조회
        assert short_cache.get_analysis("owner", "repo", "main") is not None
        
        # 만료 후 조회
        time.sleep(1.5)
        assert short_cache.get_analysis("owner", "repo", "main") is None
    
    def test_get_stats(self):
        """캐시 통계 테스트."""
        self.cache.set_analysis("owner1", "repo", "main", {})
        self.cache.set_analysis("owner2", "repo", "main", {})
        
        stats = self.cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2
        assert stats["expired_entries"] == 0
        assert stats["ttl_seconds"] == 60
    
    def test_invalidation_callback(self):
        """무효화 콜백 테스트."""
        callback_called = []
        
        def on_invalidate(owner, repo, ref):
            callback_called.append((owner, repo, ref))
        
        self.cache.register_invalidation_callback(on_invalidate)
        self.cache.set_analysis("owner", "repo", "main", {})
        self.cache.invalidate_analysis("owner", "repo", "main")
        
        assert len(callback_called) == 1
        assert callback_called[0] == ("owner", "repo", "main")


class TestCacheInvalidationTrigger:
    """캐시 무효화 트리거 테스트."""
    
    def setup_method(self):
        """각 테스트 전 초기화."""
        self.cache = AnalysisCache(ttl=60)
        self.cache.clear()
        self.trigger = CacheInvalidationTrigger(self.cache)
    
    def test_should_invalidate_on_push(self):
        """Push 이벤트 무효화 판단 테스트."""
        # 캐시 설정
        self.cache.set_analysis("owner", "repo", "main", {"test": True})
        
        # 캐시 생성 전 push → 무효화 불필요
        old_push = time.time() - 100
        assert not self.trigger.should_invalidate_on_push("owner", "repo", "main", old_push)
        
        # 캐시 생성 후 push → 무효화 필요
        new_push = time.time() + 10
        assert self.trigger.should_invalidate_on_push("owner", "repo", "main", new_push)
    
    def test_trigger_push_invalidation(self):
        """Push 무효화 트리거 테스트."""
        self.cache.set_analysis("owner", "repo", "main", {"test": True})
        
        # 새 push로 무효화
        pushed_at = time.time() + 10
        result = self.trigger.trigger_push_invalidation("owner", "repo", "main", pushed_at)
        
        assert result is True
        assert self.cache.get_analysis("owner", "repo", "main") is None
    
    def test_no_cache_no_invalidation(self):
        """캐시가 없으면 무효화 불필요."""
        result = self.trigger.should_invalidate_on_push("nonexistent", "repo", "main", time.time())
        assert result is False


class TestGlobalAnalysisCache:
    """전역 analysis_cache 테스트."""
    
    def setup_method(self):
        """각 테스트 전 캐시 초기화."""
        analysis_cache.clear()
    
    def test_global_cache_exists(self):
        """전역 캐시 인스턴스 존재 확인."""
        assert analysis_cache is not None
        assert isinstance(analysis_cache, AnalysisCache)
    
    def test_default_ttl(self):
        """기본 TTL 확인."""
        assert analysis_cache._ttl == ANALYSIS_CACHE_TTL
        assert ANALYSIS_CACHE_TTL == 86400  # 24시간


# Redis 변경 관련 정보성 테스트
class TestRedisConsiderations:
    """Redis 전환 시 고려사항 문서화 (정보성)."""
    
    def test_in_memory_vs_redis_tradeoffs(self):
        """In-Memory vs Redis 비교 정보."""
        in_memory = {
            "pros": [
                "설정 불필요",
                "빠른 응답 속도",
                "외부 의존성 없음",
            ],
            "cons": [
                "서버 재시작 시 캐시 유실",
                "다중 인스턴스 간 공유 불가",
                "메모리 제한",
            ],
        }
        
        redis = {
            "pros": [
                "서버 재시작 후에도 유지",
                "다중 인스턴스 간 공유",
                "대용량 데이터 처리",
                "TTL/Expire 자동 관리",
            ],
            "cons": [
                "추가 인프라 필요",
                "네트워크 지연",
                "복잡성 증가",
            ],
        }
        
        # 현재 선택: In-Memory (MVP)
        # 향후 확장: Redis (프로덕션)
        assert "서버 재시작 시 캐시 유실" in in_memory["cons"]
        assert "서버 재시작 후에도 유지" in redis["pros"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
