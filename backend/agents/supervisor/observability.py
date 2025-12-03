"""Observability & Operations Gate for Supervisor V1.

Structure:
- Section 1: Metrics (MetricsWindow, MetricsCollector, percentile)
- Section 2: SLO (SLOChecker, SLOCheckResult, WeeklyReport, EventValidator)
- Section 3: Canary (CanaryManager, AutoDeploymentController, ErrorMeta)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict

from backend.common.events import (
    EventType,
    Event,
    EventStore,
    get_event_store,
    emit_event,
)


# Section 1: Metrics

REQUIRED_EVENT_TYPES = [
    EventType.SUPERVISOR_INTENT_DETECTED,
    EventType.SUPERVISOR_ROUTE_SELECTED,
    EventType.NODE_STARTED,
    EventType.NODE_FINISHED,
    EventType.ANSWER_GENERATED,
]


# SLO 정의
@dataclass
class SLOConfig:
    """Service Level Objective 설정."""
    # Latency SLO (p95, milliseconds)
    greeting_p95_ms: float = 100.0
    overview_p95_ms: float = 1500.0
    expert_p95_ms: float = 10000.0  # 팀 합의 값 (기본 10초)
    
    # Quality SLO
    disambiguation_min_pct: float = 10.0
    disambiguation_max_pct: float = 25.0
    wrong_proceed_max_pct: float = 1.0
    empty_sources_max_pct: float = 0.0
    duplicate_cards_max_count: int = 0
    
    # Event SLO
    required_events_missing_max: int = 0


# DEFAULT_SLOS dictionary for testing
DEFAULT_SLOS = {
    "greeting_latency_p95": 100.0,
    "overview_latency_p95": 1500.0,
    "disambiguation_rate": (10.0, 25.0),  # min, max
    "wrong_proceed_rate": 1.0,
    "sources_empty_rate": 0.0,
    "duplicate_card_rate": 0,
    "error_recovery_rate": 95.0,
}


# 지표 집계
@dataclass
class MetricsWindow:
    """시간 윈도우 내 지표 집계."""
    window_start: float = field(default_factory=time.time)
    window_size_seconds: int = 3600  # 1시간 기본
    
    # Latency metrics (list of durations in ms)
    greeting_latencies: List[float] = field(default_factory=list)
    overview_latencies: List[float] = field(default_factory=list)
    expert_latencies: List[float] = field(default_factory=list)
    
    # Quality metrics
    total_requests: int = 0
    disambiguation_count: int = 0
    wrong_proceed_count: int = 0
    empty_sources_count: int = 0
    duplicate_cards_count: int = 0
    
    # Event tracking
    missing_events_count: int = 0
    event_type_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Error tracking
    error_count: int = 0
    error_details: List[Dict[str, Any]] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        return time.time() - self.window_start > self.window_size_seconds
    
    def reset(self) -> None:
        self.window_start = time.time()
        self.greeting_latencies.clear()
        self.overview_latencies.clear()
        self.expert_latencies.clear()
        self.total_requests = 0
        self.disambiguation_count = 0
        self.wrong_proceed_count = 0
        self.empty_sources_count = 0
        self.duplicate_cards_count = 0
        self.missing_events_count = 0
        self.event_type_counts.clear()
        self.error_count = 0
        self.error_details.clear()


def percentile(values: List[float], p: float) -> float:
    """p-percentile 계산 (0-100)."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_values) else f
    return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])


@dataclass
class SLOCheckResult:
    """SLO 검사 결과."""
    passed: bool
    metric_name: str
    current_value: float
    threshold: float
    message: str


class MetricsCollector:
    """지표 수집기."""
    
    def __init__(self, window_size_seconds: int = 3600):
        self.current_window = MetricsWindow(window_size_seconds=window_size_seconds)
        self.historical_windows: List[MetricsWindow] = []
        self.max_historical_windows = 168  # 1주일 (1시간 윈도우 기준)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        
    def _rotate_window_if_needed(self) -> None:
        if self.current_window.is_expired():
            self.historical_windows.append(self.current_window)
            if len(self.historical_windows) > self.max_historical_windows:
                self.historical_windows = self.historical_windows[-self.max_historical_windows:]
            self.current_window = MetricsWindow(
                window_size_seconds=self.current_window.window_size_seconds
            )
    
    def record_latency(self, intent: str, latency_ms: float) -> None:
        """레이턴시 기록 (테스트/집계용)."""
        self._latencies[intent].append(latency_ms)
        
        # Also record in window
        self._rotate_window_if_needed()
        if intent in ("smalltalk", "help", "greeting"):
            self.current_window.greeting_latencies.append(latency_ms)
        elif intent == "overview":
            self.current_window.overview_latencies.append(latency_ms)
        else:
            self.current_window.expert_latencies.append(latency_ms)
    
    def get_percentile(self, intent: str, p: float) -> float:
        """특정 인텐트의 p-percentile 레이턴시 반환."""
        values = self._latencies.get(intent, [])
        return percentile(values, p)
    
    def record_request(
        self,
        intent: str,
        latency_ms: float,
        disambiguated: bool = False,
        wrong_proceed: bool = False,
        sources_empty: bool = False,
        duplicate_cards: int = 0,
    ) -> None:
        """요청 지표 기록."""
        self._rotate_window_if_needed()
        
        self.current_window.total_requests += 1
        
        # Latency by intent type
        if intent in ("smalltalk", "help"):
            self.current_window.greeting_latencies.append(latency_ms)
        elif intent == "overview":
            self.current_window.overview_latencies.append(latency_ms)
        else:
            self.current_window.expert_latencies.append(latency_ms)
        
        # Quality metrics
        if disambiguated:
            self.current_window.disambiguation_count += 1
        if wrong_proceed:
            self.current_window.wrong_proceed_count += 1
        if sources_empty:
            self.current_window.empty_sources_count += 1
        self.current_window.duplicate_cards_count += duplicate_cards
    
    def record_event(self, event_type: EventType) -> None:
        """이벤트 발생 기록."""
        self._rotate_window_if_needed()
        self.current_window.event_type_counts[event_type.value] += 1
    
    def record_missing_event(self, event_type: EventType) -> None:
        """누락 이벤트 기록."""
        self._rotate_window_if_needed()
        self.current_window.missing_events_count += 1
    
    def record_error(self, error_type: str, details: Dict[str, Any]) -> None:
        """에러 기록."""
        self._rotate_window_if_needed()
        self.current_window.error_count += 1
        self.current_window.error_details.append({
            "type": error_type,
            "timestamp": time.time(),
            **details
        })
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """현재 윈도우 지표 반환."""
        w = self.current_window
        total = w.total_requests or 1  # avoid division by zero
        
        return {
            "window_start": datetime.fromtimestamp(w.window_start).isoformat(),
            "total_requests": w.total_requests,
            "latency": {
                "greeting_p95_ms": percentile(w.greeting_latencies, 95),
                "overview_p95_ms": percentile(w.overview_latencies, 95),
                "expert_p95_ms": percentile(w.expert_latencies, 95),
            },
            "quality": {
                "disambiguation_pct": (w.disambiguation_count / total) * 100,
                "wrong_proceed_pct": (w.wrong_proceed_count / total) * 100,
                "empty_sources_pct": (w.empty_sources_count / total) * 100,
                "duplicate_cards_count": w.duplicate_cards_count,
            },
            "events": {
                "missing_count": w.missing_events_count,
                "type_counts": dict(w.event_type_counts),
            },
            "errors": {
                "count": w.error_count,
                "recent": w.error_details[-10:] if w.error_details else [],
            },
        }


# 전역 메트릭 수집기
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# Section 2: SLO

class SLOChecker:
    """SLO 준수 여부 검사."""
    
    def __init__(self, config: Optional[SLOConfig] = None):
        self.config = config or SLOConfig()
    
    def check_all(self, metrics: Dict[str, Any]) -> List[SLOCheckResult]:
        """모든 SLO 검사."""
        results = []
        
        # Latency SLO
        latency = metrics.get("latency", {})
        results.append(self._check_latency(
            "greeting_p95", 
            latency.get("greeting_p95_ms", 0),
            self.config.greeting_p95_ms
        ))
        results.append(self._check_latency(
            "overview_p95",
            latency.get("overview_p95_ms", 0),
            self.config.overview_p95_ms
        ))
        results.append(self._check_latency(
            "expert_p95",
            latency.get("expert_p95_ms", 0),
            self.config.expert_p95_ms
        ))
        
        # Quality SLO
        quality = metrics.get("quality", {})
        
        # Disambiguation (10-25% 범위)
        disambig_pct = quality.get("disambiguation_pct", 0)
        results.append(SLOCheckResult(
            passed=self.config.disambiguation_min_pct <= disambig_pct <= self.config.disambiguation_max_pct,
            metric_name="disambiguation_range",
            current_value=disambig_pct,
            threshold=self.config.disambiguation_max_pct,
            message=f"Disambiguation {disambig_pct:.1f}% (target: {self.config.disambiguation_min_pct}-{self.config.disambiguation_max_pct}%)"
        ))
        
        # Wrong proceed
        results.append(self._check_max(
            "wrong_proceed",
            quality.get("wrong_proceed_pct", 0),
            self.config.wrong_proceed_max_pct
        ))
        
        # Empty sources
        results.append(self._check_max(
            "empty_sources",
            quality.get("empty_sources_pct", 0),
            self.config.empty_sources_max_pct
        ))
        
        # Duplicate cards
        results.append(self._check_max(
            "duplicate_cards",
            quality.get("duplicate_cards_count", 0),
            float(self.config.duplicate_cards_max_count)
        ))
        
        # Event SLO
        events = metrics.get("events", {})
        results.append(self._check_max(
            "missing_events",
            events.get("missing_count", 0),
            float(self.config.required_events_missing_max)
        ))
        
        return results
    
    def _check_latency(self, name: str, value: float, threshold: float) -> SLOCheckResult:
        return SLOCheckResult(
            passed=value <= threshold,
            metric_name=name,
            current_value=value,
            threshold=threshold,
            message=f"{name}: {value:.1f}ms (threshold: {threshold:.1f}ms)"
        )
    
    def _check_max(self, name: str, value: float, threshold: float) -> SLOCheckResult:
        return SLOCheckResult(
            passed=value <= threshold,
            metric_name=name,
            current_value=value,
            threshold=threshold,
            message=f"{name}: {value:.2f} (max: {threshold:.2f})"
        )
    
    def is_healthy(self, metrics: Dict[str, Any]) -> bool:
        """전체 SLO 건강 상태."""
        results = self.check_all(metrics)
        return all(r.passed for r in results)


# 주간 리포트 생성
@dataclass
class WeeklyReport:
    """주간 지표 리포트."""
    generated_at: str
    period_start: str
    period_end: str
    total_requests: int
    slo_results: List[Dict[str, Any]]
    all_slos_met: bool
    recommendations: List[str]


def generate_weekly_report(collector: MetricsCollector) -> WeeklyReport:
    """주간 리포트 생성."""
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    # 지난 1주일 윈도우 집계
    total_requests = collector.current_window.total_requests
    all_greeting = list(collector.current_window.greeting_latencies)
    all_overview = list(collector.current_window.overview_latencies)
    all_expert = list(collector.current_window.expert_latencies)
    total_disambig = collector.current_window.disambiguation_count
    total_wrong = collector.current_window.wrong_proceed_count
    total_empty = collector.current_window.empty_sources_count
    total_dup = collector.current_window.duplicate_cards_count
    total_missing = collector.current_window.missing_events_count
    
    for w in collector.historical_windows:
        if w.window_start >= week_ago.timestamp():
            total_requests += w.total_requests
            all_greeting.extend(w.greeting_latencies)
            all_overview.extend(w.overview_latencies)
            all_expert.extend(w.expert_latencies)
            total_disambig += w.disambiguation_count
            total_wrong += w.wrong_proceed_count
            total_empty += w.empty_sources_count
            total_dup += w.duplicate_cards_count
            total_missing += w.missing_events_count
    
    total = total_requests or 1
    
    aggregated_metrics = {
        "latency": {
            "greeting_p95_ms": percentile(all_greeting, 95),
            "overview_p95_ms": percentile(all_overview, 95),
            "expert_p95_ms": percentile(all_expert, 95),
        },
        "quality": {
            "disambiguation_pct": (total_disambig / total) * 100,
            "wrong_proceed_pct": (total_wrong / total) * 100,
            "empty_sources_pct": (total_empty / total) * 100,
            "duplicate_cards_count": total_dup,
        },
        "events": {
            "missing_count": total_missing,
        },
    }
    
    checker = SLOChecker()
    results = checker.check_all(aggregated_metrics)
    
    # 권장 사항 생성
    recommendations = []
    for r in results:
        if not r.passed:
            recommendations.append(f"[Action Required] {r.message}")
    
    if not recommendations:
        recommendations.append("All SLOs met. No action required.")
    
    return WeeklyReport(
        generated_at=now.isoformat(),
        period_start=week_ago.isoformat(),
        period_end=now.isoformat(),
        total_requests=total_requests,
        slo_results=[{
            "metric": r.metric_name,
            "passed": r.passed,
            "value": r.current_value,
            "threshold": r.threshold,
            "message": r.message,
        } for r in results],
        all_slos_met=all(r.passed for r in results),
        recommendations=recommendations,
    )


# 이벤트 누락 검사기
class EventValidator:
    """턴별 이벤트 누락 검사."""
    
    def __init__(self, event_store: Optional[EventStore] = None):
        self.event_store = event_store or get_event_store()
        self.collector = get_metrics_collector()
    
    def validate_turn(self, session_id: str, turn_id: str) -> List[EventType]:
        """턴에서 누락된 필수 이벤트 반환."""
        events = self.event_store.get_by_turn(session_id, turn_id)
        found_types = {e.type for e in events}
        
        missing = []
        for required in REQUIRED_EVENT_TYPES:
            if required not in found_types:
                missing.append(required)
                self.collector.record_missing_event(required)
        
        return missing
    
    def emit_validation_result(
        self,
        session_id: str,
        turn_id: str,
        missing: List[EventType]
    ) -> None:
        """검증 결과 이벤트 발생."""
        emit_event(
            EventType.ANSWER_VALIDATED,
            outputs={
                "session_id": session_id,
                "turn_id": turn_id,
                "missing_events": [e.value for e in missing],
                "valid": len(missing) == 0,
            }
        )


# Section 3: Canary Deployment

class CanaryManager:
    """Canary 배포 및 롤백 관리."""
    
    class DeploymentPhase(str, Enum):
        CANARY = "canary"      # 10% 트래픽
        GRADUAL_25 = "gradual_25"
        GRADUAL_50 = "gradual_50"
        GRADUAL_75 = "gradual_75"
        FULL = "full"         # 100%
        ROLLBACK = "rollback"
    
    def __init__(self):
        self.current_phase = self.DeploymentPhase.FULL
        self.rollback_reason: Optional[str] = None
        
        # Feature toggles
        self.feature_toggles: Dict[str, bool] = {
            "lightweight_path": True,
            "followup_planner": True,
            "expert_runner": True,
            "agentic_planning": True,
        }
        
        # Threshold overrides (for rollback)
        self.threshold_override: Optional[float] = None
    
    def get_traffic_percentage(self) -> int:
        """현재 트래픽 비율."""
        return {
            self.DeploymentPhase.CANARY: 10,
            self.DeploymentPhase.GRADUAL_25: 25,
            self.DeploymentPhase.GRADUAL_50: 50,
            self.DeploymentPhase.GRADUAL_75: 75,
            self.DeploymentPhase.FULL: 100,
            self.DeploymentPhase.ROLLBACK: 0,
        }.get(self.current_phase, 100)
    
    def should_use_new_feature(self, feature_name: str) -> bool:
        """피처 토글 확인."""
        return self.feature_toggles.get(feature_name, True)
    
    def promote(self) -> bool:
        """다음 단계로 승격."""
        phase_order = [
            self.DeploymentPhase.CANARY,
            self.DeploymentPhase.GRADUAL_25,
            self.DeploymentPhase.GRADUAL_50,
            self.DeploymentPhase.GRADUAL_75,
            self.DeploymentPhase.FULL,
        ]
        
        try:
            idx = phase_order.index(self.current_phase)
            if idx < len(phase_order) - 1:
                self.current_phase = phase_order[idx + 1]
                return True
        except ValueError:
            pass
        return False
    
    def rollback(self, reason: str, disable_features: Optional[List[str]] = None) -> None:
        """롤백 실행."""
        self.current_phase = self.DeploymentPhase.ROLLBACK
        self.rollback_reason = reason
        
        # 지정된 피처 비활성화
        if disable_features:
            for feature in disable_features:
                if feature in self.feature_toggles:
                    self.feature_toggles[feature] = False
        
        # 임계값 상향 (보수적 라우팅)
        self.threshold_override = 0.7
    
    def get_effective_threshold(self, base_threshold: float) -> float:
        """오버라이드 적용된 임계값."""
        if self.threshold_override is not None:
            return max(base_threshold, self.threshold_override)
        return base_threshold
    
    def get_status(self) -> Dict[str, Any]:
        """배포 상태 반환."""
        return {
            "phase": self.current_phase.value,
            "traffic_percentage": self.get_traffic_percentage(),
            "feature_toggles": self.feature_toggles.copy(),
            "threshold_override": self.threshold_override,
            "rollback_reason": self.rollback_reason,
        }


# 전역 Canary 매니저
_canary_manager: Optional[CanaryManager] = None


def get_canary_manager() -> CanaryManager:
    global _canary_manager
    if _canary_manager is None:
        _canary_manager = CanaryManager()
    return _canary_manager


# 자동 SLO 기반 롤백/승격 결정
class AutoDeploymentController:
    """SLO 기반 자동 배포 제어."""
    
    def __init__(
        self,
        canary: Optional[CanaryManager] = None,
        checker: Optional[SLOChecker] = None,
        collector: Optional[MetricsCollector] = None,
    ):
        self.canary = canary or get_canary_manager()
        self.checker = checker or SLOChecker()
        self.collector = collector or get_metrics_collector()
        
        # 승격/롤백 조건
        self.min_requests_for_decision = 100
        self.consecutive_healthy_windows = 0
        self.required_healthy_windows = 3  # 3시간 연속 건강 필요
    
    def evaluate(self) -> Dict[str, Any]:
        """SLO 평가 및 배포 결정."""
        metrics = self.collector.get_current_metrics()
        total_requests = metrics.get("total_requests", 0)
        
        # 최소 요청 수 확인
        if total_requests < self.min_requests_for_decision:
            return {
                "action": "wait",
                "reason": f"Insufficient data ({total_requests}/{self.min_requests_for_decision} requests)",
            }
        
        is_healthy = self.checker.is_healthy(metrics)
        
        if is_healthy:
            self.consecutive_healthy_windows += 1
            
            if self.consecutive_healthy_windows >= self.required_healthy_windows:
                # 승격 조건 충족
                if self.canary.promote():
                    self.consecutive_healthy_windows = 0
                    return {
                        "action": "promote",
                        "new_phase": self.canary.current_phase.value,
                        "traffic": self.canary.get_traffic_percentage(),
                    }
            
            return {
                "action": "hold",
                "consecutive_healthy": self.consecutive_healthy_windows,
                "required": self.required_healthy_windows,
            }
        else:
            # SLO 위반 - 롤백 고려
            self.consecutive_healthy_windows = 0
            
            # 어떤 SLO가 위반되었는지 확인
            results = self.checker.check_all(metrics)
            violations = [r for r in results if not r.passed]
            
            # 심각도에 따라 롤백 피처 결정
            features_to_disable = []
            for v in violations:
                if v.metric_name == "expert_p95":
                    features_to_disable.append("expert_runner")
                elif v.metric_name == "empty_sources":
                    features_to_disable.append("agentic_planning")
            
            if violations:
                self.canary.rollback(
                    reason="; ".join(v.message for v in violations),
                    disable_features=features_to_disable if features_to_disable else None
                )
                
                return {
                    "action": "rollback",
                    "reason": self.canary.rollback_reason,
                    "disabled_features": features_to_disable,
                }
            
            return {"action": "hold", "status": "unhealthy"}


# 에러 메타 기록
@dataclass
class ErrorMeta:
    """에러 메타데이터."""
    error_type: str
    message: str
    timestamp: float
    can_retry: bool
    retry_count: int = 0
    max_retries: int = 3
    context: Dict[str, Any] = field(default_factory=dict)
    
    def should_retry(self) -> bool:
        return self.can_retry and self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat(),
            "can_retry": self.can_retry,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "should_retry": self.should_retry(),
            "context": self.context,
        }


def emit_error_event(
    error_type: str,
    message: str,
    can_retry: bool = True,
    retry_count: int = 0,
    context: Optional[Dict[str, Any]] = None,
) -> ErrorMeta:
    """에러 이벤트 발생 및 메타 기록."""
    meta = ErrorMeta(
        error_type=error_type,
        message=message,
        timestamp=time.time(),
        can_retry=can_retry,
        retry_count=retry_count,
        context=context or {},
    )
    
    emit_event(
        EventType.ERROR_OCCURRED,
        outputs=meta.to_dict(),
        metadata={"recoverable": can_retry},
    )
    
    get_metrics_collector().record_error(error_type, meta.to_dict())
    
    return meta


# 대시보드 지표 API
def get_dashboard_metrics() -> Dict[str, Any]:
    """대시보드용 지표 반환."""
    collector = get_metrics_collector()
    canary = get_canary_manager()
    checker = SLOChecker()
    
    current = collector.get_current_metrics()
    slo_results = checker.check_all(current)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "metrics": current,
        "slo_status": {
            "all_passed": all(r.passed for r in slo_results),
            "results": [{
                "metric": r.metric_name,
                "passed": r.passed,
                "value": r.current_value,
                "threshold": r.threshold,
            } for r in slo_results],
        },
        "deployment": canary.get_status(),
    }
