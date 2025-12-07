"""성능 및 Agent 결정 추적 모듈."""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


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

