"""
소형 레포지토리 시나리오.

파일 수 100개 미만의 소형 레포지토리에 대한 성능 벤치마크.
빠른 실행 시간과 기본 기능 검증에 적합합니다.
"""
from __future__ import annotations

import logging
from typing import List

from backend.scripts.scenarios.base import (
    ScenarioBase,
    ScenarioResult,
    AgentMetrics,
    NodeMetrics,
    Timer,
)

logger = logging.getLogger(__name__)


class SmallRepoScenario(ScenarioBase):
    """
    소형 레포지토리 벤치마크 시나리오.
    
    대상: 파일 수 100개 미만
    목적: 기본 기능 동작 확인 및 baseline 성능 측정
    예상 시간: 10-30초
    """
    
    name = "small_repo"
    description = "소형 레포지토리 (<100 파일) 진단 성능 측정"
    
    # 기본 테스트 레포지토리
    repos = [
        ("Hyeri-hci", "odoc_test_repo", "main"),
    ]
    
    def run(self) -> ScenarioResult:
        """시나리오 실행."""
        from backend.agents.diagnosis.service import run_diagnosis
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            repo_id = f"{owner}/{repo}"
            self.log(f"Testing {repo_id}...")
            
            agent_metrics = AgentMetrics(agent_name="diagnosis")
            
            with Timer("diagnosis") as t:
                try:
                    output = run_diagnosis(owner=owner, repo=repo, ref=ref)
                    agent_metrics.total_time_ms = t.elapsed_ms
                    
                    # 결과에서 메트릭 추출
                    if hasattr(output, 'execution_time_ms'):
                        agent_metrics.add_node_metric(NodeMetrics(
                            node_name="total",
                            execution_time_ms=output.execution_time_ms
                        ))
                        
                except Exception as e:
                    agent_metrics.errors.append(str(e))
                    result.passed = False
                    logger.error(f"Failed for {repo_id}: {e}")
            
            agent_metrics.total_time_ms = t.elapsed_ms
            result.agent_metrics.append(agent_metrics)
            
        result.total_time_ms = self.stop_timing()
        return result


class MediumRepoScenario(ScenarioBase):
    """
    중형 레포지토리 벤치마크 시나리오.
    
    대상: 파일 수 100-500개
    목적: 일반적인 프로젝트 규모 성능 측정
    예상 시간: 30초-2분
    """
    
    name = "medium_repo"
    description = "중형 레포지토리 (100-500 파일) 진단 성능 측정"
    
    repos = [
        ("langchain-ai", "langgraph", "main"),
        ("streamlit", "streamlit", "develop"),
    ]
    
    def run(self) -> ScenarioResult:
        """시나리오 실행."""
        from backend.agents.diagnosis.service import run_diagnosis
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            repo_id = f"{owner}/{repo}"
            self.log(f"Testing {repo_id}...")
            
            agent_metrics = AgentMetrics(agent_name="diagnosis")
            
            with Timer("diagnosis") as t:
                try:
                    output = run_diagnosis(owner=owner, repo=repo, ref=ref)
                except Exception as e:
                    agent_metrics.errors.append(str(e))
                    result.passed = False
                    
            agent_metrics.total_time_ms = t.elapsed_ms
            result.agent_metrics.append(agent_metrics)
            
        result.total_time_ms = self.stop_timing()
        return result


class LargeRepoScenario(ScenarioBase):
    """
    대형 레포지토리 벤치마크 시나리오.
    
    대상: 파일 수 500개 이상
    목적: 대규모 프로젝트 처리 성능 및 병목 지점 파악
    예상 시간: 2-10분
    
    주의: 대형 레포는 GitHub API rate limit에 주의 필요
    """
    
    name = "large_repo"
    description = "대형 레포지토리 (>500 파일) 진단 성능 측정"
    
    repos = [
        ("facebook", "react", "main"),
    ]
    
    def run(self) -> ScenarioResult:
        """시나리오 실행."""
        from backend.agents.diagnosis.service import run_diagnosis
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        result.notes.append("대형 레포 - API rate limit 주의")
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            repo_id = f"{owner}/{repo}"
            self.log(f"Testing {repo_id} (large)...")
            
            agent_metrics = AgentMetrics(agent_name="diagnosis")
            
            with Timer("diagnosis") as t:
                try:
                    output = run_diagnosis(owner=owner, repo=repo, ref=ref)
                except Exception as e:
                    agent_metrics.errors.append(str(e))
                    result.passed = False
                    
            agent_metrics.total_time_ms = t.elapsed_ms
            result.agent_metrics.append(agent_metrics)
            
        result.total_time_ms = self.stop_timing()
        return result


# 시나리오 레지스트리
SCENARIOS = {
    "small_repo": SmallRepoScenario,
    "medium_repo": MediumRepoScenario,
    "large_repo": LargeRepoScenario,
}


def get_scenario(name: str) -> ScenarioBase:
    """이름으로 시나리오 인스턴스 반환."""
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario: {name}. Available: {available}")
    return SCENARIOS[name]()


def list_scenarios() -> List[str]:
    """사용 가능한 시나리오 목록."""
    return list(SCENARIOS.keys())
