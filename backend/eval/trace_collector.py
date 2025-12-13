"""Supervisor 실행 시 평가용 trace를 수집하는 콜렉터."""
from __future__ import annotations

import time
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextvars import ContextVar

from backend.eval.schemas import (
    EvalTrace, CallRecord, UsageStats, StructuredFinalAnswer
)

logger = logging.getLogger(__name__)

# 현재 활성화된 trace collector (컨텍스트 변수)
_active_collector: ContextVar[Optional["EvalTraceCollector"]] = ContextVar(
    "_active_collector", default=None
)


def get_active_collector() -> Optional["EvalTraceCollector"]:
    """현재 활성화된 trace collector 반환."""
    return _active_collector.get()


def set_active_collector(collector: Optional["EvalTraceCollector"]) -> None:
    """활성 trace collector 설정."""
    _active_collector.set(collector)


class EvalTraceCollector:
    """평가용 Supervisor 실행 추적 콜렉터.
    
    Supervisor 실행 중 plan 선택, 에이전트 호출, 최종 답변을 수집.
    
    Usage:
        collector = EvalTraceCollector("D01", "kanana2", "run_123")
        with collector:
            result = run_supervisor_diagnosis(...)
        trace = collector.finalize()
    """
    
    def __init__(
        self,
        case_id: str,
        model_id: str,
        run_id: str,
        repeat_idx: int = 0,
    ):
        self.case_id = case_id
        self.model_id = model_id
        self.run_id = run_id
        self.repeat_idx = repeat_idx
        
        self._started_at: Optional[datetime] = None
        self._ended_at: Optional[datetime] = None
        self._selected_plan: List[Dict[str, str]] = []
        self._calls: List[CallRecord] = []
        self._final_answer: Optional[StructuredFinalAnswer] = None
        self._usage = UsageStats()
        self._error: Optional[str] = None
        
        # 에이전트 호출 시작 시간 추적
        self._call_start_times: Dict[str, float] = {}
    
    def __enter__(self):
        """컨텍스트 시작: collector 활성화."""
        self._started_at = datetime.now()
        set_active_collector(self)
        logger.debug(f"[Trace] Collector 시작: {self.case_id}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료: collector 비활성화."""
        self._ended_at = datetime.now()
        set_active_collector(None)
        
        if exc_val:
            self._error = str(exc_val)
            logger.warning(f"[Trace] Collector 종료 (에러): {exc_val}")
        else:
            logger.debug(f"[Trace] Collector 종료: {self.case_id}")
        
        return False  # 예외 전파
    
    def on_plan_selected(self, plan: List[Dict[str, Any]]) -> None:
        """Planner가 선택한 plan 기록.
        
        Args:
            plan: 선택된 실행 계획
                  [{"agent": "diagnosis", "mode": "FULL"}, ...]
        """
        self._selected_plan = []
        for step in plan:
            if isinstance(step, dict):
                self._selected_plan.append({
                    "agent": step.get("agent", "unknown"),
                    "mode": step.get("mode", "auto"),
                })
        logger.debug(f"[Trace] Plan 선택됨: {self._selected_plan}")
    
    def on_agent_call_start(self, agent: str, mode: str) -> None:
        """서브 에이전트 호출 시작.
        
        Args:
            agent: 에이전트 이름 (diagnosis, security, etc.)
            mode: 실행 모드 (FAST, FULL, auto)
        """
        key = f"{agent}_{mode}"
        self._call_start_times[key] = time.time()
        logger.debug(f"[Trace] Agent 시작: {agent} ({mode})")
    
    def on_agent_call_end(
        self,
        agent: str,
        mode: str,
        ok: bool,
        error: Optional[str] = None,
    ) -> None:
        """서브 에이전트 호출 완료.
        
        Args:
            agent: 에이전트 이름
            mode: 실행 모드
            ok: 성공 여부
            error: 에러 메시지 (실패 시)
        """
        key = f"{agent}_{mode}"
        start_time = self._call_start_times.pop(key, None)
        
        latency_ms = 0.0
        if start_time:
            latency_ms = (time.time() - start_time) * 1000
        
        record = CallRecord(
            agent=agent,
            mode=mode,
            ok=ok,
            latency_ms=round(latency_ms, 2),
            error=error,
        )
        self._calls.append(record)
        
        if ok:
            logger.debug(f"[Trace] Agent 완료: {agent} ({latency_ms:.0f}ms)")
        else:
            logger.warning(f"[Trace] Agent 실패: {agent} - {error}")
    
    def on_llm_call(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """LLM 호출 통계 업데이트."""
        self._usage.llm_calls += 1
        self._usage.prompt_tokens += prompt_tokens
        self._usage.completion_tokens += completion_tokens
        self._usage.total_tokens += prompt_tokens + completion_tokens
    
    def on_finalize(self, final_answer: Dict[str, Any]) -> None:
        """최종 답변 기록.
        
        Args:
            final_answer: 구조화된 최종 답변 (StructuredFinalAnswer 형태)
        """
        try:
            self._final_answer = StructuredFinalAnswer.from_dict(final_answer)
            logger.debug(f"[Trace] Final answer 기록됨 (type={self._final_answer.task_type})")
        except Exception as e:
            # JSON 구조가 아닌 경우 폴백
            self._final_answer = StructuredFinalAnswer.from_text_fallback(str(final_answer))
            logger.warning(f"[Trace] Final answer 파싱 실패, 텍스트 폴백: {e}")
    
    def on_finalize_text(self, text: str) -> None:
        """텍스트 형태의 최종 답변 기록 (파싱 실패로 처리)."""
        self._final_answer = StructuredFinalAnswer.from_text_fallback(text)
        logger.debug("[Trace] Final answer (텍스트)")
    
    def finalize(self) -> EvalTrace:
        """수집된 정보로 EvalTrace 생성."""
        if not self._ended_at:
            self._ended_at = datetime.now()
        
        latency_ms = 0.0
        if self._started_at and self._ended_at:
            latency_ms = (self._ended_at - self._started_at).total_seconds() * 1000
        
        return EvalTrace(
            case_id=self.case_id,
            model_id=self.model_id,
            run_id=self.run_id,
            repeat_idx=self.repeat_idx,
            started_at=self._started_at.isoformat() if self._started_at else "",
            ended_at=self._ended_at.isoformat() if self._ended_at else "",
            latency_ms=round(latency_ms, 2),
            selected_plan=self._selected_plan,
            calls=self._calls,
            final_answer=self._final_answer,
            usage=self._usage,
            error=self._error,
        )


# === Hook 함수들 (Supervisor 코드에서 호출) ===

def trace_plan_selected(plan: List[Dict[str, Any]]) -> None:
    """Supervisor에서 plan 선택 시 호출."""
    collector = get_active_collector()
    if collector:
        collector.on_plan_selected(plan)


def trace_agent_start(agent: str, mode: str = "auto") -> None:
    """Supervisor에서 에이전트 호출 시작 시 호출."""
    collector = get_active_collector()
    if collector:
        collector.on_agent_call_start(agent, mode)


def trace_agent_end(agent: str, mode: str = "auto", ok: bool = True, error: str = None) -> None:
    """Supervisor에서 에이전트 호출 완료 시 호출."""
    collector = get_active_collector()
    if collector:
        collector.on_agent_call_end(agent, mode, ok, error)


def trace_llm_call(prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    """LLM 호출 시 통계 업데이트."""
    collector = get_active_collector()
    if collector:
        collector.on_llm_call(prompt_tokens, completion_tokens)


def trace_finalize(final_answer: Dict[str, Any]) -> None:
    """최종 답변 기록."""
    collector = get_active_collector()
    if collector:
        collector.on_finalize(final_answer)


# === LangChain 콜백 핸들러 (ChatOpenAI 호출 추적) ===

class EvalLLMCallbackHandler:
    """LangChain LLM 호출 추적 콜백 핸들러.
    
    모든 ChatOpenAI 호출을 추적하여 trace에 기록.
    LangSmith 또는 config.callbacks와 함께 사용.
    
    Usage:
        from langchain_openai import ChatOpenAI
        
        handler = get_eval_callback_handler()
        llm = ChatOpenAI(..., callbacks=[handler] if handler else [])
    """
    
    def __init__(self):
        self.call_count = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
    
    def on_llm_start(self, *args, **kwargs):
        """LLM 호출 시작."""
        pass
    
    def on_llm_end(self, response, **kwargs):
        """LLM 호출 완료 - 토큰 사용량 수집."""
        self.call_count += 1
        
        # 토큰 사용량 추출 (구조가 다양할 수 있음)
        prompt_tokens = 0
        completion_tokens = 0
        
        try:
            # LangChain AIMessage의 usage_metadata
            if hasattr(response, "generations") and response.generations:
                for gen_list in response.generations:
                    for gen in gen_list:
                        if hasattr(gen, "message"):
                            msg = gen.message
                            usage = getattr(msg, "usage_metadata", None) or {}
                            if isinstance(usage, dict):
                                prompt_tokens += usage.get("input_tokens", 0)
                                completion_tokens += usage.get("output_tokens", 0)
            
            # response_metadata 방식
            if hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("token_usage", {})
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                    completion_tokens = usage.get("completion_tokens", completion_tokens)
        except Exception:
            pass
        
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        
        # trace collector에 기록
        trace_llm_call(prompt_tokens, completion_tokens)
    
    def on_llm_error(self, error, **kwargs):
        """LLM 에러."""
        pass


def get_eval_callback_handler() -> Optional[EvalLLMCallbackHandler]:
    """활성 trace collector가 있으면 콜백 핸들러 반환."""
    collector = get_active_collector()
    if collector:
        return EvalLLMCallbackHandler()
    return None

