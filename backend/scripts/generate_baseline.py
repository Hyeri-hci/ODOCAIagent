"""
베이스라인 JSON 자동 생성 스크립트.

Usage:
    python backend/scripts/generate_baseline.py
    python backend/scripts/generate_baseline.py --output tests/fixtures/oss_eval_baseline.json
    python backend/scripts/generate_baseline.py --repos "owner/repo@ref,owner2/repo2"
"""
import argparse
import json
import os
import sys
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.api.agent_service import run_agent_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 기본 OSS 평가용 레포지토리 목록
DEFAULT_REPOS = [
    ("Hyeri-hci", "ODOCAIagent", "main"),
    ("Hyeri-hci", "OSSDoctor", "main"),
    ("Hyeri-hci", "odoc_test_repo", "main"),
    ("facebook", "react", "main"),
    ("microsoft", "vscode", "main"),
]


def parse_repo_string(repo_str: str) -> Tuple[str, str, str]:
    """'owner/repo@ref' 문자열을 파싱합니다."""
    repo_str = repo_str.strip()
    ref = "main"
    
    if "@" in repo_str:
        repo_part, ref = repo_str.split("@", 1)
    else:
        repo_part = repo_str
        
    if "/" not in repo_part:
        raise ValueError(f"Invalid repo format: {repo_str}")
        
    owner, repo = repo_part.split("/", 1)
    return owner.strip(), repo.strip(), ref.strip()


def generate_baseline(repos: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
    """레포지토리 목록에 대해 베이스라인 데이터를 생성합니다."""
    results = []
    total = len(repos)
    
    for idx, (owner, repo, ref) in enumerate(repos, 1):
        repo_id = f"{owner}/{repo}@{ref}"
        logger.info(f"[{idx}/{total}] Generating baseline for {repo_id}...")
        
        entry = {
            "repo_id": repo_id,
            "documentation_quality": None,
            "activity_maintainability": None,
            "health_score": None,
            "health_level": None,
            "onboarding_score": None,
            "onboarding_level": None,
            "dependency_complexity_score": None,
            "dependency_flags": "",
            "docs_issues_count": 0,
            "activity_issues_count": 0,
            "error": False,
            "error_message": None,
            "generated_at": datetime.now().isoformat(),
        }
        
        try:
            result = run_agent_task(
                task_type="diagnose_repo",
                owner=owner,
                repo=repo,
                ref=ref,
                use_llm_summary=False
            )
            
            if not result["ok"]:
                entry["error"] = True
                entry["error_message"] = result.get("error")
                logger.warning(f"  -> Error: {result.get('error')}")
            else:
                data = result["data"]
                entry["documentation_quality"] = data["documentation_quality"]
                entry["activity_maintainability"] = data["activity_maintainability"]
                entry["health_score"] = data["health_score"]
                entry["health_level"] = data["health_level"]
                entry["onboarding_score"] = data["onboarding_score"]
                entry["onboarding_level"] = data["onboarding_level"]
                entry["dependency_complexity_score"] = data["dependency_complexity_score"]
                entry["dependency_flags"] = ",".join(data["dependency_flags"]) if data["dependency_flags"] else ""
                entry["docs_issues_count"] = data["docs_issues_count"]
                entry["activity_issues_count"] = data["activity_issues_count"]
                
                logger.info(f"  -> Success. Health: {data['health_score']}, Onboarding: {data['onboarding_score']}")
                
        except Exception as e:
            entry["error"] = True
            entry["error_message"] = str(e)
            logger.error(f"  -> Exception: {e}")
        
        results.append(entry)
    
    return results


def save_baseline(results: List[Dict[str, Any]], output_path: str):
    """베이스라인을 JSON 파일로 저장합니다."""
    # generated_at 필드는 비교용이 아니므로 저장 시 제거
    clean_results = []
    for entry in results:
        clean_entry = {k: v for k, v in entry.items() if k != "generated_at"}
        clean_results.append(clean_entry)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Baseline saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate baseline JSON for regression tests.")
    parser.add_argument(
        "--output", "-o",
        default="tests/fixtures/oss_eval_baseline.json",
        help="Output path for baseline JSON"
    )
    parser.add_argument(
        "--repos",
        help="Comma-separated list of repos (owner/repo@ref)"
    )
    
    args = parser.parse_args()
    
    # 레포 목록 결정
    if args.repos:
        repos = [parse_repo_string(r) for r in args.repos.split(",")]
        logger.info(f"Using custom repos: {len(repos)} repos")
    else:
        repos = DEFAULT_REPOS
        logger.info(f"Using default repos: {len(repos)} repos")
    
    # 베이스라인 생성
    results = generate_baseline(repos)
    
    # 저장
    save_baseline(results, args.output)
    
    # 요약 출력
    success_count = sum(1 for r in results if not r["error"])
    logger.info(f"\nSummary: {success_count}/{len(results)} repos processed successfully")


if __name__ == "__main__":
    main()
