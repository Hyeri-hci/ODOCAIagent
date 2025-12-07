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
    from backend.agents.diagnosis.models import DiagnosisInput
    
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
    cache_hits = []
    cache_misses = []
    
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
        
        logger.info(f"Checking cache for {owner}/{repo}...")
        cached = analysis_cache.get_analysis(owner, repo, "main")
        if cached:
            logger.info(f"CACHE HIT for comparison: {owner}/{repo}, health_score={cached.get('health_score')}")
            cache_hits.append(repo_str)
            normalized_key = f"{owner}/{repo}"
            results[normalized_key] = cached
            if repo_str != normalized_key:
                results[repo_str] = cached
            continue
        
        cache_misses.append(repo_str)
        logger.info(f"CACHE MISS - Running diagnosis for comparison: {owner}/{repo}")
        try:
            diagnosis_input = DiagnosisInput(owner=owner, repo=repo, ref="main")
            diagnosis_result = run_diagnosis(diagnosis_input)
            if diagnosis_result:
                result_dict = diagnosis_result.to_dict()
                analysis_cache.set_analysis(owner, repo, "main", result_dict)
                normalized_key = f"{owner}/{repo}"
                results[normalized_key] = result_dict
                if repo_str != normalized_key:
                    results[repo_str] = result_dict
            else:
                warnings.append(f"{owner}/{repo} 분석 실패")
        except Exception as e:
            logger.error(f"Diagnosis failed for {owner}/{repo}: {e}")
            warnings.append(f"{owner}/{repo} 분석 중 오류: {str(e)}")
    
    logger.info(
        f"Batch diagnosis complete: {len(results)}/{len(repos)} successful, "
        f"cache_hits={cache_hits}, cache_misses={cache_misses}"
    )
    
    return {
        "compare_results": results,
        "warnings": warnings,
        "next_node_override": "compare_results_node",
        "step": state.step + 1,
    }


def compare_results_node(state: SupervisorState) -> Dict[str, Any]:
    """
    여러 저장소의 분석 결과를 비교하여 LLM 기반 요약 생성.
    
    설정하는 필드:
    - compare_summary: LLM이 생성한 비교 요약 텍스트
    - flow_adjustments: 비교 기반 조정
    """
    results = state.compare_results
    
    if not results:
        return {
            "compare_summary": "비교할 결과가 없습니다.",
            "next_node_override": "__end__",
            "step": state.step + 1,
        }
    
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
            "summary": data.get("summary_for_user", ""),
            "readme_exists": data.get("docs", {}).get("readme_exists", False),
            "contributing_exists": data.get("docs", {}).get("contributing_exists", False),
        })
    
    comparison_data.sort(key=lambda x: x["health_score"], reverse=True)
    
    llm_summary = _generate_llm_comparison(comparison_data)
    
    logger.info(f"Comparison summary generated for {len(results)} repositories")
    
    return {
        "compare_summary": llm_summary,
        "next_node_override": "__end__",
        "step": state.step + 1,
    }


def _generate_llm_comparison(comparison_data: List[Dict[str, Any]]) -> str:
    """LLM을 사용하여 비교 분석 전체 메시지 생성."""
    from backend.llm.factory import fetch_llm_client
    from backend.llm.base import ChatRequest, ChatMessage
    
    if len(comparison_data) < 2:
        return "비교할 저장소가 2개 이상 필요합니다."
    
    repo1, repo2 = comparison_data[0], comparison_data[1]
    
    score_diff = abs(repo1['health_score'] - repo2['health_score'])
    onboard_diff = abs(repo1['onboarding_score'] - repo2['onboarding_score'])
    health_winner = repo1['repo'] if repo1['health_score'] > repo2['health_score'] else repo2['repo'] if repo2['health_score'] > repo1['health_score'] else "동점"
    onboard_winner = repo1['repo'] if repo1['onboarding_score'] > repo2['onboarding_score'] else repo2['repo'] if repo2['onboarding_score'] > repo1['onboarding_score'] else "동점"
    
    prompt = f"""두 오픈소스 프로젝트를 비교 분석하여 사용자에게 보여줄 메시지를 작성해주세요.

## 분석 데이터

### {repo1['repo']}
| 항목 | 점수 |
|------|------|
| 건강 점수 | {repo1['health_score']}점 |
| 온보딩 점수 | {repo1['onboarding_score']}점 |
| 문서 품질 | {repo1['docs_score']}점 |
| 활동성 | {repo1['activity_score']}점 |

### {repo2['repo']}
| 항목 | 점수 |
|------|------|
| 건강 점수 | {repo2['health_score']}점 |
| 온보딩 점수 | {repo2['onboarding_score']}점 |
| 문서 품질 | {repo2['docs_score']}점 |
| 활동성 | {repo2['activity_score']}점 |

## 점수 차이 요약
- 건강 점수 차이: {score_diff}점 ({health_winner} 우세)
- 온보딩 점수 차이: {onboard_diff}점 ({onboard_winner} 우세)

## 작성 요청

위 데이터를 바탕으로 아래 형식의 비교 분석 메시지를 한국어로 작성해주세요.
마크다운 형식을 사용하고, 자연스러운 대화체로 작성해주세요.

**필수 포함 내용:**
1. 제목: "**{repo1['repo']} vs {repo2['repo']} 비교 분석**"
2. 점수 비교 테이블 (건강 점수, 온보딩 점수, 문서 품질, 활동성)
3. 종합 평가 (어떤 프로젝트가 전반적으로 더 좋은지, 그 이유)
4. 초보자 추천 (오픈소스 기여를 처음 시작하는 사람에게 어떤 프로젝트가 더 적합한지)
5. 각 프로젝트의 강점과 약점 간단히 언급
6. 최종 결론 한 문장

응답은 전체 메시지만 출력해주세요. 추가 설명 없이 바로 메시지를 시작하세요."""

    try:
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.7,
            max_tokens=800,
        )
        response = client.chat(request)
        
        if response.content:
            return response.content.strip()
        else:
            logger.warning("LLM returned empty response for comparison")
            return _generate_fallback_comparison(comparison_data)
            
    except Exception as e:
        logger.error(f"LLM comparison failed: {e}")
        return _generate_fallback_comparison(comparison_data)


def _generate_fallback_comparison(comparison_data: List[Dict[str, Any]]) -> str:
    """LLM 실패 시 템플릿 기반 비교 메시지 생성."""
    if len(comparison_data) < 2:
        return "비교할 데이터가 부족합니다."
    
    repo1, repo2 = comparison_data[0], comparison_data[1]
    
    score_diff = abs(repo1["health_score"] - repo2["health_score"])
    onboard_diff = abs(repo1["onboarding_score"] - repo2["onboarding_score"])
    
    health_winner = repo1["repo"] if repo1["health_score"] > repo2["health_score"] else repo2["repo"] if repo2["health_score"] > repo1["health_score"] else None
    onboard_winner = repo1["repo"] if repo1["onboarding_score"] > repo2["onboarding_score"] else repo2["repo"] if repo2["onboarding_score"] > repo1["onboarding_score"] else None
    
    lines = [
        f"**{repo1['repo']} vs {repo2['repo']} 비교 분석**",
        "",
        "**점수 비교**",
        "",
        "| 항목 | " + repo1['repo'] + " | " + repo2['repo'] + " |",
        "|------|---------|---------|",
        f"| 건강 점수 | {repo1['health_score']}점 | {repo2['health_score']}점 |",
        f"| 온보딩 점수 | {repo1['onboarding_score']}점 | {repo2['onboarding_score']}점 |",
        f"| 문서 품질 | {repo1['docs_score']}점 | {repo2['docs_score']}점 |",
        f"| 활동성 | {repo1['activity_score']}점 | {repo2['activity_score']}점 |",
        "",
        "**종합 평가**",
        "",
    ]
    
    if health_winner:
        lines.append(f"전반적인 프로젝트 건강도는 **{health_winner}**가 {score_diff}점 더 높습니다.")
    else:
        lines.append("두 프로젝트의 건강 점수가 동일합니다.")
    
    lines.append("")
    lines.append("**초보자 추천**")
    lines.append("")
    
    if onboard_winner:
        lines.append(f"오픈소스 기여를 처음 시작하는 분에게는 **{onboard_winner}**을 추천합니다. (온보딩 점수 {onboard_diff}점 차이)")
    else:
        lines.append("두 프로젝트 모두 온보딩 측면에서 비슷한 수준입니다.")
    
    lines.append("")
    lines.append("**결론**")
    lines.append("")
    
    if health_winner:
        lines.append(f"종합적으로 **{health_winner}**가 더 안정적이고 관리가 잘 되는 프로젝트입니다.")
    else:
        lines.append("두 프로젝트 모두 좋은 선택입니다. 관심 분야에 따라 선택하세요.")
    
    return "\n".join(lines)


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

