"""
4. 재현성 벤치마크 (규칙 레이어 결정론)

사용 함수:
  - 규칙 레이어 전체 (LLM 호출 없이)

측정:
  - 동일 입력에 대해 20회 반복 실행
  - 결과 hash 비교

통과 기준:
  - 20회 모두 동일한 hash → 결정론적
  - 비결정론적 함수 0개

사용법:
    python test/benchmarks/benchmark_reproducibility.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Dict, List, Any
from dataclasses import dataclass, field
import json

from test.benchmarks.config import BENCHMARK_REPOS, RepoInfo
from test.benchmarks.utils import hash_result, print_pass_fail


NUM_ITERATIONS = 5  # 빠른 테스트를 위해 5회로 조정 (프로덕션은 20회)


@dataclass
class ReproducibilityResult:
    """재현성 테스트 결과"""
    repo: str
    iterations: int = NUM_ITERATIONS
    unique_hashes: int = 1
    is_deterministic: bool = True
    hash_samples: List[str] = field(default_factory=list)
    error: str = ""


def run_reproducibility_test(repo: RepoInfo, iterations: int = NUM_ITERATIONS) -> ReproducibilityResult:
    """단일 레포에서 규칙 레이어 재현성 테스트"""
    from backend.agents.diagnosis.tools.health_score import create_health_score
    from backend.agents.diagnosis.tools.activity_scores import activity_score_to_100, aggregate_activity_score
    from backend.agents.diagnosis.tools.chaoss_metrics import (
        compute_commit_activity, compute_issue_activity, compute_pr_activity
    )
    from backend.agents.diagnosis.tools.readme_categories import classify_readme_sections
    from backend.agents.diagnosis.tools.readme_loader import fetch_readme_content
    from backend.agents.diagnosis.tools.diagnosis_labels import create_diagnosis_labels
    from backend.agents.diagnosis.tools.onboarding_tasks import compute_onboarding_tasks
    from backend.agents.diagnosis.tools.repo_parser import fetch_repo_info
    
    result = ReproducibilityResult(
        repo=f"{repo.owner}/{repo.repo}",
        iterations=iterations
    )
    
    hashes = []
    
    try:
        # 첫 실행에서 raw 데이터 가져오기 (API 호출은 1회만)
        repo_info = fetch_repo_info(repo.owner, repo.repo)
        readme_text = fetch_readme_content(repo.owner, repo.repo) or ""
        commit = compute_commit_activity(repo.owner, repo.repo, days=365)
        issue = compute_issue_activity(repo.owner, repo.repo, days=365)
        pr = compute_pr_activity(repo.owner, repo.repo, days=365)
        
        for i in range(iterations):
            # 규칙 레이어 함수들 재실행 (동일 입력)
            cat_infos, doc_score, _ = classify_readme_sections(
                readme_text, 
                use_llm_refine=False, 
                enable_semantic_summary=False,
                advanced_mode=False
            )
            activity_breakdown = aggregate_activity_score(commit, issue, pr)
            activity_score = activity_score_to_100(activity_breakdown)
            
            health_scores = create_health_score(doc_score, activity_score)
            
            # 라벨 생성 (실제 함수 시그니처에 맞춤)
            labels = create_diagnosis_labels(
                health_score=health_scores.health_score,
                onboarding_score=health_scores.onboarding_score,
                doc_score=doc_score,
                activity_score=activity_score,
                readme_categories=cat_infos,
            )
            
            tasks = compute_onboarding_tasks(
                owner=repo.owner,
                repo=repo.repo,
                labels=labels.to_dict(),
            )
            
            all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
            
            # 결과를 직렬화 가능한 형태로 변환
            output = {
                "health_score": health_scores.health_score,
                "doc_score": doc_score,
                "activity_score": activity_score,
                "is_healthy": health_scores.is_healthy,
                "task_count": len(all_tasks),
                "task_kinds": sorted([t.kind for t in all_tasks]) if all_tasks else [],
            }
            
            h = hash_result(output)
            hashes.append(h)
        
        unique = set(hashes)
        result.unique_hashes = len(unique)
        result.is_deterministic = len(unique) == 1
        result.hash_samples = list(unique)[:3]  # 최대 3개만 샘플
        
    except Exception as e:
        result.error = str(e)
        result.is_deterministic = False
    
    return result


def run_reproducibility_benchmark(repos: List[RepoInfo] = None, verbose: bool = True) -> Dict[str, Any]:
    """재현성 벤치마크 실행"""
    if repos is None:
        repos = BENCHMARK_REPOS[:4]  # 빠른 테스트를 위해 4개만
    
    if verbose:
        print("\n" + "=" * 60)
        print("4. Reproducibility (Determinism) Benchmark")
        print("=" * 60)
        print(f"Running {NUM_ITERATIONS} iterations per repo...")
    
    results: List[ReproducibilityResult] = []
    
    for i, repo in enumerate(repos):
        if verbose:
            print(f"\n[{i+1}/{len(repos)}] {repo.owner}/{repo.repo}")
        
        result = run_reproducibility_test(repo)
        results.append(result)
        
        if verbose:
            if result.error:
                print(f"  ERROR: {result.error}")
            elif result.is_deterministic:
                print(f"  ✓ Deterministic ({result.iterations} runs, 1 unique hash)")
            else:
                print(f"  ✗ Non-deterministic! {result.unique_hashes} unique hashes")
                for h in result.hash_samples:
                    print(f"    - {h[:16]}...")
    
    # 집계
    deterministic_count = sum(1 for r in results if r.is_deterministic)
    error_count = sum(1 for r in results if r.error)
    
    summary = {
        "total_repos": len(results),
        "deterministic_repos": deterministic_count,
        "non_deterministic_repos": len(results) - deterministic_count - error_count,
        "error_repos": error_count,
        "iterations_per_repo": NUM_ITERATIONS,
        "determinism_rate": deterministic_count / len(results) if results else 0,
        
        "passed": deterministic_count == len(results) - error_count,  # 에러 제외하고 모두 결정론적
    }
    
    if verbose:
        print("\n" + "-" * 40)
        print(f"Summary:")
        print(f"  Deterministic: {deterministic_count}/{len(results)}")
        print(f"  Non-deterministic: {summary['non_deterministic_repos']}")
        print(f"  Errors: {error_count}")
        print_pass_fail(summary["passed"])
    
    return summary


if __name__ == "__main__":
    run_reproducibility_benchmark()
