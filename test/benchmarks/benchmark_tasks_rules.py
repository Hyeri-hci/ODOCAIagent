"""
1-2. Onboarding Tasks 규칙 벤치마크 (LLM Off)

사용 함수: compute_onboarding_tasks (LLM 미사용)
입력: 카테고리 라벨이 붙은 레포 집합
측정:
  - 레포별 Task 통계: total, beginner/intermediate/advanced 비율
  - kind별 비율: docs / test / issue / meta (상위 5개 기준)
  - intent별 비율: contribute / study / evaluate

통과 기준:
  - beginner Task 상위 5개 중 beginner-friendly(docs/test/meta) >= 20%
  - archived/inactive에서 intent=study 비율이 contribute보다 높음
  - docs 문제 없으면 docs meta Task 생성 안 함

사용법:
    python test/benchmarks/benchmark_tasks_rules.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
from typing import Dict, List, Any
from dataclasses import dataclass, field, asdict

from test.benchmarks.config import BENCHMARK_REPOS, RepoCategory, RepoInfo
from test.benchmarks.utils import print_pass_fail


@dataclass
class TaskRuleResult:
    """규칙 검증 결과"""
    repo: str
    category: str
    
    # Task 통계
    total_tasks: int = 0
    beginner_count: int = 0
    intermediate_count: int = 0
    advanced_count: int = 0
    
    # Kind 비율 (beginner 기준)
    beginner_docs_ratio: float = 0.0
    beginner_test_ratio: float = 0.0
    beginner_docs_test_ratio: float = 0.0  # docs + test
    
    # Intent 비율 (전체)
    contribute_ratio: float = 0.0
    study_ratio: float = 0.0
    evaluate_ratio: float = 0.0
    
    # Meta Task
    meta_count: int = 0
    docs_meta_count: int = 0
    
    # 검증 결과
    checks: Dict[str, bool] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)


def analyze_tasks_for_repo(repo: RepoInfo) -> TaskRuleResult:
    """레포의 Task 규칙 분석"""
    from backend.agents.diagnosis.tools.onboarding_tasks import compute_onboarding_tasks
    from backend.agents.diagnosis.tools.readme_categories import classify_readme_sections
    from backend.agents.diagnosis.tools.readme_loader import fetch_readme_content
    
    try:
        # README 분석으로 docs_issues 결정
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
        
        has_docs_issues = doc_score < 50
        
        # Labels 설정
        is_inactive = repo.category in (RepoCategory.ARCHIVED, RepoCategory.DEPRECATED)
        labels = {
            "health_level": "bad" if is_inactive else "good",
            "activity_issues": ["inactive_project", "no_recent_commits"] if is_inactive else [],
            "docs_issues": ["missing_contributing"] if has_docs_issues else [],
        }
        
        # Task 생성
        tasks = compute_onboarding_tasks(repo.owner, repo.repo, labels, max_issues=30, min_tasks=3)
        
        # 실제 사용자에게 보여줄 Task (filter_tasks_for_user 적용)
        from backend.agents.diagnosis.tools.onboarding_tasks import filter_tasks_for_user
        beginner_filtered = filter_tasks_for_user(tasks, user_level="beginner")
        top_5_beginner = beginner_filtered[:5]  # 상위 5개만 측정 (실제 UX)
        
        all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
        beginner = tasks.beginner
        
        result = TaskRuleResult(
            repo=f"{repo.owner}/{repo.repo}",
            category=repo.category.value,
            total_tasks=len(all_tasks),
            beginner_count=len(beginner),
            intermediate_count=len(tasks.intermediate),
            advanced_count=len(tasks.advanced),
        )
        
        # Beginner-friendly kind 비율 (상위 5개 기준 - 실제 UX 반영)
        # docs, test, meta 모두 초보자 친화적 (코드 이해 없이 시작 가능)
        BEGINNER_FRIENDLY_KINDS = ("doc", "test", "meta")
        if top_5_beginner:
            result.beginner_docs_ratio = sum(1 for t in top_5_beginner if t.kind == "doc") / len(top_5_beginner)
            result.beginner_test_ratio = sum(1 for t in top_5_beginner if t.kind == "test") / len(top_5_beginner)
            result.beginner_docs_test_ratio = sum(1 for t in top_5_beginner if t.kind in BEGINNER_FRIENDLY_KINDS) / len(top_5_beginner)
        
        # Intent 비율 (전체)
        if all_tasks:
            result.contribute_ratio = sum(1 for t in all_tasks if t.intent == "contribute") / len(all_tasks)
            result.study_ratio = sum(1 for t in all_tasks if t.intent == "study") / len(all_tasks)
            result.evaluate_ratio = sum(1 for t in all_tasks if t.intent == "evaluate") / len(all_tasks)
        
        # Meta 통계
        result.meta_count = sum(1 for t in all_tasks if t.kind == "meta")
        result.docs_meta_count = sum(1 for t in all_tasks if t.kind == "meta" and "doc" in t.id.lower())
        
        # 규칙 검증
        checks = {}
        violations = []
        
        # 1. beginner-friendly >= 20% (활성 프로젝트만, 현실화된 기준)
        # 정책: 상위 5개 중 최소 1개는 docs/test/meta여야 함 (20%)
        if not is_inactive and beginner:
            passed = result.beginner_docs_test_ratio >= 0.2
            checks["beginner_friendly_20pct"] = passed
            if not passed:
                violations.append(f"beginner-friendly={result.beginner_docs_test_ratio:.1%} < 20%")
        
        # 2. archived/inactive에서 study > contribute
        if is_inactive and all_tasks:
            passed = result.study_ratio >= result.contribute_ratio
            checks["inactive_study_dominant"] = passed
            if not passed:
                violations.append(f"inactive: study={result.study_ratio:.1%} < contribute={result.contribute_ratio:.1%}")
        
        # 3. docs 문제 없으면 docs meta 생성 안 함
        if not has_docs_issues:
            passed = result.docs_meta_count == 0
            checks["no_docs_meta_without_issues"] = passed
            if not passed:
                violations.append(f"docs_meta_count={result.docs_meta_count} but no docs_issues")
        
        result.checks = checks
        result.violations = violations
        
        return result
        
    except Exception as e:
        return TaskRuleResult(
            repo=f"{repo.owner}/{repo.repo}",
            category=repo.category.value,
            violations=[f"ERROR: {e}"],
        )


def run_tasks_rules_benchmark(repos: List[RepoInfo] = None, verbose: bool = True) -> Dict[str, Any]:
    """Tasks 규칙 벤치마크 실행"""
    if repos is None:
        repos = BENCHMARK_REPOS
    
    if verbose:
        print("\n" + "=" * 60)
        print("1-2. Onboarding Tasks Rules Benchmark")
        print("=" * 60)
    
    results: List[TaskRuleResult] = []
    
    for i, repo in enumerate(repos):
        if verbose:
            print(f"\n[{i+1}/{len(repos)}] {repo.owner}/{repo.repo} ({repo.category.value})")
        
        result = analyze_tasks_for_repo(repo)
        results.append(result)
        
        if verbose:
            print(f"  Tasks: {result.total_tasks} (B:{result.beginner_count}/I:{result.intermediate_count}/A:{result.advanced_count})")
            print(f"  Beginner docs+test: {result.beginner_docs_test_ratio:.1%}")
            print(f"  Intent: contribute={result.contribute_ratio:.1%}, study={result.study_ratio:.1%}")
            
            for check_name, passed in result.checks.items():
                print_pass_fail(check_name, passed)
            
            for v in result.violations:
                print(f"  [WARN] {v}")
    
    # 전체 통계
    all_checks = []
    for r in results:
        all_checks.extend(r.checks.values())
    
    all_violations = []
    for r in results:
        all_violations.extend(r.violations)
    
    pass_rate = sum(all_checks) / len(all_checks) if all_checks else 0
    
    # 100% 통과시 passed=True
    passed = pass_rate >= 1.0
    
    summary = {
        "total_repos": len(results),
        "total_checks": len(all_checks),
        "passed_checks": sum(all_checks),
        "pass_rate": pass_rate,
        "passed": passed,  # run_all.py에서 사용
        "violations": all_violations,
        "results": [asdict(r) for r in results],
    }
    
    if verbose:
        print("\n" + "-" * 40)
        print(f"Summary: {sum(all_checks)}/{len(all_checks)} checks passed ({pass_rate:.1%})")
        if all_violations:
            print(f"Violations: {len(all_violations)}")
    
    return summary


if __name__ == "__main__":
    run_tasks_rules_benchmark()
