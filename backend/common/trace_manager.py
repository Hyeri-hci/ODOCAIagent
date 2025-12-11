"""
실행 트레이스 관리
디버깅 및 로깅을 위한 상세 실행 기록
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import json
import logging

logger = logging.getLogger(__name__)


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
