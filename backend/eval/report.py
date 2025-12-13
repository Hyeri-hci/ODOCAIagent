"""Markdown 및 CSV 리포트 생성."""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any, Dict, List

from backend.eval.schemas import EvalCase, EvalTrace, EvalMetrics, EvalSummary
from backend.eval.metrics import aggregate_metrics, compute_case_metrics

logger = logging.getLogger(__name__)


def generate_markdown_report(
    runs: Dict[str, List[EvalTrace]],
    cases: List[EvalCase],
    run_id: str = "",
) -> str:
    """모델별 비교 Markdown 리포트 생성.
    
    Args:
        runs: {model_id: [traces]} 형태
        cases: 평가 케이스 목록
        run_id: 실행 ID
    
    Returns:
        Markdown 문자열
    """
    lines = []
    
    # 헤더
    lines.append("# Supervisor 성능 평가 리포트")
    lines.append("")
    lines.append(f"**실행 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if run_id:
        lines.append(f"**Run ID**: `{run_id}`")
    lines.append(f"**총 케이스**: {len(cases)}개")
    lines.append(f"**평가 모델**: {', '.join(runs.keys())}")
    lines.append("")
    
    # 모델별 요약 테이블
    lines.append("## 모델별 성능 요약")
    lines.append("")
    lines.append("| 모델 | Plan Acc | Exec Succ | Helpfulness | Grounding | Parse OK | Latency (ms) | LLM Calls | Tokens | SubCalls |")
    lines.append("|------|----------|-----------|-------------|-----------|----------|--------------|-----------|--------|----------|")
    
    model_metrics: Dict[str, EvalMetrics] = {}
    
    for model_id, traces in runs.items():
        metrics = aggregate_metrics(traces, cases)
        model_metrics[model_id] = metrics
        eff = metrics.efficiency
        
        lines.append(
            f"| {model_id} "
            f"| {metrics.plan_accuracy:.1%} "
            f"| {metrics.exec_success_rate:.1%} "
            f"| {metrics.helpfulness:.1%} "
            f"| {metrics.grounding_coverage:.1%} "
            f"| {metrics.parse_success_rate:.1%} "
            f"| {eff.latency_avg_ms:.0f} "
            f"| {eff.llm_calls_avg:.1f} "
            f"| {eff.total_tokens_avg:.0f} "
            f"| {eff.sub_calls_avg:.1f} |"
        )
    
    lines.append("")
    
    # 실패 케이스 분석
    lines.append("## 실패 케이스 분석")
    lines.append("")
    
    case_map = {c.id: c for c in cases}
    
    for model_id, traces in runs.items():
        lines.append(f"### {model_id}")
        lines.append("")
        
        # Plan mismatch 케이스
        plan_mismatches = []
        helpfulness_failures = []
        grounding_issues = []
        parse_failures = []
        
        for trace in traces:
            case = case_map.get(trace.case_id)
            if not case:
                continue
            
            case_metrics = compute_case_metrics(trace, case)
            
            if case_metrics["plan_accuracy"] < 1.0:
                plan_mismatches.append((trace.case_id, trace.selected_plan, case.gold_plan))
            
            if case_metrics["helpfulness"] < 1.0:
                helpfulness_failures.append((trace.case_id, case_metrics["helpfulness"]))
            
            if case_metrics["grounding_coverage"] < 0.5:
                grounding_issues.append((trace.case_id, case_metrics["grounding_coverage"]))
            
            if case_metrics["parse_success"] < 1.0:
                parse_failures.append(trace.case_id)
        
        # Plan mismatch
        if plan_mismatches:
            lines.append("**Plan Mismatch (Top 5)**")
            lines.append("")
            for case_id, selected, gold in plan_mismatches[:5]:
                lines.append(f"- `{case_id}`: selected={selected}, gold={gold}")
            lines.append("")
        
        # Helpfulness 미충족
        if helpfulness_failures:
            lines.append("**Required Outputs 미충족 (Top 5)**")
            lines.append("")
            for case_id, score in sorted(helpfulness_failures, key=lambda x: x[1])[:5]:
                lines.append(f"- `{case_id}`: {score:.1%} 충족")
            lines.append("")
        
        # Grounding 부족
        if grounding_issues:
            lines.append("**Grounding Evidence 부족 (Top 5)**")
            lines.append("")
            for case_id, score in sorted(grounding_issues, key=lambda x: x[1])[:5]:
                lines.append(f"- `{case_id}`: {score:.1%} 커버리지")
            lines.append("")
        
        # Parse 실패
        if parse_failures:
            lines.append(f"**JSON Parse 실패**: {', '.join(f'`{c}`' for c in parse_failures[:10])}")
            lines.append("")
        
        if not any([plan_mismatches, helpfulness_failures, grounding_issues, parse_failures]):
            lines.append("모든 케이스 통과")
            lines.append("")
    
    # 모델 간 차이가 큰 케이스
    if len(runs) > 1:
        lines.append("## 모델 간 차이가 큰 케이스")
        lines.append("")
        lines.append("동일 케이스에서 모델별 점수 차이가 큰 항목:")
        lines.append("")
        
        # 케이스별 모델 간 지표 차이 계산
        divergent_cases = []
        
        for case in cases:
            model_scores = {}
            for model_id, traces in runs.items():
                case_traces = [t for t in traces if t.case_id == case.id]
                if case_traces:
                    avg_help = sum(compute_case_metrics(t, case)["helpfulness"] for t in case_traces) / len(case_traces)
                    model_scores[model_id] = avg_help
            
            if len(model_scores) > 1:
                scores = list(model_scores.values())
                diff = max(scores) - min(scores)
                if diff > 0.3:  # 30% 이상 차이
                    divergent_cases.append((case.id, diff, model_scores))
        
        if divergent_cases:
            divergent_cases.sort(key=lambda x: x[1], reverse=True)
            for case_id, diff, scores in divergent_cases[:10]:
                score_str = ", ".join(f"{m}={s:.1%}" for m, s in scores.items())
                lines.append(f"- `{case_id}`: 차이={diff:.1%} ({score_str})")
            lines.append("")
        else:
            lines.append("유의미한 차이가 있는 케이스 없음")
            lines.append("")
    
    # 푸터
    lines.append("---")
    lines.append("*Generated by ODOC Eval Harness*")
    
    return "\n".join(lines)


def generate_csv_report(
    runs: Dict[str, List[EvalTrace]],
    cases: List[EvalCase],
) -> str:
    """케이스별 상세 CSV 리포트 생성.
    
    Args:
        runs: {model_id: [traces]} 형태
        cases: 평가 케이스 목록
    
    Returns:
        CSV 문자열
    """
    output = io.StringIO()
    
    # 헤더 구성
    base_columns = ["case_id", "category", "priority", "repo"]
    metric_columns = [
        "plan_accuracy", "exec_success", "helpfulness", 
        "grounding_coverage", "parse_success", 
        "latency_ms", "llm_calls", "total_tokens", "sub_calls"
    ]
    
    # 모델별 컬럼 생성
    model_ids = list(runs.keys())
    header = base_columns.copy()
    for model_id in model_ids:
        for metric in metric_columns:
            header.append(f"{model_id}_{metric}")
    
    writer = csv.DictWriter(output, fieldnames=header)
    writer.writeheader()
    
    case_map = {c.id: c for c in cases}
    
    # 케이스별 행 생성
    for case in cases:
        row = {
            "case_id": case.id,
            "category": case.category,
            "priority": case.priority,
            "repo": case.repo,
        }
        
        for model_id in model_ids:
            traces = [t for t in runs.get(model_id, []) if t.case_id == case.id]
            
            if traces:
                # 여러 repeat의 평균
                metrics_list = [compute_case_metrics(t, case) for t in traces]
                
                for metric in metric_columns:
                    values = [m[metric] for m in metrics_list]
                    avg_value = sum(values) / len(values)
                    row[f"{model_id}_{metric}"] = round(avg_value, 4)
            else:
                for metric in metric_columns:
                    row[f"{model_id}_{metric}"] = ""
        
        writer.writerow(row)
    
    return output.getvalue()


def generate_summary_json(
    runs: Dict[str, List[EvalTrace]],
    cases: List[EvalCase],
    run_id: str,
) -> Dict[str, Any]:
    """평가 요약 JSON 생성.
    
    Returns:
        요약 데이터 dict
    """
    summaries = []
    
    for model_id, traces in runs.items():
        metrics = aggregate_metrics(traces, cases)
        
        failed_ids = []
        case_map = {c.id: c for c in cases}
        for trace in traces:
            case = case_map.get(trace.case_id)
            if case:
                case_metrics = compute_case_metrics(trace, case)
                if case_metrics["helpfulness"] < 1.0 or trace.error:
                    failed_ids.append(trace.case_id)
        
        summary = EvalSummary(
            model_id=model_id,
            run_id=run_id,
            total_cases=len(cases),
            completed_cases=len(traces),
            failed_cases=len(set(failed_ids)),
            metrics=metrics,
            failed_case_ids=list(set(failed_ids)),
        )
        summaries.append(summary.to_dict())
    
    return {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(cases),
        "models": summaries,
    }
