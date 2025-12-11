"""
성능 측정 시나리오 베이스 및 유틸리티.

이 모듈은 Diagnosis/Supervisor 에이전트의 성능 측정을 위한
시나리오 기반 벤치마크 시스템의 핵심 클래스를 정의합니다.
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """측정 지표 유형."""
    LATENCY = "latency"           # 소요 시간 (ms)
    COUNT = "count"               # 호출 횟수
    RATE = "rate"                 # 비율 (%)
    SIZE = "size"                 # 크기 (bytes, items)


@dataclass
class NodeMetrics:
    """
    노드별 성능 메트릭.
    
    각 그래프 노드의 실행 시간과 호출 정보를 추적합니다.
    
    Attributes:
        node_name: 노드 이름 (e.g., "fetch_readme", "analyze_dependencies")
        execution_time_ms: 실행 시간 (밀리초)
        call_count: 호출 횟수
        success: 성공 여부
        from_cache: 캐시에서 결과를 가져왔는지 여부
        metadata: 추가 메타데이터 (e.g., 처리된 아이템 수)
    """
    node_name: str
    execution_time_ms: float = 0.0
    call_count: int = 1
    success: bool = True
    from_cache: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentMetrics:
    """
    에이전트 전체 성능 메트릭.
    
    하나의 에이전트 실행에 대한 전체 성능 정보를 집계합니다.
    
    Attributes:
        agent_name: 에이전트 이름 (e.g., "diagnosis", "supervisor")
        total_time_ms: 전체 실행 시간
        node_metrics: 노드별 메트릭 목록
        api_calls: 외부 API 호출 횟수
        llm_calls: LLM 호출 횟수
        llm_time_ms: LLM 호출에 소요된 총 시간
        cache_hits: 캐시 히트 횟수
        cache_misses: 캐시 미스 횟수
        errors: 발생한 에러 목록
        custom_metrics: 에이전트별 커스텀 메트릭 (점수, 등급 등)
    """
    agent_name: str
    total_time_ms: float = 0.0
    node_metrics: List[NodeMetrics] = field(default_factory=list)
    api_calls: int = 0
    llm_calls: int = 0
    llm_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: List[str] = field(default_factory=list)
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def cache_hit_rate(self) -> float:
        """캐시 히트율 계산."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """노드 성공률 계산."""
        if not self.node_metrics:
            return 100.0
        success = sum(1 for n in self.node_metrics if n.success)
        return success / len(self.node_metrics) * 100
    
    def add_node_metric(self, node: NodeMetrics):
        """노드 메트릭 추가."""
        self.node_metrics.append(node)
        if node.from_cache:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def set_metric(self, key: str, value: Any):
        """커스텀 메트릭 설정."""
        self.custom_metrics[key] = value
    
    def get_slowest_nodes(self, top_n: int = 5) -> List[NodeMetrics]:
        """가장 느린 노드 반환."""
        sorted_nodes = sorted(
            self.node_metrics, 
            key=lambda n: n.execution_time_ms, 
            reverse=True
        )
        return sorted_nodes[:top_n]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "total_time_ms": self.total_time_ms,
            "node_metrics": [n.to_dict() for n in self.node_metrics],
            "api_calls": self.api_calls,
            "llm_calls": self.llm_calls,
            "llm_time_ms": self.llm_time_ms,
            "cache_hit_rate": round(self.cache_hit_rate, 2),
            "success_rate": round(self.success_rate, 2),
            "errors": self.errors,
            "timestamp": self.timestamp,
        }
    
    def summary(self) -> str:
        """사람이 읽기 쉬운 요약."""
        lines = [
            f"=== {self.agent_name.upper()} Performance Summary ===",
            f"Total Time: {self.total_time_ms:.2f}ms",
            f"Nodes: {len(self.node_metrics)}, Success Rate: {self.success_rate:.1f}%",
            f"Cache Hit Rate: {self.cache_hit_rate:.1f}%",
            f"LLM Calls: {self.llm_calls} ({self.llm_time_ms:.2f}ms)",
            f"API Calls: {self.api_calls}",
        ]
        
        slowest = self.get_slowest_nodes(3)
        if slowest:
            lines.append("Slowest Nodes:")
            for node in slowest:
                lines.append(f"  - {node.node_name}: {node.execution_time_ms:.2f}ms")
        
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            
        return "\n".join(lines)


@dataclass
class ScenarioResult:
    """
    시나리오 실행 결과.
    
    Attributes:
        scenario_name: 시나리오 이름
        description: 시나리오 설명
        repos: 테스트된 레포지토리 목록
        agent_metrics: 에이전트별 메트릭
        total_time_ms: 전체 시나리오 실행 시간
        passed: 시나리오 통과 여부
        notes: 추가 노트
    """
    scenario_name: str
    description: str
    repos: List[str]
    agent_metrics: List[AgentMetrics] = field(default_factory=list)
    total_time_ms: float = 0.0
    passed: bool = True
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "description": self.description,
            "repos": self.repos,
            "agent_metrics": [m.to_dict() for m in self.agent_metrics],
            "total_time_ms": self.total_time_ms,
            "passed": self.passed,
            "notes": self.notes,
        }


class ScenarioBase(ABC):
    """
    벤치마크 시나리오 베이스 클래스.
    
    모든 시나리오는 이 클래스를 상속받아 구현합니다.
    
    Example:
        class SmallRepoScenario(ScenarioBase):
            name = "small_repo"
            description = "소형 레포지토리 (<100 파일) 벤치마크"
            repos = [("lodash", "lodash", "main")]
            
            def run(self) -> ScenarioResult:
                # 시나리오 실행 로직
                ...
    """
    
    # 서브클래스에서 오버라이드
    name: str = "base"
    description: str = "Base scenario"
    repos: List[tuple] = []  # [(owner, repo, ref), ...]
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._start_time: Optional[float] = None
        self._current_metrics: Optional[AgentMetrics] = None
    
    @abstractmethod
    def run(self) -> ScenarioResult:
        """
        시나리오 실행.
        
        Returns:
            ScenarioResult: 실행 결과
        """
        pass
    
    def start_timing(self) -> float:
        """타이밍 시작."""
        self._start_time = time.time()
        return self._start_time
    
    def stop_timing(self) -> float:
        """타이밍 종료 및 경과 시간 반환 (ms)."""
        if self._start_time is None:
            return 0.0
        elapsed = (time.time() - self._start_time) * 1000
        self._start_time = None
        return elapsed
    
    def measure_node(self, node_name: str, func: Callable, *args, **kwargs) -> tuple:
        """
        노드 실행 시간 측정.
        
        Args:
            node_name: 노드 이름
            func: 실행할 함수
            *args, **kwargs: 함수 인자
            
        Returns:
            (결과, NodeMetrics)
        """
        start = time.time()
        success = True
        result = None
        
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            success = False
            logger.error(f"Node {node_name} failed: {e}")
            
        elapsed = (time.time() - start) * 1000
        
        metrics = NodeMetrics(
            node_name=node_name,
            execution_time_ms=elapsed,
            success=success,
        )
        
        return result, metrics
    
    def log(self, message: str):
        """조건부 로깅."""
        if self.verbose:
            logger.info(f"[{self.name}] {message}")


class Timer:
    """컨텍스트 매니저 기반 타이머."""
    
    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time: float = 0
        self.end_time: float = 0
        self.elapsed_ms: float = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000
    
    def __repr__(self):
        return f"Timer({self.name}: {self.elapsed_ms:.2f}ms)"
