"""Observability 도구 - 실행 추적 및 상태 관리."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """실행 상태."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolExecution:
    """단일 도구 실행 기록."""
    tool_name: str
    agent: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    input_params: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "agent": self.agent,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "input_params": self.input_params,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class ToolExecutionTracker:
    """
    도구 실행 추적기.
    
    Security Agent의 ReActExecutor에서 사용된 패턴을 적용하여
    모든 도구 실행을 추적하고 관찰 가능성을 제공합니다.
    """
    
    def __init__(self, session_id: str = None):
        """ToolExecutionTracker 초기화."""
        self.session_id = session_id or f"session_{int(time.time())}"
        self.executions: List[ToolExecution] = []
        self.current_execution: Optional[ToolExecution] = None
        self.start_time = datetime.now()
        
    def start_execution(
        self,
        tool_name: str,
        agent: str,
        input_params: Dict[str, Any] = None,
    ) -> ToolExecution:
        """
        도구 실행 시작 기록.
        
        Args:
            tool_name: 도구 이름
            agent: 실행 에이전트
            input_params: 입력 파라미터
            
        Returns:
            생성된 ToolExecution 객체
        """
        execution = ToolExecution(
            tool_name=tool_name,
            agent=agent,
            input_params=input_params or {},
            status=ExecutionStatus.RUNNING,
        )
        self.current_execution = execution
        self.executions.append(execution)
        
        logger.info(f"[{self.session_id}] Started: {tool_name} (agent={agent})")
        return execution
    
    def end_execution(
        self,
        output: Any = None,
        error: Optional[str] = None,
    ) -> Optional[ToolExecution]:
        """
        현재 도구 실행 종료 기록.
        
        Args:
            output: 실행 결과
            error: 에러 메시지 (실패 시)
            
        Returns:
            종료된 ToolExecution 객체
        """
        if not self.current_execution:
            logger.warning("No current execution to end")
            return None
            
        execution = self.current_execution
        execution.end_time = datetime.now()
        execution.duration_ms = int((execution.end_time - execution.start_time).total_seconds() * 1000)
        
        if error:
            execution.status = ExecutionStatus.FAILED
            execution.error = error
            logger.error(f"[{self.session_id}] Failed: {execution.tool_name} - {error}")
        else:
            execution.status = ExecutionStatus.SUCCESS
            execution.output = output
            logger.info(f"[{self.session_id}] Completed: {execution.tool_name} ({execution.duration_ms}ms)")
        
        self.current_execution = None
        return execution
    
    def skip_execution(self, tool_name: str, agent: str, reason: str = "") -> ToolExecution:
        """
        도구 실행 스킵 기록.
        
        Args:
            tool_name: 도구 이름
            agent: 에이전트
            reason: 스킵 사유
            
        Returns:
            생성된 ToolExecution 객체
        """
        execution = ToolExecution(
            tool_name=tool_name,
            agent=agent,
            status=ExecutionStatus.SKIPPED,
            error=reason,
            end_time=datetime.now(),
        )
        self.executions.append(execution)
        
        logger.info(f"[{self.session_id}] Skipped: {tool_name} - {reason}")
        return execution
    
    def get_summary(self) -> Dict[str, Any]:
        """
        실행 요약 반환.
        
        Returns:
            실행 요약 딕셔너리
        """
        total = len(self.executions)
        success = sum(1 for e in self.executions if e.status == ExecutionStatus.SUCCESS)
        failed = sum(1 for e in self.executions if e.status == ExecutionStatus.FAILED)
        skipped = sum(1 for e in self.executions if e.status == ExecutionStatus.SKIPPED)
        
        total_duration = sum(e.duration_ms for e in self.executions)
        
        return {
            "session_id": self.session_id,
            "total_executions": total,
            "success_count": success,
            "failed_count": failed,
            "skipped_count": skipped,
            "total_duration_ms": total_duration,
            "start_time": self.start_time.isoformat(),
            "executions": [e.to_dict() for e in self.executions],
        }
    
    def get_failed_executions(self) -> List[ToolExecution]:
        """실패한 실행 목록 반환."""
        return [e for e in self.executions if e.status == ExecutionStatus.FAILED]
    
    def get_execution_by_agent(self, agent: str) -> List[ToolExecution]:
        """특정 에이전트의 실행 목록 반환."""
        return [e for e in self.executions if e.agent == agent]


# 상태 업데이트 헬퍼 함수
def update_thought(state_updates: Dict[str, Any], thought: str) -> Dict[str, Any]:
    """
    상태에 thought 추가.
    
    Args:
        state_updates: 현재 상태 업데이트 딕셔너리
        thought: 추가할 thought
        
    Returns:
        업데이트된 딕셔너리
    """
    thoughts = state_updates.get("thoughts", [])
    thoughts.append({
        "content": thought,
        "timestamp": datetime.now().isoformat(),
    })
    state_updates["thoughts"] = thoughts
    return state_updates


def update_action(state_updates: Dict[str, Any], action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    상태에 action 추가.
    
    Args:
        state_updates: 현재 상태 업데이트 딕셔너리
        action: 실행할 action
        params: action 파라미터
        
    Returns:
        업데이트된 딕셔너리
    """
    actions = state_updates.get("actions", [])
    actions.append({
        "action": action,
        "params": params or {},
        "timestamp": datetime.now().isoformat(),
    })
    state_updates["actions"] = actions
    return state_updates


def update_observation(state_updates: Dict[str, Any], observation: str, source: str = "") -> Dict[str, Any]:
    """
    상태에 observation 추가.
    
    Args:
        state_updates: 현재 상태 업데이트 딕셔너리
        observation: 관찰 결과
        source: 관찰 소스
        
    Returns:
        업데이트된 딕셔너리
    """
    observations = state_updates.get("observations", [])
    observations.append({
        "content": observation,
        "source": source,
        "timestamp": datetime.now().isoformat(),
    })
    state_updates["observations"] = observations
    return state_updates


def update_error(state_updates: Dict[str, Any], error: str, recoverable: bool = True) -> Dict[str, Any]:
    """
    상태에 error 추가.
    
    Args:
        state_updates: 현재 상태 업데이트 딕셔너리
        error: 에러 메시지
        recoverable: 복구 가능 여부
        
    Returns:
        업데이트된 딕셔너리
    """
    errors = state_updates.get("errors", [])
    errors.append({
        "error": error,
        "recoverable": recoverable,
        "timestamp": datetime.now().isoformat(),
    })
    state_updates["errors"] = errors
    return state_updates


def merge_task_results(current: Dict[str, Any], new_result: Dict[str, Any], agent: str) -> Dict[str, Any]:
    """
    task_results에 새 결과 병합.
    
    Args:
        current: 현재 task_results
        new_result: 새로운 결과
        agent: 에이전트 이름
        
    Returns:
        병합된 task_results
    """
    merged = dict(current) if current else {}
    merged[agent] = new_result
    return merged


def create_state_update(
    step: int,
    next_node: str = None,
    task_results: Dict[str, Any] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    표준화된 상태 업데이트 딕셔너리 생성.
    
    Args:
        step: 현재 스텝
        next_node: 다음 노드 (선택)
        task_results: 작업 결과 (선택)
        **kwargs: 추가 필드
        
    Returns:
        상태 업데이트 딕셔너리
    """
    update = {"step": step + 1}
    
    if next_node:
        update["next_node_override"] = next_node
    if task_results:
        update["task_results"] = task_results
        
    update.update(kwargs)
    return update
