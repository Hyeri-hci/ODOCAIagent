"""Comparison Nodes - 여러 저장소 비교 분석 노드."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


def batch_diagnosis_node(state: SupervisorState) -> Dict[str, Any]:
    """
    여러 저장소를 순차적으로 분석하거나 캐시에서 로드.
    
    설정하는 필드:
    - compare_results: 각 저장소별 분석 결과
    - warnings: 실패한 저장소에 대한 경고
    """
    from backend.common.cache import analysis_cache
    from backend.agents.diagnosis.service import run_diagnosis
    
    repos = state.compare_repos
    if not repos:
        logger.warning("No repositories to compare")
        return {
            "warnings": list(state.warnings) + ["비교할 저장소가 없습니다."],
            "next_node_override": "__end__",
            "step": state.step + 1,
        }
    
    results = dict(state.compare_results)
    warnings = list(state.warnings)
    
    for repo_str in repos:
        if repo_str in results:
            logger.info(f"Already have result for {repo_str}")
            continue
        
        try:
            owner, repo = _parse_repo_string(repo_str)
        except ValueError as e:
            warnings.append(f"잘못된 저장소 형식: {repo_str}")
            logger.warning(f"Invalid repo format: {repo_str}, error: {e}")
            continue
        
        cached = analysis_cache.get_analysis(owner, repo, "main")
        if cached:
            logger.info(f"Cache hit for comparison: {owner}/{repo}")
            results[repo_str] = cached
            continue
        
        logger.info(f"Running diagnosis for comparison: {owner}/{repo}")
        try:
            diagnosis_result = run_diagnosis(owner, repo, "main", use_llm_summary=False)
            if diagnosis_result:
                result_dict = diagnosis_result.to_dict()
                analysis_cache.set_analysis(owner, repo, "main", result_dict)
                results[repo_str] = result_dict
            else:
                warnings.append(f"{owner}/{repo} 분석 실패")
        except Exception as e:
            logger.error(f"Diagnosis failed for {owner}/{repo}: {e}")
            warnings.append(f"{owner}/{repo} 분석 중 오류: {str(e)}")
    
    logger.info(f"Batch diagnosis complete: {len(results)}/{len(repos)} successful")
    
    return {
        "compare_results": results,
        "warnings": warnings,
        "next_node_override": "compare_results_node",
        "step": state.step + 1,
    }


def compare_results_node(state: SupervisorState) -> Dict[str, Any]:
    """
    여러 저장소의 분석 결과를 비교하여 요약 생성.
    
    설정하는 필드:
    - compare_summary: 비교 요약 텍스트
    - flow_adjustments: 비교 기반 조정
    """
    results = state.compare_results
    
    if not results:
        return {
            "compare_summary": "비교할 결과가 없습니다.",
            "next_node_override": "__end__",
            "step": state.step + 1,
        }
    
    summary_lines = ["# 저장소 비교 분석\n"]
    
    comparison_data = []
    for repo_str, data in results.items():
        comparison_data.append({
            "repo": repo_str,
            "health_score": data.get("health_score", 0),
            "onboarding_score": data.get("onboarding_score", 0),
            "docs_score": data.get("documentation_quality", data.get("docs", {}).get("total_score", 0)),
            "activity_score": data.get("activity_maintainability", data.get("activity", {}).get("total_score", 0)),
            "health_level": data.get("health_level", "unknown"),
            "onboarding_level": data.get("onboarding_level", "unknown"),
        })
    
    comparison_data.sort(key=lambda x: x["health_score"], reverse=True)
    
    summary_lines.append("## 점수 비교\n")
    summary_lines.append("| 저장소 | 건강 점수 | 온보딩 점수 | 문서 | 활동성 |")
    summary_lines.append("|--------|----------|------------|------|--------|")
    
    for item in comparison_data:
        summary_lines.append(
            f"| {item['repo']} | {item['health_score']} | "
            f"{item['onboarding_score']} | {item['docs_score']} | {item['activity_score']} |"
        )
    
    summary_lines.append("\n## 추천\n")
    
    if comparison_data:
        best = comparison_data[0]
        summary_lines.append(f"**가장 건강한 프로젝트**: {best['repo']} (점수: {best['health_score']})\n")
        
        best_onboard = max(comparison_data, key=lambda x: x["onboarding_score"])
        summary_lines.append(
            f"**온보딩하기 좋은 프로젝트**: {best_onboard['repo']} "
            f"(온보딩 점수: {best_onboard['onboarding_score']})\n"
        )
    
    summary_lines.append("\n## 주요 차이점\n")
    if len(comparison_data) >= 2:
        scores = [d["health_score"] for d in comparison_data]
        diff = max(scores) - min(scores)
        summary_lines.append(f"- 건강 점수 차이: {diff}점\n")
        
        onboard_scores = [d["onboarding_score"] for d in comparison_data]
        onboard_diff = max(onboard_scores) - min(onboard_scores)
        summary_lines.append(f"- 온보딩 점수 차이: {onboard_diff}점\n")
    
    compare_summary = "\n".join(summary_lines)
    
    logger.info(f"Comparison summary generated for {len(results)} repositories")
    
    return {
        "compare_summary": compare_summary,
        "next_node_override": "__end__",
        "step": state.step + 1,
    }


def _parse_repo_string(repo_str: str) -> tuple:
    """
    저장소 문자열을 owner, repo로 파싱.
    
    지원 형식:
    - owner/repo
    - https://github.com/owner/repo
    """
    repo_str = repo_str.strip()
    
    if repo_str.startswith("http"):
        import re
        match = re.search(r"github\.com/([^/]+)/([^/\s#?]+)", repo_str)
        if match:
            return match.group(1), match.group(2).replace(".git", "")
        raise ValueError(f"Invalid GitHub URL: {repo_str}")
    
    if "/" in repo_str:
        parts = repo_str.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
    
    raise ValueError(f"Invalid repo format: {repo_str}")

