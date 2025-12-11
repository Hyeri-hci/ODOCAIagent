"""Comparison Agent 데이터 모델."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


# === LangGraph State 정의 ===
class ComparisonState(TypedDict):
    """Comparison Agent LangGraph State"""
    
    # 입력 필드
    repos: List[str]  # ["owner/repo", ...]
    ref: str
    use_cache: bool
    user_message: Optional[str]
    
    # 처리 중 필드
    validated_repos: Optional[List[str]]
    batch_results: Optional[Dict[str, Any]]
    comparison_data: Optional[List[Dict[str, Any]]]
    
    # 에이전트 분석 필드 (Core Scoring 연동)
    agent_analysis: Optional[Dict[str, Any]]  # 강점 분석, 추천 등
    
    # 캐시 관련
    cache_hits: Optional[List[str]]
    cache_misses: Optional[List[str]]
    warnings: Optional[List[str]]
    
    # 결과 필드
    comparison_summary: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_path: Optional[str]


class ComparisonInput(BaseModel):
    """비교 분석 입력 모델."""
    repos: List[str] = Field(default_factory=list, description="비교할 저장소 목록 (owner/repo 형식)")
    ref: str = Field(default="main", description="분석할 브랜치/태그")
    use_cache: bool = Field(default=True, description="캐시 사용 여부")


class ComparisonResult(BaseModel):
    """단일 저장소 비교 결과."""
    repo: str
    health_score: int = 0
    onboarding_score: int = 0
    docs_score: int = 0
    activity_score: int = 0
    health_level: str = "unknown"
    onboarding_level: str = "unknown"
    summary: str = ""
    readme_exists: bool = False
    contributing_exists: bool = False


class ComparisonOutput(BaseModel):
    """비교 분석 출력 모델."""
    results: Dict[str, Any] = Field(default_factory=dict, description="각 저장소별 분석 결과")
    comparison_summary: str = Field(default="", description="LLM 비교 요약")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지")
    cache_hits: List[str] = Field(default_factory=list, description="캐시 히트된 저장소")
    cache_misses: List[str] = Field(default_factory=list, description="캐시 미스된 저장소")
