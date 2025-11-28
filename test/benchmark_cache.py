"""캐시/병렬 처리 성능 벤치마크 스크립트"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, List, Any, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.common.cache import github_cache
from backend.common.github_client import (
    fetch_repo, fetch_readme, fetch_recent_commits,
    clear_repo_cache, clear_all_cache
)
from backend.agents.diagnosis.service import run_diagnosis
from backend.agents.diagnosis.tools.readme_loader import fetch_readme_content, compute_reademe_metrics
from backend.agents.diagnosis.tools.readme_categories import classify_readme_sections
from backend.agents.diagnosis.tools.chaoss_metrics import compute_commit_activity
from backend.agents.diagnosis.tools.health_score import aggregate_health_scores
from backend.common.parallel import run_parallel


@dataclass
class BenchmarkResult:
    name: str
    duration_ms: float
    cache_hit: bool = False
    label: str = ""  # cold/warm/advanced 등 구분용


def measure_time(func: Callable, name: str, cache_hit: bool = False, label: str = "") -> BenchmarkResult:
    """함수 실행 시간 측정"""
    start = time.perf_counter()
    func()
    end = time.perf_counter()
    return BenchmarkResult(
        name=name,
        duration_ms=(end - start) * 1000,
        cache_hit=cache_hit,
        label=label
    )


def benchmark_github_api(owner: str, repo: str) -> List[BenchmarkResult]:
    """GitHub API 캐시 성능 테스트"""
    results = []
    
    # 1. 캐시 비움 상태에서 첫 호출 (Cold)
    clear_repo_cache(owner, repo)
    
    results.append(measure_time(
        lambda: fetch_repo(owner, repo),
        "fetch_repo", cache_hit=False, label="cold"
    ))
    results.append(measure_time(
        lambda: fetch_readme(owner, repo),
        "fetch_readme", cache_hit=False, label="cold"
    ))
    results.append(measure_time(
        lambda: fetch_recent_commits(owner, repo, days=90),
        "fetch_commits", cache_hit=False, label="cold"
    ))
    
    # 2. 캐시 있는 상태에서 재호출 (Warm)
    results.append(measure_time(
        lambda: fetch_repo(owner, repo),
        "fetch_repo", cache_hit=True, label="warm"
    ))
    results.append(measure_time(
        lambda: fetch_readme(owner, repo),
        "fetch_readme", cache_hit=True, label="warm"
    ))
    results.append(measure_time(
        lambda: fetch_recent_commits(owner, repo, days=90),
        "fetch_commits", cache_hit=True, label="warm"
    ))
    
    return results


def benchmark_logic_only(owner: str, repo: str) -> List[BenchmarkResult]:
    """LLM 없이 순수 로직만 테스트 (GitHub API + 파싱/룰 기반 분석)"""
    results = []
    
    # 캐시 워밍업 (API 시간 제외하고 순수 로직만 측정하기 위해)
    fetch_repo(owner, repo)
    readme_text = fetch_readme_content(owner, repo)
    fetch_recent_commits(owner, repo, days=90)
    
    # 1. README 메트릭 계산 (파싱만)
    results.append(measure_time(
        lambda: compute_reademe_metrics(readme_text) if readme_text else None,
        "readme_metrics (parse)", label="logic"
    ))
    
    # 2. README 분류 - LLM 없이 룰 기반만
    results.append(measure_time(
        lambda: classify_readme_sections(readme_text, use_llm_refine=False, enable_semantic_summary=False) if readme_text else None,
        "readme_classify (rule-only)", label="logic"
    ))
    
    # 3. 커밋 활동 분석
    commit_metrics = None
    def measure_commit():
        nonlocal commit_metrics
        commit_metrics = compute_commit_activity(owner, repo, days=90)
    
    results.append(measure_time(
        measure_commit,
        "commit_activity", label="logic"
    ))
    
    # 4. 헬스 스코어 계산
    readme_stats = compute_reademe_metrics(readme_text) if readme_text else None
    has_readme = readme_text is not None
    
    results.append(measure_time(
        lambda: aggregate_health_scores(has_readme, commit_metrics, readme_stats),
        "health_score", label="logic"
    ))
    
    return results


def benchmark_parallel_vs_sequential(owner: str, repo: str) -> List[BenchmarkResult]:
    """병렬 vs 순차 실행 비교 테스트 (GitHub API 호출)"""
    results = []
    
    # 1. 순차 실행 (캐시 비움)
    clear_repo_cache(owner, repo)
    
    def run_sequential():
        fetch_repo(owner, repo)
        fetch_readme(owner, repo)
        fetch_recent_commits(owner, repo, days=90)
    
    results.append(measure_time(
        run_sequential,
        "GitHub API (sequential)", label="sequential"
    ))
    
    # 2. 병렬 실행 (캐시 비움)
    clear_repo_cache(owner, repo)
    
    def run_parallel_api():
        tasks = {
            "repo": lambda: fetch_repo(owner, repo),
            "readme": lambda: fetch_readme(owner, repo),
            "commits": lambda: fetch_recent_commits(owner, repo, days=90),
        }
        return run_parallel(tasks)
    
    results.append(measure_time(
        run_parallel_api,
        "GitHub API (parallel)", label="parallel"
    ))
    
    # 3. 순차 + README 분류 (캐시 워밍업 후)
    fetch_repo(owner, repo)
    readme_text = fetch_readme_content(owner, repo)
    fetch_recent_commits(owner, repo, days=90)
    
    def run_sequential_with_classify():
        # API는 캐시 히트, 분류 로직만 측정
        clear_repo_cache(owner, repo)
        repo_data = fetch_repo(owner, repo)
        readme_raw = fetch_readme(owner, repo)
        commits = fetch_recent_commits(owner, repo, days=90)
        # README 분류 (LLM 없이)
        if readme_text:
            classify_readme_sections(readme_text, use_llm_refine=False, enable_semantic_summary=False)
        # 커밋 분석
        compute_commit_activity(owner, repo, days=90)
    
    results.append(measure_time(
        run_sequential_with_classify,
        "API + Logic (sequential)", label="sequential"
    ))
    
    # 4. 병렬 + README 분류
    clear_repo_cache(owner, repo)
    
    def run_parallel_with_classify():
        # Phase 1: API 병렬 호출
        api_tasks = {
            "repo": lambda: fetch_repo(owner, repo),
            "readme": lambda: fetch_readme(owner, repo),
            "commits": lambda: fetch_recent_commits(owner, repo, days=90),
        }
        api_results = run_parallel(api_tasks)
        
        # Phase 2: 로직 병렬 실행 (README 분류 + 커밋 분석)
        readme_text_local = fetch_readme_content(owner, repo)
        logic_tasks = {
            "classify": lambda: classify_readme_sections(
                readme_text_local, use_llm_refine=False, enable_semantic_summary=False
            ) if readme_text_local else None,
            "activity": lambda: compute_commit_activity(owner, repo, days=90),
        }
        return run_parallel(logic_tasks)
    
    results.append(measure_time(
        run_parallel_with_classify,
        "API + Logic (parallel)", label="parallel"
    ))
    
    return results


def print_parallel_comparison(results: List[BenchmarkResult]):
    """병렬 vs 순차 비교 출력"""
    print(f"\n{'='*70}")
    print(f" Parallel vs Sequential Comparison")
    print(f"{'='*70}")
    
    seq = [r for r in results if r.label == "sequential"]
    par = [r for r in results if r.label == "parallel"]
    
    print(f"{'Metric':<30} {'Sequential':>12} {'Parallel':>12} {'Saved':>10} {'Speedup':>10}")
    print(f"{'-'*70}")
    
    for s, p in zip(seq, par):
        saved = s.duration_ms - p.duration_ms
        speedup = s.duration_ms / p.duration_ms if p.duration_ms > 0 else 0
        print(f"{s.name:<30} {s.duration_ms:>10.1f}ms {p.duration_ms:>10.1f}ms {saved:>8.1f}ms {speedup:>9.2f}x")
    
    total_seq = sum(r.duration_ms for r in seq)
    total_par = sum(r.duration_ms for r in par)
    total_saved = total_seq - total_par
    total_speedup = total_seq / total_par if total_par > 0 else 0
    
    print(f"{'-'*70}")
    print(f"{'TOTAL':<30} {total_seq:>10.1f}ms {total_par:>10.1f}ms {total_saved:>8.1f}ms {total_speedup:>9.2f}x")
    print(f"\n[Result] Parallel saved {total_saved:.1f}ms ({total_speedup:.2f}x faster)")


def benchmark_diagnosis(owner: str, repo: str) -> List[BenchmarkResult]:
    """전체 진단 파이프라인 성능 테스트"""
    results = []
    
    payload = {
        "owner": owner,
        "repo": repo,
        "task_type": "full_diagnosis",
        "focus": ["documentation", "activity"],
        "user_context": {"level": "beginner"},
        "advanced_analysis": False,
    }
    
    # 1. 캐시 비움 상태 (Cold)
    clear_repo_cache(owner, repo)
    results.append(measure_time(
        lambda: run_diagnosis(payload),
        "full_diagnosis", cache_hit=False, label="cold"
    ))
    
    # 2. 같은 설정으로 재실행 (Warm) - 1:1 비교용
    results.append(measure_time(
        lambda: run_diagnosis(payload),
        "full_diagnosis", cache_hit=True, label="warm"
    ))
    
    # 3. 고급 분석 모드 (별도 측정)
    payload_adv = {**payload, "advanced_analysis": True}
    results.append(measure_time(
        lambda: run_diagnosis(payload_adv),
        "full_diagnosis_advanced", cache_hit=True, label="advanced"
    ))
    
    return results


def print_results(results: List[BenchmarkResult], title: str):
    """결과 출력"""
    print(f"\n{'='*65}")
    print(f" {title}")
    print(f"{'='*65}")
    print(f"{'Name':<30} {'Label':>10} {'Time (ms)':>12} {'Cache':>8}")
    print(f"{'-'*65}")
    
    for r in results:
        cache_str = "HIT" if r.cache_hit else ("MISS" if r.label in ["cold", "warm"] else "-")
        label_str = r.label if r.label else "-"
        print(f"{r.name:<30} {label_str:>10} {r.duration_ms:>10.1f}ms {cache_str:>8}")


def print_comparison(results: List[BenchmarkResult], title: str):
    """Cold vs Warm 1:1 비교 출력"""
    print(f"\n{'='*65}")
    print(f" {title} - Cold vs Warm Comparison")
    print(f"{'='*65}")
    
    cold = [r for r in results if r.label == "cold"]
    warm = [r for r in results if r.label == "warm"]
    
    if not cold or not warm:
        print("비교할 데이터 없음")
        return
    
    print(f"{'Metric':<25} {'Cold (ms)':>12} {'Warm (ms)':>12} {'Saved':>10} {'Speedup':>10}")
    print(f"{'-'*65}")
    
    for c, w in zip(cold, warm):
        saved = c.duration_ms - w.duration_ms
        speedup = c.duration_ms / w.duration_ms if w.duration_ms > 0 else 0
        print(f"{c.name:<25} {c.duration_ms:>10.1f}ms {w.duration_ms:>10.1f}ms {saved:>8.1f}ms {speedup:>9.1f}x")
    
    total_cold = sum(r.duration_ms for r in cold)
    total_warm = sum(r.duration_ms for r in warm)
    total_saved = total_cold - total_warm
    total_speedup = total_cold / total_warm if total_warm > 0 else 0
    
    print(f"{'-'*65}")
    print(f"{'TOTAL':<25} {total_cold:>10.1f}ms {total_warm:>10.1f}ms {total_saved:>8.1f}ms {total_speedup:>9.1f}x")


def print_logic_summary(results: List[BenchmarkResult]):
    """순수 로직 벤치마크 요약"""
    total = sum(r.duration_ms for r in results)
    print(f"\n{'='*65}")
    print(f" Logic-Only Summary (LLM 제외, 캐시된 API 데이터 사용)")
    print(f"{'='*65}")
    print(f"{'Step':<35} {'Time (ms)':>12} {'Ratio':>10}")
    print(f"{'-'*65}")
    
    for r in results:
        ratio = (r.duration_ms / total * 100) if total > 0 else 0
        print(f"{r.name:<35} {r.duration_ms:>10.1f}ms {ratio:>9.1f}%")
    
    print(f"{'-'*65}")
    print(f"{'TOTAL':<35} {total:>10.1f}ms {100.0:>9.1f}%")
    print(f"\n[Note] Pure logic time without LLM calls")


def run_benchmark(owner: str = "langchain-ai", repo: str = "langchain"):
    """전체 벤치마크 실행"""
    print(f"\nBenchmark: {owner}/{repo}")
    print(f"Cache entries: {github_cache.size()}")
    
    api_results = benchmark_github_api(owner, repo)
    print_results(api_results, "GitHub API Cache Benchmark")
    print_comparison(api_results, "GitHub API")
    
    print("\nRunning logic-only benchmark...")
    try:
        logic_results = benchmark_logic_only(owner, repo)
        print_results(logic_results, "Logic-Only Benchmark (No LLM)")
        print_logic_summary(logic_results)
    except Exception as e:
        print(f"[Error] Logic benchmark failed: {e}")
    
    print("\nRunning full diagnosis benchmark (includes LLM, may take time)...")
    try:
        diag_results = benchmark_diagnosis(owner, repo)
        print_results(diag_results, "Full Diagnosis Pipeline Benchmark")
        print_comparison(diag_results, "Full Diagnosis")
        
        advanced = [r for r in diag_results if r.label == "advanced"]
        if advanced:
            print(f"\nAdvanced mode: {advanced[0].duration_ms:.1f}ms (5 LLM calls)")
    except Exception as e:
        print(f"[Error] Diagnosis benchmark failed: {e}")
    
    print(f"\nFinal cache entries: {github_cache.size()}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cache/Parallel Performance Benchmark")
    parser.add_argument("--owner", default="Hyeri-hci", help="GitHub owner")
    parser.add_argument("--repo", default="OSSDoctor", help="GitHub repo")
    parser.add_argument("--api-only", action="store_true", help="API 캐시만 테스트")
    parser.add_argument("--logic-only", action="store_true", help="순수 로직만 테스트 (LLM 제외)")
    parser.add_argument("--parallel", action="store_true", help="병렬 vs 순차 비교 테스트")
    parser.add_argument("--full", action="store_true", help="전체 진단 테스트 (LLM 포함)")
    
    args = parser.parse_args()
    
    if args.api_only:
        print(f"\nAPI-only Benchmark: {args.owner}/{args.repo}")
        results = benchmark_github_api(args.owner, args.repo)
        print_results(results, "GitHub API Cache Benchmark")
        print_comparison(results, "GitHub API")
    elif args.logic_only:
        print(f"\nLogic-only Benchmark: {args.owner}/{args.repo}")
        clear_repo_cache(args.owner, args.repo)
        fetch_repo(args.owner, args.repo)
        fetch_readme(args.owner, args.repo)
        fetch_recent_commits(args.owner, args.repo, days=90)
        
        results = benchmark_logic_only(args.owner, args.repo)
        print_results(results, "Logic-Only Benchmark (No LLM)")
        print_logic_summary(results)
    elif args.parallel:
        print(f"\nParallel vs Sequential Benchmark: {args.owner}/{args.repo}")
        results = benchmark_parallel_vs_sequential(args.owner, args.repo)
        print_results(results, "Parallel vs Sequential Benchmark")
        print_parallel_comparison(results)
    elif args.full:
        print(f"\nFull Diagnosis Benchmark: {args.owner}/{args.repo}")
        results = benchmark_diagnosis(args.owner, args.repo)
        print_results(results, "Full Diagnosis Pipeline Benchmark")
        print_comparison(results, "Full Diagnosis")
    else:
        run_benchmark(args.owner, args.repo)
