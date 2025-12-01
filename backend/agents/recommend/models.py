"""Onboarding Agent v0 - 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional


# ============================================================
# 입력 스키마
# ============================================================

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


# ============================================================
# 출력 스키마
# ============================================================

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
    """Onboarding Agent 전체 결과"""
    
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
