"""
캐시 관리 API 라우터.

분석 결과 캐시의 조회, 무효화, 통계 기능을 제공합니다.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.common.cache import analysis_cache, cache_invalidation_trigger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


class CacheStatsResponse(BaseModel):
    """캐시 통계 응답."""
    total_entries: int
    active_entries: int
    expired_entries: int
    ttl_seconds: int


class CacheInvalidateResponse(BaseModel):
    """캐시 무효화 응답."""
    ok: bool
    message: str
    invalidated: bool = False


class CacheInvalidateRequest(BaseModel):
    """캐시 무효화 요청."""
    repo_url: Optional[str] = Field(default=None, description="GitHub 저장소 URL")
    owner: Optional[str] = Field(default=None, description="저장소 소유자")
    repo: Optional[str] = Field(default=None, description="저장소 이름")
    ref: str = Field(default="main", description="브랜치/태그")
    all_refs: bool = Field(default=False, description="모든 ref 무효화 여부")


class WebhookPushEvent(BaseModel):
    """GitHub Push Webhook 이벤트."""
    repository: dict
    ref: str
    pusher: dict
    head_commit: Optional[dict] = None


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """
    캐시 통계 조회.
    
    현재 캐시의 상태 정보를 반환합니다.
    """
    stats = analysis_cache.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(request: CacheInvalidateRequest) -> CacheInvalidateResponse:
    """
    캐시 무효화.
    
    특정 저장소의 분석 결과 캐시를 무효화합니다.
    repo_url 또는 (owner, repo) 조합으로 지정할 수 있습니다.
    """
    owner = request.owner
    repo = request.repo
    ref = request.ref
    
    # repo_url에서 owner/repo 추출
    if request.repo_url:
        from backend.api.http_router import parse_github_url
        try:
            owner, repo, ref = parse_github_url(request.repo_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    if not owner or not repo:
        raise HTTPException(
            status_code=400, 
            detail="repo_url 또는 (owner, repo) 필수"
        )
    
    if request.all_refs:
        count = analysis_cache.invalidate_all_refs(owner, repo)
        return CacheInvalidateResponse(
            ok=True,
            message=f"{owner}/{repo}의 모든 캐시 무효화됨 ({count}개)",
            invalidated=count > 0,
        )
    else:
        invalidated = analysis_cache.invalidate_analysis(owner, repo, ref)
        return CacheInvalidateResponse(
            ok=True,
            message=f"{owner}/{repo}@{ref} 캐시 {'무효화됨' if invalidated else '없음'}",
            invalidated=invalidated,
        )


@router.delete("/clear")
async def clear_all_cache() -> dict:
    """
    전체 캐시 삭제.
    
    주의: 모든 분석 결과 캐시가 삭제됩니다.
    """
    stats_before = analysis_cache.get_stats()
    analysis_cache.clear()
    
    logger.warning(f"All analysis cache cleared: {stats_before['total_entries']} entries")
    
    return {
        "ok": True,
        "message": "전체 캐시 삭제됨",
        "deleted_entries": stats_before["total_entries"],
    }


@router.post("/webhook/push")
async def handle_push_webhook(event: WebhookPushEvent) -> dict:
    """
    GitHub Push Webhook 핸들러.
    
    저장소에 Push가 발생하면 해당 캐시를 자동으로 무효화합니다.
    
    GitHub Webhook 설정:
    1. Repository Settings → Webhooks → Add webhook
    2. Payload URL: https://your-domain/api/cache/webhook/push
    3. Content type: application/json
    4. Events: Just the push event
    """
    try:
        repo_info = event.repository
        owner = repo_info.get("owner", {}).get("login") or repo_info.get("owner", {}).get("name")
        repo = repo_info.get("name")
        
        # refs/heads/main → main
        ref = event.ref.replace("refs/heads/", "").replace("refs/tags/", "")
        
        # Push 시간
        pushed_at = None
        if event.head_commit:
            # ISO 8601 → Unix timestamp
            import datetime
            timestamp_str = event.head_commit.get("timestamp")
            if timestamp_str:
                try:
                    dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    pushed_at = dt.timestamp()
                except ValueError:
                    pushed_at = time.time()
        
        if not owner or not repo:
            return {"ok": False, "message": "Invalid webhook payload"}
        
        # 캐시 무효화 트리거
        invalidated = cache_invalidation_trigger.trigger_push_invalidation(
            owner, repo, ref, pushed_at
        )
        
        logger.info(f"Push webhook: {owner}/{repo}@{ref}, invalidated={invalidated}")
        
        return {
            "ok": True,
            "message": f"Webhook processed for {owner}/{repo}@{ref}",
            "cache_invalidated": invalidated,
        }
        
    except Exception as e:
        logger.exception(f"Webhook processing failed: {e}")
        return {"ok": False, "message": str(e)}


@router.get("/check/{owner}/{repo}")
async def check_cache(
    owner: str,
    repo: str,
    ref: str = Query(default="main", description="브랜치/태그")
) -> dict:
    """
    캐시 존재 여부 확인.
    
    특정 저장소의 분석 결과가 캐시되어 있는지 확인합니다.
    """
    cached = analysis_cache.get_analysis(owner, repo, ref)
    
    if cached:
        return {
            "cached": True,
            "owner": owner,
            "repo": repo,
            "ref": ref,
            "health_score": cached.get("score") or cached.get("analysis", {}).get("health_score"),
        }
    else:
        return {
            "cached": False,
            "owner": owner,
            "repo": repo,
            "ref": ref,
        }
