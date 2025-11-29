"""
Diagnosis 메트릭 수집

LLM 호출 횟수, Fallback 비율 등 추적.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class LLMMetrics:
    """LLM 호출 메트릭."""
    total: int = 0
    success: int = 0
    failed: int = 0
    fallback: int = 0
    total_duration_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return (self.success / self.total * 100) if self.total else 0.0
    
    @property
    def fallback_rate(self) -> float:
        return (self.fallback / self.total * 100) if self.total else 0.0
    
    @property
    def avg_duration_ms(self) -> float:
        return (self.total_duration_ms / self.success) if self.success else 0.0


@dataclass
class TaskMetrics:
    """Task 생성 메트릭."""
    total_generations: int = 0
    total_tasks: int = 0
    beginner: int = 0
    intermediate: int = 0
    advanced: int = 0


@dataclass
class ScenarioMetrics:
    """시나리오 생성 메트릭."""
    attempts: int = 0
    success: int = 0
    failed: int = 0


class DiagnosisMetrics:
    """Diagnosis 메트릭 수집기 (싱글톤)."""
    
    _instance: Optional["DiagnosisMetrics"] = None
    _lock = Lock()
    
    def __new__(cls) -> "DiagnosisMetrics":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._llm = LLMMetrics()
        self._task = TaskMetrics()
        self._scenario = ScenarioMetrics()
        self._start_time = datetime.now(timezone.utc)
        self._lock = Lock()
    
    def record_llm_call(self, success: bool, duration_ms: float = 0.0) -> None:
        with self._lock:
            self._llm.total += 1
            if success:
                self._llm.success += 1
                self._llm.total_duration_ms += duration_ms
            else:
                self._llm.failed += 1
    
    def record_fallback(self, reason: str = "") -> None:
        with self._lock:
            self._llm.fallback += 1
    
    def record_scenario(self, success: bool) -> None:
        with self._lock:
            self._scenario.attempts += 1
            if success:
                self._scenario.success += 1
            else:
                self._scenario.failed += 1
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "llm": {
                    "total": self._llm.total,
                    "success_rate": f"{self._llm.success_rate:.1f}%",
                    "fallback_rate": f"{self._llm.fallback_rate:.1f}%",
                    "avg_duration_ms": f"{self._llm.avg_duration_ms:.0f}",
                },
                "scenario": {
                    "attempts": self._scenario.attempts,
                    "success": self._scenario.success,
                },
            }
    
    def reset(self) -> None:
        with self._lock:
            self._llm = LLMMetrics()
            self._task = TaskMetrics()
            self._scenario = ScenarioMetrics()


class LLMTimer:
    """LLM 호출 타이밍 컨텍스트 매니저."""
    
    def __init__(self, metrics: DiagnosisMetrics):
        self.metrics = metrics
        self.start: float = 0
        self.success: bool = False
    
    def __enter__(self) -> "LLMTimer":
        self.start = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = (time.perf_counter() - self.start) * 1000
        self.metrics.record_llm_call(self.success, duration)
        if not self.success and exc_type is None:
            self.metrics.record_fallback()
    
    def mark_success(self) -> None:
        self.success = True


# 싱글톤 인스턴스
diagnosis_metrics = DiagnosisMetrics()
