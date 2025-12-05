"""
ODOCAIagent FastAPI 서버.

Usage:
    uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.http_router import router as api_router

app = FastAPI(
    title="ODOCAIagent API",
    description="오픈소스 저장소 진단 및 온보딩 에이전트 API",
    version="1.0.0",
)

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 기본 포트
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(api_router)


@app.get("/")
async def root():
    """루트 엔드포인트."""
    return {
        "service": "ODOCAIagent",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "analyze": "POST /api/analyze",
            "agent_task": "POST /api/agent/task",
            "health": "GET /api/health",
        }
    }
