"""평가 실행 CLI."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.eval.schemas import EvalCase, EvalTrace
from backend.eval.model_loader import EvalLLMContext, list_available_models
from backend.eval.trace_collector import EvalTraceCollector
from backend.eval.metrics import aggregate_metrics
from backend.eval.report import (
    generate_markdown_report,
    generate_csv_report,
    generate_summary_json,
)

logger = logging.getLogger(__name__)


def load_cases(cases_path: str) -> List[EvalCase]:
    """JSONL 파일에서 평가 케이스 로드."""
    cases = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
                cases.append(EvalCase.from_dict(data))
            except json.JSONDecodeError as e:
                logger.warning(f"케이스 파싱 실패 (line {line_num}): {e}")
    
    logger.info(f"케이스 로드 완료: {len(cases)}개")
    return cases


def parse_repo(repo_str: str) -> tuple:
    """repo 문자열 파싱: "owner/repo@ref" → (owner, repo, ref)."""
    if "@" in repo_str:
        repo_part, ref = repo_str.rsplit("@", 1)
    else:
        repo_part, ref = repo_str, "main"
    
    if "/" in repo_part:
        owner, repo = repo_part.split("/", 1)
    else:
        owner, repo = repo_part, repo_part
    
    return owner, repo, ref


async def run_single_case(
    case: EvalCase,
    model_id: str,
    run_id: str,
    repeat_idx: int,
) -> EvalTrace:
    """단일 케이스 실행."""
    from backend.agents.supervisor.service import run_supervisor_diagnosis_async
    
    owner, repo, ref = parse_repo(case.repo)
    
    collector = EvalTraceCollector(
        case_id=case.id,
        model_id=model_id,
        run_id=run_id,
        repeat_idx=repeat_idx,
    )
    
    try:
        with collector:
            # Supervisor 실행 - 튜플 반환: (diagnosis_result, error_msg, trace)
            diagnosis_result, error_msg, trace = await run_supervisor_diagnosis_async(
                owner=owner,
                repo=repo,
                ref=ref,
                use_llm_summary=True,
                debug_trace=True,  # trace 수집을 위해 활성화
                user_message=case.user_query,
            )
            
            if error_msg:
                collector._error = error_msg
            
            # Plan 기록 (diagnosis_result에서 추출)
            if isinstance(diagnosis_result, dict):
                # target_agent로 간단한 plan 구성
                # TODO: task_plan 필드가 있으면 사용
                plan = []
                task_plan = diagnosis_result.get("task_plan")
                if task_plan and isinstance(task_plan, list):
                    plan = task_plan
                else:
                    # diagnosis_result가 있으면 diagnosis 에이전트 사용으로 추정
                    if diagnosis_result.get("health_score") is not None:
                        plan = [{"agent": "diagnosis", "mode": "FULL"}]
                    elif diagnosis_result.get("security_score") is not None:
                        plan = [{"agent": "security", "mode": "FAST"}]
                
                collector.on_plan_selected(plan)
                
                # Final answer 기록 - 구조화된 형태로 변환
                structured = _extract_structured_answer_from_diagnosis(diagnosis_result)
                collector.on_finalize(structured)
            else:
                collector.on_finalize_text(str(diagnosis_result))
    
    except Exception as e:
        logger.error(f"케이스 {case.id} 실행 실패: {e}")
        collector._error = str(e)
    
    return collector.finalize()


def _extract_structured_answer_from_diagnosis(diagnosis_result: Dict[str, Any]) -> Dict[str, Any]:
    """diagnosis_result에서 구조화된 답변 추출.
    
    Supervisor 결과의 diagnosis_result를 평가용 형태로 변환.
    """
    structured = {
        "task_type": "diagnosis",
        "key_metrics": {},
        "top_reasons": [],
        "next_actions": [],
        "plan_used": [],
        "parse_success": True,
    }
    
    if not diagnosis_result or not isinstance(diagnosis_result, dict):
        structured["parse_success"] = False
        return structured
    
    # key_metrics 추출
    structured["key_metrics"] = {
        "health_score": diagnosis_result.get("health_score"),
        "onboarding_score": diagnosis_result.get("onboarding_score"),
        "docs_score": diagnosis_result.get("docs_score"),
        "activity_score": diagnosis_result.get("activity_score"),
        "security_score": diagnosis_result.get("security_score"),
    }
    
    # task_type 추정
    if diagnosis_result.get("health_score") is not None:
        structured["task_type"] = "diagnosis"
    elif diagnosis_result.get("security_score") is not None:
        structured["task_type"] = "security"
    
    # warnings를 top_reasons로 변환
    warnings = diagnosis_result.get("warnings", [])
    for w in warnings[:5]:
        if isinstance(w, str):
            structured["top_reasons"].append({
                "claim": w,
                "evidence": [],
            })
        elif isinstance(w, dict):
            structured["top_reasons"].append({
                "claim": w.get("message", str(w)),
                "evidence": w.get("evidence", []),
            })
    
    # recommendations를 next_actions로 변환
    recs = diagnosis_result.get("recommendations", [])
    for i, r in enumerate(recs[:5]):
        if isinstance(r, str):
            structured["next_actions"].append({
                "action": r,
                "priority": "P0" if i == 0 else "P1",
                "evidence": [],
            })
        elif isinstance(r, dict):
            structured["next_actions"].append({
                "action": r.get("message", r.get("action", str(r))),
                "priority": r.get("priority", "P0" if i == 0 else "P1"),
                "evidence": r.get("evidence", []),
            })
    
    # plan 추출
    task_plan = diagnosis_result.get("task_plan")
    if task_plan and isinstance(task_plan, list):
        structured["plan_used"] = task_plan
    else:
        # health_score가 있으면 diagnosis, security_score가 있으면 security
        if diagnosis_result.get("health_score") is not None:
            structured["plan_used"] = [{"agent": "diagnosis", "mode": "FULL"}]
        elif diagnosis_result.get("security_score") is not None:
            structured["plan_used"] = [{"agent": "security", "mode": "FAST"}]
    
    return structured


def _extract_structured_answer(result: Dict[str, Any]) -> Dict[str, Any]:
    """Supervisor 결과에서 구조화된 답변 추출 (레거시).
    
    운영 모드의 텍스트 출력에서 최대한 구조화된 형태로 변환.
    """
    structured = {
        "task_type": "unknown",
        "key_metrics": {},
        "top_reasons": [],
        "next_actions": [],
        "plan_used": [],
        "parse_success": True,
    }
    
    # target_agent로 task_type 추정
    target = result.get("target_agent", "")
    if target in ("diagnosis", "security", "onboarding", "recommend", "comparison"):
        structured["task_type"] = target
    
    # diagnosis_result에서 key_metrics 추출
    diag = result.get("diagnosis_result", {})
    if isinstance(diag, dict):
        structured["key_metrics"] = {
            "health_score": diag.get("health_score"),
            "onboarding_score": diag.get("onboarding_score"),
            "docs_score": diag.get("docs_score"),
            "activity_score": diag.get("activity_score"),
        }
        
        # warnings를 top_reasons로 변환
        warnings = diag.get("warnings", [])
        for w in warnings[:5]:
            structured["top_reasons"].append({
                "claim": w,
                "evidence": [],  # 운영 모드에서는 evidence 없음
            })
        
        # recommendations를 next_actions로 변환
        recs = diag.get("recommendations", [])
        for i, r in enumerate(recs[:5]):
            structured["next_actions"].append({
                "action": r,
                "priority": "P0" if i == 0 else "P1",
                "evidence": [],
            })
    
    # security_result 처리
    sec = result.get("security_result", {})
    if isinstance(sec, dict) and sec:
        structured["key_metrics"]["security_score"] = sec.get("security_score")
        structured["key_metrics"]["risk_level"] = sec.get("risk_level")
    
    # plan 추출
    target = result.get("target_agent")
    if target:
        structured["plan_used"] = [{"agent": target, "mode": "FULL"}]
    
    # final_answer가 텍스트인 경우 raw_text로 저장
    final_answer = result.get("final_answer")
    if isinstance(final_answer, str):
        structured["raw_text"] = final_answer[:500]
    
    return structured


async def run_model_evaluation(
    cases: List[EvalCase],
    model_id: str,
    run_id: str,
    repeat: int = 1,
    max_cases: Optional[int] = None,
) -> List[EvalTrace]:
    """단일 모델에 대한 평가 실행."""
    traces = []
    
    target_cases = cases[:max_cases] if max_cases else cases
    total = len(target_cases) * repeat
    
    logger.info(f"[{model_id}] 평가 시작: {len(target_cases)}개 케이스 x {repeat}회 반복 = {total}회 실행")
    
    with EvalLLMContext(model_id):
        for case in target_cases:
            for r in range(repeat):
                try:
                    logger.info(f"[{model_id}] 실행 중: {case.id} (repeat {r+1}/{repeat})")
                    trace = await run_single_case(case, model_id, run_id, r)
                    traces.append(trace)
                    
                    # 간단한 진행 상황 출력
                    status = "OK" if not trace.error else f"ERROR: {trace.error[:50]}"
                    logger.info(f"[{model_id}] {case.id} 완료: {trace.latency_ms:.0f}ms - {status}")
                    
                except Exception as e:
                    logger.error(f"[{model_id}] {case.id} 예외: {e}")
                    # 실패한 케이스도 trace로 기록
                    failed_trace = EvalTrace(
                        case_id=case.id,
                        model_id=model_id,
                        run_id=run_id,
                        repeat_idx=r,
                        error=str(e),
                    )
                    traces.append(failed_trace)
    
    logger.info(f"[{model_id}] 평가 완료: {len(traces)}개 trace 수집")
    return traces


def save_results(
    runs: Dict[str, List[EvalTrace]],
    cases: List[EvalCase],
    run_id: str,
    output_dir: str,
):
    """결과 저장."""
    base_path = Path(output_dir) / run_id
    
    for model_id, traces in runs.items():
        model_path = base_path / model_id
        traces_path = model_path / "traces"
        traces_path.mkdir(parents=True, exist_ok=True)
        
        # 개별 trace 저장
        for trace in traces:
            trace_file = traces_path / f"{trace.case_id}.{trace.repeat_idx}.json"
            trace.save(str(trace_file))
        
        logger.info(f"[{model_id}] Trace 저장: {traces_path}")
    
    # 공통 리포트 저장 (모든 모델 포함)
    report_path = base_path
    report_path.mkdir(parents=True, exist_ok=True)
    
    # Markdown 리포트
    md_report = generate_markdown_report(runs, cases, run_id)
    with open(report_path / "report.md", "w", encoding="utf-8") as f:
        f.write(md_report)
    
    # CSV 리포트
    csv_report = generate_csv_report(runs, cases)
    with open(report_path / "report.csv", "w", encoding="utf-8") as f:
        f.write(csv_report)
    
    # Summary JSON
    summary = generate_summary_json(runs, cases, run_id)
    with open(report_path / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"리포트 저장: {report_path}")


async def main_async(args):
    """비동기 메인 함수."""
    # 로깅 설정
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    # 케이스 로드
    cases = load_cases(args.cases)
    if not cases:
        logger.error("로드된 케이스가 없습니다.")
        return 1
    
    # 모델 목록 결정
    if args.models:
        model_ids = [m.strip() for m in args.models.split(",")]
    elif args.model:
        model_ids = [args.model]
    else:
        model_ids = ["kanana2"]
    
    # 사용 가능한 모델 확인
    available = list_available_models()
    for m in model_ids:
        if m not in available:
            logger.error(f"모델을 찾을 수 없음: {m}. 사용 가능: {available}")
            return 1
    
    # Run ID 생성
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    logger.info(f"=== 평가 시작 ===")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"모델: {model_ids}")
    logger.info(f"케이스: {len(cases)}개")
    logger.info(f"반복: {args.repeat}회")
    
    # 모델별 평가 실행
    all_runs: Dict[str, List[EvalTrace]] = {}
    
    for model_id in model_ids:
        traces = await run_model_evaluation(
            cases=cases,
            model_id=model_id,
            run_id=run_id,
            repeat=args.repeat,
            max_cases=args.max_cases,
        )
        all_runs[model_id] = traces
    
    # 결과 저장
    save_results(all_runs, cases, run_id, args.out)
    
    # 요약 출력
    logger.info("=== 평가 완료 ===")
    for model_id, traces in all_runs.items():
        metrics = aggregate_metrics(traces, cases)
        logger.info(
            f"[{model_id}] "
            f"PlanAcc={metrics.plan_accuracy:.1%}, "
            f"ExecSucc={metrics.exec_success_rate:.1%}, "
            f"Helpfulness={metrics.helpfulness:.1%}, "
            f"Grounding={metrics.grounding_coverage:.1%}"
        )
    
    return 0


def main():
    """CLI 엔트리포인트."""
    parser = argparse.ArgumentParser(
        description="Supervisor LLM 성능 평가 하네스",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 단일 모델 평가
  python -m backend.eval.run --cases backend/eval/cases.jsonl --model kanana2

  # 다중 모델 비교
  python -m backend.eval.run --cases backend/eval/cases.jsonl --models kanana2,llama,qwen

  # 스모크 테스트 (케이스 2개만)
  python -m backend.eval.run --cases backend/eval/cases.jsonl --model kanana2 --max_cases 2
        """,
    )
    
    parser.add_argument(
        "--cases",
        required=True,
        help="평가 케이스 JSONL 파일 경로",
    )
    parser.add_argument(
        "--model",
        help="평가할 단일 모델 ID",
    )
    parser.add_argument(
        "--models",
        help="평가할 모델 ID 목록 (쉼표 구분)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="각 케이스 반복 실행 횟수 (기본: 1)",
    )
    parser.add_argument(
        "--max_cases",
        type=int,
        help="실행할 최대 케이스 수 (스모크 테스트용)",
    )
    parser.add_argument(
        "--out",
        default="artifacts/eval_runs",
        help="결과 저장 디렉토리 (기본: artifacts/eval_runs)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로깅 활성화",
    )
    
    args = parser.parse_args()
    
    # 모델 지정 확인
    if not args.model and not args.models:
        parser.error("--model 또는 --models 중 하나를 지정하세요.")
    
    # 비동기 실행
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
