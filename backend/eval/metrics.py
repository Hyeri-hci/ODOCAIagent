"""평가 지표 계산 모듈."""
from __future__ import annotations

import re
import logging
import statistics
from typing import Any, Dict, List, Optional, Tuple

from backend.eval.schemas import (
    EvalCase, EvalTrace, EvalMetrics, EfficiencyStats, StructuredFinalAnswer
)

logger = logging.getLogger(__name__)


def calc_plan_accuracy(trace: EvalTrace, case: EvalCase) -> float:
    """Plan 정확도 계산: 실제 실행 plan vs gold_plan.
    
    우선순위:
    1. selected_plan (planning 노드에서 기록)
    2. final_answer.plan_used (결과에 포함된 plan)
    3. calls에서 재구성 (실제 실행된 agent 목록)
    
    Returns:
        0.0 ~ 1.0 점수
    """
    gold = case.gold_plan
    
    if not gold:
        # gold_plan이 없으면 평가 불가 → 1.0 (패널티 없음)
        return 1.0
    
    # 실제 plan 결정: selected_plan > plan_used > calls
    selected = trace.selected_plan
    
    if not selected:
        # selected_plan이 비어있으면 plan_used 사용
        if trace.final_answer and trace.final_answer.plan_used:
            selected = trace.final_answer.plan_used
        elif trace.calls:
            # calls에서 재구성
            selected = [{"agent": c.agent, "mode": c.mode} for c in trace.calls]
    
    if not selected:
        # 여전히 없으면 0점
        return 0.0
    
    # agent만 비교 (mode는 무시) - 더 유연한 비교
    gold_agents = [g.get("agent", "").lower() for g in gold]
    selected_agents = [s.get("agent", "").lower() for s in selected]
    
    # 순서 무관, 집합 비교
    gold_set = set(gold_agents)
    selected_set = set(selected_agents)
    
    if gold_set == selected_set:
        return 1.0
    
    # gold의 모든 agent가 selected에 포함되면 0.8
    if gold_set.issubset(selected_set):
        return 0.8
    
    # 부분 일치
    intersection = gold_set & selected_set
    if intersection:
        return len(intersection) / len(gold_set)
    
    return 0.0


def calc_plan_accuracy_partial(trace: EvalTrace, case: EvalCase) -> float:
    """Plan 정확도 (부분 점수 버전).
    
    - agent만 맞으면 0.5점
    - agent + mode 맞으면 1.0점
    - 순서 무시, 집합 비교
    
    Returns:
        0.0 ~ 1.0 점수
    """
    selected = trace.selected_plan
    gold = case.gold_plan
    
    if not gold:
        return 1.0
    if not selected:
        return 0.0
    
    # 집합 비교
    gold_set = {(g.get("agent", "").lower(), g.get("mode", "auto").upper()) for g in gold}
    selected_set = {(s.get("agent", "").lower(), s.get("mode", "auto").upper()) for s in selected}
    
    # agent만 비교
    gold_agents = {g[0] for g in gold_set}
    selected_agents = {s[0] for s in selected_set}
    
    # 완전 일치
    if gold_set == selected_set:
        return 1.0
    
    # agent만 일치
    if gold_agents == selected_agents:
        return 0.7
    
    # 부분 일치
    intersection = gold_agents & selected_agents
    if intersection:
        return 0.3 * len(intersection) / len(gold_agents)
    
    return 0.0


def calc_exec_success(trace: EvalTrace) -> float:
    """실행 성공률: calls 중 ok=True 비율.
    
    Returns:
        0.0 ~ 1.0 점수
    """
    if not trace.calls:
        return 1.0  # 호출이 없으면 성공으로 간주
    
    success_count = sum(1 for c in trace.calls if c.ok)
    return success_count / len(trace.calls)


def _resolve_jsonpath(data: Any, path: str) -> Tuple[bool, Any]:
    """간단한 JSONPath 스타일 경로 해석.
    
    지원 패턴:
    - "key_metrics.health_score" → data["key_metrics"]["health_score"]
    - "top_reasons" → data["top_reasons"]
    - "top_reasons[].evidence" → data["top_reasons"][*]["evidence"] (하나라도 존재 시 True)
    
    Returns:
        (존재여부, 값)
    """
    if not data or not path:
        return False, None
    
    # 배열 내 필드 패턴: "top_reasons[].evidence"
    array_pattern = re.match(r"^(\w+)\[\]\.(\w+)$", path)
    if array_pattern:
        array_key = array_pattern.group(1)
        field_key = array_pattern.group(2)
        
        if not isinstance(data, dict) or array_key not in data:
            return False, None
        
        array = data[array_key]
        if not isinstance(array, list):
            return False, None
        
        # 하나라도 해당 필드가 있으면 True
        for item in array:
            if isinstance(item, dict) and field_key in item:
                value = item[field_key]
                # 빈 값 체크
                if value and (not isinstance(value, (list, str)) or len(value) > 0):
                    return True, value
        
        return False, None
    
    # 일반 경로: "key_metrics.health_score"
    parts = path.split(".")
    current = data
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    
    # 값이 None이 아니고 비어있지 않은지 확인
    if current is None:
        return False, None
    if isinstance(current, (list, str, dict)) and len(current) == 0:
        return False, None
    
    return True, current


def calc_helpfulness(trace: EvalTrace, case: EvalCase) -> float:
    """필수 출력 충족률 (Helpfulness).
    
    required_outputs의 각 경로가 final_answer에 존재하는지 확인.
    
    Returns:
        0.0 ~ 1.0 점수
    """
    required = case.required_outputs
    if not required:
        return 1.0
    
    if not trace.final_answer:
        return 0.0
    
    # final_answer를 dict로 변환
    answer_dict = trace.final_answer.to_dict()
    
    fulfilled = 0
    for path in required:
        exists, _ = _resolve_jsonpath(answer_dict, path)
        if exists:
            fulfilled += 1
    
    return fulfilled / len(required)


def calc_grounding_coverage(trace: EvalTrace) -> float:
    """근거 커버리지 (Grounding Coverage).
    
    top_reasons[].evidence, next_actions[].evidence 존재 비율.
    
    Note: parse_success=False면 0 반환 (측정 불가).
    Note: top_reasons/next_actions가 모두 비어있으면 0 반환 (100% 방지).
    
    Returns:
        0.0 ~ 1.0 점수
    """
    if not trace.final_answer:
        return 0.0
    
    answer = trace.final_answer
    
    # parse_success=False면 grounding 측정 불가 → 0
    if not answer.parse_success:
        return 0.0
    
    total_items = 0
    items_with_evidence = 0
    
    # top_reasons 체크
    for reason in answer.top_reasons:
        total_items += 1
        evidence = reason.get("evidence", [])
        if evidence and isinstance(evidence, list) and len(evidence) > 0:
            # 빈 문자열/너무 짧은 evidence 필터링
            valid_evidence = [e for e in evidence if isinstance(e, str) and len(e.strip()) > 5]
            if valid_evidence:
                items_with_evidence += 1
    
    # next_actions 체크
    for action in answer.next_actions:
        total_items += 1
        evidence = action.get("evidence", [])
        if evidence and isinstance(evidence, list) and len(evidence) > 0:
            valid_evidence = [e for e in evidence if isinstance(e, str) and len(e.strip()) > 5]
            if valid_evidence:
                items_with_evidence += 1
    
    # 평가 항목 없음 → 0 (100% 방지)
    if total_items == 0:
        return 0.0
    
    return items_with_evidence / total_items


def calc_parse_success_rate(traces: List[EvalTrace]) -> float:
    """JSON 파싱 성공률."""
    if not traces:
        return 1.0
    
    success = sum(1 for t in traces if t.final_answer and t.final_answer.parse_success)
    return success / len(traces)


def calc_efficiency(traces: List[EvalTrace]) -> EfficiencyStats:
    """효율성 지표 계산.
    
    latency_ms, llm_calls, total_tokens, sub_calls 집계.
    
    Returns:
        EfficiencyStats 객체
    """
    if not traces:
        return EfficiencyStats()
    
    latencies = [t.latency_ms for t in traces if t.latency_ms > 0]
    llm_calls = [t.usage.llm_calls for t in traces]
    tokens = [t.usage.total_tokens for t in traces]
    sub_calls = [len(t.calls) for t in traces]
    
    def safe_avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0
    
    def safe_median(lst: List[float]) -> float:
        return statistics.median(lst) if lst else 0.0
    
    def safe_stdev(lst: List[float]) -> float:
        return statistics.stdev(lst) if len(lst) > 1 else 0.0
    
    return EfficiencyStats(
        latency_avg_ms=round(safe_avg(latencies), 2),
        latency_median_ms=round(safe_median(latencies), 2),
        latency_std_ms=round(safe_stdev(latencies), 2),
        llm_calls_avg=round(safe_avg(llm_calls), 2),
        total_tokens_avg=round(safe_avg(tokens), 2),
        sub_calls_avg=round(safe_avg(sub_calls), 2),
    )


def aggregate_metrics(
    traces: List[EvalTrace],
    cases: List[EvalCase],
) -> EvalMetrics:
    """전체 케이스에 대한 지표 집계.
    
    Args:
        traces: 실행된 trace 목록
        cases: 평가 케이스 목록
    
    Returns:
        EvalMetrics 객체
    """
    if not traces:
        return EvalMetrics()
    
    # case_id → case 매핑
    case_map = {c.id: c for c in cases}
    
    plan_scores = []
    exec_scores = []
    help_scores = []
    ground_scores = []
    
    for trace in traces:
        case = case_map.get(trace.case_id)
        if not case:
            logger.warning(f"케이스를 찾을 수 없음: {trace.case_id}")
            continue
        
        plan_scores.append(calc_plan_accuracy(trace, case))
        exec_scores.append(calc_exec_success(trace))
        help_scores.append(calc_helpfulness(trace, case))
        ground_scores.append(calc_grounding_coverage(trace))
    
    def safe_avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0
    
    return EvalMetrics(
        plan_accuracy=safe_avg(plan_scores),
        exec_success_rate=safe_avg(exec_scores),
        helpfulness=safe_avg(help_scores),
        grounding_coverage=safe_avg(ground_scores),
        efficiency=calc_efficiency(traces),
        parse_success_rate=calc_parse_success_rate(traces),
    )


def compute_case_metrics(
    trace: EvalTrace,
    case: EvalCase,
) -> Dict[str, float]:
    """단일 케이스에 대한 지표 계산.
    
    Returns:
        {"plan_accuracy": 0.0, "exec_success": 1.0, ...}
    """
    return {
        "plan_accuracy": calc_plan_accuracy(trace, case),
        "plan_accuracy_partial": calc_plan_accuracy_partial(trace, case),
        "exec_success": calc_exec_success(trace),
        "helpfulness": calc_helpfulness(trace, case),
        "grounding_coverage": calc_grounding_coverage(trace),
        "parse_success": 1.0 if trace.final_answer and trace.final_answer.parse_success else 0.0,
        "latency_ms": trace.latency_ms,
        "llm_calls": trace.usage.llm_calls,
        "total_tokens": trace.usage.total_tokens,
        "sub_calls": len(trace.calls),
    }
