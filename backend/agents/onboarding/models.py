"""Onboarding Agent 데이터 모델."""
from typing import Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
UserGoal = Literal["first_pr", "docs", "bugfix", "feature"]
ToolMode = Literal["guide", "curriculum", "both"]


# === 공통 컨텍스트 DTO (Unified Onboarding) ===

class DocsIndex(TypedDict):
    """프로젝트 문서 인덱스"""
    readme: Optional[str]           # README.md 요약
    contributing: Optional[str]     # CONTRIBUTING.md 요약
    code_of_conduct: Optional[str]
    security: Optional[str]
    templates: List[str]            # .github/ISSUE_TEMPLATE, PR_TEMPLATE 등 경로
    file_paths: Dict[str, str]      # 문서명 -> 실제 경로


class WorkflowHints(TypedDict):
    """기여 워크플로우 힌트"""
    fork_required: bool
    branch_convention: Optional[str]    # 예: "feature/xxx"
    commit_convention: Optional[str]    # 예: "Conventional Commits"
    test_command: Optional[str]         # 예: "npm test"
    build_command: Optional[str]        # 예: "npm run build"
    ci_present: bool
    review_process: Optional[str]


class CodeMap(TypedDict):
    """코드 구조 맵"""
    main_directories: List[str]         # 예: ["src/", "lib/", "tests/"]
    entry_points: List[str]             # 예: ["main.py", "index.js"]
    language: str                       # Primary language
    package_manager: Optional[str]      # 예: "npm", "pip", "cargo"


class OnboardingContext(TypedDict):
    """온보딩 에이전트 공통 컨텍스트"""
    owner: str
    repo: str
    ref: str
    docs_index: DocsIndex
    workflow_hints: WorkflowHints
    code_map: CodeMap
    # 캐시 메타
    cached_at: Optional[str]
    cache_ttl_seconds: int


# === LangGraph State 정의 ===
class OnboardingState(TypedDict):
    """Onboarding Agent LangGraph State"""
    
    # 입력 필드
    owner: str
    repo: str
    ref: str
    experience_level: ExperienceLevel
    diagnosis_summary: str
    user_context: Dict[str, Any]
    user_message: Optional[str]
    
    # 처리 중 필드
    candidate_issues: Optional[List[Dict[str, Any]]]
    plan: Optional[List[Dict[str, Any]]]
    summary: Optional[str]
    
    # 컨텍스트 필드 (이전 플랜 참조용)
    previous_plan: Optional[List[Dict[str, Any]]]
    previous_summary: Optional[str]
    
    # 에이전트 분석 필드 (Core Scoring 연동)
    diagnosis_analysis: Optional[Dict[str, Any]]  # health_score, onboarding_score 등
    onboarding_risks: Optional[List[Dict[str, Any]]]  # 경험 수준별 리스크
    plan_config: Optional[Dict[str, Any]]  # 플랜 설정 (weeks, issues_per_week 등)
    agent_decision: Optional[Dict[str, Any]]  # 에이전트 결정 로그
    
    # 추천 관련 필드 (Recommend 에이전트 통합)
    similar_projects: Optional[List[Dict[str, Any]]]  # 유사 프로젝트 추천 결과
    include_recommendations: bool  # 추천 포함 여부 (기본값: True)
    
    # 결과 필드
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_path: Optional[str]


class OnboardingInput(BaseModel):
    """온보딩 가이드 입력 모델."""
    owner: str = Field(..., description="저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    experience_level: ExperienceLevel = Field(default="beginner", description="사용자 경험 수준")
    diagnosis_summary: str = Field(default="", description="진단 요약 (있으면)")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="사용자 컨텍스트")


class WeeklyPlan(BaseModel):
    """주차별 온보딩 계획."""
    week: int
    title: str
    description: str
    tasks: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)


class CandidateIssue(BaseModel):
    """추천 이슈."""
    number: int
    title: str
    url: str
    labels: List[str] = Field(default_factory=list)


class OnboardingOutput(BaseModel):
    """온보딩 가이드 출력 모델."""
    repo_id: str = Field(default="", description="저장소 식별자")
    experience_level: ExperienceLevel = Field(default="beginner")
    plan: List[Dict[str, Any]] = Field(default_factory=list, description="주차별 계획")
    candidate_issues: List[Dict[str, Any]] = Field(default_factory=list, description="추천 이슈")
    summary: str = Field(default="", description="온보딩 요약")
    error: Optional[str] = Field(default=None, description="에러 메시지")


# === 추천 에이전트 모델 (recommend에서 통합) ===

from dataclasses import dataclass, field, asdict


@dataclass
class UserContext:
    """사용자 컨텍스트 (언어, 경험, 스택, 목표)."""
    target_language: str = "ko"  # "ko" | "en"
    experience_level: str = "beginner"  # "beginner" | "intermediate" | "advanced"
    
    # 기술 스택 선호도
    preferred_stack: List[str] = field(default_factory=list)  # ["python", "react", "go"]
    
    # 시간 가용성
    available_hours_per_week: int = 5  # 주당 투자 가능 시간
    
    # 기여 목표
    goal: str = "첫 PR 경험"  # "첫 PR 경험" | "장기 기여" | "학습 목적"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserContext":
        return cls(
            target_language=data.get("target_language", "ko"),
            experience_level=data.get("experience_level", "beginner"),
            preferred_stack=data.get("preferred_stack", []),
            available_hours_per_week=data.get("available_hours_per_week", 5),
            goal=data.get("goal", "첫 PR 경험"),
        )


@dataclass
class CandidateRepo:
    """후보 저장소"""
    owner: str
    repo: str
    
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {"owner": self.owner, "repo": self.repo, "full_name": self.full_name}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateRepo":
        if "full_name" in data and "/" in data["full_name"]:
            owner, repo = data["full_name"].split("/", 1)
            return cls(owner=owner, repo=repo)
        return cls(owner=data["owner"], repo=data["repo"])
    
    @classmethod
    def from_string(cls, full_name: str) -> "CandidateRepo":
        """문자열에서 생성 (e.g., 'owner/repo')"""
        if "/" not in full_name:
            raise ValueError(f"Invalid repo format: {full_name}. Expected 'owner/repo'.")
        owner, repo = full_name.split("/", 1)
        return cls(owner=owner, repo=repo)


@dataclass
class RepoRecommendation:
    """단일 저장소 추천 결과"""
    
    # 저장소 정보
    repo: str  # "owner/repo" 형식
    
    # 추천 이유 (규칙 기반으로 생성)
    reason: str
    
    # 추천 점수 (0-100)
    match_score: int
    
    # 매칭 상세
    matched_stack: List[str] = field(default_factory=list)  # 매칭된 기술 스택
    
    # 진단 결과 요약
    health_level: str = "warning"  # "good" | "warning" | "bad"
    onboarding_level: str = "normal"  # "easy" | "normal" | "hard"
    
    # 온보딩 계획 (diagnosis에서 가져옴)
    onboarding_plan: Dict[str, Any] = field(default_factory=dict)
    
    # 원본 진단 결과 (선택적 포함)
    diagnosis_summary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # None인 diagnosis_summary는 제외
        if result.get("diagnosis_summary") is None:
            del result["diagnosis_summary"]
        return result


@dataclass
class OnboardingAgentResult:
    """Onboarding Agent 전체 결과 (추천 + 온보딩)"""
    
    # 입력 정보
    user_context: Dict[str, Any] = field(default_factory=dict)
    candidate_repos: List[str] = field(default_factory=list)  # ["owner/repo", ...]
    
    # 추천 결과 (TOP N)
    recommendations: List[RepoRecommendation] = field(default_factory=list)
    
    # 진단 실패한 저장소
    failed_repos: List[Dict[str, str]] = field(default_factory=list)  # [{"repo": "...", "error": "..."}]
    
    # 자연어 요약 (LLM 생성)
    natural_language_summary: str = ""
    
    # 메타 정보
    total_diagnosed: int = 0
    total_recommended: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_context": self.user_context,
            "candidate_repos": self.candidate_repos,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "failed_repos": self.failed_repos,
            "natural_language_summary": self.natural_language_summary,
            "meta": {
                "total_diagnosed": self.total_diagnosed,
                "total_recommended": self.total_recommended,
            },
        }

