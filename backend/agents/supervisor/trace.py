"""Trace 모듈 - 에이전트 실행 추적을 위한 모델 및 콜백 핸들러."""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """단일 노드 실행 추적 정보."""
    node: str                          # 노드 이름
    status: str                        # "started" | "completed" | "error"
    timestamp: float = 0.0             # epoch seconds
    duration_ms: float = 0.0           # 실행 시간 (completed일 때만)
    input_summary: Dict[str, Any] = field(default_factory=dict)
    output_summary: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화용 dict 변환."""
        result = asdict(self)
        # None 값 제거
        return {k: v for k, v in result.items() if v is not None and v != {}}


class TracingCallbackHandler(BaseCallbackHandler):
    """LangGraph 노드 실행 추적을 위한 콜백 핸들러.
    
    on_chain_start/on_chain_end를 통해 각 노드의 시작/종료를 추적합니다.
    LangGraph에서는 각 노드가 "chain"으로 취급됩니다.
    """
    
    def __init__(self):
        self.steps: List[TraceStep] = []
        self._pending_steps: Dict[str, TraceStep] = {}  # run_id -> TraceStep
        self._start_times: Dict[str, float] = {}  # run_id -> start_time
    
    def _extract_node_name(self, serialized: Dict[str, Any]) -> str:
        """serialized 객체에서 노드 이름 추출."""
        if not serialized:
            return "unknown_node"
            
        # LangGraph 노드의 이름 추출 시도 순서
        # 1. 직접 name 키
        if "name" in serialized and serialized["name"]:
            return str(serialized["name"])
        
        # 2. graph 메타데이터에서 이름
        if "graph" in serialized:
            graph = serialized["graph"]
            if isinstance(graph, dict) and "name" in graph:
                return str(graph["name"])
        
        # 3. id 키에서 추출
        if "id" in serialized:
            id_val = serialized["id"]
            if isinstance(id_val, (list, tuple)) and id_val:
                # 마지막 요소가 보통 노드 이름
                last = id_val[-1]
                if last and str(last) not in ("RunnableSequence", "RunnableLambda"):
                    return str(last)
            elif id_val:
                return str(id_val)
        
        # 4. kwargs에서 이름 추출 시도
        if "kwargs" in serialized:
            kwargs = serialized["kwargs"]
            if isinstance(kwargs, dict) and "name" in kwargs:
                return str(kwargs["name"])
        
        return "unknown_node"
    
    def _summarize_dict(self, data: Any, max_keys: int = 5) -> Dict[str, Any]:
        """dict를 요약 (핵심 키만 포함)."""
        # Pydantic 모델인 경우 dict로 변환
        if hasattr(data, "model_dump"):
            try:
                data = data.model_dump()
            except Exception:
                return {"type": type(data).__name__}
        elif hasattr(data, "dict"):
            try:
                data = data.dict()
            except Exception:
                return {"type": type(data).__name__}
        
        if not isinstance(data, dict):
            if data is None:
                return {}
            return {"value": str(data)[:100]}
        
        # 핵심 키 우선순위
        priority_keys = ["task_type", "owner", "repo", "health_score", "error", "status"]
        summary = {}
        
        try:
            # 우선순위 키 먼저
            for key in priority_keys:
                if key in data:
                    val = data[key]
                    if isinstance(val, (str, int, float, bool, type(None))):
                        summary[key] = val
                    else:
                        summary[key] = f"<{type(val).__name__}>"
            
            # 나머지 키 추가 (max_keys까지)
            for key in data:
                if len(summary) >= max_keys:
                    break
                if key not in summary:
                    val = data[key]
                    if isinstance(val, (str, int, float, bool, type(None))):
                        summary[key] = val
                    else:
                        summary[key] = f"<{type(val).__name__}>"
        except Exception as e:
            logger.debug(f"Error summarizing dict: {e}")
            return {"error": "failed to summarize"}
        
        return summary
    
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ) -> None:
        """체인(노드) 시작 시 호출."""
        try:
            node_name = self._extract_node_name(serialized or {})
            run_id_str = str(run_id)
            
            # 시작 시간 기록
            start_time = time.time()
            self._start_times[run_id_str] = start_time
            
            # TraceStep 생성
            step = TraceStep(
                node=node_name,
                status="started",
                timestamp=start_time,
                input_summary=self._summarize_dict(inputs),
            )
            self._pending_steps[run_id_str] = step
            
            logger.debug(f"[Trace] Node started: {node_name}")
        except Exception as e:
            logger.debug(f"[Trace] Error in on_chain_start: {e}")
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        **kwargs,
    ) -> None:
        """체인(노드) 종료 시 호출."""
        run_id_str = str(run_id)
        
        if run_id_str not in self._pending_steps:
            return
        
        step = self._pending_steps.pop(run_id_str)
        start_time = self._start_times.pop(run_id_str, step.timestamp)
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Step 업데이트
        step.status = "completed"
        step.duration_ms = round(duration_ms, 2)
        step.output_summary = self._summarize_dict(outputs)
        
        self.steps.append(step)
        logger.debug(f"[Trace] Node completed: {step.node} ({step.duration_ms:.1f}ms)")
    
    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        **kwargs,
    ) -> None:
        """체인(노드) 에러 시 호출."""
        run_id_str = str(run_id)
        
        if run_id_str not in self._pending_steps:
            return
        
        step = self._pending_steps.pop(run_id_str)
        start_time = self._start_times.pop(run_id_str, step.timestamp)
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Step 업데이트
        step.status = "error"
        step.duration_ms = round(duration_ms, 2)
        step.error_message = str(error)[:200]
        
        self.steps.append(step)
        logger.debug(f"[Trace] Node error: {step.node} - {error}")
    
    def get_trace(self) -> List[Dict[str, Any]]:
        """수집된 trace를 dict 리스트로 반환."""
        return [step.to_dict() for step in self.steps]
    
    def clear(self) -> None:
        """trace 초기화."""
        self.steps.clear()
        self._pending_steps.clear()
        self._start_times.clear()
