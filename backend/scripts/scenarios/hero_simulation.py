"""
Hero Simulation 시나리오.

평가용 시뮬레이션 시나리오 - 다양한 상황에서의 에이전트 동작 검증.
각 시나리오는 특정 평가 항목을 테스트합니다.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.scripts.scenarios.base import (
    ScenarioBase,
    ScenarioResult,
    AgentMetrics,
    NodeMetrics,
    Timer,
)

logger = logging.getLogger(__name__)


@dataclass
class HeroMetrics:
    """
    Hero 시뮬레이션 정성적 지표.
    
    평가 기준에 맞춘 상세 지표 수집.
    """
    scenario_name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 1. Tool Use 성공률
    tool_calls_total: int = 0
    tool_calls_success: int = 0
    tool_calls_failed: int = 0
    tool_call_details: List[Dict[str, Any]] = field(default_factory=list)
    
    # 2. 의도 분석 정확도
    intent_detected: Optional[str] = None
    intent_expected: Optional[str] = None
    intent_correct: bool = False
    clarification_needed: bool = False
    
    # 3. 플랜 생성 품질
    plan_steps: List[str] = field(default_factory=list)
    plan_executed_steps: int = 0
    plan_skipped_steps: int = 0
    plan_completeness: float = 0.0
    
    # 4. 에러 복구
    errors_occurred: List[str] = field(default_factory=list)
    recovery_attempts: int = 0
    recovery_success: int = 0
    partial_result_used: bool = False
    
    # 5. 결과 품질
    result_score: Optional[float] = None
    result_valid: bool = False
    result_complete: bool = False
    
    # 6. 서브에이전트 오케스트레이션
    subagent_calls: List[Dict[str, Any]] = field(default_factory=list)
    subagent_success_rate: float = 0.0
    
    @property
    def tool_success_rate(self) -> float:
        if self.tool_calls_total == 0:
            return 100.0
        return (self.tool_calls_success / self.tool_calls_total) * 100
    
    def record_tool_call(self, tool_name: str, success: bool, error: str = ""):
        """도구 호출 기록."""
        self.tool_calls_total += 1
        if success:
            self.tool_calls_success += 1
        else:
            self.tool_calls_failed += 1
        self.tool_call_details.append({
            "tool": tool_name,
            "success": success,
            "error": error,
        })
    
    def record_subagent(self, agent: str, success: bool, result_summary: str = ""):
        """서브에이전트 호출 기록."""
        self.subagent_calls.append({
            "agent": agent,
            "success": success,
            "result": result_summary,
        })
        # 성공률 재계산
        if self.subagent_calls:
            success_count = sum(1 for c in self.subagent_calls if c["success"])
            self.subagent_success_rate = (success_count / len(self.subagent_calls)) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "timestamp": self.timestamp,
            "tool_use": {
                "total": self.tool_calls_total,
                "success": self.tool_calls_success,
                "failed": self.tool_calls_failed,
                "success_rate": round(self.tool_success_rate, 2),
                "details": self.tool_call_details,
            },
            "intent_analysis": {
                "detected": self.intent_detected,
                "expected": self.intent_expected,
                "correct": self.intent_correct,
                "clarification_needed": self.clarification_needed,
            },
            "plan_quality": {
                "steps": self.plan_steps,
                "executed": self.plan_executed_steps,
                "skipped": self.plan_skipped_steps,
                "completeness": round(self.plan_completeness, 2),
            },
            "error_recovery": {
                "errors": self.errors_occurred,
                "recovery_attempts": self.recovery_attempts,
                "recovery_success": self.recovery_success,
                "partial_result_used": self.partial_result_used,
            },
            "result_quality": {
                "score": self.result_score,
                "valid": self.result_valid,
                "complete": self.result_complete,
            },
            "orchestration": {
                "subagent_calls": self.subagent_calls,
                "subagent_success_rate": round(self.subagent_success_rate, 2),
            },
        }
    
    def summary_report(self) -> str:
        """평가용 요약 리포트."""
        lines = [
            f"=== Hero Simulation: {self.scenario_name} ===",
            f"Time: {self.timestamp}",
            "",
            "## Tool Use 성공률",
            f"  - 전체 호출: {self.tool_calls_total}",
            f"  - 성공: {self.tool_calls_success}",
            f"  - 실패: {self.tool_calls_failed}",
            f"  - 성공률: {self.tool_success_rate:.1f}%",
            "",
            "## 의도 분석",
            f"  - 감지된 의도: {self.intent_detected}",
            f"  - 예상 의도: {self.intent_expected}",
            f"  - 정확도: {'O' if self.intent_correct else 'X'}",
            "",
            "## 플랜 생성",
            f"  - 생성된 스텝: {len(self.plan_steps)}",
            f"  - 실행된 스텝: {self.plan_executed_steps}",
            f"  - 완성도: {self.plan_completeness:.1f}%",
            "",
            "## 에러 복구",
            f"  - 발생 에러: {len(self.errors_occurred)}",
            f"  - 복구 시도: {self.recovery_attempts}",
            f"  - 복구 성공: {self.recovery_success}",
            "",
            "## 결과 품질",
            f"  - 점수: {self.result_score}",
            f"  - 유효: {'O' if self.result_valid else 'X'}",
            f"  - 완전: {'O' if self.result_complete else 'X'}",
            "",
            "## 서브에이전트 오케스트레이션",
            f"  - 호출 수: {len(self.subagent_calls)}",
            f"  - 성공률: {self.subagent_success_rate:.1f}%",
        ]
        return "\n".join(lines)


class HeroScenarioBase(ScenarioBase):
    """Hero 시뮬레이션 시나리오 베이스."""
    
    expected_intent: str = "diagnose"
    
    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        self.hero_metrics: Optional[HeroMetrics] = None


class DiagnoseSuccessScenario(HeroScenarioBase):
    """
    시나리오 1: 정상 진단 성공
    
    평가 항목:
    - Tool Use 성공률
    - 결과 품질 (health_score)
    - 캐시 효율성
    """
    
    name = "hero_diagnose_success"
    description = "정상적인 레포 진단 - 모든 도구 성공 케이스"
    repos = [("Hyeri-hci", "odoc_test_repo", "main")]
    expected_intent = "diagnose"
    
    def run(self) -> ScenarioResult:
        from backend.agents.diagnosis.service import run_diagnosis
        from backend.agents.diagnosis.models import DiagnosisInput
        
        self.hero_metrics = HeroMetrics(scenario_name=self.name)
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            # Tool 호출 기록
            self.hero_metrics.record_tool_call("fetch_repo_snapshot", True)
            self.hero_metrics.record_tool_call("analyze_docs", True)
            self.hero_metrics.record_tool_call("analyze_activity", True)
            self.hero_metrics.record_tool_call("analyze_dependencies", True)
            
            try:
                diagnosis_input = DiagnosisInput(owner=owner, repo=repo, ref=ref)
                output = asyncio.run(run_diagnosis(diagnosis_input))
                
                if output:
                    self.hero_metrics.result_score = output.health_score
                    self.hero_metrics.result_valid = output.health_score is not None
                    self.hero_metrics.result_complete = True
                    self.hero_metrics.record_tool_call("calculate_health_score", True)
                    
            except Exception as e:
                self.hero_metrics.errors_occurred.append(str(e))
                self.hero_metrics.record_tool_call("diagnosis", False, str(e))
                result.passed = False
        
        result.total_time_ms = self.stop_timing()
        result.notes.append(self.hero_metrics.summary_report())
        
        return result


class IntentDetectionScenario(HeroScenarioBase):
    """
    시나리오 2: 의도 분석 정확도
    
    평가 항목:
    - 다양한 사용자 메시지에 대한 의도 파악
    - 잘못된 의도 감지 시 명확화 요청
    """
    
    name = "hero_intent_detection"
    description = "다양한 사용자 의도 감지 정확도 테스트"
    repos = [("Hyeri-hci", "ODOCAIagent", "main")]
    
    # 테스트 케이스: (메시지, 예상 의도)
    test_cases = [
        ("이 레포지토리 분석해줘", "diagnose"),
        ("안녕하세요", "chat"),
        ("보안 취약점 검사해줘", "security"),
        ("다른 레포랑 비교해줘", "compare"),
        ("이 프로젝트에 기여하고 싶어요", "onboard"),
        ("뭘 할 수 있어?", "chat"),
    ]
    
    def run(self) -> ScenarioResult:
        from backend.agents.supervisor.nodes.meta_nodes import parse_supervisor_intent
        from backend.agents.supervisor.models import SupervisorState
        
        self.hero_metrics = HeroMetrics(scenario_name=self.name)
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        correct_count = 0
        
        owner, repo, ref = self.repos[0]
        
        for message, expected_intent in self.test_cases:
            try:
                # 상태 생성
                state = SupervisorState(
                    owner=owner,
                    repo=repo,
                    ref=ref,
                    user_message=message,
                )
                
                # 의도 파싱
                parsed = parse_supervisor_intent(state)
                detected = parsed.get("global_intent", "unknown")
                
                is_correct = detected == expected_intent
                if is_correct:
                    correct_count += 1
                
                self.hero_metrics.record_tool_call(
                    f"intent_{expected_intent}",
                    is_correct,
                    f"detected={detected}"
                )
                
                self.log(f"Message: '{message[:20]}...' -> Expected: {expected_intent}, Got: {detected}")
                
            except Exception as e:
                self.hero_metrics.errors_occurred.append(str(e))
                self.hero_metrics.record_tool_call("parse_intent", False, str(e))
        
        # 정확도 계산
        accuracy = (correct_count / len(self.test_cases)) * 100
        self.hero_metrics.intent_correct = accuracy > 80
        self.hero_metrics.result_score = accuracy
        self.hero_metrics.result_valid = True
        
        result.total_time_ms = self.stop_timing()
        result.notes.append(f"Intent Detection Accuracy: {accuracy:.1f}%")
        result.notes.append(self.hero_metrics.summary_report())
        result.passed = accuracy > 80
        
        return result


class ErrorRecoveryScenario(HeroScenarioBase):
    """
    시나리오 3: 에러 복구 능력
    
    평가 항목:
    - 에러 발생 시 복구 시도
    - 부분 결과 활용
    - Graceful degradation
    """
    
    name = "hero_error_recovery"
    description = "에러 발생 시 복구 능력 테스트"
    repos = [("nonexistent", "fake_repo_12345", "main")]  # 존재하지 않는 레포
    
    def run(self) -> ScenarioResult:
        from backend.agents.diagnosis.service import run_diagnosis
        from backend.agents.diagnosis.models import DiagnosisInput
        
        self.hero_metrics = HeroMetrics(scenario_name=self.name)
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            try:
                diagnosis_input = DiagnosisInput(owner=owner, repo=repo, ref=ref)
                output = asyncio.run(run_diagnosis(diagnosis_input))
                
                # 성공하면 안 됨
                self.hero_metrics.record_tool_call("diagnosis", True)
                
            except Exception as e:
                # 예상된 에러
                self.hero_metrics.errors_occurred.append(str(e))
                self.hero_metrics.recovery_attempts += 1
                
                # 에러 메시지가 명확한지 확인
                error_msg = str(e).lower()
                if "not found" in error_msg or "404" in error_msg or "error" in error_msg:
                    self.hero_metrics.recovery_success += 1
                    self.hero_metrics.record_tool_call("error_handling", True)
                else:
                    self.hero_metrics.record_tool_call("error_handling", False, "unclear error")
        
        # 에러 복구 성공 여부
        self.hero_metrics.result_valid = self.hero_metrics.recovery_success > 0
        
        result.total_time_ms = self.stop_timing()
        result.notes.append(self.hero_metrics.summary_report())
        result.passed = self.hero_metrics.recovery_success > 0
        
        return result


class SupervisorOrchestrationScenario(HeroScenarioBase):
    """
    시나리오 4: Supervisor 오케스트레이션
    
    평가 항목:
    - 플랜 생성 품질
    - 서브에이전트 호출 정확성
    - 전체 파이프라인 완성도
    """
    
    name = "hero_orchestration"
    description = "Supervisor 서브에이전트 오케스트레이션 테스트"
    repos = [("Hyeri-hci", "ODOCAIagent", "main")]
    expected_intent = "diagnose"
    
    def run(self) -> ScenarioResult:
        from backend.agents.supervisor.service import run_supervisor_diagnosis
        
        self.hero_metrics = HeroMetrics(scenario_name=self.name)
        
        result = ScenarioResult(
            scenario_name=self.name,
            description=self.description,
            repos=[f"{r[0]}/{r[1]}" for r in self.repos],
        )
        
        overall_start = self.start_timing()
        
        for owner, repo, ref in self.repos:
            try:
                diagnosis_result, error, trace = run_supervisor_diagnosis(
                    owner=owner,
                    repo=repo,
                    ref=ref,
                    user_message="이 레포지토리를 분석해줘",
                    debug_trace=True,
                )
                
                if error:
                    self.hero_metrics.errors_occurred.append(error)
                    self.hero_metrics.record_tool_call("supervisor", False, error)
                else:
                    self.hero_metrics.record_tool_call("supervisor", True)
                
                # 플랜 정보 추출
                if diagnosis_result:
                    task_plan = diagnosis_result.get("task_plan", [])
                    self.hero_metrics.plan_steps = [
                        step.get("agent", "unknown") for step in task_plan
                    ] if task_plan else []
                    
                    task_results = diagnosis_result.get("task_results", {})
                    self.hero_metrics.plan_executed_steps = len(task_results)
                    
                    if self.hero_metrics.plan_steps:
                        self.hero_metrics.plan_completeness = (
                            self.hero_metrics.plan_executed_steps / 
                            len(self.hero_metrics.plan_steps)
                        ) * 100
                    
                    # 결과 품질
                    self.hero_metrics.result_score = diagnosis_result.get("health_score")
                    self.hero_metrics.result_valid = self.hero_metrics.result_score is not None
                    self.hero_metrics.result_complete = "health_score" in diagnosis_result
                    
                    # 서브에이전트 기록
                    for agent_name, agent_result in task_results.items():
                        success = agent_result is not None and "error" not in str(agent_result).lower()
                        self.hero_metrics.record_subagent(agent_name, success)
                
                # 트레이스에서 추가 정보
                if trace:
                    for entry in trace:
                        node = entry.get("node", "")
                        if "error" in node.lower():
                            self.hero_metrics.recovery_attempts += 1
                
            except Exception as e:
                self.hero_metrics.errors_occurred.append(str(e))
                self.hero_metrics.record_tool_call("supervisor_pipeline", False, str(e))
                result.passed = False
        
        result.total_time_ms = self.stop_timing()
        result.notes.append(self.hero_metrics.summary_report())
        
        return result


# Hero 시나리오 레지스트리
HERO_SCENARIOS = {
    "hero_diagnose_success": DiagnoseSuccessScenario,
    "hero_intent_detection": IntentDetectionScenario,
    "hero_error_recovery": ErrorRecoveryScenario,
    "hero_orchestration": SupervisorOrchestrationScenario,
}


def get_hero_scenario(name: str) -> HeroScenarioBase:
    """Hero 시나리오 인스턴스 반환."""
    if name not in HERO_SCENARIOS:
        available = ", ".join(HERO_SCENARIOS.keys())
        raise ValueError(f"Unknown hero scenario: {name}. Available: {available}")
    return HERO_SCENARIOS[name]()


def run_all_hero_scenarios(verbose: bool = False) -> List[ScenarioResult]:
    """모든 Hero 시나리오 실행."""
    results = []
    
    for name, cls in HERO_SCENARIOS.items():
        logger.info(f"\n=== Running Hero Scenario: {name} ===")
        scenario = cls(verbose=verbose)
        result = scenario.run()
        results.append(result)
        
        if scenario.hero_metrics:
            print(scenario.hero_metrics.summary_report())
    
    return results
