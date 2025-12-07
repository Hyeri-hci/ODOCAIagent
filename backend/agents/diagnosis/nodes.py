"""Diagnosis LangGraph 노드 - 저장소 분석의 개별 단계."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from backend.agents.diagnosis.models import DiagnosisState

logger = logging.getLogger(__name__)


def fetch_snapshot_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    GitHub 저장소 스냅샷 수집 노드.
    """
    from backend.core.github_core import fetch_repo_snapshot
    
    if state.repo_snapshot:
        logger.info("Reusing existing repo snapshot")
        return {"step": state.step + 1}
    
    start_time = time.time()
    
    try:
        snapshot = fetch_repo_snapshot(state.owner, state.repo, state.ref)
        
        # Pydantic 모델을 dict로 변환
        snapshot_dict = snapshot.model_dump() if hasattr(snapshot, "model_dump") else {
            "owner": snapshot.owner,
            "repo": snapshot.repo,
            "ref": snapshot.ref,
            "stars": snapshot.stars,
            "forks": snapshot.forks,
            "tree": snapshot.tree,
            "readme_content": getattr(snapshot, "readme_content", ""),
            "languages": getattr(snapshot, "languages", {}),
        }
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["fetch_snapshot"] = elapsed
        
        logger.info(f"Fetched snapshot for {state.owner}/{state.repo} in {elapsed}s")
        
        return {
            "repo_snapshot": snapshot_dict,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch snapshot: {e}")
        return {
            "error": str(e),
            "failed_step": "fetch_snapshot",
            "step": state.step + 1,
        }


def analyze_docs_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    문서 분석 노드.
    
    README, CONTRIBUTING 등 문서 품질을 분석합니다.
    """
    from backend.core.docs_core import analyze_docs
    from backend.core.models import RepoSnapshot
    
    if state.docs_result:
        logger.info("Reusing existing docs result")
        return {"step": state.step + 1}
    
    if not state.repo_snapshot:
        return {
            "error": "No snapshot available for docs analysis",
            "failed_step": "analyze_docs",
            "step": state.step + 1,
        }
    
    start_time = time.time()
    
    try:
        # Dict를 RepoSnapshot으로 변환
        snapshot_dict = state.repo_snapshot
        snapshot = RepoSnapshot(**snapshot_dict)
        
        docs_result = analyze_docs(snapshot)
        
        # 결과를 dict로 변환
        docs_dict = docs_result.to_dict() if hasattr(docs_result, "to_dict") else docs_result.__dict__
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["analyze_docs"] = elapsed
        
        logger.info(f"Docs analysis completed in {elapsed}s")
        
        return {
            "docs_result": docs_dict,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Docs analysis failed: {e}")
        return {
            "error": str(e),
            "failed_step": "analyze_docs",
            "step": state.step + 1,
        }


def analyze_activity_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    활동성 분석 노드.
    
    커밋, PR, 이슈 등 저장소 활동성을 분석합니다.
    """
    from backend.core.activity_core import analyze_activity_optimized
    from backend.core.models import RepoSnapshot
    
    if state.activity_result:
        logger.info("Reusing existing activity result")
        return {"step": state.step + 1}
    
    if not state.repo_snapshot:
        return {
            "error": "No snapshot available for activity analysis",
            "failed_step": "analyze_activity",
            "step": state.step + 1,
        }
    
    start_time = time.time()
    
    try:
        snapshot_dict = state.repo_snapshot
        snapshot = RepoSnapshot(**snapshot_dict)
        
        activity_result = analyze_activity_optimized(snapshot)
        
        # 결과를 dict로 변환
        activity_dict = activity_result.to_dict() if hasattr(activity_result, "to_dict") else activity_result.__dict__
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["analyze_activity"] = elapsed
        
        logger.info(f"Activity analysis completed in {elapsed}s")
        
        return {
            "activity_result": activity_dict,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Activity analysis failed: {e}")
        return {
            "error": str(e),
            "failed_step": "analyze_activity",
            "step": state.step + 1,
        }


def analyze_structure_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    구조 분석 노드.
    
    프로젝트 구조, 디렉토리 레이아웃 등을 분석합니다.
    """
    from backend.core.structure_core import analyze_structure
    from backend.core.models import RepoSnapshot
    
    if state.structure_result:
        logger.info("Reusing existing structure result")
        return {"step": state.step + 1}
    
    # quick 모드에서는 스킵 가능
    if "structure" in state.skip_components:
        logger.info("Skipping structure analysis (skip_components)")
        return {"step": state.step + 1}
    
    if not state.repo_snapshot:
        return {
            "error": "No snapshot available for structure analysis",
            "failed_step": "analyze_structure",
            "step": state.step + 1,
        }
    
    start_time = time.time()
    
    try:
        snapshot_dict = state.repo_snapshot
        snapshot = RepoSnapshot(**snapshot_dict)
        
        structure_result = analyze_structure(snapshot)
        
        # 결과를 dict로 변환
        structure_dict = structure_result.to_dict() if hasattr(structure_result, "to_dict") else structure_result
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["analyze_structure"] = elapsed
        
        logger.info(f"Structure analysis completed in {elapsed}s")
        
        return {
            "structure_result": structure_dict,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Structure analysis failed: {e}")
        return {
            "error": str(e),
            "failed_step": "analyze_structure",
            "step": state.step + 1,
        }


def parse_deps_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    의존성 파싱 노드.
    
    package.json, requirements.txt 등에서 의존성을 추출합니다.
    """
    from backend.core.dependencies_core import parse_dependencies
    from backend.core.models import RepoSnapshot
    
    if state.deps_result:
        logger.info("Reusing existing deps result")
        return {"step": state.step + 1}
    
    # quick 모드에서는 스킵
    if state.analysis_depth == "quick" or "dependencies" in state.skip_components:
        logger.info("Skipping dependency parsing (quick mode or skip)")
        return {"step": state.step + 1}
    
    if not state.repo_snapshot:
        return {
            "error": "No snapshot available for dependency parsing",
            "failed_step": "parse_deps",
            "step": state.step + 1,
        }
    
    start_time = time.time()
    
    try:
        snapshot_dict = state.repo_snapshot
        snapshot = RepoSnapshot(**snapshot_dict)
        
        deps = parse_dependencies(snapshot)
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["parse_dependencies"] = elapsed
        
        logger.info(f"Dependency parsing completed in {elapsed}s")
        
        return {
            "deps_result": deps,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Dependency parsing failed: {e}")
        return {
            "error": str(e),
            "failed_step": "parse_deps",
            "step": state.step + 1,
        }


def compute_scores_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    점수 계산 노드.
    
    개별 분석 결과를 종합하여 건강 점수, 온보딩 점수 등을 계산합니다.
    """
    from backend.core.scoring_core import compute_scores
    from backend.core.models import DocsResult, ActivityResult, StructureResult
    
    if state.scoring_result:
        logger.info("Reusing existing scoring result")
        return {"step": state.step + 1}
    
    start_time = time.time()
    
    try:
        # 개별 결과들을 적절한 형태로 변환
        docs_result = None
        if state.docs_result:
            docs_result = DocsResult(**state.docs_result) if isinstance(state.docs_result, dict) else state.docs_result
        
        activity_result = None  
        if state.activity_result:
            activity_result = ActivityResult(**state.activity_result) if isinstance(state.activity_result, dict) else state.activity_result
        
        structure_result = None
        if state.structure_result:
            structure_result = StructureResult(**state.structure_result) if isinstance(state.structure_result, dict) else state.structure_result
        
        deps = state.deps_result
        
        # 점수 계산
        diagnosis = compute_scores(docs_result, activity_result, deps, structure_result)
        
        # 결과를 dict로 변환
        scoring_dict = diagnosis.to_dict() if hasattr(diagnosis, "to_dict") else diagnosis.__dict__
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["compute_scores"] = elapsed
        
        logger.info(f"Score computation completed in {elapsed}s")
        
        return {
            "scoring_result": scoring_dict,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Score computation failed: {e}")
        return {
            "error": str(e),
            "failed_step": "compute_scores",
            "step": state.step + 1,
        }


def generate_summary_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    요약 생성 노드.
    
    LLM 또는 규칙 기반으로 사용자용 요약을 생성합니다.
    """
    if state.summary_text:
        logger.info("Reusing existing summary")
        return {"step": state.step + 1}
    
    # LLM 요약 스킵 조건
    if not state.use_llm_summary or "llm_summary" in state.skip_components or state.analysis_depth == "quick":
        logger.info("Using fallback summary (LLM skipped)")
        summary = _generate_fallback_summary(state)
        return {
            "summary_text": summary,
            "step": state.step + 1,
        }
    
    start_time = time.time()
    
    try:
        summary = _generate_llm_summary(state)
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["generate_summary"] = elapsed
        
        logger.info(f"Summary generation completed in {elapsed}s")
        
        return {
            "summary_text": summary,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.warning(f"LLM summary failed, using fallback: {e}")
        summary = _generate_fallback_summary(state)
        return {
            "summary_text": summary,
            "error": None,  # fallback 성공이므로 에러 클리어
            "step": state.step + 1,
        }


def _generate_fallback_summary(state: DiagnosisState) -> str:
    """규칙 기반 fallback 요약 생성."""
    scoring = state.scoring_result or {}
    
    health_score = scoring.get("health_score", 50)
    health_level = scoring.get("health_level", "unknown")
    onboarding_score = scoring.get("onboarding_score", 50)
    
    # 레벨별 메시지
    level_messages = {
        "good": "건강한 프로젝트입니다. 기여를 환영합니다!",
        "fair": "괜찮은 상태의 프로젝트입니다.",
        "warning": "일부 개선이 필요한 프로젝트입니다.",
        "bad": "주의가 필요한 프로젝트입니다.",
    }
    
    message = level_messages.get(health_level, "프로젝트 분석이 완료되었습니다.")
    
    summary = f"""## {state.owner}/{state.repo} 진단 결과

**건강 점수**: {health_score:.0f}점 ({health_level})
**온보딩 점수**: {onboarding_score:.0f}점

{message}
"""
    
    return summary


def _generate_llm_summary(state: DiagnosisState) -> str:
    """LLM 기반 요약 생성."""
    from backend.llm.factory import fetch_llm_client
    from backend.llm.base import ChatRequest, ChatMessage
    from backend.common.config import LLM_MODEL_NAME
    
    scoring = state.scoring_result or {}
    docs = state.docs_result or {}
    activity = state.activity_result or {}
    
    prompt = f"""다음 오픈소스 프로젝트 진단 결과를 한국어로 간결하게 요약해주세요:

**저장소**: {state.owner}/{state.repo}
**건강 점수**: {scoring.get('health_score', 'N/A')}점
**온보딩 점수**: {scoring.get('onboarding_score', 'N/A')}점
**문서 품질**: {docs.get('documentation_quality', 'N/A')}점
**활동성**: {activity.get('activity_maintainability', 'N/A')}점

요약은 3-4문장으로 작성하고, 기여자에게 도움이 될 정보를 포함하세요."""

    client = fetch_llm_client()
    request = ChatRequest(
        messages=[ChatMessage(role="user", content=prompt)],
        model=LLM_MODEL_NAME,
        temperature=0.7,
    )
    
    response = client.chat(request, timeout=30)
    return response.content


def build_output_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    최종 출력 생성 노드.
    
    모든 분석 결과를 DiagnosisOutput 형태로 조합합니다.
    """
    scoring = state.scoring_result or {}
    docs = state.docs_result or {}
    activity = state.activity_result or {}
    structure = state.structure_result or {}
    snapshot = state.repo_snapshot or {}
    
    # 타이밍 합산
    timings = state.timings.copy()
    timings["total"] = sum(v for v in timings.values() if isinstance(v, (int, float)))
    timings["analysis_depth"] = state.analysis_depth
    
    output = {
        "repo_id": scoring.get("repo_id", f"{state.owner}/{state.repo}"),
        "health_score": scoring.get("health_score", 50),
        "health_level": scoring.get("health_level", "unknown"),
        "onboarding_score": scoring.get("onboarding_score", 50),
        "onboarding_level": scoring.get("onboarding_level", "unknown"),
        "documentation_quality": docs.get("documentation_quality", 0),
        "activity_maintainability": activity.get("activity_maintainability", 0),
        "docs": docs,
        "activity": activity,
        "structure": structure,
        "dependency_complexity_score": scoring.get("dependency_complexity_score", 0),
        "dependency_flags": scoring.get("dependency_flags", []),
        "stars": snapshot.get("stars", 0),
        "forks": snapshot.get("forks", 0),
        "summary_for_user": state.summary_text or "",
        "raw_metrics": scoring,
        "timings": timings,
        "analysis_depth_used": state.analysis_depth,
    }
    
    # 이슈 정보 추가
    output["docs_issues"] = docs.get("docs_issues", [])
    output["activity_issues"] = activity.get("activity_issues", [])
    
    # 추가 메트릭
    output["days_since_last_commit"] = activity.get("days_since_last_commit")
    output["total_commits_30d"] = activity.get("total_commits_30d", 0)
    output["unique_contributors"] = activity.get("unique_contributors", 0)
    output["issue_close_rate"] = activity.get("issue_close_rate", 0)
    output["median_pr_merge_days"] = activity.get("median_pr_merge_days")
    output["median_issue_close_days"] = activity.get("median_issue_close_days")
    
    logger.info(f"Diagnosis output built: health={output['health_score']}, onboarding={output['onboarding_score']}")
    
    return {
        "diagnosis_output": output,
        "step": state.step + 1,
    }


def check_error_node(state: DiagnosisState) -> Dict[str, Any]:
    """
    에러 체크 및 복구 노드.
    
    현재 에러 상태를 확인하고 복구 가능한지 결정합니다.
    """
    if not state.error:
        return {"step": state.step + 1}
    
    failed_step = state.failed_step or "unknown"
    retry_count = state.retry_count
    
    logger.warning(f"Error detected in {failed_step}: {state.error}, retry={retry_count}/{state.max_retry}")
    
    if retry_count >= state.max_retry:
        logger.error(f"Max retries reached for {failed_step}")
        return {
            "step": state.step + 1,
        }
    
    # 재시도 가능한 단계들
    retryable_steps = ["fetch_snapshot", "analyze_docs", "analyze_activity", "analyze_structure"]
    
    if failed_step in retryable_steps:
        logger.info(f"Scheduling retry for {failed_step}")
        return {
            "error": None,  # 에러 클리어
            "retry_count": retry_count + 1,
            "step": state.step + 1,
        }
    
    # 스킵 가능한 단계들
    skippable_steps = ["parse_deps", "generate_summary"]
    if failed_step in skippable_steps:
        logger.info(f"Skipping failed step: {failed_step}")
        return {
            "error": None,
            "skip_components": list(state.skip_components) + [failed_step],
            "step": state.step + 1,
        }
    
    return {"step": state.step + 1}


# 라우팅 함수들

def route_after_snapshot(state: DiagnosisState) -> str:
    """스냅샷 수집 후 라우팅."""
    if state.error:
        return "check_error_node"
    return "analyze_docs_node"


def route_after_docs(state: DiagnosisState) -> str:
    """문서 분석 후 라우팅."""
    if state.error:
        return "check_error_node"
    return "analyze_activity_node"


def route_after_activity(state: DiagnosisState) -> str:
    """활동성 분석 후 라우팅."""
    if state.error:
        return "check_error_node"
    if state.analysis_depth == "quick":
        return "compute_scores_node"  # quick 모드는 구조 분석 스킵
    return "analyze_structure_node"


def route_after_structure(state: DiagnosisState) -> str:
    """구조 분석 후 라우팅."""
    if state.error:
        return "check_error_node"
    return "parse_deps_node"


def route_after_deps(state: DiagnosisState) -> str:
    """의존성 파싱 후 라우팅."""
    if state.error:
        return "check_error_node"
    return "compute_scores_node"


def route_after_scores(state: DiagnosisState) -> str:
    """점수 계산 후 라우팅."""
    if state.error:
        return "check_error_node"
    return "generate_summary_node"


def route_after_summary(state: DiagnosisState) -> str:
    """요약 생성 후 라우팅."""
    return "build_output_node"


def route_after_error_check(state: DiagnosisState) -> str:
    """에러 체크 후 라우팅."""
    if state.error:
        # 복구 불가 - 부분 결과로 출력 생성
        return "build_output_node"
    
    # 재시도가 필요한 경우
    failed_step = state.failed_step
    if failed_step == "fetch_snapshot":
        return "fetch_snapshot_node"
    elif failed_step == "analyze_docs":
        return "analyze_docs_node"
    elif failed_step == "analyze_activity":
        return "analyze_activity_node"
    elif failed_step == "analyze_structure":
        return "analyze_structure_node"
    
    # 일반적으로는 다음 단계로 진행
    return "build_output_node"
