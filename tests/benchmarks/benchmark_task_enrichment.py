"""
2-2. Task Enrichment 품질 벤치마크

사용 함수:
  - compute_onboarding_tasks(...) → 기본 task 생성
  - enrich_onboarding_tasks(tasks, repo, use_llm=False) → 규칙 기반 enrichment
  - enrich_onboarding_tasks(tasks, repo, use_llm=True) → LLM enrichment

측정:
  - reason_text 길이 (chars)
  - LLM enriched vs Fallback 품질 점수

통과 기준:
  - LLM enriched reason 평균 길이 > fallback * 2
  - LLM 호출 실패율 < 5%

사용법:
    python test/benchmarks/benchmark_task_enrichment.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from test.benchmarks.config import BENCHMARK_REPOS, RepoInfo
from test.benchmarks.utils import print_pass_fail


@dataclass
class TaskEnrichmentResult:
    """개별 레포 enrichment 결과"""
    repo: str
    task_count: int = 0
    
    # Fallback (use_llm=False)
    fallback_total_chars: int = 0
    fallback_avg_chars: float = 0.0
    
    # LLM (use_llm=True)
    llm_total_chars: int = 0
    llm_avg_chars: float = 0.0
    llm_error: Optional[str] = None
    
    # 비교
    char_ratio: float = 0.0  # llm / fallback
    llm_wins: int = 0  # task별로 LLM이 더 긴 경우


def run_task_enrichment_test(repo: RepoInfo) -> TaskEnrichmentResult:
    """단일 레포에서 enrichment 비교"""
    from backend.agents.diagnosis.tools.onboarding_tasks import compute_onboarding_tasks
    from backend.agents.diagnosis.tools.onboarding_recommender_llm import enrich_onboarding_tasks
    from backend.agents.diagnosis.tools.diagnosis_labels import create_diagnosis_labels
    from backend.agents.diagnosis.tools.health_score import create_health_score
    
    result = TaskEnrichmentResult(repo=f"{repo.owner}/{repo.repo}")
    
    # Health 점수 계산
    is_healthy = repo.category in ["very_active", "active"]
    scores = create_health_score(doc=50, activity=50 if is_healthy else 30)
    
    # 라벨 생성 (실제 함수 시그니처에 맞춤)
    labels = create_diagnosis_labels(
        health_score=scores.health_score,
        onboarding_score=scores.onboarding_score,
        doc_score=50,
        activity_score=50 if is_healthy else 30,
    )
    
    tasks = compute_onboarding_tasks(
        owner=repo.owner,
        repo=repo.repo,
        labels=labels.to_dict(),
    )
    
    all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
    if not all_tasks:
        return result
    
    result.task_count = len(all_tasks)
    
    repo_full = f"{repo.owner}/{repo.repo}"
    
    # Fallback enrichment (use_llm=False) - enrich_onboarding_tasks는 Dict 반환
    # enriched_tasks는 {task_id: EnrichedTask} 형태의 Dict
    fallback_result = enrich_onboarding_tasks(tasks, repo_full, use_llm=False)
    fallback_tasks_dict = fallback_result.get("enriched_tasks", {})
    # Dict에서 값들을 리스트로 변환하고 reason_text 추출
    fallback_chars = []
    for task_id, task_data in list(fallback_tasks_dict.items())[:3]:
        if isinstance(task_data, dict):
            reason_text = task_data.get("reason_text", "") or ""
        else:
            reason_text = ""
        fallback_chars.append(len(reason_text))
    result.fallback_total_chars = sum(fallback_chars)
    result.fallback_avg_chars = result.fallback_total_chars / len(fallback_chars) if fallback_chars else 0
    
    # LLM enrichment (use_llm=True)
    try:
        llm_result = enrich_onboarding_tasks(tasks, repo_full, use_llm=True)
        llm_tasks_dict = llm_result.get("enriched_tasks", {})
        # Dict에서 값들을 리스트로 변환하고 reason_text 추출
        llm_chars = []
        for task_id, task_data in list(llm_tasks_dict.items())[:3]:
            if isinstance(task_data, dict):
                reason_text = task_data.get("reason_text", "") or ""
            else:
                reason_text = ""
            llm_chars.append(len(reason_text))
        result.llm_total_chars = sum(llm_chars)
        result.llm_avg_chars = result.llm_total_chars / len(llm_chars) if llm_chars else 0
        
        # 비교
        result.char_ratio = result.llm_avg_chars / result.fallback_avg_chars if result.fallback_avg_chars > 0 else 1.0
        result.llm_wins = sum(1 for l, f in zip(llm_chars, fallback_chars) if l > f)
        
    except Exception as e:
        result.llm_error = str(e)
    
    return result


def run_task_enrichment_benchmark(repos: List[RepoInfo] = None, verbose: bool = True) -> Dict[str, Any]:
    """Task enrichment 벤치마크 실행"""
    if repos is None:
        repos = BENCHMARK_REPOS[:5]
    
    if verbose:
        print("\n" + "=" * 60)
        print("2-2. Task Enrichment Quality Benchmark")
        print("=" * 60)
    
    results: List[TaskEnrichmentResult] = []
    
    for i, repo in enumerate(repos):
        if verbose:
            print(f"\n[{i+1}/{len(repos)}] {repo.owner}/{repo.repo}")
        
        result = run_task_enrichment_test(repo)
        results.append(result)
        
        if verbose:
            print(f"  Tasks: {result.task_count}")
            print(f"  Fallback avg: {result.fallback_avg_chars:.0f} chars")
            if result.llm_error:
                print(f"  LLM ERROR: {result.llm_error}")
            else:
                print(f"  LLM avg: {result.llm_avg_chars:.0f} chars (ratio: {result.char_ratio:.2f}x)")
                print(f"  LLM wins: {result.llm_wins}/{min(3, result.task_count)}")
    
    # 집계
    valid = [r for r in results if r.llm_error is None]
    failed = len(results) - len(valid)
    
    total_fallback_chars = sum(r.fallback_total_chars for r in valid)
    total_llm_chars = sum(r.llm_total_chars for r in valid)
    total_llm_wins = sum(r.llm_wins for r in valid)
    total_tasks = sum(min(3, r.task_count) for r in valid)  # 각 레포당 최대 3개 task
    
    avg_ratio = total_llm_chars / total_fallback_chars if total_fallback_chars > 0 else 1.0
    
    summary = {
        "total_repos": len(results),
        "success_repos": len(valid),
        "failed_repos": failed,
        "fail_rate": failed / len(results) if results else 0,
        
        "total_fallback_chars": total_fallback_chars,
        "total_llm_chars": total_llm_chars,
        "avg_char_ratio": avg_ratio,
        
        "llm_wins": total_llm_wins,
        "total_comparisons": total_tasks,
        "llm_win_rate": total_llm_wins / total_tasks if total_tasks > 0 else 0,
        
        # 통과 기준 확인
        "pass_char_ratio": avg_ratio >= 2.0,  # LLM이 평균 2배 이상 길어야 함
        "pass_fail_rate": (failed / len(results)) < 0.05 if results else True,  # 실패율 5% 미만
    }
    
    summary["passed"] = summary["pass_char_ratio"] and summary["pass_fail_rate"]
    
    if verbose:
        print("\n" + "-" * 40)
        print(f"Summary:")
        print(f"  Success: {len(valid)}/{len(results)}, Failed: {failed}")
        print(f"  Fail rate: {summary['fail_rate']:.1%} (threshold: <5%)")
        print(f"  Total fallback chars: {total_fallback_chars}")
        print(f"  Total LLM chars: {total_llm_chars}")
        print(f"  Avg char ratio: {avg_ratio:.2f}x (threshold: ≥2.0x)")
        print(f"  LLM win rate: {summary['llm_win_rate']:.1%}")
        print_pass_fail(summary["passed"])
    
    return summary


if __name__ == "__main__":
    run_task_enrichment_benchmark()
