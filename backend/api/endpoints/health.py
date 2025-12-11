"""
Health Check 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class HealthCheckResponse(BaseModel):
    """Health check 응답."""
    status: str = Field(..., description="서비스 상태", examples=["ok"])
    service: str = Field(..., description="서비스 이름", examples=["ODOCAIagent"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    API 상태 확인.
    
    Returns:
        HealthCheckResponse: 서비스 상태 정보
    """
    return HealthCheckResponse(status="ok", service="ODOCAIagent")
