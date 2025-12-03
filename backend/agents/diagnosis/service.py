from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Dict, List
import logging

from backend.agents.diagnosis.tools.readme.readme_loader import (
    fetch_readme_content,
    compute_readme_metrics,
)
from backend.agents.diagnosis.tools.readme.readme_categories import classify_readme_sections
from backend.agents.diagnosis.tools.readme.docs_effective import compute_docs_effective
from backend.agents.diagnosis.tools.readme.sustainability_gate import check_sustainability_gate
from backend.common.github_client import DEFAULT_ACTIVITY_DAYS
from backend.common.parallel import run_parallel
from .tools.repo_parser import fetch_repo_info
from .tools.scoring.chaoss_metrics import (
    compute_commit_activity,
    compute_issue_activity,
    compute_pr_activity,
)
from .tools.scoring.activity_scores import (
    aggregate_activity_score,
    activity_score_to_100,
)
from .tools.scoring.health_score import HealthScore, create_health_score, create_health_score_v2
from .tools.scoring.diagnosis_labels import create_diagnosis_labels
from .tools.onboarding.onboarding_plan import create_onboarding_plan
from .tools.onboarding.onboarding_tasks import compute_onboarding_tasks
from .tools.scoring.reasoning_builder import build_explain_context
from .task_type import DiagnosisTaskType, parse_task_type
from .llm_summarizer import summarize_diagnosis_repository

logger = logging.getLogger(__name__)

USE_LLM_SUMMARY = True
USE_LLM_ONBOARDING = False  # v0: 규칙 기반, True로 변경하면 v1: LLM 기반
USE_ONBOARDING_TASKS = True  # True: onboarding_tasks 블록 포함


def _summarize_common(repo_info, scores: HealthScore, commit_metrics=None) -> str:
    """규칙 기반 자연어 요약."""
    parts: List[str] = []
    parts.append(f"Repository: {repo_info.full_name}")
    if repo_info.description:
        parts.append(f"Description: {repo_info.description}")
    parts.append(f"Stars: {repo_info.stars}, Forks: {repo_info.forks}, Watchers: {repo_info.watchers}")
    parts.append(f"Open Issues: {repo_info.open_issues}")
    parts.append(
        f"README Present: {'Yes' if repo_info.has_readme else 'No'} "
        f"(Documentation Score: {scores.documentation_quality}/100)"
    )
    parts.append(f"Activity Score: {scores.activity_maintainability}/100")
    parts.append(f"Health Score: {scores.health_score}/100")
    parts.append(f"Onboarding Score: {scores.onboarding_score}/100")
    parts.append(f"Is Healthy: {'Yes' if scores.is_healthy else 'No'}")

    if commit_metrics is not None:
        if commit_metrics.days_since_last_commit is not None:
            parts.append(
                f"Total Commits in last {commit_metrics.window_days} days: {commit_metrics.total_commits}, "
                f"Days since last commit: {commit_metrics.days_since_last_commit}"
            )
        else:
            parts.append(
                f"No commits in the last {commit_metrics.window_days} days."
            )

    return "\n".join(parts)


def run_diagnosis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnosis Agent 진입점. 5-Phase 파이프라인 실행."""

    owner = (payload.get("owner") or "").strip()
    repo = (payload.get("repo") or "").strip()
    if not owner or not repo:
        raise ValueError("owner 및 repo는 필수 항목입니다.")

    task_type = parse_task_type(payload.get("task_type"))
    focus = payload.get("focus") or []
    user_context = payload.get("user_context") or {}
    user_level = user_context.get("level", "beginner")
    
    # needs 기반 Phase 실행 분기 (Supervisor에서 전달)
    needs = payload.get("needs")
    if needs is None:
        # fallback: task_type 기반으로 needs 생성
        needs = {
            "need_health": True,
            "need_readme": True,
            "need_activity": task_type == DiagnosisTaskType.FULL or task_type == DiagnosisTaskType.ACTIVITY_ONLY,
            "need_onboarding": USE_ONBOARDING_TASKS,
        }
    
    # 고급 분석 모드: 카테고리별 상세 요약 포함 (LLM 5회, 기본 1회보다 느림)
    advanced_analysis = payload.get("advanced_analysis", False)

    phase_times = {}

    # Phase 1: GitHub API 병렬 호출
    logger.info("Phase 1: Fetching GitHub data...")
    t0 = time.time()
    
    if task_type == DiagnosisTaskType.FULL:
        # FULL 모드: repo_info, readme, commits, issues, prs 병렬 호출
        parallel_results = run_parallel({
            "repo_info": lambda: fetch_repo_info(owner, repo),
            "readme_text": lambda: fetch_readme_content(owner, repo) or "",
            "commit_metrics": lambda: compute_commit_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "issue_metrics": lambda: compute_issue_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "pr_metrics": lambda: compute_pr_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
        })
        repo_info = parallel_results["repo_info"]
        readme_text = parallel_results["readme_text"]
        commit_metrics = parallel_results["commit_metrics"]
        issue_metrics = parallel_results["issue_metrics"]
        pr_metrics = parallel_results["pr_metrics"]
    else:
        # DOCS_ONLY 또는 ACTIVITY_ONLY: 필요한 것만 병렬 호출
        parallel_results = run_parallel({
            "repo_info": lambda: fetch_repo_info(owner, repo),
            "readme_text": lambda: fetch_readme_content(owner, repo) or "",
        })
        repo_info = parallel_results["repo_info"]
        readme_text = parallel_results["readme_text"]
        commit_metrics = None
        issue_metrics = None
        pr_metrics = None
    
    phase_times["phase1_github"] = time.time() - t0
    logger.info("Phase 1 완료: %.2fs", phase_times["phase1_github"])

    # README 메트릭 계산 (로컬, 빠름)
    readme_metrics = None
    if readme_text:
        readme_metrics = compute_readme_metrics(readme_text)

    # Phase 2: README 분류 + 요약
    logger.info("Phase 2: README classification...")
    t1 = time.time()
    
    if readme_text:
        # LLM 재분류로 정확도 향상
        readme_categories, readme_category_score, unified_summary = classify_readme_sections(
            readme_text,
            use_llm_refine=True,  # LLM으로 애매한 섹션 재분류
            advanced_mode=advanced_analysis,
        )
    else:
        from backend.agents.diagnosis.tools.readme.readme_summarizer import ReadmeUnifiedSummary
        readme_categories, readme_category_score = {}, 0
        unified_summary = ReadmeUnifiedSummary(summary_en="", summary_ko="")
    
    phase_times["phase2_readme"] = time.time() - t1
    logger.info("Phase 2 완료: %.2fs", phase_times["phase2_readme"])

    # details 기본 구성
    details: Dict[str, Any] = {
        "repo_info": asdict(repo_info),
        "analysis_mode": "advanced" if advanced_analysis else "basic",
    }
    if readme_metrics is not None:
        details["readme_metrics"] = asdict(readme_metrics)

    details["docs"] = {
        "readme_categories": readme_categories,
        "readme_category_score": readme_category_score,
        "readme_summary_for_embedding": unified_summary.summary_en,
        "readme_summary_for_user": unified_summary.summary_ko,
    }

    details["readme_raw"] = readme_text

    # Phase 3: 점수 계산
    logger.info("Phase 3: Computing scores...")
    t2 = time.time()
    scores: HealthScore
    
    # v2: docs_effective 계산 (교차검증 포함)
    docs_effective_result = None
    if readme_text and needs.get("need_readme", True):
        try:
            docs_effective_result = compute_docs_effective(
                owner=owner,
                repo=repo,
                readme_content=readme_text,
                docs_quality_raw=readme_category_score,
                skip_consilience=False,  # 교차검증 수행
            )
            details["docs_effective"] = docs_effective_result.to_dict()
        except Exception as e:
            logger.warning("docs_effective 계산 실패: %s", e)

    if task_type == DiagnosisTaskType.FULL:
        # CHAOSS 기반 activity 점수 계산
        activity_breakdown = aggregate_activity_score(
            commit=commit_metrics,
            issue=issue_metrics,
            pr=pr_metrics,
        )
        
        # D = readme_category_score, A = CHAOSS activity
        # health_score = 0.3*D + 0.7*A, onboarding_score = 0.6*D_eff + 0.4*A
        doc_score = readme_category_score
        activity_score = activity_score_to_100(activity_breakdown)
        
        # v2: sustainability gate 계산
        gate_result = None
        try:
            activity_data_for_gate = {
                "commit": asdict(commit_metrics),
                "issue": asdict(issue_metrics),
                "pr": asdict(pr_metrics),
            }
            gate_result = check_sustainability_gate(activity_data_for_gate)
            details["sustainability_gate"] = gate_result.to_dict()
        except Exception as e:
            logger.warning("sustainability_gate 계산 실패: %s", e)
        
        # v2: 확장된 HealthScore 생성
        if docs_effective_result and gate_result:
            scores = create_health_score_v2(
                doc=doc_score,
                activity=activity_score,
                docs_effective=docs_effective_result.docs_effective,
                tech_score=docs_effective_result.tech_score,
                marketing_penalty=docs_effective_result.marketing_penalty,
                consilience_score=docs_effective_result.consilience_score,
                sustainability_score=gate_result.sustainability_score,
                gate_level=gate_result.gate_level,
                is_sustainable=gate_result.is_sustainable,
                is_marketing_heavy=docs_effective_result.is_marketing_heavy,
                has_broken_refs=docs_effective_result.has_broken_refs,
            )
            details["docs_effective"] = docs_effective_result.to_dict()
            details["sustainability_gate"] = gate_result.to_dict()
        else:
            scores = create_health_score(doc_score, activity_score)

        # CHAOSS 기반 activity 블록 (commit, issue, pr + scores)
        details["activity"] = {
            "commit": asdict(commit_metrics),
            "issue": asdict(issue_metrics),
            "pr": asdict(pr_metrics),
            "scores": activity_breakdown.to_dict(),
        }

    elif task_type == DiagnosisTaskType.DOCS_ONLY:
        # DOCS_ONLY: documentation만 평가
        if docs_effective_result:
            scores = create_health_score_v2(
                doc=readme_category_score,
                activity=0,
                docs_effective=docs_effective_result.docs_effective,
                tech_score=docs_effective_result.tech_score,
                marketing_penalty=docs_effective_result.marketing_penalty,
                consilience_score=docs_effective_result.consilience_score,
                sustainability_score=0,
                gate_level="unknown",
                is_sustainable=True,  # 활동성 데이터 없음 - 기본값
                is_marketing_heavy=docs_effective_result.is_marketing_heavy,
                has_broken_refs=docs_effective_result.has_broken_refs,
            )
            details["docs_effective"] = docs_effective_result.to_dict()
        else:
            scores = create_health_score(readme_category_score, 0)

    elif task_type == DiagnosisTaskType.ACTIVITY_ONLY:
        # ACTIVITY_ONLY: commit, issue, pr 메트릭 병렬 호출
        activity_results = run_parallel({
            "commit_metrics": lambda: compute_commit_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "issue_metrics": lambda: compute_issue_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
            "pr_metrics": lambda: compute_pr_activity(
                owner=owner,
                repo=repo,
                days=DEFAULT_ACTIVITY_DAYS,
            ),
        })
        commit_metrics = activity_results["commit_metrics"]
        issue_metrics = activity_results["issue_metrics"]
        pr_metrics = activity_results["pr_metrics"]

        # CHAOSS 기반 activity 점수 계산
        activity_breakdown = aggregate_activity_score(
            commit=commit_metrics,
            issue=issue_metrics,
            pr=pr_metrics,
        )

        activity_score = activity_score_to_100(activity_breakdown)

        # Sustainability Gate 계산
        gate_activity_data = {
            "commit": asdict(commit_metrics),
            "issue": asdict(issue_metrics),
            "pr": asdict(pr_metrics),
        }
        gate_result = check_sustainability_gate(activity_data=gate_activity_data)

        scores = create_health_score_v2(
            doc=0,
            activity=activity_score,
            docs_effective=0,
            tech_score=0,
            marketing_penalty=0,
            consilience_score=100,
            sustainability_score=gate_result.sustainability_score,
            gate_level=gate_result.gate_level,
            is_sustainable=gate_result.is_sustainable,
            is_marketing_heavy=False,
            has_broken_refs=False,
        )

        details["activity"] = {
            "commit": asdict(commit_metrics),
            "issue": asdict(issue_metrics),
            "pr": asdict(pr_metrics),
            "scores": activity_breakdown.to_dict(),
        }
        details["sustainability_gate"] = gate_result.to_dict()

    else:
        scores = create_health_score_v2(
            doc=0,
            activity=0,
            docs_effective=0,
            tech_score=0,
            marketing_penalty=0,
            consilience_score=100,
            sustainability_score=0,
            gate_level="abandoned",
            is_sustainable=False,
            is_marketing_heavy=False,
            has_broken_refs=False,
        )

    phase_times["phase3_scores"] = time.time() - t2
    logger.info("Phase 3 완료: %.2fs", phase_times["phase3_scores"])

    # 규칙 기반 기본 요약
    natural_summary = _summarize_common(
        repo_info=repo_info,
        scores=scores,
        commit_metrics=commit_metrics,
    )

    # 규칙 기반 라벨 생성 (v2: 마케팅/지속가능성 파라미터 추가)
    readme_categories = details.get("docs", {}).get("readme_categories")
    activity_scores_dict = details.get("activity", {}).get("scores")
    
    labels = create_diagnosis_labels(
        health_score=scores.health_score,
        onboarding_score=scores.onboarding_score,
        doc_score=scores.documentation_quality,
        activity_score=scores.activity_maintainability,
        readme_categories=readme_categories,
        activity_scores=activity_scores_dict,
        repo_info=details.get("repo_info"),
        activity_data=details.get("activity"),
        # v2 파라미터
        is_marketing_heavy=scores.is_marketing_heavy,
        has_broken_refs=scores.has_broken_refs,
        docs_effective=scores.docs_effective,
        gate_level=scores.gate_level,
        is_sustainable=scores.is_sustainable,
    )

    # 온보딩 계획 생성 (needs["need_onboarding"]이 True일 때만)
    onboarding_plan = None
    if needs.get("need_onboarding", False):
        docs_summary = details.get("docs", {}).get("readme_summary_for_user", "")
        onboarding_plan = create_onboarding_plan(
            scores=asdict(scores),
            labels=labels.to_dict(),
            docs_summary=docs_summary,
            repo_info=details.get("repo_info"),
            use_llm=USE_LLM_ONBOARDING,
        )

    # 온보딩 Task 목록 생성 (needs["need_onboarding"]이 True일 때만)
    onboarding_tasks = None
    if needs.get("need_onboarding", False):
        logger.info("Phase 4: Computing onboarding tasks...")
        t3 = time.time()
        onboarding_tasks = compute_onboarding_tasks(
            owner=owner,
            repo=repo,
            labels=labels.to_dict(),
            onboarding_plan=onboarding_plan.to_dict() if onboarding_plan else {},
        )
        phase_times["phase4_onboarding"] = time.time() - t3
        logger.info("Phase 4 완료: %.2fs", phase_times["phase4_onboarding"])
    else:
        logger.info("Phase 4: 온보딩 Task 생성 건너뜀 (need_onboarding=False)")

    # 최종 JSON 결과
    result_json: Dict[str, Any] = {
        "input": {
            "owner": owner,
            "repo": repo,
            "task_type": task_type.value if isinstance(task_type, DiagnosisTaskType) else str(task_type),
            "focus": focus,
            "user_context": user_context,
            "needs": needs,
        },
        "scores": asdict(scores),
        "labels": labels.to_dict(),
        "onboarding_plan": onboarding_plan.to_dict() if onboarding_plan else None,
        "onboarding_tasks": onboarding_tasks.to_dict() if onboarding_tasks else None,
        "details": details,
    }

    # explain 모드를 위한 reasoning 데이터 생성
    result_json["explain_context"] = build_explain_context(result_json)

    # LLM 기반 요약
    if USE_LLM_SUMMARY:
        t4 = time.time()
        natural_summary = summarize_diagnosis_repository(
            diagnosis_result=result_json,
            user_level=user_level,
            language="ko",
        )
        phase_times["phase5_llm_summary"] = time.time() - t4
        logger.info("Phase 5 (LLM 요약) 완료: %.2fs", phase_times["phase5_llm_summary"])

    result_json["natural_language_summary_for_user"] = natural_summary
    
    # 전체 시간 로깅
    total_time = sum(phase_times.values())
    logger.info("=== Diagnosis 완료: 총 %.2fs ===", total_time)
    for phase, t in phase_times.items():
        logger.info("  %s: %.2fs (%.1f%%)", phase, t, t/total_time*100 if total_time > 0 else 0)
    
    return result_json
