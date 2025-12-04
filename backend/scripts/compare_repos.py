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

from backend.api.diagnosis_service import diagnose_repository

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

def run_diagnosis_safe(repo_str: str) -> Dict[str, Any]:
    """진단을 실행하고 에러 발생 시 종료합니다."""
    try:
        owner, repo, ref = parse_repo_string(repo_str)
        logger.info(f"Diagnosing {repo_str}...")
        
        # CLI에서는 기본적으로 LLM 요약 없이 빠르게 진행 (필요시 옵션 처리 가능)
        # 하지만 compare_repos는 상세 비교이므로 LLM 요약이 있으면 좋을 수도 있음.
        # 일단 속도를 위해 False로 설정하거나, 인자로 받을 수 있게 확장 가능.
        # 여기서는 사용자 요청에 따라 "점수 계산은 항상 빠르게, LLM 요약은 선택 사항" 취지를 살려 False로 둠.
        response = diagnose_repository(owner, repo, ref, use_llm_summary=False)
        
        if not response["ok"]:
            logger.error(f"Failed to diagnose {repo_str}: {response['error']}")
            sys.exit(1)
            
        return response["data"]
    except Exception as e:
        logger.error(f"Exception while diagnosing {repo_str}: {e}")
        sys.exit(1)

def print_comparison_table(repo1_str: str, result1: Dict[str, Any], 
                           repo2_str: str, result2: Dict[str, Any]):
    """두 진단 결과를 텍스트 표 형태로 출력합니다."""
    
    # 데이터 준비
    metrics = [
        ("Docs Quality", result1["documentation_quality"], result2["documentation_quality"]),
        ("Activity", result1["activity_maintainability"], result2["activity_maintainability"]),
        ("Health Score", f"{result1['health_score']} ({result1['health_level']})", f"{result2['health_score']} ({result2['health_level']})"),
        ("Onboarding", f"{result1['onboarding_score']} ({result1['onboarding_level']})", f"{result2['onboarding_score']} ({result2['onboarding_level']})"),
        ("Dep Complexity", result1["dependency_complexity_score"], result2["dependency_complexity_score"]),
        ("Dep Flags", ",".join(result1["dependency_flags"]) or "-", ",".join(result2["dependency_flags"]) or "-"),
        ("Docs Issues", result1["docs_issues_count"], result2["docs_issues_count"]),
        ("Activity Issues", result1["activity_issues_count"], result2["activity_issues_count"]),
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

def print_comparison_json(repo1_str: str, result1: Dict[str, Any],
                          repo2_str: str, result2: Dict[str, Any]):
    """두 진단 결과를 JSON 형태로 출력합니다."""
    
    # 이미 DTO(dict) 형태이므로 바로 사용 가능
    # 다만 구조를 조금 더 명확히 하기 위해 재구성할 수도 있지만,
    # 여기서는 간단히 DTO 자체를 출력하거나, 기존 포맷을 유지하기 위해 약간의 매핑을 할 수 있음.
    # 사용자 요청에 따라 "JSON 출력은 {'repo_a': dto1.to_dict(), ...}" 형태로 교체.
    
    output = {
        "repo_a": result1,
        "repo_b": result2,
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
