"""
HealthScore 벤치마크 - is_healthy 임계값 검증

다양한 활동 수준의 레포에 HealthScore를 적용하여 임계값 타당성 검증.
"""
from backend.agents.diagnosis.tools.chaoss_metrics import (
    compute_commit_activity,
    compute_issue_activity,
    compute_pr_activity,
)
from backend.agents.diagnosis.tools.activity_scores import (
    aggregate_activity_score,
    activity_score_to_100,
)
from backend.agents.diagnosis.tools.health_score import create_health_score

# 테스트 레포 (owner, repo, category, estimated_doc_score)
REPOS = [
    # Very Active - 대형 프로젝트
    ("facebook", "react", "very_active", 80),
    ("vercel", "next.js", "very_active", 85),
    ("microsoft", "vscode", "very_active", 90),
    
    # Active - 중형 프로젝트
    ("langchain-ai", "langchain", "active", 75),
    ("astral-sh", "ruff", "active", 70),
    
    # Small - 소규모 프로젝트
    ("Hyeri-hci", "OSSDoctor", "small", 100),
    
    # Archived/Deprecated
    ("facebookarchive", "flux", "archived", 40),
    ("request", "request", "deprecated", 30),
]


def run_benchmark():
    print("HealthScore Benchmark")
    print("=" * 90)
    print(f"{'Repo':<30} {'Cat':<12} {'D':>4} {'A':>4} | {'Health':>6} {'Onboard':>7} {'Healthy':>7}")
    print("-" * 90)
    
    results = []
    
    for owner, repo, cat, doc_est in REPOS:
        try:
            commit = compute_commit_activity(owner, repo, days=90)
            issue = compute_issue_activity(owner, repo, days=90)
            pr = compute_pr_activity(owner, repo, days=90)
            
            breakdown = aggregate_activity_score(commit, issue, pr)
            activity = activity_score_to_100(breakdown)
            
            scores = create_health_score(doc_est, activity)
            
            healthy = "Yes" if scores.is_healthy else "No"
            print(f"{owner}/{repo:<20} {cat:<12} {doc_est:>4} {activity:>4} | {scores.health_score:>6} {scores.onboarding_score:>7} {healthy:>7}")
            
            results.append({
                "repo": f"{owner}/{repo}",
                "cat": cat,
                "doc": doc_est,
                "activity": activity,
                "health": scores.health_score,
                "onboarding": scores.onboarding_score,
                "is_healthy": scores.is_healthy,
            })
        except Exception as e:
            print(f"{owner}/{repo:<20} {cat:<12} ERROR: {e}")
    
    print("=" * 90)
    
    # 분석
    print("\n=== Analysis ===")
    
    healthy_repos = [r for r in results if r["is_healthy"]]
    unhealthy_repos = [r for r in results if not r["is_healthy"]]
    
    print(f"Healthy: {len(healthy_repos)}, Unhealthy: {len(unhealthy_repos)}")
    
    if unhealthy_repos:
        print("\nUnhealthy repos:")
        for r in unhealthy_repos:
            reason = []
            if r["doc"] < 60:
                reason.append(f"doc={r['doc']}<60")
            if r["activity"] < 50:
                reason.append(f"activity={r['activity']}<50")
            print(f"  {r['repo']}: {', '.join(reason)}")
    
    # 카테고리별 평균
    print("\nCategory averages:")
    for cat in ["very_active", "active", "small", "archived", "deprecated"]:
        cat_results = [r for r in results if r["cat"] == cat]
        if cat_results:
            avg_health = sum(r["health"] for r in cat_results) / len(cat_results)
            avg_onboard = sum(r["onboarding"] for r in cat_results) / len(cat_results)
            print(f"  {cat:<12}: health={avg_health:.1f}, onboarding={avg_onboard:.1f}")


if __name__ == "__main__":
    run_benchmark()
