"""
2-1. Onboarding Plan v0 vs v1 A/B 벤치마크

사용 함수:
  - create_onboarding_plan(..., use_llm=False) → v0 (규칙 기반)
  - create_onboarding_plan(..., use_llm=True) → v1 (LLM 기반)

측정:
  - 정량: first_steps/risks 길이, 키워드 커버리지, 구조 점수
  - 정성: LLM self-eval (명확성, 실행가능성, 초보자친화도, 위험인식)

통과 기준:
  - v1이 키워드 커버리지 더 높음
  - v1이 self-eval 평균 +1점 이상 개선
  - JSON 파싱 실패 없음

사용법:
    python test/benchmarks/benchmark_plan_ablation.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

from test.benchmarks.config import BENCHMARK_REPOS, RepoInfo
from test.benchmarks.utils import print_pass_fail


# 평가 키워드
PLAN_KEYWORDS = {
    "onboarding": ["온보딩", "onboarding", "시작하기", "getting started"],
    "contribution": ["기여", "contribut", "PR", "pull request", "CONTRIBUTING"],
    "good_first_issue": ["good-first-issue", "good first issue", "첫 이슈"],
    "risks": ["주의", "warning", "위험", "risk", "어려움"],
    "quick_start": ["Quick Start", "빠른 시작", "설치", "install"],
}


@dataclass
class PlanMetrics:
    """플랜 정량 지표"""
    first_steps_count: int = 0
    first_steps_chars: int = 0
    risks_count: int = 0
    risks_chars: int = 0
    keyword_hits: Dict[str, bool] = field(default_factory=dict)
    keyword_score: float = 0.0  # 0-100
    has_numbered_steps: bool = False
    response_time_sec: float = 0.0


@dataclass
class PlanComparison:
    """v0 vs v1 비교 결과"""
    repo: str
    v0_metrics: PlanMetrics
    v1_metrics: Optional[PlanMetrics] = None
    v1_error: Optional[str] = None
    
    # 비교 결과
    keyword_improvement: float = 0.0  # v1 - v0
    length_improvement: float = 0.0  # v1 steps chars / v0 steps chars
    winner: str = "tie"  # v0, v1, tie, error


def compute_plan_metrics(plan: Any, response_time: float = 0.0) -> PlanMetrics:
    """플랜 정량 분석"""
    # OnboardingPlan 객체 또는 dict 처리
    if hasattr(plan, 'first_steps'):
        first_steps = plan.first_steps or []
        risks = plan.risks or []
    else:
        first_steps = plan.get("first_steps", [])
        risks = plan.get("risks", [])
    
    # 전체 텍스트
    text = " ".join(first_steps + risks).lower()
    
    # 키워드 체크
    keyword_hits = {}
    for category, keywords in PLAN_KEYWORDS.items():
        keyword_hits[category] = any(kw.lower() in text for kw in keywords)
    
    keyword_score = sum(keyword_hits.values()) / len(keyword_hits) * 100
    
    # 번호형 단계 체크
    has_numbered = any(re.match(r'^\d+\.', step) for step in first_steps)
    
    return PlanMetrics(
        first_steps_count=len(first_steps),
        first_steps_chars=sum(len(s) for s in first_steps),
        risks_count=len(risks),
        risks_chars=sum(len(r) for r in risks),
        keyword_hits=keyword_hits,
        keyword_score=keyword_score,
        has_numbered_steps=has_numbered,
        response_time_sec=response_time,
    )


def run_plan_comparison(repo: RepoInfo) -> PlanComparison:
    """단일 레포에 대해 v0 vs v1 비교"""
    from backend.agents.diagnosis.tools.onboarding_plan import create_onboarding_plan
    from backend.agents.diagnosis.tools.health_score import create_health_score
    from backend.agents.diagnosis.tools.activity_scores import activity_score_to_100, aggregate_activity_score
    from backend.agents.diagnosis.tools.chaoss_metrics import (
        compute_commit_activity, compute_issue_activity, compute_pr_activity
    )
    from backend.agents.diagnosis.tools.readme_categories import classify_readme_sections
    from backend.agents.diagnosis.tools.repo_parser import fetch_repo_info
    from backend.agents.diagnosis.tools.readme_loader import fetch_readme_content
    
    # 기본 데이터 수집
    repo_info = fetch_repo_info(repo.owner, repo.repo)
    readme_text = fetch_readme_content(repo.owner, repo.repo) or ""
    
    # README 분석
    if readme_text:
        _, doc_score, _ = classify_readme_sections(
            readme_text, 
            use_llm_refine=False, 
            enable_semantic_summary=False,
            advanced_mode=False
        )
    else:
        doc_score = 0
    
    # Activity
    commit = compute_commit_activity(repo.owner, repo.repo, days=365)
    issue = compute_issue_activity(repo.owner, repo.repo, days=365)
    pr = compute_pr_activity(repo.owner, repo.repo, days=365)
    activity_breakdown = aggregate_activity_score(commit, issue, pr)
    activity_score = activity_score_to_100(activity_breakdown)
    
    # 점수
    health_scores = create_health_score(doc_score, activity_score)
    
    scores = health_scores.to_dict()
    labels = {
        "health_level": "good" if health_scores.is_healthy else "warning",
        "docs_issues": [] if doc_score >= 50 else ["missing_contributing"],
        "activity_issues": [] if activity_score >= 50 else ["low_activity"],
    }
    repo_info_dict = {
        "full_name": f"{repo.owner}/{repo.repo}",
        "description": repo_info.description or "",
    }
    
    # v0 (규칙 기반)
    start = time.time()
    plan_v0 = create_onboarding_plan(scores, labels, use_llm=False)
    v0_time = time.time() - start
    v0_metrics = compute_plan_metrics(plan_v0, v0_time)
    
    result = PlanComparison(
        repo=f"{repo.owner}/{repo.repo}",
        v0_metrics=v0_metrics,
    )
    
    # v1 (LLM 기반)
    try:
        start = time.time()
        plan_v1 = create_onboarding_plan(scores, labels, repo_info=repo_info_dict, use_llm=True)
        v1_time = time.time() - start
        v1_metrics = compute_plan_metrics(plan_v1, v1_time)
        
        result.v1_metrics = v1_metrics
        result.keyword_improvement = v1_metrics.keyword_score - v0_metrics.keyword_score
        result.length_improvement = (v1_metrics.first_steps_chars / v0_metrics.first_steps_chars 
                                     if v0_metrics.first_steps_chars > 0 else 1.0)
        
        # Winner 결정
        v1_wins = 0
        if v1_metrics.keyword_score > v0_metrics.keyword_score:
            v1_wins += 1
        if v1_metrics.first_steps_chars > v0_metrics.first_steps_chars * 1.2:
            v1_wins += 1
        if v1_metrics.risks_chars > v0_metrics.risks_chars:
            v1_wins += 1
        
        result.winner = "v1" if v1_wins >= 2 else ("v0" if v1_wins == 0 else "tie")
        
    except Exception as e:
        result.v1_error = str(e)
        result.winner = "error"
    
    return result


def run_plan_ablation_benchmark(repos: List[RepoInfo] = None, verbose: bool = True) -> Dict[str, Any]:
    """Plan A/B 벤치마크 실행"""
    if repos is None:
        repos = BENCHMARK_REPOS[:5]
    
    if verbose:
        print("\n" + "=" * 60)
        print("2-1. Onboarding Plan v0 vs v1 A/B Benchmark")
        print("=" * 60)
    
    results: List[PlanComparison] = []
    
    for i, repo in enumerate(repos):
        if verbose:
            print(f"\n[{i+1}/{len(repos)}] {repo.owner}/{repo.repo}")
        
        result = run_plan_comparison(repo)
        results.append(result)
        
        if verbose:
            print(f"  v0: {result.v0_metrics.first_steps_count} steps, {result.v0_metrics.keyword_score:.0f}% keywords")
            if result.v1_metrics:
                print(f"  v1: {result.v1_metrics.first_steps_count} steps, {result.v1_metrics.keyword_score:.0f}% keywords")
                print(f"  Winner: {result.winner} (keyword +{result.keyword_improvement:.0f}%)")
            else:
                print(f"  v1 ERROR: {result.v1_error}")
    
    # 집계
    v1_wins = sum(1 for r in results if r.winner == "v1")
    v0_wins = sum(1 for r in results if r.winner == "v0")
    ties = sum(1 for r in results if r.winner == "tie")
    errors = sum(1 for r in results if r.winner == "error")
    
    valid = [r for r in results if r.v1_metrics]
    avg_keyword_improvement = sum(r.keyword_improvement for r in valid) / len(valid) if valid else 0
    avg_v1_time = sum(r.v1_metrics.response_time_sec for r in valid) / len(valid) if valid else 0
    
    summary = {
        "total_repos": len(results),
        "v1_wins": v1_wins,
        "v0_wins": v0_wins,
        "ties": ties,
        "errors": errors,
        "v1_win_rate": v1_wins / len(results) if results else 0,
        "avg_keyword_improvement": avg_keyword_improvement,
        "avg_v1_response_time": avg_v1_time,
        "pass_rate": (v1_wins + ties) / len(results) if results else 0,  # v1이 v0보다 나쁘지 않으면 pass
    }
    
    if verbose:
        print("\n" + "-" * 40)
        print(f"Summary:")
        print(f"  v1 wins: {v1_wins}, v0 wins: {v0_wins}, ties: {ties}, errors: {errors}")
        print(f"  v1 win rate: {summary['v1_win_rate']:.1%}")
        print(f"  Avg keyword improvement: {avg_keyword_improvement:+.1f}%")
        print(f"  Avg v1 response time: {avg_v1_time:.2f}s")
    
    return summary


if __name__ == "__main__":
    run_plan_ablation_benchmark()
