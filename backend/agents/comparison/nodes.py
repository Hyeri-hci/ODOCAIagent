"""Comparison Agent 노드 함수."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def batch_diagnosis(
    repos: List[str],
    ref: str = "main",
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    여러 저장소를 순차적으로 분석하거나 캐시에서 로드.
    
    Returns:
        {
            "results": {repo: diagnosis_result},
            "warnings": [],
            "cache_hits": [],
            "cache_misses": [],
        }
    """
    from backend.common.cache_manager import analysis_cache
    # diagnosis/graph.py의 run_diagnosis 사용 (직접 파라미터)
    from backend.agents.diagnosis.graph import run_diagnosis as run_diagnosis_graph
    
    results = {}
    warnings = []
    cache_hits = []
    cache_misses = []
    
    for repo_str in repos:
        try:
            owner, repo = _parse_repo_string(repo_str)
        except ValueError as e:
            warnings.append(f"잘못된 저장소 형식: {repo_str}")
            logger.warning(f"Invalid repo format: {repo_str}, error: {e}")
            continue
        
        normalized_key = f"{owner}/{repo}"
        
        if normalized_key in results:
            logger.info(f"Already processed {normalized_key}, skipping duplicate")
            continue
        
        # 캐시 확인
        if use_cache:
            cached = analysis_cache.get_analysis(owner, repo, ref)
            if cached:
                cached_health = cached.get("health_score")
                if cached_health is not None and cached_health > 0:
                    logger.info(f"CACHE HIT: {normalized_key}, health_score={cached_health}")
                    cache_hits.append(normalized_key)
                    results[normalized_key] = cached
                    continue
                else:
                    logger.warning(f"Invalid cache: {normalized_key}, re-analyzing")
                    analysis_cache._store.pop(
                        analysis_cache.make_repo_key(owner, repo, ref), None
                    )
        
        # 캐시 미스 - 진단 실행 (비동기)
        cache_misses.append(normalized_key)
        logger.info(f"CACHE MISS - Running diagnosis: {normalized_key}")
        
        try:
            # graph.run_diagnosis 사용 (직접 파라미터)
            result_dict = await run_diagnosis_graph(
                owner=owner,
                repo=repo,
                ref=ref,
            )
            if result_dict and result_dict.get("health_score"):
                analysis_cache.set_analysis(owner, repo, ref, result_dict)
                results[normalized_key] = result_dict
            else:
                warnings.append(f"{normalized_key} 분석 실패")
        except Exception as e:
            logger.error(f"Diagnosis failed for {normalized_key}: {e}")
            warnings.append(f"{normalized_key} 분석 중 오류: {str(e)}")
    
    logger.info(
        f"Batch diagnosis complete: {len(results)}/{len(repos)} successful, "
        f"cache_hits={len(cache_hits)}, cache_misses={len(cache_misses)}"
    )
    
    return {
        "results": results,
        "warnings": warnings,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }


async def compare_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    여러 저장소의 분석 결과를 비교하여 LLM 기반 요약 생성.
    
    Returns:
        {"summary": str}
    """
    if not results or len(results) < 2:
        return {"summary": "비교할 저장소가 2개 이상 필요합니다."}
    
    # 비교 데이터 준비
    comparison_data = []
    for repo_str, data in results.items():
        health = data.get("health_score", 0)
        if health == 0 and data.get("health_level") == "unknown":
            logger.warning(f"Skipping invalid result for {repo_str}")
            continue
        
        comparison_data.append({
            "repo": repo_str,
            "health_score": health,
            "onboarding_score": data.get("onboarding_score", 0),
            "docs_score": data.get("documentation_quality", data.get("docs", {}).get("total_score", 0)),
            "activity_score": data.get("activity_maintainability", data.get("activity", {}).get("total_score", 0)),
            "health_level": data.get("health_level", "unknown"),
            "onboarding_level": data.get("onboarding_level", "unknown"),
        })
    
    comparison_data.sort(key=lambda x: x["health_score"], reverse=True)
    
    # LLM 비교 요약 생성 (비동기)
    summary = await _generate_llm_comparison_async(comparison_data)
    
    return {"summary": summary}


async def _generate_llm_comparison_async(comparison_data: List[Dict[str, Any]]) -> str:
    """LLM을 사용하여 비교 분석 메시지 생성 (비동기)."""
    import asyncio
    from backend.llm.factory import fetch_llm_client
    from backend.llm.base import ChatRequest, ChatMessage
    
    if len(comparison_data) < 2:
        return "비교할 저장소가 2개 이상 필요합니다."
    
    repo1, repo2 = comparison_data[0], comparison_data[1]
    
    score_diff = abs(repo1['health_score'] - repo2['health_score'])
    onboard_diff = abs(repo1['onboarding_score'] - repo2['onboarding_score'])
    
    if repo1['health_score'] > repo2['health_score']:
        health_summary = f"{score_diff}점 차이 ({repo1['repo']} 우세)"
    elif repo2['health_score'] > repo1['health_score']:
        health_summary = f"{score_diff}점 차이 ({repo2['repo']} 우세)"
    else:
        health_summary = "동점"
    
    if repo1['onboarding_score'] > repo2['onboarding_score']:
        onboard_summary = f"{onboard_diff}점 차이 ({repo1['repo']} 우세)"
    elif repo2['onboarding_score'] > repo1['onboarding_score']:
        onboard_summary = f"{onboard_diff}점 차이 ({repo2['repo']} 우세)"
    else:
        onboard_summary = "동점"
    
    prompt = f"""당신은 ODOC(Open-source Doctor) AI입니다.
ODOC 평가 기준: 건강점수=문서25%+활동성65%+구조10%, 온보딩점수=문서55%+활동성35%+구조10%
등급: 80점이상=Excellent, 60-79=Good, 40-59=Fair, 40미만=Poor

두 오픈소스 프로젝트를 비교 분석하여 사용자에게 보여줄 메시지를 작성해주세요.

[분석 데이터]

{repo1['repo']}:
- 건강 점수: {repo1['health_score']}점
- 온보딩 점수: {repo1['onboarding_score']}점
- 문서 품질: {repo1['docs_score']}점
- 활동성: {repo1['activity_score']}점

{repo2['repo']}:
- 건강 점수: {repo2['health_score']}점
- 온보딩 점수: {repo2['onboarding_score']}점
- 문서 품질: {repo2['docs_score']}점
- 활동성: {repo2['activity_score']}점

[점수 비교]
- 건강 점수: {health_summary}
- 온보딩 점수: {onboard_summary}

[작성 요청]
위 데이터를 바탕으로 비교 분석 메시지를 한국어로 작성해주세요.
마크다운 테이블은 사용하지 마세요. 일반 텍스트 형식으로 작성하세요.

필수 포함 내용:
1. 제목 (굵은 글씨로)
2. 각 프로젝트의 점수를 한 줄씩 나열
3. 종합 평가 (어떤 프로젝트가 더 좋은지, 이유)
4. 초보자에게 어떤 프로젝트가 더 적합한지
5. 최종 결론 한 문장

응답은 메시지만 출력하세요."""

    try:
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.7,
            max_tokens=800,
        )
        
        # 동기 LLM 호출을 비동기로 실행
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, client.chat, request)
        
        if response.content:
            return response.content.strip()
        else:
            logger.warning("LLM returned empty response")
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
    
    health_winner = (
        repo1["repo"] if repo1["health_score"] > repo2["health_score"]
        else repo2["repo"] if repo2["health_score"] > repo1["health_score"]
        else None
    )
    onboard_winner = (
        repo1["repo"] if repo1["onboarding_score"] > repo2["onboarding_score"]
        else repo2["repo"] if repo2["onboarding_score"] > repo1["onboarding_score"]
        else None
    )
    
    lines = [
        f"**{repo1['repo']} vs {repo2['repo']} 비교 분석**",
        "",
        f"**{repo1['repo']}**: 건강 {repo1['health_score']}점, 온보딩 {repo1['onboarding_score']}점",
        f"**{repo2['repo']}**: 건강 {repo2['health_score']}점, 온보딩 {repo2['onboarding_score']}점",
        "",
    ]
    
    if health_winner:
        lines.append(f"전반적인 프로젝트 건강도는 **{health_winner}**가 {score_diff}점 더 높습니다.")
    else:
        lines.append("두 프로젝트의 건강 점수가 동일합니다.")
    
    if onboard_winner:
        lines.append(f"초보자 기여에는 **{onboard_winner}**이 더 적합합니다.")
    
    if health_winner:
        lines.append(f"\n**결론**: 종합적으로 **{health_winner}**가 더 안정적인 프로젝트입니다.")
    
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
        match = re.search(r"github\.com/([^/]+)/([^/\s#?]+)", repo_str)
        if match:
            return match.group(1), match.group(2).replace(".git", "")
        raise ValueError(f"Invalid GitHub URL: {repo_str}")
    
    if "/" in repo_str:
        parts = repo_str.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
    
    raise ValueError(f"Invalid repo format: {repo_str}")
