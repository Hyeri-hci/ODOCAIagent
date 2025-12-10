# models/recommend_state.py

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field

class CandidateRepo(BaseModel):
    """
    RAG 검색 결과로 선정된 후보 리포지토리 스키마.
    State의 'search_results' 리스트에 들어갈 객체입니다.
    """
    # --- 1. GitHub 기본 정보 (Metadata) ---
    id: int = Field(..., description="GitHub Repository ID")
    name: str = Field(..., description="Repository Name (e.g., 'langchain')")
    owner: str = Field(..., description="Repository Owner")

    html_url: str = Field(..., description="GitHub URL")

    description: Optional[str] = Field(None, description="Project Description")

    main_language: str = Field("Unknown", description="Primary Language (e.g., Python)")
    language: List[str] = Field("Unknown", description="Languages")

    topics: List[str] = Field(default_factory=list, description="GitHub Topics")

    forks: int = Field(0, description="Forks Count")
    stars: int = Field(0, description="Stargazers Count")
    
    # --- 2. 검색/추천 근거 (RAG Result) ---
    score: float = Field(0.0, description="유사도 점수 (Rerank Score)")
    match_snippet: str = Field(..., description="검색 쿼리와 매칭된 핵심 텍스트 조각 (설명 또는 README 일부)")

    ai_score: int = Field(0, description="LLM evaluated relevance score (0-100)")
    ai_reason: str = Field(None, description="Reason why LLM recommends this project")

    class Config:
        # 딕셔너리에서 객체로 변환할 때 유연하게 처리
        from_attributes = True

class RecommendState(BaseModel):
    """추천 LangGraph 상태 모델."""

    # 진행 상태
    step: int = 0
    max_step: int = 4

    # 사용자의 의도
    user_intent: str = Field("", description="LLM이 분석한 사용자의 구체적인 의도 (예: '기능은 유지하되 언어만 변경된 프로젝트 탐색')")

    # 입력값
    repo_url: str
    owner: Optional[str] = None
    repo: Optional[str] = None
    user_request: str = ""
    ref: str = "main"

    # GitHub 스냅샷 (첫 단계에서 수집)
    repo_snapshot: Optional[Dict[str, Any]] = None

    # readme 요약
    readme_summary: Optional[Dict[str, Any]] = None

    # RAG 검색용 결과 저장소
    search_query: str = ""
    search_keywords: List[str] = []
    search_filters: Dict[str, Any] = {}

    search_results: List[CandidateRepo] = Field(default_factory=list)
    
    # 에러 및 복구
    error: Optional[str] = None
    failed_step: Optional[str] = None
    retry_count: int = 0
    max_retry: int = 2
    
    # 타이밍 정보
    timings: Dict[str, float] = {}