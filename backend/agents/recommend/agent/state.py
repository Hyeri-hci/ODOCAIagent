# models/recommend_state.py

from typing import Any, Dict, Optional, List, Literal
from pydantic import BaseModel, Field, model_validator

class CandidateRepo(BaseModel):
    """
    RAG 검색 결과로 선정된 후보 리포지토리 스키마.
    State의 'search_results' 리스트에 들어갈 객체입니다.
    """
    # --- 1. GitHub 기본 정보 (Metadata) ---
    id: int = Field(0, description="GitHub Repository ID")
    name: str = Field(..., description="Repository Name (e.g., 'langchain')")
    owner: str = Field(..., description="Repository Owner")

    html_url: str = Field(..., description="GitHub URL")

    description: Optional[str] = Field(None, description="Project Description")

    main_language: str = Field("Unknown", description="Primary Language (e.g., Python)")
    languages: List[str] = Field("Unknown", description="Languages")

    topics: List[str] = Field(default_factory=list, description="GitHub Topics")

    forks: int = Field(0, description="Forks Count")
    stars: int = Field(0, description="Stargazers Count")
    
    # --- 2. 검색/추천 근거 (RAG Result) ---
    score: float = Field(0.0, description="유사도 점수 (Rerank Score)")
    match_snippet: str = Field(..., description="검색 쿼리와 매칭된 핵심 텍스트 조각 (설명 또는 README 일부)")

    ai_score: int = Field(0, description="LLM evaluated relevance score (0-100)")
    ai_reason: str = Field(None, description="Reason why LLM recommends this project")

    rank: int = Field(0, description="트렌드 순위 (TrendService 결과에만 채워짐)")
    stars_since: int = Field(0, description="해당 기간 동안 받은 스타 수 (TrendService 결과에만 채워짐)")

    class Config:
        # 딕셔너리에서 객체로 변환할 때 유연하게 처리
        from_attributes = True

# Metric 및 Operator의 허용된 값 목록
MetricName = Literal["ISSUE_COUNT", "COMMIT_ACTIVITY", "PR_VELOCITY", "STAR_COUNT", "AGE_DAYS", "CONTRIBUTOR_COUNT", "FORK_COUNT", "ISSUE_CLOSING_RATE", "RESPONSE_TIME_DAYS", "LAST_RELEASE_AGE_DAYS", "TREND_LANGUAGE", "TREND_SINCE"]
OperatorName = Literal["HIGH", "LOW", "ACTIVE", "INACTIVE", "GT", "LT", "EQ", "TIME_RANGE"]
SearchIntent = Literal["url_analysis", "semantic_search", "search_criteria", "trend_analysis"]

class QuantitativeCondition(BaseModel):
    metric: MetricName = Field(description="적용할 정량적 속성의 이름.")
    operator: OperatorName = Field(description="비교 연산자 (HIGH, LOW, GT, LT 등).")
    value: Optional[str] = Field(description="비교 대상 값 (예: '100', '90 days'). 추상적 연산자 사용 시 null.")

    @model_validator(mode='before')
    def validate_trend_since_value(cls, values):
        """
        metric이 TREND_SINCE일 때, value는 반드시 'daily', 'weekly', 'monthly' 중 하나여야 합니다.
        """
        if values.get('metric') == 'TREND_SINCE':
            allowed_values = ["past_24_hours", "past_week", "past_month", "past_3_months"]
            value = values.get('value')
            if value not in allowed_values:
                raise ValueError(
                    f"Metric 'TREND_SINCE'는 'value'로 {allowed_values} 중 하나만 허용합니다. (받은 값: '{value}')"
                )
        return values

# LLM 출력 스키마
class FocusedParsingResult(BaseModel):
    """
    LLM이 사용자 요청에서 핵심 의도 및 정량적 조건만을 추출한 결과 스키마.
    """
    user_intent: SearchIntent = Field(description="사용자 요청의 핵심 의도 분류.")
    quantitative_filters: List[QuantitativeCondition] = Field(description="정량적 필터 조건의 리스트.")

class FinalRecommendation(BaseModel):
    """
    최종 사용자 응답을 위한 스키마: 프로젝트 정보와 AI 분석 결과만 포함.
    (CandidateRepo에서 최종 필터링/평가 후 생성됨)
    """
    name: str = Field(..., description="프로젝트 이름")
    owner: str = Field(..., description="프로젝트 소유자")
    url: str = Field(..., description="GitHub URL")
    
    simple_summary: str = Field(..., description="프로젝트의 간결한 한 줄 요약 (사용자 요청 기반)")
    
    ai_score: int = Field(0, description="LLM 평가 점수 (0-100)")
    ai_reason: str = Field(..., description="LLM이 평가한 최종 추천 근거 (왜 이 프로젝트를 추천하는지)")

class RecommendState(BaseModel):
    """추천 LangGraph 상태 모델."""

    # 진행 상태
    step: int = 0
    max_step: int = 4

    # 사용자의 의도
    user_intent: str = Field("", description="LLM이 분석한 사용자의 구체적인 의도 (예: '기능은 유지하되 언어만 변경된 프로젝트 탐색')")
    quantitative_filters: List[QuantitativeCondition] = Field(default_factory=list, description="LLM이 사용자 요청에서 추출한 정량적 필터 조건 (Issue, Commit 등).")

    # 입력값
    repo_url: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None
    user_request: str = ""
    ref: str = "main"

    # GitHub 스냅샷 (첫 단계에서 수집)
    repo_snapshot: Optional[Dict[str, Any]] = None

    # readme 요약
    readme_summary: Optional[Dict[str, Any]] = None

    # RAG 검색 결과 저장소
    search_query: str = "" 
    search_keywords: List[str] = []
    search_filters: Optional[Dict[str, Any]] = None

    github_seach_query: Optional[Dict[str, Any]] = None

    search_results: List[CandidateRepo] = Field(default_factory=list)

    final_results: List[FinalRecommendation] = Field(default_factory=list, description="최종 사용자에게 보여줄 추천 결과 목록")
    
    # 에러 및 복구
    error: Optional[str] = None
    failed_step: Optional[str] = None
    retry_count: int = 0
    max_retry: int = 2
    
    # 타이밍 정보
    timings: Dict[str, float] = {}