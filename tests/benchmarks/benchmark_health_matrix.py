"""
1-1. Health / Onboarding / CHAOSS 규칙 벤치마크

사용 함수: chaoss_metrics.py + health_score.py + compute_onboarding_tasks
입력: 카테고리 라벨이 붙은 레포 집합
측정:
  - documentation_quality, activity_maintainability, health_score, onboarding_score, is_healthy
  - 카테고리별 평균, is_healthy 정확도

통과 기준:
  - 평균 Health: very_active > active > small > archived/deprecated
  - is_healthy가 archived/deprecated에서 80% 이상 False

사용법:
    python test/benchmarks/benchmark_health_matrix.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

from test.benchmarks.config import BENCHMARK_REPOS, RepoCategory, RepoInfo
from test.benchmarks.utils import BenchmarkResult, compute_category_stats, print_pass_fail


def run_health_diagnosis(repo: RepoInfo) -> BenchmarkResult:
    """단일 레포에 대해 규칙 기반 진단 (LLM 미사용)"""
    from backend.agents.diagnosis.tools.scoring.health_score import create_health_score
    from backend.agents.diagnosis.tools.scoring.activity_scores import activity_score_to_100, aggregate_activity_score
    from backend.agents.diagnosis.tools.scoring.chaoss_metrics import (
        compute_commit_activity, compute_issue_activity, compute_pr_activity
    )
    from backend.agents.diagnosis.tools.readme.readme_categories import classify_readme_sections
    from backend.agents.diagnosis.tools.readme.readme_loader import fetch_readme_content
    from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import compute_onboarding_tasks
    
    start = time.time()
    
    try:
        # README 점수
        readme_text = fetch_readme_content(repo.owner, repo.repo) or ""
        if readme_text:
            _, doc_score, _ = classify_readme_sections(
                readme_text, 
                use_llm_refine=False, 
                enable_semantic_summary=False,
                advanced_mode=False
            )
        else:
            doc_score = 0
        
        # Activity 점수
        commit = compute_commit_activity(repo.owner, repo.repo, days=365)
        issue = compute_issue_activity(repo.owner, repo.repo, days=365)
        pr = compute_pr_activity(repo.owner, repo.repo, days=365)
        activity_breakdown = aggregate_activity_score(commit, issue, pr)
        activity_score = activity_score_to_100(activity_breakdown)
        
        # Health Score 계산
        scores = create_health_score(doc_score, activity_score)
        
        # Labels
        health_level = "good" if scores.is_healthy else ("warning" if scores.health_score >= 40 else "bad")
        onboarding_level = "easy" if scores.onboarding_score >= 70 else ("normal" if scores.onboarding_score >= 40 else "hard")
        
        labels = {
            "health_level": health_level,
            "activity_issues": [],
            "docs_issues": [],
        }
        
        # Task 생성
        tasks = compute_onboarding_tasks(repo.owner, repo.repo, labels, max_issues=20, min_tasks=3)
        
        # Task 통계
        all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
        task_count = len(all_tasks)
        
        def kind_ratio(kind: str) -> float:
            return sum(1 for t in all_tasks if t.kind == kind) / task_count if task_count else 0
        
        def intent_ratio(intent: str) -> float:
            return sum(1 for t in all_tasks if t.intent == intent) / task_count if task_count else 0
        
        return BenchmarkResult(
            repo_owner=repo.owner,
            repo_name=repo.repo,
            category=repo.category.value,
            health_score=scores.health_score,
            onboarding_score=scores.onboarding_score,
            documentation_score=doc_score,
            activity_score=activity_score,
            health_level=health_level,
            onboarding_level=onboarding_level,
            is_healthy=scores.is_healthy,
            task_count=task_count,
            beginner_count=len(tasks.beginner),
            intermediate_count=len(tasks.intermediate),
            advanced_count=len(tasks.advanced),
            docs_kind_ratio=kind_ratio("doc"),
            test_kind_ratio=kind_ratio("test"),
            issue_kind_ratio=kind_ratio("issue"),
            meta_kind_ratio=kind_ratio("meta"),
            contribute_intent_ratio=intent_ratio("contribute"),
            study_intent_ratio=intent_ratio("study"),
            evaluate_intent_ratio=intent_ratio("evaluate"),
            execution_time_sec=time.time() - start,
        )
        
    except Exception as e:
        return BenchmarkResult(
            repo_owner=repo.owner,
            repo_name=repo.repo,
            category=repo.category.value,
            execution_time_sec=time.time() - start,
            error=str(e),
        )


def run_health_matrix_benchmark(repos: List[RepoInfo] = None, verbose: bool = True) -> Dict[str, Any]:
    """Health Matrix 벤치마크 실행"""
    if repos is None:
        repos = BENCHMARK_REPOS
    
    if verbose:
        print("\n" + "=" * 60)
        print("1-1. Health / Onboarding Matrix Benchmark")
        print("=" * 60)
    
    results: List[BenchmarkResult] = []
    
    for i, repo in enumerate(repos):
        if verbose:
            print(f"\n[{i+1}/{len(repos)}] {repo.owner}/{repo.repo} ({repo.category.value})")
        
        result = run_health_diagnosis(repo)
        results.append(result)
        
        if verbose:
            if result.error:
                print(f"  ERROR: {result.error}")
            else:
                print(f"  Health: {result.health_score:.0f}, Onboarding: {result.onboarding_score:.0f}")
                print(f"  is_healthy: {result.is_healthy}, Tasks: {result.task_count}")
    
    # 카테고리별 통계
    categories = ["very_active", "active", "small", "archived", "deprecated"]
    stats = {cat: compute_category_stats(results, cat) for cat in categories}
    
    # 통과 기준 검증
    checks = {}
    
    # 1. 평균 Health 단조성: very_active > active > small > archived
    health_order = [stats.get(c, {}).get("avg_health", 0) for c in ["very_active", "active", "small", "archived"]]
    health_monotonic = all(health_order[i] >= health_order[i+1] for i in range(len(health_order)-1) if health_order[i] and health_order[i+1])
    checks["health_monotonicity"] = health_monotonic
    
    # 2. is_healthy가 archived/deprecated에서 80% 이상 False
    inactive_results = [r for r in results if r.category in ("archived", "deprecated") and r.is_healthy is not None]
    if inactive_results:
        unhealthy_ratio = sum(1 for r in inactive_results if not r.is_healthy) / len(inactive_results)
        checks["inactive_unhealthy_ratio"] = unhealthy_ratio >= 0.8
        checks["inactive_unhealthy_value"] = unhealthy_ratio
    else:
        checks["inactive_unhealthy_ratio"] = True  # 해당 데이터 없음
    
    # 3. 활성 프로젝트에서 is_healthy=True 비율
    active_results = [r for r in results if r.category in ("very_active", "active") and r.is_healthy is not None]
    if active_results:
        healthy_ratio = sum(1 for r in active_results if r.is_healthy) / len(active_results)
        checks["active_healthy_ratio"] = healthy_ratio >= 0.6
        checks["active_healthy_value"] = healthy_ratio
    
    # 결과 요약
    pass_count = sum(1 for k, v in checks.items() if not k.endswith("_value") and v)
    total_checks = sum(1 for k in checks if not k.endswith("_value"))
    
    summary = {
        "total_repos": len(results),
        "successful_repos": sum(1 for r in results if r.error is None),
        "category_stats": stats,
        "checks": checks,
        "pass_rate": pass_count / total_checks if total_checks else 0,
        "monotonicity_rate": 1.0 if checks.get("health_monotonicity", False) else 0.0,
        "healthy_accuracy": checks.get("active_healthy_value", 0),
        "passed": pass_count == total_checks,
    }
    
    if verbose:
        print("\n" + "-" * 40)
        print("Summary:")
        for cat, s in stats.items():
            if s:
                print(f"  {cat}: avg_health={s.get('avg_health', 0):.1f}, is_healthy={s.get('is_healthy_ratio', 0):.1%}")
        
        print("\nChecks:")
        print_pass_fail(checks.get("health_monotonicity", False), "Health monotonicity")
        print_pass_fail(checks.get("inactive_unhealthy_ratio", False), 
                       f"Inactive unhealthy >= 80%: {checks.get('inactive_unhealthy_value', 0):.1%}")
        print_pass_fail(checks.get("active_healthy_ratio", False),
                       f"Active healthy >= 60%: {checks.get('active_healthy_value', 0):.1%}")
        
        print(f"\nPass Rate: {summary['pass_rate']:.1%}")
    
    return summary


if __name__ == "__main__":
    run_health_matrix_benchmark()



