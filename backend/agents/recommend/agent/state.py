# models/recommend_state.py

from typing import Any, Dict, Optional, List
from pydantic import BaseModel

class RecommendState(BaseModel):
    """추천 LangGraph 상태 모델."""

    # 진행 상태
    step: int = 0
    max_step: int = 4

    # 입력값
    repo_url: str
    owner: Optional[str] = None
    repo: Optional[str] = None
    ref: str = "main"

    # GitHub 스냅샷 (첫 단계에서 수집)
    repo_snapshot: Optional[Dict[str, Any]] = None

    # readme 요약
    readme_summary: Optional[Dict[str, Any]] = None

    
    # 에러 및 복구
    error: Optional[str] = None
    failed_step: Optional[str] = None
    retry_count: int = 0
    max_retry: int = 2
    
    # 타이밍 정보
    timings: Dict[str, float] = {}