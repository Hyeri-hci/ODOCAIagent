"""
Onboarding Agent v0 - 메인 서비스

User → Agent → 여러 Tool → 추천/계획 구조의 핵심 로직.

흐름:
1. 사용자 컨텍스트 + 후보 repo 리스트 입력
2. 각 repo에 대해 run_diagnosis(task_type='full') 병렬 호출
3. scores, labels, onboarding_plan 추출
4. 스코어링 규칙으로 TOP N 추천
5. LLM으로 자연어 요약 생성
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.common.parallel import run_parallel_safe
from backend.agents.diagnosis.service import run_diagnosis

from .models import (
    UserContext,
    CandidateRepo,
    RepoRecommendation,
    OnboardingAgentResult,
)
from .scoring import create_recommendation_from_diagnosis
from .llm_summarizer import generate_recommendation_summary

logger = logging.getLogger(__name__)

# 설정
DEFAULT_TOP_N = 3
USE_LLM_SUMMARY = True  # True: LLM 요약, False: 규칙 기반 요약


# ============================================================
# 진단 실행
# ============================================================

def diagnose_single_repo(owner: str, repo: str) -> Dict[str, Any]:
    """단일 repo 진단 실행."""
    payload = {
        "owner": owner,
        "repo": repo,
        "task_type": "full",
        "focus": [],
        "user_context": {},
        "advanced_analysis": False,  # 속도를 위해 기본 분석
    }
    return run_diagnosis(payload)


def diagnose_multiple_repos(
    candidates: List[CandidateRepo],
    max_workers: int = 3,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Exception]]:
    """
    여러 repo 병렬 진단.
    
    Returns:
        (성공 결과 딕셔너리, 실패 에러 딕셔너리)
    """
    if not candidates:
        return {}, {}
    
    # 병렬 작업 준비
    tasks = {
        candidate.full_name: (
            lambda c=candidate: diagnose_single_repo(c.owner, c.repo)
        )
        for candidate in candidates
    }
    
    logger.info("Starting diagnosis for %d repos...", len(candidates))
    results, errors = run_parallel_safe(tasks, max_workers=max_workers)
    logger.info("Diagnosis complete: %d success, %d failed", len(results) - len(errors), len(errors))
    
    # 에러가 발생한 결과는 None이므로 필터링
    successful_results = {k: v for k, v in results.items() if v is not None}
    
    return successful_results, errors


# ============================================================
# 추천 생성
# ============================================================

def rank_and_filter_recommendations(
    recommendations: List[RepoRecommendation],
    top_n: int = DEFAULT_TOP_N,
    min_score: int = 20,
) -> List[RepoRecommendation]:
    """
    추천 결과 정렬 및 필터링.
    
    Args:
        recommendations: 전체 추천 목록
        top_n: 상위 N개 반환
        min_score: 최소 점수 (이하는 제외)
    """
    # 최소 점수 필터
    filtered = [r for r in recommendations if r.match_score >= min_score]
    
    # 점수 내림차순 정렬
    sorted_recs = sorted(filtered, key=lambda r: r.match_score, reverse=True)
    
    # TOP N
    return sorted_recs[:top_n]


# ============================================================
# 메인 에이전트 함수
# ============================================================

def run_onboarding_agent(
    user_context: Dict[str, Any],
    candidate_repos: List[str],
    top_n: int = DEFAULT_TOP_N,
    use_llm_summary: bool = USE_LLM_SUMMARY,
    include_full_diagnosis: bool = False,
    max_workers: int = 3,
) -> Dict[str, Any]:
    """
    Onboarding Agent v0 메인 진입점.
    
    Args:
        user_context: 사용자 컨텍스트 딕셔너리
            {
                "target_language": "ko",
                "experience_level": "beginner",
                "preferred_stack": ["python", "react"],
                "available_hours_per_week": 5,
                "goal": "첫 PR 경험"
            }
        candidate_repos: 후보 저장소 리스트 ["owner/repo", ...]
        top_n: 상위 N개 추천
        use_llm_summary: LLM 요약 사용 여부
        include_full_diagnosis: 전체 진단 결과 포함 여부
        max_workers: 병렬 처리 워커 수
    
    Returns:
        OnboardingAgentResult.to_dict()
    """
    # 입력 파싱
    user_ctx = UserContext.from_dict(user_context)
    candidates = [CandidateRepo.from_string(repo) for repo in candidate_repos]
    
    if not candidates:
        result = OnboardingAgentResult(
            user_context=user_ctx.to_dict(),
            candidate_repos=candidate_repos,
            natural_language_summary="후보 저장소가 없습니다. 추천할 저장소를 입력해주세요.",
        )
        return result.to_dict()
    
    # Phase 1: 다중 repo 진단
    logger.info("Phase 1: Diagnosing %d repos...", len(candidates))
    diagnosis_results, diagnosis_errors = diagnose_multiple_repos(
        candidates=candidates,
        max_workers=max_workers,
    )
    
    # Phase 2: 추천 점수 계산
    logger.info("Phase 2: Computing recommendation scores...")
    all_recommendations: List[RepoRecommendation] = []
    
    for repo_name, diagnosis in diagnosis_results.items():
        try:
            recommendation = create_recommendation_from_diagnosis(
                repo_full_name=repo_name,
                diagnosis_result=diagnosis,
                user_context=user_ctx,
                include_full_diagnosis=include_full_diagnosis,
            )
            all_recommendations.append(recommendation)
        except Exception as e:
            logger.warning("Failed to create recommendation for %s: %s", repo_name, e)
            diagnosis_errors[repo_name] = e
    
    # Phase 3: 정렬 및 필터링
    logger.info("Phase 3: Ranking and filtering...")
    top_recommendations = rank_and_filter_recommendations(
        recommendations=all_recommendations,
        top_n=top_n,
    )
    
    # Phase 4: LLM 요약 생성
    logger.info("Phase 4: Generating summary...")
    summary = generate_recommendation_summary(
        user_context=user_ctx,
        recommendations=top_recommendations,
        use_llm=use_llm_summary,
    )
    
    # 결과 조립
    failed_repos = [
        {"repo": repo_name, "error": str(error)}
        for repo_name, error in diagnosis_errors.items()
    ]
    
    result = OnboardingAgentResult(
        user_context=user_ctx.to_dict(),
        candidate_repos=candidate_repos,
        recommendations=top_recommendations,
        failed_repos=failed_repos,
        natural_language_summary=summary,
        total_diagnosed=len(diagnosis_results),
        total_recommended=len(top_recommendations),
    )
    
    logger.info(
        "Onboarding Agent complete: %d diagnosed, %d recommended, %d failed",
        result.total_diagnosed,
        result.total_recommended,
        len(failed_repos),
    )
    
    return result.to_dict()


# ============================================================
# 편의 함수
# ============================================================

def quick_recommend(
    preferred_stack: List[str],
    candidate_repos: List[str],
    experience_level: str = "beginner",
    goal: str = "첫 PR 경험",
    top_n: int = 3,
) -> Dict[str, Any]:
    """
    빠른 추천을 위한 단순화된 인터페이스.
    
    예시:
        result = quick_recommend(
            preferred_stack=["python", "react"],
            candidate_repos=["facebook/react", "tensorflow/tensorflow"],
            experience_level="beginner",
            goal="첫 PR 경험",
        )
    """
    user_context = {
        "target_language": "ko",
        "experience_level": experience_level,
        "preferred_stack": preferred_stack,
        "available_hours_per_week": 5,
        "goal": goal,
    }
    
    return run_onboarding_agent(
        user_context=user_context,
        candidate_repos=candidate_repos,
        top_n=top_n,
        use_llm_summary=True,
    )
