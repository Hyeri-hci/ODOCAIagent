"""
Diagnosis Agent 전용 벤치마크 스크립트.

Usage:
    python backend/scripts/benchmark_diagnosis.py
    python backend/scripts/benchmark_diagnosis.py --repo Hyeri-hci/ODOCAIagent
    python backend/scripts/benchmark_diagnosis.py --scenario small_repo
    python backend/scripts/benchmark_diagnosis.py --scenario medium_repo --verbose
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.scripts.scenarios.base import AgentMetrics, NodeMetrics, Timer, ScenarioResult
from backend.scripts.scenarios.repo_size import get_scenario, list_scenarios, SCENARIOS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DiagnosisBenchmark:
    """
    Diagnosis Agent 성능 벤치마크.
    
    노드별 실행 시간, API 호출 횟수, 캐시 히트율 등을 측정합니다.
    
    측정 지표:
        - 전체 실행 시간 (total_time_ms)
        - 노드별 실행 시간 (fetch_readme, analyze_dependencies 등)
        - GitHub API 호출 횟수
        - LLM 호출 횟수 및 시간
        - 캐시 히트율
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[AgentMetrics] = []
    
    def run_single(
        self,
        owner: str,
        repo: str,
        ref: str = "main",
        use_llm: bool = False
    ) -> AgentMetrics:
        """
        단일 레포지토리 진단 벤치마크.
        
        Args:
            owner: 레포 소유자
            repo: 레포 이름
            ref: 브랜치/커밋
            use_llm: LLM 요약 사용 여부
            
        Returns:
            AgentMetrics: 성능 메트릭
        """
        from backend.agents.diagnosis.service import run_diagnosis
        from backend.agents.diagnosis.models import DiagnosisInput
        
        repo_id = f"{owner}/{repo}@{ref}"
        logger.info(f"Benchmarking Diagnosis for {repo_id}...")
        
        metrics = AgentMetrics(agent_name="diagnosis")
        
        # 전체 실행 시간 측정
        with Timer("total") as total_timer:
            try:
                diagnosis_input = DiagnosisInput(
                    owner=owner,
                    repo=repo,
                    ref=ref,
                )
                # async 함수를 동기적으로 실행
                output = asyncio.run(run_diagnosis(diagnosis_input))
                
                # 결과에서 노드별 timings 추출
                if output:
                    # health_score 메타데이터
                    metrics.add_node_metric(NodeMetrics(
                        node_name="health_score",
                        execution_time_ms=0,
                        metadata={
                            "health_score": output.health_score,
                            "health_level": output.health_level,
                        }
                    ))
                    
                    # timings 딕셔너리에서 노드별 시간 추출
                    if hasattr(output, 'timings') and output.timings:
                        for node_name, elapsed_sec in output.timings.items():
                            metrics.add_node_metric(NodeMetrics(
                                node_name=node_name,
                                execution_time_ms=elapsed_sec * 1000,  # sec -> ms
                                success=True,
                            ))
                    
                    # 문서 품질 점수
                    if hasattr(output, 'documentation_quality'):
                        metrics.set_metric("documentation_quality", output.documentation_quality)
                    
                    # 활동 유지보수성
                    if hasattr(output, 'activity_maintainability'):
                        metrics.set_metric("activity_maintainability", output.activity_maintainability)
                    
                    # 온보딩 점수
                    if hasattr(output, 'onboarding_score'):
                        metrics.set_metric("onboarding_score", output.onboarding_score)
                    
                    # 의존성 복잡도
                    if hasattr(output, 'dependency_complexity_score'):
                        metrics.set_metric("dependency_complexity_score", output.dependency_complexity_score)
                        
            except Exception as e:
                metrics.errors.append(str(e))
                logger.error(f"Diagnosis failed: {e}")
        
        metrics.total_time_ms = total_timer.elapsed_ms
        self.results.append(metrics)
        
        if self.verbose:
            print(metrics.summary())
            
        return metrics
    
    def run_scenario(self, scenario_name: str) -> ScenarioResult:
        """
        시나리오 기반 벤치마크 실행.
        
        Args:
            scenario_name: 시나리오 이름 (small_repo, medium_repo, large_repo)
            
        Returns:
            ScenarioResult: 시나리오 결과
        """
        scenario = get_scenario(scenario_name)
        scenario.verbose = self.verbose
        
        logger.info(f"Running scenario: {scenario.name}")
        logger.info(f"Description: {scenario.description}")
        logger.info(f"Repos: {len(scenario.repos)}")
        
        result = scenario.run()
        
        # 결과 기록
        for m in result.agent_metrics:
            self.results.append(m)
            
        return result
    
    def generate_report(self) -> Dict[str, Any]:
        """
        벤치마크 결과 리포트 생성.
        
        Returns:
            리포트 딕셔너리
        """
        if not self.results:
            return {"error": "No results"}
        
        total_time = sum(m.total_time_ms for m in self.results)
        avg_time = total_time / len(self.results)
        
        errors = []
        for m in self.results:
            errors.extend(m.errors)
        
        return {
            "benchmark_type": "diagnosis",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_runs": len(self.results),
                "total_time_ms": round(total_time, 2),
                "avg_time_ms": round(avg_time, 2),
                "errors": len(errors),
            },
            "results": [m.to_dict() for m in self.results],
        }
    
    def save_report(self, output_path: str):
        """결과 파일 저장."""
        report = self.generate_report()
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnosis Agent 성능 벤치마크",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 단일 레포 벤치마크
  python benchmark_diagnosis.py --repo Hyeri-hci/ODOCAIagent
  
  # 시나리오 실행
  python benchmark_diagnosis.py --scenario small_repo
  python benchmark_diagnosis.py --scenario medium_repo --verbose
  
  # 시나리오 목록 확인
  python benchmark_diagnosis.py --list-scenarios
        """
    )
    
    parser.add_argument(
        "--repo",
        help="단일 레포지토리 (owner/repo 형식)"
    )
    parser.add_argument(
        "--scenario",
        help="실행할 시나리오 이름"
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="사용 가능한 시나리오 목록 출력"
    )
    parser.add_argument(
        "--output",
        help="결과 저장 경로 (JSON)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 출력"
    )
    
    args = parser.parse_args()
    
    # 시나리오 목록 출력
    if args.list_scenarios:
        print("\n=== Available Scenarios ===")
        for name, cls in SCENARIOS.items():
            instance = cls()
            print(f"  {name}: {instance.description}")
        return
    
    benchmark = DiagnosisBenchmark(verbose=args.verbose)
    
    # 실행 모드 결정
    if args.repo:
        # 단일 레포 모드
        if "/" not in args.repo:
            print("Error: repo must be in 'owner/repo' format")
            sys.exit(1)
            
        owner, repo = args.repo.split("/", 1)
        ref = "main"
        if "@" in repo:
            repo, ref = repo.split("@", 1)
            
        benchmark.run_single(owner, repo, ref)
        
    elif args.scenario:
        # 시나리오 모드
        try:
            result = benchmark.run_scenario(args.scenario)
            print(f"\n=== Scenario Result: {result.scenario_name} ===")
            print(f"Passed: {result.passed}")
            print(f"Total Time: {result.total_time_ms:.2f}ms")
            for m in result.agent_metrics:
                print(f"\n{m.summary()}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # 기본: small_repo 시나리오
        result = benchmark.run_scenario("small_repo")
        print(f"\n=== Default Scenario (small_repo) ===")
        print(f"Total Time: {result.total_time_ms:.2f}ms")
    
    # 결과 저장
    if args.output:
        benchmark.save_report(args.output)
    else:
        # 기본 출력 경로
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = f"diagnosis_benchmark_{date_str}.json"
        benchmark.save_report(default_output)


if __name__ == "__main__":
    main()
