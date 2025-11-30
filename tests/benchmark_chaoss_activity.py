"""
CHAOSS Activity Score v1.0 Benchmark

점수 산정 공식 검증을 위한 벤치마크 스크립트.
Spec: docs/CHAOSS_ACTIVITY_SCORE_v1.md

사용법:
    python -m test.benchmark_chaoss_activity
    python -m test.benchmark_chaoss_activity --quick
    python -m test.benchmark_chaoss_activity --output results.json
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from typing import List, Dict, Any

from backend.agents.diagnosis.tools.chaoss_metrics import (
    compute_commit_activity,
    compute_issue_activity,
    compute_pr_activity,
)
from backend.agents.diagnosis.tools.activity_scores import (
    score_commit_activity,
    score_issue_activity,
    score_pr_activity,
    aggregate_activity_score,
    activity_score_to_100,
)

# 벤치마크 대상 레포 (카테고리별)
BENCHMARK_REPOS = [
    # 매우 활발한 대형 프로젝트
    {"owner": "facebook", "repo": "react", "category": "very_active"},
    {"owner": "vercel", "repo": "next.js", "category": "very_active"},
    {"owner": "microsoft", "repo": "vscode", "category": "very_active"},
    
    # 활발한 중형 프로젝트
    {"owner": "langchain-ai", "repo": "langchain", "category": "active"},
    {"owner": "astral-sh", "repo": "ruff", "category": "active"},
    
    # 소규모/개인 프로젝트
    {"owner": "Hyeri-hci", "repo": "OSSDoctor", "category": "small"},
    
    # 유지보수 중단/아카이브 프로젝트
    {"owner": "facebookarchive", "repo": "flux", "category": "archived"},
    {"owner": "request", "repo": "request", "category": "deprecated"},
]


def run_benchmark(repos: List[Dict[str, str]], days: int = 90) -> List[Dict[str, Any]]:
    """벤치마크 실행."""
    results = []
    
    for repo_info in repos:
        owner = repo_info["owner"]
        repo = repo_info["repo"]
        category = repo_info.get("category", "unknown")
        
        print(f"[{category}] {owner}/{repo}...", end=" ", flush=True)
        
        try:
            # 메트릭 수집
            commit_m = compute_commit_activity(owner, repo, days=days)
            issue_m = compute_issue_activity(owner, repo, days=days)
            pr_m = compute_pr_activity(owner, repo, days=days)
            
            # 점수 계산
            breakdown = aggregate_activity_score(commit_m, issue_m, pr_m)
            
            result = {
                "owner": owner,
                "repo": repo,
                "category": category,
                "window_days": days,
                
                # Raw metrics (요약)
                "commits": commit_m.total_commits,
                "unique_authors": commit_m.unique_authors,
                "commits_per_week": round(commit_m.commits_per_week, 2),
                "days_since_last_commit": commit_m.days_since_last_commit,
                
                "issues_opened": issue_m.opened_issues_in_window,
                "issues_closed": issue_m.closed_issues_in_window,
                "issue_closure_ratio": round(issue_m.issue_closure_ratio, 3),
                "median_issue_close_days": (
                    round(issue_m.median_time_to_close_days, 2)
                    if issue_m.median_time_to_close_days else None
                ),
                
                "prs_opened": pr_m.prs_in_window,
                "prs_merged": pr_m.merged_in_window,
                "pr_merge_ratio": round(pr_m.pr_merge_ratio, 3),
                "median_pr_merge_days": (
                    round(pr_m.median_time_to_merge_days, 2)
                    if pr_m.median_time_to_merge_days else None
                ),
                
                # Sub-scores (0-1)
                "score_commit": breakdown.commit_score,
                "score_issue": breakdown.issue_score,
                "score_pr": breakdown.pr_score,
                
                # Final score (0-100)
                "activity_score": activity_score_to_100(breakdown),
            }
            
            results.append(result)
            print(f"score={result['activity_score']}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "owner": owner,
                "repo": repo,
                "category": category,
                "error": str(e),
            })
    
    return results


def print_table(results: List[Dict[str, Any]]) -> None:
    """결과를 테이블 형식으로 출력."""
    print()
    print("=" * 120)
    print(f"{'Repo':<35} {'Cat':<12} {'Commits':>7} {'Issues':>7} {'PRs':>7} "
          f"{'C.Sc':>6} {'I.Sc':>6} {'P.Sc':>6} {'TOTAL':>6}")
    print("=" * 120)
    
    # 카테고리별 정렬
    category_order = {"very_active": 0, "active": 1, "small": 2, "archived": 3, "deprecated": 4}
    sorted_results = sorted(
        [r for r in results if "error" not in r],
        key=lambda x: (category_order.get(x["category"], 99), -x["activity_score"])
    )
    
    current_category = None
    for r in sorted_results:
        if r["category"] != current_category:
            if current_category is not None:
                print("-" * 120)
            current_category = r["category"]
        
        repo_name = f"{r['owner']}/{r['repo']}"
        if len(repo_name) > 33:
            repo_name = repo_name[:30] + "..."
        
        print(f"{repo_name:<35} {r['category']:<12} "
              f"{r['commits']:>7} {r['issues_opened']:>7} {r['prs_opened']:>7} "
              f"{r['score_commit']:>6.3f} {r['score_issue']:>6.3f} {r['score_pr']:>6.3f} "
              f"{r['activity_score']:>6}")
    
    print("=" * 120)
    
    # 에러 레포 출력
    errors = [r for r in results if "error" in r]
    if errors:
        print("\nErrors:")
        for r in errors:
            print(f"  {r['owner']}/{r['repo']}: {r['error']}")


def print_analysis(results: List[Dict[str, Any]]) -> None:
    """점수 분석 및 개선점 제안."""
    valid = [r for r in results if "error" not in r]
    if not valid:
        return
    
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    
    # 카테고리별 평균
    categories = {}
    for r in valid:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r["activity_score"])
    
    print("\nCategory Averages:")
    for cat in ["very_active", "active", "small", "archived", "deprecated"]:
        if cat in categories:
            scores = categories[cat]
            avg = sum(scores) / len(scores)
            print(f"  {cat:<15}: {avg:.1f} (n={len(scores)})")
    
    # 점수 분포 확인
    scores = [r["activity_score"] for r in valid]
    print(f"\nScore Distribution:")
    print(f"  Min: {min(scores)}, Max: {max(scores)}, Range: {max(scores) - min(scores)}")
    
    # 이상치 탐지
    print("\nPotential Issues:")
    
    # 1. 소규모 PR 때문에 PR 점수가 과대평가된 경우
    for r in valid:
        if r["prs_opened"] < 5 and r["score_pr"] > 0.8:
            print(f"  [PR Overfit] {r['owner']}/{r['repo']}: "
                  f"PRs={r['prs_opened']}, pr_score={r['score_pr']:.3f}")
    
    # 2. 이슈가 없어서 중립 점수(0.5)인 경우
    for r in valid:
        if r["issues_opened"] == 0 and r["score_issue"] == 0.5:
            print(f"  [No Issues] {r['owner']}/{r['repo']}: "
                  f"issue_score=0.5 (neutral)")
    
    # 3. 활발한데 점수가 낮은 경우
    for r in valid:
        if r["category"] == "very_active" and r["activity_score"] < 60:
            print(f"  [Low Score for Active] {r['owner']}/{r['repo']}: "
                  f"score={r['activity_score']}")
    
    # 4. 아카이브인데 점수가 높은 경우
    for r in valid:
        if r["category"] in ("archived", "deprecated") and r["activity_score"] > 50:
            print(f"  [High Score for Archived] {r['owner']}/{r['repo']}: "
                  f"score={r['activity_score']}")


def save_json(results: List[Dict[str, Any]], path: str) -> None:
    """JSON 파일로 저장."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {path}")


def save_csv(results: List[Dict[str, Any]], path: str) -> None:
    """CSV 파일로 저장."""
    import csv
    
    valid = [r for r in results if "error" not in r]
    if not valid:
        return
    
    fieldnames = list(valid[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid)
    print(f"\nSaved to {path}")


def main():
    parser = argparse.ArgumentParser(description="CHAOSS Activity Benchmark")
    parser.add_argument("--days", type=int, default=90, help="Window days (default: 90)")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file")
    parser.add_argument("--csv", type=str, help="Output CSV file")
    parser.add_argument("--quick", action="store_true", help="Quick mode (fewer repos)")
    args = parser.parse_args()
    
    repos = BENCHMARK_REPOS
    if args.quick:
        # Quick 모드: 카테고리당 1개씩만
        seen = set()
        repos = []
        for r in BENCHMARK_REPOS:
            if r["category"] not in seen:
                repos.append(r)
                seen.add(r["category"])
    
    print(f"Benchmarking {len(repos)} repositories (window={args.days} days)...")
    print()
    
    results = run_benchmark(repos, days=args.days)
    
    print_table(results)
    print_analysis(results)
    
    if args.output:
        save_json(results, args.output)
    if args.csv:
        save_csv(results, args.csv)


if __name__ == "__main__":
    main()
