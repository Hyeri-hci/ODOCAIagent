"""평가 하네스 데이터 모델 정의."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


@dataclass
class CallRecord:
    """서브 에이전트 호출 기록."""
    agent: str
    mode: str
    ok: bool
    latency_ms: float
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class UsageStats:
    """LLM 사용량 통계."""
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EfficiencyStats:
    """효율성 지표 통계."""
    latency_avg_ms: float = 0.0
    latency_median_ms: float = 0.0
    latency_std_ms: float = 0.0
    llm_calls_avg: float = 0.0
    total_tokens_avg: float = 0.0
    sub_calls_avg: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalCase:
    """평가 케이스 정의."""
    id: str
    repo: str  # "owner/repo@ref" 형태
    user_query: str
    gold_plan: List[Dict[str, str]]  # [{"agent": "diagnosis", "mode": "FULL"}]
    required_outputs: List[str]  # JSONPath 형태: ["key_metrics.health_score", "top_reasons"]
    priority: str = "P0"  # P0 = 필수, P1 = 분별력 향상용
    category: str = "diagnosis"  # diagnosis, onboarding, compare, security, multi_intent, escalation, recovery
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalCase":
        return cls(
            id=data["id"],
            repo=data["repo"],
            user_query=data["user_query"],
            gold_plan=data.get("gold_plan", []),
            required_outputs=data.get("required_outputs", []),
            priority=data.get("priority", "P0"),
            category=data.get("category", "diagnosis"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StructuredFinalAnswer:
    """평가용 구조화된 최종 답변.
    
    Supervisor가 평가 모드에서 출력해야 하는 JSON 구조.
    """
    task_type: str  # diagnosis, recommend, compare, explain, security, onboarding
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    top_reasons: List[Dict[str, Any]] = field(default_factory=list)  # [{"claim": "...", "evidence": [...]}]
    next_actions: List[Dict[str, Any]] = field(default_factory=list)  # [{"action": "...", "priority": "P0", "evidence": [...]}]
    plan_used: List[Dict[str, str]] = field(default_factory=list)  # [{"agent": "diagnosis", "mode": "FULL"}]
    parse_success: bool = True
    raw_text: Optional[str] = None  # JSON 파싱 실패 시 원본 텍스트
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredFinalAnswer":
        return cls(
            task_type=data.get("task_type", "unknown"),
            key_metrics=data.get("key_metrics", {}),
            top_reasons=data.get("top_reasons", []),
            next_actions=data.get("next_actions", []),
            plan_used=data.get("plan_used", []),
            parse_success=data.get("parse_success", True),
            raw_text=data.get("raw_text"),
        )
    
    @classmethod
    def from_text_fallback(cls, text: str) -> "StructuredFinalAnswer":
        """JSON 파싱 실패 시 텍스트 폴백."""
        return cls(
            task_type="unknown",
            parse_success=False,
            raw_text=text,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if result.get("raw_text") is None:
            del result["raw_text"]
        return result


@dataclass
class EvalTrace:
    """단일 평가 실행 추적 기록."""
    case_id: str
    model_id: str
    run_id: str
    repeat_idx: int = 0
    started_at: str = ""
    ended_at: str = ""
    latency_ms: float = 0.0
    selected_plan: List[Dict[str, str]] = field(default_factory=list)
    calls: List[CallRecord] = field(default_factory=list)
    final_answer: Optional[StructuredFinalAnswer] = None
    usage: UsageStats = field(default_factory=UsageStats)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "case_id": self.case_id,
            "model_id": self.model_id,
            "run_id": self.run_id,
            "repeat_idx": self.repeat_idx,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "latency_ms": self.latency_ms,
            "selected_plan": self.selected_plan,
            "calls": [c.to_dict() for c in self.calls],
            "final_answer": self.final_answer.to_dict() if self.final_answer else None,
            "usage": self.usage.to_dict(),
        }
        if self.error:
            result["error"] = self.error
        return result
    
    def save(self, path: str) -> None:
        """Trace를 JSON 파일로 저장."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "EvalTrace":
        """JSON 파일에서 Trace 로드."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        calls = [CallRecord(**c) for c in data.get("calls", [])]
        usage = UsageStats(**data.get("usage", {}))
        final_answer = None
        if data.get("final_answer"):
            final_answer = StructuredFinalAnswer.from_dict(data["final_answer"])
        
        return cls(
            case_id=data["case_id"],
            model_id=data["model_id"],
            run_id=data["run_id"],
            repeat_idx=data.get("repeat_idx", 0),
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at", ""),
            latency_ms=data.get("latency_ms", 0.0),
            selected_plan=data.get("selected_plan", []),
            calls=calls,
            final_answer=final_answer,
            usage=usage,
            error=data.get("error"),
        )


@dataclass
class EvalMetrics:
    """평가 지표 결과."""
    plan_accuracy: float = 0.0  # selected_plan vs gold_plan
    exec_success_rate: float = 0.0  # calls 성공률
    helpfulness: float = 0.0  # required_outputs 충족률
    grounding_coverage: float = 0.0  # evidence 존재 비율
    efficiency: EfficiencyStats = field(default_factory=EfficiencyStats)
    parse_success_rate: float = 1.0  # JSON 파싱 성공률
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_accuracy": round(self.plan_accuracy, 4),
            "exec_success_rate": round(self.exec_success_rate, 4),
            "helpfulness": round(self.helpfulness, 4),
            "grounding_coverage": round(self.grounding_coverage, 4),
            "parse_success_rate": round(self.parse_success_rate, 4),
            "efficiency": self.efficiency.to_dict(),
        }


@dataclass
class EvalSummary:
    """모델별 평가 요약."""
    model_id: str
    run_id: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    metrics: EvalMetrics
    failed_case_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "run_id": self.run_id,
            "total_cases": self.total_cases,
            "completed_cases": self.completed_cases,
            "failed_cases": self.failed_cases,
            "metrics": self.metrics.to_dict(),
            "failed_case_ids": self.failed_case_ids,
        }
