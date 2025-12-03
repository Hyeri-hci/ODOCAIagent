"""
두 레포지토리 진단 결과 비교 스크립트.

Usage:
    python backend/scripts/compare_repos.py repo1 repo2
    python backend/scripts/compare_repos.py repo1 repo2 --output-json
"""
import argparse
import json
import os
import sys
import logging
from typing import Tuple, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.agents.supervisor.service import run_supervisor_diagnosis
from backend.core.models import DiagnosisCoreResult

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def parse_repo_string(repo_str: str) -> Tuple[str, str, str]:
    """
    'owner/repo' 또는 'owner/repo@ref' 문자열을 파싱합니다.
    ref가 없으면 'main'을 기본값으로 사용합니다.
    (benchmark_repos.py와 동일한 로직)
    """
    repo_str = repo_str.strip()
    ref = "main"
    
    if "@" in repo_str:
        repo_part, ref = repo_str.split("@", 1)
    else:
        repo_part = repo_str
        
    if "/" not in repo_part:
        raise ValueError(f"Invalid repo format: {repo_str}. Expected 'owner/repo' or 'owner/repo@ref'")
        
    owner, repo = repo_part.split("/", 1)
    return owner.strip(), repo.strip(), ref.strip()

def run_diagnosis_safe(repo_str: str) -> DiagnosisCoreResult:
    """진단을 실행하고 에러 발생 시 종료합니다."""
    try:
        owner, repo, ref = parse_repo_string(repo_str)
        logger.info(f"Diagnosing {repo_str}...")
        result, error_msg = run_supervisor_diagnosis(owner, repo, ref)
        
        if error_msg:
            logger.error(f"Failed to diagnose {repo_str}: {error_msg}")
            sys.exit(1)
        if not result:
            logger.error(f"Failed to diagnose {repo_str}: Unknown error (Result is None)")
            sys.exit(1)
            
        return result
    except Exception as e:
        logger.error(f"Exception while diagnosing {repo_str}: {e}")
        sys.exit(1)

def print_comparison_table(repo1_str: str, result1: DiagnosisCoreResult, 
                           repo2_str: str, result2: DiagnosisCoreResult):
    """두 진단 결과를 텍스트 표 형태로 출력합니다."""
    
    # 데이터 준비
    metrics = [
        ("Docs Quality", result1.documentation_quality, result2.documentation_quality),
        ("Activity", result1.activity_maintainability, result2.activity_maintainability),
        ("Health Score", f"{result1.health_score} ({result1.health_level})", f"{result2.health_score} ({result2.health_level})"),
        ("Onboarding", f"{result1.onboarding_score} ({result1.onboarding_level})", f"{result2.onboarding_score} ({result2.onboarding_level})"),
        ("Dep Complexity", result1.dependency_complexity_score, result2.dependency_complexity_score),
        ("Dep Flags", ",".join(result1.dependency_flags) or "-", ",".join(result2.dependency_flags) or "-"),
        ("Docs Issues", len(result1.docs_issues), len(result2.docs_issues)),
        ("Activity Issues", len(result1.activity_issues), len(result2.activity_issues)),
    ]
    
    # 출력
    print(f"\nComparing Repositories:")
    print(f"Repo A: {repo1_str}")
    print(f"Repo B: {repo2_str}")
    print("\n" + "-" * 80)
    print(f"{'Metric':<25} {'Repo A':<25} {'Repo B':<25}")
    print("-" * 80)
    
    for label, val1, val2 in metrics:
        # 긴 문자열 자르기 (특히 Flags)
        val1_str = str(val1)
        val2_str = str(val2)
        if len(val1_str) > 23: val1_str = val1_str[:20] + "..."
        if len(val2_str) > 23: val2_str = val2_str[:20] + "..."
        
        print(f"{label:<25} {val1_str:<25} {val2_str:<25}")
    print("-" * 80 + "\n")

def print_comparison_json(repo1_str: str, result1: DiagnosisCoreResult,
                          repo2_str: str, result2: DiagnosisCoreResult):
    """두 진단 결과를 JSON 형태로 출력합니다."""
    
    def to_summary_dict(repo_id, res: DiagnosisCoreResult):
        return {
            "id": repo_id,
            "scores": {
                "documentation_quality": res.documentation_quality,
                "activity_maintainability": res.activity_maintainability,
                "health_score": res.health_score,
                "onboarding_score": res.onboarding_score,
                "dependency_complexity_score": res.dependency_complexity_score,
            },
            "levels": {
                "health_level": res.health_level,
                "onboarding_level": res.onboarding_level,
            },
            "issues": {
                "dependency_flags": res.dependency_flags,
                "docs_issues_count": len(res.docs_issues),
                "activity_issues_count": len(res.activity_issues),
                "docs_issues": res.docs_issues,
                "activity_issues": res.activity_issues,
            }
        }

    output = {
        "repo_a": to_summary_dict(repo1_str, result1),
        "repo_b": to_summary_dict(repo2_str, result2),
    }
    
    print(json.dumps(output, indent=2, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description="Compare diagnosis results of two GitHub repositories.")
    parser.add_argument("repo1", help="First repository (owner/repo or owner/repo@ref)")
    parser.add_argument("repo2", help="Second repository (owner/repo or owner/repo@ref)")
    parser.add_argument("--output-json", action="store_true", help="Output result as JSON")
    
    args = parser.parse_args()
    
    # 진단 실행
    result1 = run_diagnosis_safe(args.repo1)
    result2 = run_diagnosis_safe(args.repo2)
    
    # 결과 출력
    if args.output_json:
        print_comparison_json(args.repo1, result1, args.repo2, result2)
    else:
        print_comparison_table(args.repo1, result1, args.repo2, result2)

if __name__ == "__main__":
    main()
