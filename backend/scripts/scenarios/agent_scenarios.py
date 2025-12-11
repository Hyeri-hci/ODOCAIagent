"""
비교 분석 시나리오.

여러 레포지토리를 동시에 분석하고 비교하는 벤치마크.
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


class ComparisonScenario(ScenarioBase):
    """
    다중 레포지토리 비교 시나리오.
    
    목적: comparison 에이전트 성능 측정
    측정: 배치 진단 시간, 비교 분석 시간
    """
    
    name = "comparison"
    description = "다중 레포지토리 비교 분석 성능 측정"
    
    repos = [
        ("Hyeri-hci", "ODOCAIagent", "main"),
        ("Hyeri-hci", "OSSDoctor", "main"),
    ]
    
    def run(self) -> ScenarioResult:
        """시나리오 실행."""
        from backend.agents.comparison.service import run_comparison
        from backend.agents.comparison.models import ComparisonInput
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        agent_metrics = AgentMetrics(agent_name="comparison")
        
        with Timer("comparison") as t:
            try:
                comparison_input = ComparisonInput(
                    repos=[f"{r[0]}/{r[1]}" for r in self.repos]
                )
                output = run_comparison(comparison_input)
                
                # 배치 진단 시간 추출
                if hasattr(output, 'results') and output.results:
                    for repo_result in output.results:
                        agent_metrics.add_node_metric(NodeMetrics(
                            node_name=f"diagnose_{repo_result.repo_id}",
                            execution_time_ms=repo_result.execution_time_ms or 0,
                        ))
                        
            except Exception as e:
                agent_metrics.errors.append(str(e))
                result.passed = False
                logger.error(f"Comparison failed: {e}")
        
        agent_metrics.total_time_ms = t.elapsed_ms
        result.agent_metrics.append(agent_metrics)
        result.total_time_ms = self.stop_timing()
        
        return result


class OnboardingScenario(ScenarioBase):
    """
    온보딩 가이드 생성 시나리오.
    
    목적: onboarding 에이전트 성능 측정
    측정: 이슈 가져오기, 플랜 생성, 요약 시간
    """
    
    name = "onboarding"
    description = "온보딩 가이드 생성 성능 측정"
    
    repos = [
        ("Hyeri-hci", "ODOCAIagent", "main"),
    ]
    
    def run(self) -> ScenarioResult:
        """시나리오 실행."""
        from backend.agents.onboarding.service import run_onboarding
        from backend.agents.onboarding.models import OnboardingInput
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            agent_metrics = AgentMetrics(agent_name="onboarding")
            
            with Timer("onboarding") as t:
                try:
                    onboarding_input = OnboardingInput(
                        owner=owner,
                        repo=repo,
                        ref=ref,
                        experience_level="intermediate",
                    )
                    output = run_onboarding(onboarding_input)
                    
                except Exception as e:
                    agent_metrics.errors.append(str(e))
                    result.passed = False
                    logger.error(f"Onboarding failed: {e}")
            
            agent_metrics.total_time_ms = t.elapsed_ms
            result.agent_metrics.append(agent_metrics)
        
        result.total_time_ms = self.stop_timing()
        return result


# 시나리오 레지스트리에 추가
ADDITIONAL_SCENARIOS = {
    "comparison": ComparisonScenario,
    "onboarding": OnboardingScenario,
}
