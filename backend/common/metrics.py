"""
성능 메트릭 및 실행 트레이스 통합 모듈.

Task 수행 시간, Agent 결정, LLM 호출 등을 추적하고
디버깅을 위한 상세 실행 기록을 관리합니다.
"""
from __future__ import annotations

import time
import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Task Metrics (성능 추적)
# =============================================================================

@dataclass
class TaskMetrics:
    """단일 Task 수행 메트릭."""
    task_id: str
    task_type: str
    owner: str
    repo: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    
    # Agent 결정 추적
    detected_intent: Optional[str] = None
    decision_reason: Optional[str] = None
    flow_adjustments: List[str] = field(default_factory=list)
    cache_hit: bool = False
    rerun_count: int = 0
    
    # 단계별 소요 시간 (ms)
    step_timings: Dict[str, float] = field(default_factory=dict)
    
    # LLM 호출 정보
    llm_calls: int = 0
    llm_total_time_ms: float = 0.0
    
    # 결과
    success: bool = False
    error: Optional[str] = None
    
    def complete(self, success: bool = True, error: Optional[str] = None):
        """Task 완료 처리."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.success = success
        self.error = error
    
    def add_step_timing(self, step_name: str, duration_seconds: float):
        """단계별 소요 시간 추가."""
        self.step_timings[step_name] = round(duration_seconds * 1000, 2)
    
    def add_llm_call(self, duration_seconds: float):
        """LLM 호출 기록."""
        self.llm_calls += 1
        self.llm_total_time_ms += round(duration_seconds * 1000, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환."""
        return asdict(self)


class MetricsTracker:
    """
    싱글톤 메트릭 추적기.
    
    Task 수행 시간, Agent 결정, LLM 호출 등을 추적합니다.
    """
    _instance: Optional["MetricsTracker"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._metrics: List[TaskMetrics] = []
        self._max_history = 1000
        self._lock = threading.Lock()
    
    def start_task(
        self,
        task_type: str,
        owner: str,
        repo: str,
        task_id: Optional[str] = None,
    ) -> TaskMetrics:
        """새 Task 시작."""
        task_id = task_id or f"{task_type}_{owner}_{repo}_{int(time.time() * 1000)}"
        metrics = TaskMetrics(
            task_id=task_id,
            task_type=task_type,
            owner=owner,
            repo=repo,
        )
        return metrics
    
    def record_task(self, metrics: TaskMetrics):
        """완료된 Task 기록."""
        with self._lock:
            self._metrics.append(metrics)
            if len(self._metrics) > self._max_history:
                self._metrics = self._metrics[-self._max_history:]
        
        logger.info(
            f"[METRICS] Task completed: {metrics.task_type} "
            f"{metrics.owner}/{metrics.repo} "
            f"duration={metrics.duration_ms}ms "
            f"intent={metrics.detected_intent} "
            f"cache_hit={metrics.cache_hit} "
            f"llm_calls={metrics.llm_calls}"
        )
    
    def get_recent_metrics(self, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 메트릭 조회."""
        with self._lock:
            recent = self._metrics[-limit:]
        return [m.to_dict() for m in reversed(recent)]
    
    def get_summary(self) -> Dict[str, Any]:
        """전체 요약 통계."""
        with self._lock:
            if not self._metrics:
                return {"total_tasks": 0}
            
            total = len(self._metrics)
            successful = sum(1 for m in self._metrics if m.success)
            cache_hits = sum(1 for m in self._metrics if m.cache_hit)
            
            durations = [m.duration_ms for m in self._metrics if m.duration_ms]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            llm_calls = sum(m.llm_calls for m in self._metrics)
            llm_time = sum(m.llm_total_time_ms for m in self._metrics)
            
            by_intent = {}
            for m in self._metrics:
                intent = m.detected_intent or "unknown"
                by_intent[intent] = by_intent.get(intent, 0) + 1
            
            return {
                "total_tasks": total,
                "successful": successful,
                "success_rate": round(successful / total * 100, 1) if total else 0,
                "cache_hit_rate": round(cache_hits / total * 100, 1) if total else 0,
                "avg_duration_ms": round(avg_duration, 2),
                "total_llm_calls": llm_calls,
                "total_llm_time_ms": round(llm_time, 2),
                "by_intent": by_intent,
            }
    
    def clear(self):
        """메트릭 초기화."""
        with self._lock:
            self._metrics.clear()
    
    @classmethod
    def reset_instance(cls):
        """싱글톤 인스턴스 리셋 (테스트용)."""
        with cls._lock:
            cls._instance = None


def get_metrics_tracker() -> MetricsTracker:
    """메트릭 추적기 싱글톤 반환."""
    return MetricsTracker()


# =============================================================================
# Execution Trace (디버깅/로깅)
# =============================================================================

@dataclass
class ExecutionTrace:
    """실행 트레이스 (디버깅/로깅 전용)"""
    
    session_id: str
    turn_number: int
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    
    # 실행 플로우
    supervisor_state_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    subagent_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    # LLM 호출
    llm_calls: List[Dict[str, Any]] = field(default_factory=list)
    total_llm_calls: int = 0
    
    # 성능
    execution_time_ms: int = 0
    
    # 디버깅
    debug_logs: List[str] = field(default_factory=list)
    
    def log_supervisor_state(self, state: Dict[str, Any], step: str):
        """Supervisor State 스냅샷"""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "state": self._sanitize_state(state)
        }
        self.supervisor_state_snapshots.append(snapshot)
        logger.debug(f"[Trace] Supervisor state at {step}")
    
    def log_subagent_call(
        self,
        agent: str,
        input_params: Dict[str, Any],
        output: Dict[str, Any],
        execution_time_ms: int,
        from_cache: bool = False
    ):
        """Sub-agent 호출 기록"""
        call = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "input_params": input_params,
            "output_summary": self._summarize_output(output),
            "execution_time_ms": execution_time_ms,
            "from_cache": from_cache
        }
        self.subagent_calls.append(call)
        logger.debug(f"[Trace] Sub-agent call: {agent} ({execution_time_ms}ms)")
    
    def log_llm_call(
        self,
        model: str,
        prompt_summary: str,
        response_summary: str,
        tokens: int,
        execution_time_ms: int
    ):
        """LLM 호출 기록"""
        call = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "prompt_summary": prompt_summary[:200],  # 처음 200자만
            "response_summary": response_summary[:200],
            "tokens": tokens,
            "execution_time_ms": execution_time_ms
        }
        self.llm_calls.append(call)
        self.total_llm_calls += 1
        logger.debug(f"[Trace] LLM call: {model} ({tokens} tokens, {execution_time_ms}ms)")
    
    def add_debug_log(self, message: str):
        """디버그 로그 추가"""
        log_entry = f"[{datetime.now().isoformat()}] {message}"
        self.debug_logs.append(log_entry)
        logger.debug(f"[Trace] {message}")
    
    def finalize(self):
        """트레이스 종료"""
        self.ended_at = datetime.now()
        if self.started_at:
            self.execution_time_ms = int((self.ended_at - self.started_at).total_seconds() * 1000)
        logger.info(f"[Trace] Turn {self.turn_number} completed in {self.execution_time_ms}ms")
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "execution_time_ms": self.execution_time_ms,
            "supervisor_state_snapshots": self.supervisor_state_snapshots,
            "subagent_calls": self.subagent_calls,
            "llm_calls": self.llm_calls,
            "total_llm_calls": self.total_llm_calls,
            "debug_logs": self.debug_logs
        }
    
    def export_json(self, filepath: str):
        """JSON 파일로 내보내기"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Trace exported to {filepath}")
    
    @staticmethod
    def _sanitize_state(state: Dict[str, Any]) -> Dict[str, Any]:
        """State에서 중요한 필드만 추출"""
        important_fields = [
            "session_id", "owner", "repo", "user_message",
            "detected_intent", "next_node_override", "step",
            "error", "cache_hit"
        ]
        return {k: v for k, v in state.items() if k in important_fields}
    
    @staticmethod
    def _summarize_output(output: Dict[str, Any]) -> str:
        """출력 요약"""
        if not output:
            return "empty"
        
        # 주요 키만 나열
        keys = list(output.keys())[:5]
        summary = f"keys: {', '.join(keys)}"
        
        if "error" in output:
            summary += f" | error: {output['error']}"
        
        return summary


class TraceManager:
    """트레이스 관리자"""
    
    def __init__(self):
        self._active_traces: Dict[str, ExecutionTrace] = {}
        logger.info("TraceManager initialized")
    
    def start_trace(self, session_id: str, turn_number: int) -> ExecutionTrace:
        """트레이스 시작"""
        trace_key = f"{session_id}_{turn_number}"
        trace = ExecutionTrace(session_id=session_id, turn_number=turn_number)
        self._active_traces[trace_key] = trace
        logger.info(f"Trace started: {trace_key}")
        return trace
    
    def get_trace(self, session_id: str, turn_number: int) -> Optional[ExecutionTrace]:
        """트레이스 조회"""
        trace_key = f"{session_id}_{turn_number}"
        return self._active_traces.get(trace_key)
    
    def finalize_trace(self, session_id: str, turn_number: int) -> Optional[ExecutionTrace]:
        """트레이스 종료"""
        trace_key = f"{session_id}_{turn_number}"
        trace = self._active_traces.get(trace_key)
        
        if trace:
            trace.finalize()
            # 메모리 관리를 위해 삭제 (필요시 파일로 저장)
            del self._active_traces[trace_key]
            logger.info(f"Trace finalized: {trace_key}")
            return trace
        
        return None
    
    def export_trace(self, session_id: str, turn_number: int, filepath: str):
        """트레이스 파일로 내보내기"""
        trace = self.get_trace(session_id, turn_number)
        if trace:
            trace.export_json(filepath)


# === 싱글톤 인스턴스 ===
_trace_manager_instance: Optional[TraceManager] = None


def get_trace_manager() -> TraceManager:
    """트레이스 관리자 싱글톤 인스턴스 반환"""
    global _trace_manager_instance
    if _trace_manager_instance is None:
        _trace_manager_instance = TraceManager()
    return _trace_manager_instance
