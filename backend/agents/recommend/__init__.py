"""
Onboarding Agent v0

User → Agent → 여러 Tool → 추천/계획 구조.

주요 함수:
- run_onboarding_agent: 메인 진입점
- quick_recommend: 단순화된 인터페이스
"""
from .service import run_onboarding_agent, quick_recommend
from .models import UserContext, CandidateRepo, RepoRecommendation, OnboardingAgentResult

__all__ = [
    # 서비스
    "run_onboarding_agent",
    "quick_recommend",
    # 모델
    "UserContext",
    "CandidateRepo",
    "RepoRecommendation",
    "OnboardingAgentResult",
]
