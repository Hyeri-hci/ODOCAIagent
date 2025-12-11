"""
Performance Metrics 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any

router = APIRouter()


class MetricsResponse(BaseModel):
    """성능 메트릭 응답."""
    summary: dict[str, Any] = Field(..., description="메트릭 요약")
    recent_tasks: list[dict[str, Any]] = Field(default_factory=list, description="최근 작업 목록")


class MetricsSummaryResponse(BaseModel):
    """메트릭 요약 응답."""
    task_count: int = Field(..., ge=0, description="총 작업 수")
    avg_duration: float = Field(..., ge=0, description="평균 실행 시간 (초)")
    success_rate: float = Field(..., ge=0, le=1, description="성공률 (0-1)")
    agent_stats: dict[str, Any] = Field(default_factory=dict, description="에이전트별 통계")


@router.get("/admin/metrics", response_model=MetricsResponse)
async def get_performance_metrics(limit: int = 50) -> MetricsResponse:
    """
    성능 메트릭 조회.
    
    Args:
        limit: 조회할 최근 작업 수 (기본값: 50)
    
    Returns:
        MetricsResponse: 메트릭 요약 및 최근 작업 목록
    """
    from backend.common.metrics import get_metrics_tracker
    
    tracker = get_metrics_tracker()
    return MetricsResponse(
        summary=tracker.get_summary(),
        recent_tasks=tracker.get_recent_metrics(limit=limit),
    )


@router.get("/admin/metrics/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary() -> MetricsSummaryResponse:
    """
    메트릭 요약 조회.
    
    Returns:
        MetricsSummaryResponse: 집계된 메트릭 정보
    """
    from backend.common.metrics import get_metrics_tracker
    
    tracker = get_metrics_tracker()
    summary = tracker.get_summary()
    return MetricsSummaryResponse(
        task_count=summary.get("task_count", 0),
        avg_duration=summary.get("avg_duration", 0.0),
        success_rate=summary.get("success_rate", 0.0),
        agent_stats=summary.get("agent_stats", {}),
    )
