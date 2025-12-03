"""
다중 레포지토리 벤치마크 실행 스크립트.

Usage:
    python backend/scripts/benchmark_repos.py
    python backend/scripts/benchmark_repos.py --preset oss_eval --output-format json
    python backend/scripts/benchmark_repos.py --output-path my_results.csv
"""
import argparse
import csv
import json
import os
import sys
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.agents.supervisor.service import run_supervisor_diagnosis

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 기본 샘플 레포지토리 목록
SAMPLE_REPOS = [
    ("Hyeri-hci", "ODOCAIagent", "main"),
    ("langchain-ai", "langgraph", "main"),
    ("streamlit", "streamlit", "develop"),
]

# OSS 평가용 프리셋
OSS_EVAL_REPOS = [
    ("Hyeri-hci", "ODOCAIagent", "main"),
    ("Hyeri-hci", "OSSDoctor", "main"),
    ("Hyeri-hci", "odoc_test_repo", "main"),
    ("facebook", "react", "main"),
    ("microsoft", "vscode", "main"),
]

def parse_repo_string(repo_str: str) -> Tuple[str, str, str]:
    """
    'owner/repo' 또는 'owner/repo@ref' 문자열을 파싱합니다.
    ref가 없으면 'main'을 기본값으로 사용합니다.
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

def load_repos_from_file(file_path: str) -> List[Tuple[str, str, str]]:
    repos = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    repos.append(parse_repo_string(line))
                except ValueError as e:
                    logger.warning(f"Skipping invalid line in {file_path}: {e}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    return repos

def run_benchmark(repos: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
    results = []
    total = len(repos)
    
    for idx, (owner, repo, ref) in enumerate(repos, 1):
        repo_id = f"{owner}/{repo}@{ref}"
        logger.info(f"[{idx}/{total}] Diagnosing {repo_id}...")
        
        entry = {
            "repo_id": repo_id,
            "documentation_quality": None,
            "activity_maintainability": None,
            "health_score": None,
            "health_level": None,
            "onboarding_score": None,
            "onboarding_level": None,
            "dependency_complexity_score": None,
            "dependency_flags": None,
            "docs_issues_count": 0,
            "activity_issues_count": 0,
            "error": False,
            "error_message": None,
        }
        
        try:
            # run_supervisor_diagnosis 호출
            result, error_msg = run_supervisor_diagnosis(owner, repo, ref)
            
            if error_msg:
                entry["error"] = True
                entry["error_message"] = error_msg
                logger.warning(f"  -> Error: {error_msg}")
            elif result:
                entry["documentation_quality"] = result.documentation_quality
                entry["activity_maintainability"] = result.activity_maintainability
                entry["health_score"] = result.health_score
                entry["health_level"] = result.health_level
                entry["onboarding_score"] = result.onboarding_score
                entry["onboarding_level"] = result.onboarding_level
                
                # 의존성 복잡도
                entry["dependency_complexity_score"] = result.dependency_complexity_score
                entry["dependency_flags"] = ",".join(result.dependency_flags) if result.dependency_flags else ""
                
                entry["docs_issues_count"] = len(result.docs_issues)
                entry["activity_issues_count"] = len(result.activity_issues)
                
                logger.info(f"  -> Success. Health: {result.health_score}, Complexity: {result.dependency_complexity_score}")
            else:
                entry["error"] = True
                entry["error_message"] = "Unknown error: Result is None"
                logger.warning("  -> Result is None")
                
        except Exception as e:
            entry["error"] = True
            entry["error_message"] = str(e)
            logger.error(f"  -> Exception: {e}")
            
        results.append(entry)
        
    return results

def save_results(results: List[Dict[str, Any]], output_path: str, output_format: str):
    if not results:
        logger.warning("No results to save.")
        return

    try:
        if output_format == "csv":
            keys = [
                "repo_id", "documentation_quality", "activity_maintainability",
                "health_score", "health_level",
                "onboarding_score", "onboarding_level",
                "dependency_complexity_score", "dependency_flags",
                "docs_issues_count", "activity_issues_count",
                "error", "error_message"
            ]
            with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in results:
                    # CSV에 없는 키가 있을 수 있으므로 필터링하거나 get 사용
                    filtered_row = {k: row.get(k) for k in keys}
                    writer.writerow(filtered_row)
        else: # json
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
        logger.info(f"Results saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to save results: {e}")

def main():
    parser = argparse.ArgumentParser(description="Benchmark GitHub repositories for ODOCAIagent diagnosis.")
    parser.add_argument("--repos-file", help="Path to a file containing list of repos (owner/repo per line)")
    parser.add_argument("--preset", help="Preset name (e.g., 'oss_eval')")
    parser.add_argument("--output-format", choices=["csv", "json"], default="csv", help="Output format (csv or json)")
    parser.add_argument("--output-path", help="Path to save the results")
    
    args = parser.parse_args()
    
    # 레포 목록 로드
    if args.repos_file:
        repos = load_repos_from_file(args.repos_file)
        logger.info(f"Loaded {len(repos)} repos from file: {args.repos_file}")
    elif args.preset == "oss_eval":
        repos = OSS_EVAL_REPOS
        logger.info(f"Using 'oss_eval' preset with {len(repos)} repos.")
    elif args.preset:
        logger.error(f"Unknown preset: {args.preset}")
        sys.exit(1)
    else:
        repos = SAMPLE_REPOS
        logger.info("No repos file or preset provided. Using sample repos.")

    # 벤치마크 실행
    results = run_benchmark(repos)
    
    # 결과 저장
    if args.output_path:
        output_path = args.output_path
    else:
        date_str = datetime.now().strftime("%Y%m%d")
        ext = args.output_format
        output_path = f"benchmark_results_{date_str}.{ext}"
        
    save_results(results, output_path, args.output_format)

if __name__ == "__main__":
    main()
