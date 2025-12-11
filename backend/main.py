"""
ODOCAIagent FastAPI 서버.

Usage:
    uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from backend.api.http_router import router as api_router
from backend.api.sse_analyze import router as sse_router
from backend.api.cache_router import router as cache_router
# from backend.api.chat_stream import router as chat_stream_router  # V2로 대체됨
from backend.api.chat_router import router as chat_router
from backend.common.errors import BaseError, ErrorKind

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ODOCAIagent API",
    description="오픈소스 저장소 진단 및 온보딩 에이전트 API",
    version="1.0.0",
)

# 전역 에러 핸들러
@app.exception_handler(BaseError)
async def base_error_handler(request: Request, exc: BaseError):
    """BaseError (모든 커스텀 에러) 핸들러."""
    exc.log(level="warning" if exc.http_status < 500 else "error")
    
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """예상치 못한 예외 핸들러."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method}
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "kind": ErrorKind.INTERNAL_ERROR.value,
            "suggested_action": "abort",
        },
    )


# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 기본 포트
        "http://localhost:5174",  # Vite 대체 포트
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(api_router)
app.include_router(sse_router)
app.include_router(cache_router)
app.include_router(chat_router)  # 세션 기반 채팅 API


@app.get("/")
async def root():
    """루트 엔드포인트."""
    return {
        "service": "ODOCAIagent",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "analyze": "POST /api/analyze",
            "analyze_stream": "GET /api/analyze/stream",
            "chat": "POST /api/chat",
            "chat_stream": "POST /api/chat/stream",
            "agent_task": "POST /api/agent/task",
            "health": "GET /api/health",
            "cache_stats": "GET /api/cache/stats",
            "cache_invalidate": "POST /api/cache/invalidate",
        }
    }

