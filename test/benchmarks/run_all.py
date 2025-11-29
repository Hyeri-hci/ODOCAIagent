"""
4축 벤치마크 스위트 러너

1축: 정확성 / 커버리지
  - 1-1. Health Matrix (benchmark_health_matrix.py)
  - 1-2. Tasks Rules (benchmark_tasks_rules.py)

2축: LLM 품질
  - 2-1. Plan Ablation (benchmark_plan_ablation.py)
  - 2-2. Task Enrichment (benchmark_task_enrichment.py)

3축: 개인화
  - 3. Personalization (benchmark_personalization.py)

4축: 안정성
  - 4. Reproducibility (benchmark_reproducibility.py)

사용법:
    python test/benchmarks/run_all.py
    python test/benchmarks/run_all.py --quick    # 빠른 테스트 (적은 레포)
    python test/benchmarks/run_all.py --no-llm   # LLM 테스트 제외
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import argparse
from datetime import datetime
from typing import Dict, Any, List
import json

from test.benchmarks.config import BENCHMARK_REPOS


def compute_overall_score(results: Dict[str, Dict[str, Any]]) -> float:
    """전체 점수 계산 (100점 만점)"""
    weights = {
        "health_matrix": 15,
        "tasks_rules": 15,
        "plan_ablation": 20,
        "task_enrichment": 20,
        "personalization": 15,
        "reproducibility": 15,
    }
    
    score = 0.0
    
    # 1-1 Health Matrix
    if "health_matrix" in results:
        r = results["health_matrix"]
        monotonicity_score = (r.get("monotonicity_rate", 0) + r.get("healthy_accuracy", 0)) / 2
        score += weights["health_matrix"] * monotonicity_score
    
    # 1-2 Tasks Rules
    if "tasks_rules" in results:
        r = results["tasks_rules"]
        score += weights["tasks_rules"] * (1.0 if r.get("passed", False) else 0.5)
    
    # 2-1 Plan Ablation
    if "plan_ablation" in results:
        r = results["plan_ablation"]
        score += weights["plan_ablation"] * r.get("pass_rate", 0)
    
    # 2-2 Task Enrichment
    if "task_enrichment" in results:
        r = results["task_enrichment"]
        score += weights["task_enrichment"] * (1.0 if r.get("passed", False) else 0.5)
    
    # 3 Personalization
    if "personalization" in results:
        r = results["personalization"]
        score += weights["personalization"] * r.get("monotonicity_rate", 0)
    
    # 4 Reproducibility
    if "reproducibility" in results:
        r = results["reproducibility"]
        score += weights["reproducibility"] * r.get("determinism_rate", 0)
    
    return score


def get_grade(score: float) -> str:
    """점수를 등급으로 변환"""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def run_all_benchmarks(quick: bool = False, skip_llm: bool = False) -> Dict[str, Any]:
    """전체 벤치마크 실행"""
    from test.benchmarks.benchmark_health_matrix import run_health_matrix_benchmark
    from test.benchmarks.benchmark_tasks_rules import run_tasks_rules_benchmark
    from test.benchmarks.benchmark_personalization import run_personalization_benchmark
    from test.benchmarks.benchmark_reproducibility import run_reproducibility_benchmark
    
    # 레포 수 결정
    if quick:
        repos = BENCHMARK_REPOS[:4]
    else:
        repos = BENCHMARK_REPOS
    
    print("=" * 70)
    print("     ODOCA Diagnosis Agent - 4-Axis Benchmark Suite")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'Quick' if quick else 'Full'} | LLM tests: {'Skipped' if skip_llm else 'Enabled'}")
    print(f"Repos: {len(repos)}")
    print()
    
    results = {}
    
    # 1-1. Health Matrix
    print("\n" + "▶" * 3 + " Running 1-1. Health Matrix...")
    try:
        results["health_matrix"] = run_health_matrix_benchmark(repos, verbose=True)
    except Exception as e:
        print(f"  ERROR: {e}")
        results["health_matrix"] = {"error": str(e), "passed": False}
    
    # 1-2. Tasks Rules
    print("\n" + "▶" * 3 + " Running 1-2. Tasks Rules...")
    try:
        results["tasks_rules"] = run_tasks_rules_benchmark(repos, verbose=True)
    except Exception as e:
        print(f"  ERROR: {e}")
        results["tasks_rules"] = {"error": str(e), "passed": False}
    
    # 2-1. Plan Ablation (LLM)
    if not skip_llm:
        print("\n" + "▶" * 3 + " Running 2-1. Plan Ablation...")
        try:
            from test.benchmarks.benchmark_plan_ablation import run_plan_ablation_benchmark
            results["plan_ablation"] = run_plan_ablation_benchmark(repos[:3], verbose=True)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["plan_ablation"] = {"error": str(e), "passed": False}
    else:
        print("\n⏭ Skipping 2-1. Plan Ablation (LLM)")
        results["plan_ablation"] = {"skipped": True, "pass_rate": 0.5}
    
    # 2-2. Task Enrichment (LLM)
    if not skip_llm:
        print("\n" + "▶" * 3 + " Running 2-2. Task Enrichment...")
        try:
            from test.benchmarks.benchmark_task_enrichment import run_task_enrichment_benchmark
            results["task_enrichment"] = run_task_enrichment_benchmark(repos[:3], verbose=True)
        except Exception as e:
            print(f"  ERROR: {e}")
            results["task_enrichment"] = {"error": str(e), "passed": False}
    else:
        print("\n⏭ Skipping 2-2. Task Enrichment (LLM)")
        results["task_enrichment"] = {"skipped": True, "passed": True}
    
    # 3. Personalization
    print("\n" + "▶" * 3 + " Running 3. Personalization...")
    try:
        results["personalization"] = run_personalization_benchmark(repos, verbose=True)
    except Exception as e:
        print(f"  ERROR: {e}")
        results["personalization"] = {"error": str(e), "passed": False}
    
    # 4. Reproducibility
    print("\n" + "▶" * 3 + " Running 4. Reproducibility...")
    try:
        results["reproducibility"] = run_reproducibility_benchmark(repos[:4], verbose=True)
    except Exception as e:
        print(f"  ERROR: {e}")
        results["reproducibility"] = {"error": str(e), "passed": False}
    
    # 최종 리포트
    overall_score = compute_overall_score(results)
    grade = get_grade(overall_score)
    
    print("\n")
    print("=" * 70)
    print("                    FINAL BENCHMARK REPORT")
    print("=" * 70)
    print()
    print("┌─────────────────────────────────────────────────────────────────┐")
    print(f"│  Overall Score: {overall_score:.1f}/100  Grade: {grade}                           │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print()
    
    print("Axis Results:")
    print("─" * 50)
    
    axis_results = [
        ("1-1. Health Matrix", results.get("health_matrix", {})),
        ("1-2. Tasks Rules", results.get("tasks_rules", {})),
        ("2-1. Plan Ablation", results.get("plan_ablation", {})),
        ("2-2. Task Enrichment", results.get("task_enrichment", {})),
        ("3. Personalization", results.get("personalization", {})),
        ("4. Reproducibility", results.get("reproducibility", {})),
    ]
    
    for name, r in axis_results:
        if r.get("error"):
            status = "❌ ERROR"
        elif r.get("skipped"):
            status = "⏭ SKIPPED"
        elif r.get("passed", False):
            status = "✅ PASS"
        else:
            status = "⚠️ PARTIAL"
        
        print(f"  {name:<25} {status}")
    
    print()
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    return {
        "overall_score": overall_score,
        "grade": grade,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Run ODOCA 4-Axis Benchmark Suite")
    parser.add_argument("--quick", action="store_true", help="Quick mode (fewer repos)")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM-based benchmarks")
    args = parser.parse_args()
    
    run_all_benchmarks(quick=args.quick, skip_llm=args.no_llm)


if __name__ == "__main__":
    main()
