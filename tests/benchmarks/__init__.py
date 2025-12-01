"""
Diagnosis Benchmark Suite

4축 벤치마크 프레임워크:

1. 규칙 레이어 정확성/커버리지
   - benchmark_health_matrix.py: 카테고리별 점수 단조성
   - benchmark_tasks_rules.py: Task 규칙 커버리지

2. LLM 품질
   - benchmark_plan_ablation.py: v0 vs v1 A/B 테스트
   - benchmark_task_enrichment.py: LLM vs Fallback

3. 개인화/레벨 적합성
   - benchmark_personalization.py: beginner/intermediate/advanced 분포

4. 안정성/재현성
   - benchmark_reproducibility.py: N회 반복 일관성

사용법:
    python -m test.benchmarks.run_all --quick
    python test/benchmarks/benchmark_health_matrix.py
"""
from pathlib import Path

BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

from .config import BENCHMARK_REPOS, RepoCategory, BenchmarkConfig, RepoInfo
from .utils import BenchmarkResult, compute_stats, hash_result, print_pass_fail

__all__ = [
    "BENCHMARK_REPOS",
    "RepoCategory",
    "BenchmarkConfig",
    "RepoInfo",
    "BenchmarkResult",
    "compute_stats",
    "hash_result",
    "print_pass_fail",
    "BENCHMARK_DIR",
    "RESULTS_DIR",
]



