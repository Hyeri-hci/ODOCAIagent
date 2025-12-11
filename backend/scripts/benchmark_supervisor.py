"""
Supervisor Agent 전용 벤치마크 스크립트.

메타 에이전트 플로우 (parse -> plan -> execute -> reflect -> finalize)의
각 단계별 성능을 측정합니다.

Usage:
    python backend/scripts/benchmark_supervisor.py
    python backend/scripts/benchmark_supervisor.py --repo Hyeri-hci/ODOCAIagent
    python backend/scripts/benchmark_supervisor.py --intent diagnose
    python backend/scripts/benchmark_supervisor.py --all-intents
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.scripts.scenarios.base import AgentMetrics, NodeMetrics, Timer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class SupervisorMetrics(AgentMetrics):
    """
    Supervisor Agent 전용 메트릭.
    
    메타 플로우 단계별 시간과 서브 에이전트 호출 통계를 추가로 추적합니다.
    
    Attributes:
        meta_flow_timings: 메타 플로우 단계별 시간
        subagent_calls: 서브 에이전트 호출 정보
        detected_intent: 감지된 의도
        task_plan: 생성된 태스크 플랜
        error_recovery_count: 에러 복구 횟수
    """
    meta_flow_timings: Dict[str, float] = field(default_factory=dict)
    subagent_calls: List[Dict[str, Any]] = field(default_factory=list)
    detected_intent: Optional[str] = None
    task_plan: Optional[List[str]] = None
    error_recovery_count: int = 0
    
    def add_meta_timing(self, step: str, time_ms: float):
        """메타 플로우 단계 시간 추가."""
        self.meta_flow_timings[step] = time_ms
    
    def add_subagent_call(
        self,
        agent_name: str,
        time_ms: float,
        success: bool = True
    ):
        """서브 에이전트 호출 기록."""
        self.subagent_calls.append({
            "agent": agent_name,
            "time_ms": time_ms,
            "success": success,
        })
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "meta_flow_timings": self.meta_flow_timings,
            "subagent_calls": self.subagent_calls,
            "detected_intent": self.detected_intent,
            "task_plan": self.task_plan,
            "error_recovery_count": self.error_recovery_count,
        })
        return base
    
    def summary(self) -> str:
        """Supervisor 전용 요약."""
        lines = [
            f"=== SUPERVISOR Performance Summary ===",
            f"Total Time: {self.total_time_ms:.2f}ms",
            f"Detected Intent: {self.detected_intent or 'N/A'}",
            f"Error Recoveries: {self.error_recovery_count}",
        ]
        
        if self.meta_flow_timings:
            lines.append("\nMeta Flow Timings:")
            for step, ms in self.meta_flow_timings.items():
                lines.append(f"  - {step}: {ms:.2f}ms")
        
        if self.subagent_calls:
            lines.append(f"\nSubagent Calls: {len(self.subagent_calls)}")
            for call in self.subagent_calls:
                status = "OK" if call["success"] else "FAIL"
                lines.append(f"  - {call['agent']}: {call['time_ms']:.2f}ms [{status}]")
        
        if self.errors:
            lines.append(f"\nErrors: {len(self.errors)}")
            
        return "\n".join(lines)


class SupervisorBenchmark:
    """
    Supervisor Agent 성능 벤치마크.
    
    측정 지표:
        - 전체 실행 시간
        - 메타 플로우 단계별 시간:
            - parse_supervisor_intent
            - create_supervisor_plan
            - execute_supervisor_plan
            - reflect_supervisor
            - finalize_supervisor_answer
        - 서브 에이전트 호출 횟수 및 시간
        - 에러 복구 빈도
    """
    
    # 테스트할 의도 목록
    INTENTS = ["diagnose", "chat", "compare", "onboard", "security"]
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[SupervisorMetrics] = []
    
    def run_single(
        self,
        owner: str,
        repo: str,
        ref: str = "main",
        user_message: Optional[str] = None,
    ) -> SupervisorMetrics:
        """
        단일 Supervisor 실행 벤치마크.
        
        Args:
            owner: 레포 소유자
            repo: 레포 이름
            ref: 브랜치
            user_message: 사용자 메시지 (의도 결정용)
            
        Returns:
            SupervisorMetrics: 성능 메트릭
        """
        from backend.agents.supervisor.service import run_supervisor_diagnosis
        
        repo_id = f"{owner}/{repo}@{ref}"
        logger.info(f"Benchmarking Supervisor for {repo_id}...")
        if user_message:
            logger.info(f"User message: {user_message[:50]}...")
        
        metrics = SupervisorMetrics(agent_name="supervisor")
        
        with Timer("total") as total_timer:
            try:
                result, error, trace = run_supervisor_diagnosis(
                    owner=owner,
                    repo=repo,
                    ref=ref,
                    user_message=user_message,
                    debug_trace=True,  # 트레이스 활성화
                )
                
                if error:
                    metrics.errors.append(error)
                
                # 트레이스에서 단계별 시간 추출
                if trace:
                    self._extract_timings_from_trace(metrics, trace)
                
                # 결과에서 메타데이터 추출
                if result:
                    if "task_plan" in result:
                        plan = result["task_plan"]
                        if plan:
                            metrics.task_plan = [
                                step.get("agent", "unknown") 
                                for step in plan
                            ]
                    
            except Exception as e:
                metrics.errors.append(str(e))
                logger.error(f"Supervisor failed: {e}")
        
        metrics.total_time_ms = total_timer.elapsed_ms
        self.results.append(metrics)
        
        if self.verbose:
            print(metrics.summary())
            
        return metrics
    
    def _extract_timings_from_trace(
        self,
        metrics: SupervisorMetrics,
        trace: List[Dict[str, Any]]
    ):
        """트레이스에서 노드별 시간 추출."""
        meta_nodes = [
            "parse_supervisor_intent",
            "create_supervisor_plan", 
            "execute_supervisor_plan",
            "reflect_supervisor",
            "finalize_supervisor_answer",
        ]
        
        for entry in trace:
            node_name = entry.get("node", "")
            duration_ms = entry.get("duration_ms", 0)
            
            if node_name in meta_nodes:
                metrics.add_meta_timing(node_name, duration_ms)
            
            # 서브 에이전트 호출 추출
            if "subagent" in entry:
                metrics.add_subagent_call(
                    entry["subagent"],
                    entry.get("subagent_duration_ms", 0),
                    entry.get("success", True)
                )
            
            # 에러 복구 카운트
            if "error_recovery" in node_name:
                metrics.error_recovery_count += 1
    
    def run_intent_test(
        self,
        owner: str,
        repo: str,
        intent: str,
    ) -> SupervisorMetrics:
        """
        특정 의도에 대한 벤치마크.
        
        Args:
            intent: 테스트할 의도 (diagnose, chat, compare, etc.)
        """
        intent_messages = {
            "diagnose": "이 레포지토리를 분석해줘",
            "chat": "안녕하세요",
            "compare": "다른 레포와 비교해줘",
            "onboard": "이 프로젝트에 기여하고 싶어요",
            "security": "보안 분석 해줘",
        }
        
        message = intent_messages.get(intent, "분석해줘")
        metrics = self.run_single(owner, repo, user_message=message)
        metrics.detected_intent = intent
        
        return metrics
    
    def run_all_intents(
        self,
        owner: str,
        repo: str,
    ) -> List[SupervisorMetrics]:
        """모든 의도에 대해 벤치마크 실행."""
        results = []
        
        for intent in self.INTENTS:
            logger.info(f"\n--- Testing intent: {intent} ---")
            try:
                metrics = self.run_intent_test(owner, repo, intent)
                results.append(metrics)
            except Exception as e:
                logger.error(f"Failed for intent {intent}: {e}")
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """벤치마크 결과 리포트 생성."""
        if not self.results:
            return {"error": "No results"}
        
        total_time = sum(m.total_time_ms for m in self.results)
        avg_time = total_time / len(self.results)
        
        # 의도별 집계
        by_intent = {}
        for m in self.results:
            intent = m.detected_intent or "unknown"
            if intent not in by_intent:
                by_intent[intent] = {"count": 0, "total_ms": 0, "errors": 0}
            by_intent[intent]["count"] += 1
            by_intent[intent]["total_ms"] += m.total_time_ms
            by_intent[intent]["errors"] += len(m.errors)
        
        return {
            "benchmark_type": "supervisor",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_runs": len(self.results),
                "total_time_ms": round(total_time, 2),
                "avg_time_ms": round(avg_time, 2),
                "by_intent": by_intent,
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
        description="Supervisor Agent 성능 벤치마크",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 단일 레포 벤치마크
  python benchmark_supervisor.py --repo Hyeri-hci/ODOCAIagent
  
  # 특정 의도 테스트
  python benchmark_supervisor.py --repo Hyeri-hci/ODOCAIagent --intent diagnose
  
  # 모든 의도 테스트
  python benchmark_supervisor.py --repo Hyeri-hci/ODOCAIagent --all-intents
  
  # 커스텀 메시지
  python benchmark_supervisor.py --repo Hyeri-hci/ODOCAIagent --message "보안 분석해줘"
        """
    )
    
    parser.add_argument(
        "--repo",
        default="Hyeri-hci/ODOCAIagent",
        help="테스트할 레포지토리 (owner/repo 형식)"
    )
    parser.add_argument(
        "--intent",
        choices=SupervisorBenchmark.INTENTS,
        help="테스트할 특정 의도"
    )
    parser.add_argument(
        "--all-intents",
        action="store_true",
        help="모든 의도에 대해 테스트"
    )
    parser.add_argument(
        "--message",
        help="커스텀 사용자 메시지"
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
    
    # 레포 파싱
    if "/" not in args.repo:
        print("Error: repo must be in 'owner/repo' format")
        sys.exit(1)
        
    owner, repo = args.repo.split("/", 1)
    ref = "main"
    if "@" in repo:
        repo, ref = repo.split("@", 1)
    
    benchmark = SupervisorBenchmark(verbose=args.verbose)
    
    # 실행 모드 결정
    if args.all_intents:
        benchmark.run_all_intents(owner, repo)
    elif args.intent:
        benchmark.run_intent_test(owner, repo, args.intent)
    elif args.message:
        benchmark.run_single(owner, repo, ref, user_message=args.message)
    else:
        # 기본: diagnose 의도
        benchmark.run_intent_test(owner, repo, "diagnose")
    
    # 결과 저장
    if args.output:
        benchmark.save_report(args.output)
    else:
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = f"supervisor_benchmark_{date_str}.json"
        benchmark.save_report(default_output)
    
    # 요약 출력
    report = benchmark.generate_report()
    print(f"\n=== Supervisor Benchmark Summary ===")
    print(f"Total Runs: {report['summary']['total_runs']}")
    print(f"Avg Time: {report['summary']['avg_time_ms']:.2f}ms")


if __name__ == "__main__":
    main()
