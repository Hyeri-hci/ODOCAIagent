"""
OSS 평가 회귀 테스트.
에이전트 스코어 변경을 감지하기 위한 regression 테스트.

실제 GitHub API 호출이 필요하므로 slow 마커 적용.
--skip-slow 옵션으로 건너뛸 수 있음.
"""
import json
import os
import pytest

# 전체 모듈에 slow 마커 적용 (실제 API 호출 필요)
pytestmark = pytest.mark.slow
from typing import Dict, Any, Tuple

from backend.api.agent_service import run_agent_task

# 픽스처 파일 경로
BASELINE_FILE = os.path.join(os.path.dirname(__file__), "fixtures", "oss_eval_baseline.json")

# 허용 오차 설정
SCORE_TOLERANCE = 5  # 점수 허용 오차 (±5점)
DEPENDENCY_TOLERANCE = 10  # 의존성 복잡도 허용 오차 (±10점)


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


@pytest.fixture
def baseline_data():
    """베이스라인 데이터를 로드합니다."""
    if not os.path.exists(BASELINE_FILE):
        pytest.skip(f"Baseline file not found: {BASELINE_FILE}")
    
    with open(BASELINE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class TestAgentScoreRegression:
    """에이전트 스코어 회귀 테스트."""
    
    @pytest.mark.slow
    def test_oss_eval_regression(self, baseline_data):
        """
        OSS 벤치마크 베이스라인 회귀 테스트.
        run_agent_task API를 통해 진단을 수행하고 허용 오차 범위를 확인합니다.
        """
        for entry in baseline_data:
            repo_id = entry.get("repo_id")
            
            if entry.get("error"):
                continue
                
            print(f"\nTesting regression for {repo_id}...")
            
            owner, repo, ref = parse_repo_string(repo_id)
            
            # run_agent_task API 호출
            result = run_agent_task(
                task_type="diagnose_repo",
                owner=owner,
                repo=repo,
                ref=ref,
                use_llm_summary=False
            )
            
            assert result["ok"], f"Diagnosis failed for {repo_id}: {result.get('error')}"
            
            data = result["data"]
            
            # 1. 점수 비교 (허용 오차 ±5)
            self._assert_score_in_range(
                data["documentation_quality"], 
                entry["documentation_quality"], 
                "documentation_quality", 
                repo_id
            )
            self._assert_score_in_range(
                data["activity_maintainability"], 
                entry["activity_maintainability"], 
                "activity_maintainability", 
                repo_id
            )
            self._assert_score_in_range(
                data["health_score"], 
                entry["health_score"], 
                "health_score", 
                repo_id
            )
            self._assert_score_in_range(
                data["onboarding_score"], 
                entry["onboarding_score"], 
                "onboarding_score", 
                repo_id
            )
            
            # 2. 레벨 비교 (정확히 일치)
            assert data["health_level"] == entry["health_level"], \
                f"Health level changed for {repo_id}: {entry['health_level']} -> {data['health_level']}"
            assert data["onboarding_level"] == entry["onboarding_level"], \
                f"Onboarding level changed for {repo_id}: {entry['onboarding_level']} -> {data['onboarding_level']}"
            
            # 3. 의존성 복잡도 (허용 오차 ±10)
            baseline_dep = entry.get("dependency_complexity_score") or 0
            assert abs(data["dependency_complexity_score"] - baseline_dep) <= DEPENDENCY_TOLERANCE, \
                f"Dependency complexity changed too much for {repo_id}: {baseline_dep} -> {data['dependency_complexity_score']}"
    
    def _assert_score_in_range(self, actual: int, expected: int, field: str, repo_id: str):
        """점수가 허용 범위 내에 있는지 확인."""
        assert abs(actual - expected) <= SCORE_TOLERANCE, \
            f"{field} changed too much for {repo_id}: {expected} -> {actual} (tolerance: ±{SCORE_TOLERANCE})"
    
    @pytest.mark.slow
    def test_trace_included_when_enabled(self, baseline_data):
        """debug_trace=True일 때 trace가 포함되는지 확인."""
        if not baseline_data:
            pytest.skip("No baseline data")
        
        entry = baseline_data[0]
        if entry.get("error"):
            pytest.skip("First baseline entry has error")
        
        owner, repo, ref = parse_repo_string(entry["repo_id"])
        
        result = run_agent_task(
            task_type="diagnose_repo",
            owner=owner,
            repo=repo,
            ref=ref,
            use_llm_summary=False,
            debug_trace=True
        )
        
        assert result["ok"], f"Diagnosis failed: {result.get('error')}"
        assert "trace" in result, "Trace should be included when debug_trace=True"
        assert isinstance(result["trace"], list), "Trace should be a list"
        assert len(result["trace"]) > 0, "Trace should not be empty"

