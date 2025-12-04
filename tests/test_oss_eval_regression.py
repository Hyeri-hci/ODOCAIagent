import json
import os
import pytest
from typing import Dict, Any, Tuple

from backend.agents.supervisor.service import run_supervisor_diagnosis
from backend.core.models import DiagnosisCoreResult

# 픽스처 파일 경로
BASELINE_FILE = os.path.join(os.path.dirname(__file__), "fixtures", "oss_eval_baseline.json")

def parse_repo_string(repo_str: str) -> Tuple[str, str, str]:
    """
    'owner/repo@ref' 문자열을 파싱합니다.
    (benchmark_repos.py와 동일한 로직)
    """
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

@pytest.fixture
def baseline_data():
    """베이스라인 데이터를 로드합니다."""
    if not os.path.exists(BASELINE_FILE):
        pytest.skip(f"Baseline file not found: {BASELINE_FILE}")
    
    with open(BASELINE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.slow
def test_oss_eval_regression(baseline_data):
    """
    OSS 벤치마크 베이스라인 회귀 테스트.
    각 레포지토리에 대해 진단을 다시 수행하고, 결과가 허용 오차 범위 내인지 확인합니다.
    """
    for entry in baseline_data:
        repo_id = entry.get("repo_id")
        
        # 에러가 있었던 항목은 건너뜀 (또는 에러가 재현되는지 확인할 수도 있음)
        if entry.get("error"):
            continue
            
        print(f"\nTesting regression for {repo_id}...")
        
        owner, repo, ref = parse_repo_string(repo_id)
        
        # 진단 실행
        result, error_msg = run_supervisor_diagnosis(owner, repo, ref)
        
        assert error_msg is None, f"Diagnosis failed for {repo_id}: {error_msg}"
        assert result is not None, f"Diagnosis result is None for {repo_id}"
        
        # 1. 점수 비교 (허용 오차 +/- 5)
        assert abs(result.documentation_quality - entry["documentation_quality"]) <= 5, \
            f"Docs quality changed too much for {repo_id}: {entry['documentation_quality']} -> {result.documentation_quality}"
            
        assert abs(result.activity_maintainability - entry["activity_maintainability"]) <= 5, \
            f"Activity score changed too much for {repo_id}: {entry['activity_maintainability']} -> {result.activity_maintainability}"
            
        assert abs(result.health_score - entry["health_score"]) <= 5, \
            f"Health score changed too much for {repo_id}: {entry['health_score']} -> {result.health_score}"
            
        assert abs(result.onboarding_score - entry["onboarding_score"]) <= 5, \
            f"Onboarding score changed too much for {repo_id}: {entry['onboarding_score']} -> {result.onboarding_score}"
            
        # 2. 레벨 비교 (정확히 일치해야 함)
        assert result.health_level == entry["health_level"], \
            f"Health level changed for {repo_id}: {entry['health_level']} -> {result.health_level}"
            
        assert result.onboarding_level == entry["onboarding_level"], \
            f"Onboarding level changed for {repo_id}: {entry['onboarding_level']} -> {result.onboarding_level}"
            
        # 3. 의존성 복잡도 (허용 오차 +/- 10)
        # entry에 값이 없는 경우(None) 0으로 취급
        baseline_dep_score = entry.get("dependency_complexity_score") or 0
        assert abs(result.dependency_complexity_score - baseline_dep_score) <= 10, \
            f"Dependency complexity changed too much for {repo_id}: {baseline_dep_score} -> {result.dependency_complexity_score}"
            
        # 4. 의존성 플래그 (Superset 검사)
        # baseline에 있는 플래그는 모두 현재 결과에도 있어야 함
        baseline_flags = set(entry.get("dependency_flags", "").split(",")) if entry.get("dependency_flags") else set()
        current_flags = set(result.dependency_flags)
        
        # 빈 문자열 split 결과 처리
        baseline_flags.discard("")
        
        missing_flags = baseline_flags - current_flags
        assert not missing_flags, \
            f"Missing dependency flags for {repo_id}: {missing_flags}"
