"""
3. 개인화 로직 벤치마크

사용 함수:
  - compute_onboarding_tasks(...) → 전체 task 풀
  - filter_tasks_for_user(tasks, user_level, ...) → 유저 레벨별 필터링

측정:
  - User 유형별 (beginner, intermediate, advanced) task 수
  - Task 난이도 단조성: beginner ≤ intermediate ≤ advanced

통과 기준:
  - 모든 레포에서 단조성 만족 (beginner tasks ≤ intermediate ≤ advanced)
  - 각 유저 레벨에서 해당 레벨 이하 task만 포함

사용법:
    python test/benchmarks/benchmark_personalization.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from test.benchmarks.config import BENCHMARK_REPOS, RepoInfo
from test.benchmarks.utils import print_pass_fail


USER_LEVELS = ["beginner", "intermediate", "advanced"]


@dataclass
class PersonalizationResult:
    """개인화 테스트 결과"""
    repo: str
    total_tasks: int = 0
    
    # 유저 레벨별 task 수
    beginner_count: int = 0
    intermediate_count: int = 0
    advanced_count: int = 0
    
    # 검증 결과
    is_monotonic: bool = False  # beginner ≤ intermediate ≤ advanced
    violations: List[str] = field(default_factory=list)


def run_personalization_test(repo: RepoInfo) -> PersonalizationResult:
    """단일 레포에서 개인화 단조성 테스트"""
    from backend.agents.diagnosis.tools.onboarding_tasks import compute_onboarding_tasks, filter_tasks_for_user
    from backend.agents.diagnosis.tools.diagnosis_labels import create_diagnosis_labels
    
    result = PersonalizationResult(repo=f"{repo.owner}/{repo.repo}")
    
    # 기본 labels (실제 함수 시그니처에 맞춤)
    is_healthy = repo.category in ["very_active", "active"]
    labels = create_diagnosis_labels(
        health_score=70 if is_healthy else 40,
        onboarding_score=70 if is_healthy else 40,
        doc_score=60,
        activity_score=60 if is_healthy else 30,
    )
    
    # 전체 task 풀
    tasks = compute_onboarding_tasks(
        owner=repo.owner,
        repo=repo.repo,
        labels=labels.to_dict(),
    )
    
    all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
    result.total_tasks = len(all_tasks)
    
    if not all_tasks:
        result.is_monotonic = True
        return result
    
    # 유저 레벨별 필터링 (OnboardingTasks 객체 전달)
    beginner_tasks = filter_tasks_for_user(tasks, user_level="beginner")
    intermediate_tasks = filter_tasks_for_user(tasks, user_level="intermediate")
    advanced_tasks = filter_tasks_for_user(tasks, user_level="advanced")
    
    result.beginner_count = len(beginner_tasks)
    result.intermediate_count = len(intermediate_tasks)
    result.advanced_count = len(advanced_tasks)
    
    # 단조성 검증
    violations = []
    
    if result.beginner_count > result.intermediate_count:
        violations.append(f"beginner({result.beginner_count}) > intermediate({result.intermediate_count})")
    
    if result.intermediate_count > result.advanced_count:
        violations.append(f"intermediate({result.intermediate_count}) > advanced({result.advanced_count})")
    
    # 고급자가 초급자 task를 포함하는지 확인
    beginner_ids = {t.id for t in beginner_tasks if hasattr(t, 'id')}
    advanced_ids = {t.id for t in advanced_tasks if hasattr(t, 'id')}
    
    if beginner_ids and advanced_ids:
        missing = beginner_ids - advanced_ids
        if missing:
            violations.append(f"Advanced missing beginner tasks: {len(missing)}")
    
    result.violations = violations
    result.is_monotonic = len(violations) == 0
    
    return result


def run_personalization_benchmark(repos: List[RepoInfo] = None, verbose: bool = True) -> Dict[str, Any]:
    """개인화 벤치마크 실행"""
    if repos is None:
        repos = BENCHMARK_REPOS[:8]
    
    if verbose:
        print("\n" + "=" * 60)
        print("3. Personalization Monotonicity Benchmark")
        print("=" * 60)
    
    results: List[PersonalizationResult] = []
    
    for i, repo in enumerate(repos):
        if verbose:
            print(f"\n[{i+1}/{len(repos)}] {repo.owner}/{repo.repo}")
        
        result = run_personalization_test(repo)
        results.append(result)
        
        if verbose:
            print(f"  Total: {result.total_tasks}, B:{result.beginner_count}, I:{result.intermediate_count}, A:{result.advanced_count}")
            if result.is_monotonic:
                print(f"  ✓ Monotonic")
            else:
                print(f"  ✗ Violations: {result.violations}")
    
    # 집계
    monotonic_count = sum(1 for r in results if r.is_monotonic)
    total_violations = sum(len(r.violations) for r in results)
    
    avg_beginner = sum(r.beginner_count for r in results) / len(results) if results else 0
    avg_intermediate = sum(r.intermediate_count for r in results) / len(results) if results else 0
    avg_advanced = sum(r.advanced_count for r in results) / len(results) if results else 0
    
    summary = {
        "total_repos": len(results),
        "monotonic_repos": monotonic_count,
        "violation_repos": len(results) - monotonic_count,
        "total_violations": total_violations,
        "monotonicity_rate": monotonic_count / len(results) if results else 0,
        
        "avg_beginner_tasks": avg_beginner,
        "avg_intermediate_tasks": avg_intermediate,
        "avg_advanced_tasks": avg_advanced,
        
        "passed": monotonic_count == len(results),  # 모든 레포가 단조성 만족해야 통과
    }
    
    if verbose:
        print("\n" + "-" * 40)
        print(f"Summary:")
        print(f"  Monotonic repos: {monotonic_count}/{len(results)}")
        print(f"  Total violations: {total_violations}")
        print(f"  Avg tasks: B={avg_beginner:.1f}, I={avg_intermediate:.1f}, A={avg_advanced:.1f}")
        print_pass_fail(summary["passed"])
    
    return summary


if __name__ == "__main__":
    run_personalization_benchmark()
