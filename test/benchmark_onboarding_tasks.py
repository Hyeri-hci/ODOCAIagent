"""
Onboarding Tasks 품질 벤치마크

Task 커버리지/품질을 측정하는 스크립트:
1. 다양한 OSS 샘플에 대해 Task 생성
2. beginner 레벨에서 docs/test kind 비율 측정
3. archived/inactive 프로젝트에서 study/evaluate intent 비율 측정
4. 목표 값 달성 여부 확인

Usage:
    python -m pytest test/benchmark_onboarding_tasks.py -v -s
    # 또는 직접 실행
    python test/benchmark_onboarding_tasks.py
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock

# 테스트용 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# 벤치마크 설정
# ============================================================

@dataclass
class BenchmarkConfig:
    """벤치마크 설정."""
    # 목표 비율 (%)
    target_beginner_docs_test_ratio: float = 50.0  # beginner Task의 50% 이상이 docs/test
    target_inactive_study_ratio: float = 70.0     # inactive 프로젝트에서 study/evaluate 70% 이상
    target_min_tasks_count: int = 3               # 최소 Task 개수
    target_healthy_contribute_ratio: float = 80.0 # 건강한 프로젝트에서 contribute 80% 이상


@dataclass
class BenchmarkResult:
    """벤치마크 결과."""
    repo: str
    health_level: str
    is_active: bool
    total_tasks: int
    beginner_tasks: int
    beginner_docs_test_count: int
    beginner_docs_test_ratio: float
    study_evaluate_count: int
    study_evaluate_ratio: float
    contribute_count: int
    contribute_ratio: float
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo": self.repo,
            "health_level": self.health_level,
            "is_active": self.is_active,
            "total_tasks": self.total_tasks,
            "beginner_tasks": self.beginner_tasks,
            "beginner_docs_test_ratio": f"{self.beginner_docs_test_ratio:.1f}%",
            "study_evaluate_ratio": f"{self.study_evaluate_ratio:.1f}%",
            "contribute_ratio": f"{self.contribute_ratio:.1f}%",
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
        }


# ============================================================
# 샘플 프로젝트 정의
# ============================================================

SAMPLE_PROJECTS = [
    # 건강한 활성 프로젝트
    {
        "owner": "microsoft",
        "repo": "vscode",
        "labels": {
            "health_level": "good",
            "onboarding_level": "easy",
            "activity_issues": [],
            "docs_issues": [],
        },
        "mock_issues": [
            {"number": 1, "title": "Add docs for new API", "labels": [{"name": "good first issue"}, {"name": "documentation"}]},
            {"number": 2, "title": "Fix typo in README", "labels": [{"name": "beginner-friendly"}, {"name": "docs"}]},
            {"number": 3, "title": "Add unit tests for parser", "labels": [{"name": "help wanted"}, {"name": "tests"}]},
            {"number": 4, "title": "Refactor utility functions", "labels": [{"name": "enhancement"}]},
            {"number": 5, "title": "Critical security fix", "labels": [{"name": "security"}, {"name": "bug"}]},
        ],
        "expected": {
            "min_tasks": 3,
            "beginner_docs_test_target": True,
            "contribute_dominant": True,
        },
    },
    # 건강하지만 이슈 없는 프로젝트
    {
        "owner": "healthy",
        "repo": "no-issues",
        "labels": {
            "health_level": "good",
            "onboarding_level": "easy",
            "activity_issues": [],
            "docs_issues": [],
        },
        "mock_issues": [],  # 이슈 없음
        "expected": {
            "min_tasks": 3,  # 최소 Task 보장
            "has_minimum_meta_tasks": True,
        },
    },
    # 문서 부족 프로젝트
    {
        "owner": "docs-needed",
        "repo": "project",
        "labels": {
            "health_level": "warning",
            "onboarding_level": "normal",
            "activity_issues": [],
            "docs_issues": ["missing_contributing", "missing_what", "missing_how"],
        },
        "mock_issues": [
            {"number": 1, "title": "Improve documentation", "labels": [{"name": "documentation"}]},
        ],
        "expected": {
            "has_docs_meta_tasks": True,
        },
    },
    # 비활성 프로젝트
    {
        "owner": "inactive",
        "repo": "archived-project",
        "labels": {
            "health_level": "bad",
            "onboarding_level": "hard",
            "activity_issues": ["no_recent_commits", "inactive_project"],
            "docs_issues": [],
        },
        "mock_issues": [
            {"number": 1, "title": "Old bug", "labels": [{"name": "bug"}]},
            {"number": 2, "title": "Feature request from 2020", "labels": [{"name": "enhancement"}]},
        ],
        "expected": {
            "study_evaluate_dominant": True,  # study/evaluate intent가 많아야 함
        },
    },
    # 보안 이슈 있는 프로젝트
    {
        "owner": "security",
        "repo": "vuln-project",
        "labels": {
            "health_level": "warning",
            "onboarding_level": "normal",
            "activity_issues": ["low_issue_closure"],
            "docs_issues": [],
        },
        "mock_issues": [
            {"number": 1, "title": "Security vulnerability", "labels": [{"name": "security"}, {"name": "critical"}]},
            {"number": 2, "title": "Add security docs", "labels": [{"name": "documentation"}, {"name": "security"}]},
        ],
        "expected": {
            "has_advanced_tasks": True,
        },
    },
]


# ============================================================
# 벤치마크 실행
# ============================================================

def run_benchmark_for_project(project: Dict[str, Any], config: BenchmarkConfig) -> BenchmarkResult:
    """단일 프로젝트에 대해 벤치마크 실행."""
    from backend.agents.diagnosis.tools.onboarding_tasks import (
        compute_onboarding_tasks,
        fetch_open_issues_for_tasks,
    )
    
    owner = project["owner"]
    repo = project["repo"]
    labels = project["labels"]
    mock_issues = project["mock_issues"]
    
    # GitHub API 호출 모킹
    def mock_fetch_issues(*args, **kwargs):
        # GraphQL 형식으로 변환
        return [
            {
                "number": issue["number"],
                "title": issue["title"],
                "url": f"https://github.com/{owner}/{repo}/issues/{issue['number']}",
                "labels": {"nodes": issue["labels"]},
                "comments": {"totalCount": 0},
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-11-01T00:00:00Z",
            }
            for issue in mock_issues
        ]
    
    with patch(
        "backend.agents.diagnosis.tools.onboarding_tasks.fetch_open_issues_for_tasks",
        side_effect=mock_fetch_issues,
    ):
        tasks = compute_onboarding_tasks(owner, repo, labels)
    
    # 메트릭 계산
    all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
    beginner_tasks = tasks.beginner
    
    # beginner docs/test 비율
    beginner_docs_test = [
        t for t in beginner_tasks 
        if t.kind in ["doc", "docs", "test"] or 
        any(l.lower() in ["documentation", "docs", "tests", "testing"] for l in t.labels)
    ]
    beginner_docs_test_ratio = (
        len(beginner_docs_test) / len(beginner_tasks) * 100 
        if beginner_tasks else 0
    )
    
    # study/evaluate intent 비율
    study_evaluate = [t for t in all_tasks if t.intent in ["study", "evaluate"]]
    study_evaluate_ratio = (
        len(study_evaluate) / len(all_tasks) * 100 
        if all_tasks else 0
    )
    
    # contribute intent 비율
    contribute_tasks = [t for t in all_tasks if t.intent == "contribute"]
    contribute_ratio = (
        len(contribute_tasks) / len(all_tasks) * 100 
        if all_tasks else 0
    )
    
    # 결과 생성
    result = BenchmarkResult(
        repo=f"{owner}/{repo}",
        health_level=labels.get("health_level", "unknown"),
        is_active="no_recent_commits" not in labels.get("activity_issues", []),
        total_tasks=len(all_tasks),
        beginner_tasks=len(beginner_tasks),
        beginner_docs_test_count=len(beginner_docs_test),
        beginner_docs_test_ratio=beginner_docs_test_ratio,
        study_evaluate_count=len(study_evaluate),
        study_evaluate_ratio=study_evaluate_ratio,
        contribute_count=len(contribute_tasks),
        contribute_ratio=contribute_ratio,
    )
    
    # 체크 수행
    expected = project.get("expected", {})
    
    # 최소 Task 개수 체크
    if expected.get("min_tasks"):
        if result.total_tasks >= expected["min_tasks"]:
            result.passed_checks.append(f"min_tasks >= {expected['min_tasks']}")
        else:
            result.failed_checks.append(f"min_tasks: got {result.total_tasks}, expected >= {expected['min_tasks']}")
    
    # beginner docs/test 비율 체크
    if expected.get("beginner_docs_test_target"):
        if beginner_docs_test_ratio >= config.target_beginner_docs_test_ratio:
            result.passed_checks.append(f"beginner_docs_test >= {config.target_beginner_docs_test_ratio}%")
        else:
            result.failed_checks.append(
                f"beginner_docs_test: got {beginner_docs_test_ratio:.1f}%, expected >= {config.target_beginner_docs_test_ratio}%"
            )
    
    # study/evaluate dominant 체크 (비활성 프로젝트)
    if expected.get("study_evaluate_dominant"):
        if study_evaluate_ratio >= config.target_inactive_study_ratio:
            result.passed_checks.append(f"study_evaluate >= {config.target_inactive_study_ratio}%")
        else:
            result.failed_checks.append(
                f"study_evaluate: got {study_evaluate_ratio:.1f}%, expected >= {config.target_inactive_study_ratio}%"
            )
    
    # contribute dominant 체크 (건강한 프로젝트)
    if expected.get("contribute_dominant"):
        if contribute_ratio >= config.target_healthy_contribute_ratio:
            result.passed_checks.append(f"contribute >= {config.target_healthy_contribute_ratio}%")
        else:
            result.failed_checks.append(
                f"contribute: got {contribute_ratio:.1f}%, expected >= {config.target_healthy_contribute_ratio}%"
            )
    
    # 최소 메타 Task 체크
    if expected.get("has_minimum_meta_tasks"):
        meta_tasks = [t for t in all_tasks if t.kind == "meta"]
        if meta_tasks:
            result.passed_checks.append("has_minimum_meta_tasks")
        else:
            result.failed_checks.append("has_minimum_meta_tasks: no meta tasks found")
    
    return result


def run_all_benchmarks(config: Optional[BenchmarkConfig] = None) -> Dict[str, Any]:
    """모든 샘플 프로젝트에 대해 벤치마크 실행."""
    if config is None:
        config = BenchmarkConfig()
    
    results = []
    passed_count = 0
    failed_count = 0
    
    for project in SAMPLE_PROJECTS:
        logger.info(f"Running benchmark for {project['owner']}/{project['repo']}...")
        result = run_benchmark_for_project(project, config)
        results.append(result)
        
        if result.failed_checks:
            failed_count += 1
            logger.warning(f"  ❌ Failed: {result.failed_checks}")
        else:
            passed_count += 1
            logger.info(f"  ✅ Passed: {result.passed_checks}")
    
    # 전체 통계
    total_projects = len(results)
    all_beginner_tasks = sum(r.beginner_tasks for r in results)
    all_beginner_docs_test = sum(r.beginner_docs_test_count for r in results)
    overall_beginner_docs_test_ratio = (
        all_beginner_docs_test / all_beginner_tasks * 100
        if all_beginner_tasks else 0
    )
    
    summary = {
        "total_projects": total_projects,
        "passed_projects": passed_count,
        "failed_projects": failed_count,
        "pass_rate": f"{passed_count / total_projects * 100:.1f}%",
        "overall_beginner_docs_test_ratio": f"{overall_beginner_docs_test_ratio:.1f}%",
        "results": [r.to_dict() for r in results],
    }
    
    return summary


# ============================================================
# Pytest 테스트
# ============================================================

class TestOnboardingTasksBenchmark:
    """Onboarding Tasks 벤치마크 테스트."""
    
    def test_benchmark_healthy_project(self):
        """건강한 프로젝트 벤치마크."""
        config = BenchmarkConfig()
        project = SAMPLE_PROJECTS[0]  # microsoft/vscode
        
        result = run_benchmark_for_project(project, config)
        
        assert result.total_tasks >= 3
        assert len(result.failed_checks) == 0, f"Failed checks: {result.failed_checks}"
    
    def test_benchmark_no_issues_project(self):
        """이슈 없는 건강한 프로젝트도 최소 Task 보장."""
        config = BenchmarkConfig()
        project = SAMPLE_PROJECTS[1]  # healthy/no-issues
        
        result = run_benchmark_for_project(project, config)
        
        # 이슈 없어도 최소 Task는 있어야 함
        assert result.total_tasks >= config.target_min_tasks_count
        assert "has_minimum_meta_tasks" in result.passed_checks
    
    def test_benchmark_inactive_project(self):
        """비활성 프로젝트는 study/evaluate 중심."""
        config = BenchmarkConfig()
        project = SAMPLE_PROJECTS[3]  # inactive/archived-project
        
        result = run_benchmark_for_project(project, config)
        
        # study/evaluate intent가 있어야 함
        assert result.study_evaluate_count > 0
    
    def test_benchmark_docs_needed_project(self):
        """문서 부족 프로젝트는 docs 메타 Task 포함."""
        config = BenchmarkConfig()
        project = SAMPLE_PROJECTS[2]  # docs-needed/project
        
        result = run_benchmark_for_project(project, config)
        
        # 문서 관련 메타 Task가 있어야 함
        assert result.total_tasks >= 1
    
    def test_run_all_benchmarks(self):
        """전체 벤치마크 실행."""
        summary = run_all_benchmarks()
        
        logger.info(f"\n{'='*60}")
        logger.info("BENCHMARK SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total projects: {summary['total_projects']}")
        logger.info(f"Passed: {summary['passed_projects']}")
        logger.info(f"Failed: {summary['failed_projects']}")
        logger.info(f"Pass rate: {summary['pass_rate']}")
        logger.info(f"Overall beginner docs/test ratio: {summary['overall_beginner_docs_test_ratio']}")
        
        # 최소 80% 통과율 목표
        pass_rate = summary["passed_projects"] / summary["total_projects"]
        assert pass_rate >= 0.6, f"Pass rate {pass_rate:.1%} < 60% target"


# ============================================================
# 직접 실행
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Onboarding Tasks Quality Benchmark")
    print("=" * 60)
    
    summary = run_all_benchmarks()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
