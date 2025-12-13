"""
Diagnosis Agent - Full Path
전체 진단 실행 (기존 파이프라인 + 병렬 처리)
"""
from typing import Dict, Any, Optional
import asyncio
import time
import logging
from concurrent.futures import ThreadPoolExecutor

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity_optimized
from backend.core.structure_core import analyze_structure
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_scores, compute_health_level, compute_onboarding_level
from backend.llm.factory import fetch_llm_client
from backend.llm.base import ChatRequest, ChatMessage

logger = logging.getLogger(__name__)


async def execute_full_path(
    owner: str,
    repo: str,
    ref: str = "main",
    analysis_depth: str = "standard",
    use_llm_summary: bool = True,
    force_refresh: bool = False
) -> Dict[str, Any]:
    start_time = time.time()
    logger.info(f"Full path execution: {owner}/{repo}@{ref} (depth={analysis_depth})")
    
    try:
        snapshot = await _fetch_snapshot_async(owner, repo, ref, analysis_depth)
        docs_result, activity_result, structure_result, deps_result = await asyncio.gather(
            _analyze_docs_async(snapshot),
            _analyze_activity_async(snapshot, analysis_depth),
            _analyze_structure_async(snapshot),
            _parse_dependencies_async(snapshot, analysis_depth)
        )
        
        if deps_result is None:
            from backend.core.models import DependenciesSnapshot
            deps_result = DependenciesSnapshot(
                repo_id=f"{owner}/{repo}",
                dependencies=[],
                analyzed_files=[],
                parse_errors=[]
            )
        
        scoring_result = compute_scores(
            docs=docs_result,
            activity=activity_result,
            deps=deps_result,
            structure=structure_result
        )
        
        llm_summary = None
        if use_llm_summary:
            llm_summary = await _generate_summary_async(
                owner, repo, scoring_result, docs_result, activity_result
            )
        
        key_findings = _extract_key_findings(docs_result, activity_result, scoring_result)
        warnings = _extract_warnings(docs_result, activity_result, scoring_result)
        recommendations = _generate_recommendations(scoring_result, docs_result, activity_result)
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Full path completed in {execution_time_ms}ms")
        
        # activity_result에서 상세 메트릭 추출 - 딕셔너리 또는 객체 모두 처리
        def get_activity_attr(key, default=None):
            """activity_result에서 속성 가져오기 (dict 또는 객체)"""
            if isinstance(activity_result, dict):
                return activity_result.get(key, default)
            return getattr(activity_result, key, default)
        
        # activity_result를 딕셔너리로 변환 (serialization용)
        if hasattr(activity_result, '__dict__'):
            activity_dict = activity_result.__dict__.copy()
        elif isinstance(activity_result, dict):
            activity_dict = activity_result
        else:
            activity_dict = {}
        
        return {
            "type": "full_diagnosis",
            "owner": owner,
            "repo": repo,
            "ref": ref,
            "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "analysis_depth": analysis_depth,
            
            # 점수 - DiagnosisCoreResult 객체에서 속성 추출
            "health_score": getattr(scoring_result, 'health_score', 0),
            "onboarding_score": getattr(scoring_result, 'onboarding_score', 0),
            "health_level": compute_health_level(getattr(scoring_result, 'health_score', 0)),
            "onboarding_level": compute_onboarding_level(getattr(scoring_result, 'onboarding_score', 0)),
            "docs_score": getattr(scoring_result, 'documentation_quality', 0),
            "activity_score": getattr(scoring_result, 'activity_maintainability', 0),
            "structure_score": structure_result.structure_score if structure_result else 0,
            
            # Repository Statistics (snapshot에서)
            "stars": getattr(snapshot, 'stars', 0),
            "forks": getattr(snapshot, 'forks', 0),
            # open_issues_count와 open_prs_count는 activity_result에서 가져옴 (GitHub API의 open_issues는 이슈+PR 합산)
            "open_issues_count": get_activity_attr("open_issues_count", 0),
            "open_prs_count": get_activity_attr("open_prs_count", 0),
            
            # 상세 메트릭 (activity_result에서)
            "days_since_last_commit": get_activity_attr("days_since_last_commit"),
            "total_commits_30d": get_activity_attr("total_commits_in_window", 0),
            "unique_contributors": get_activity_attr("unique_authors", 0) or get_activity_attr("unique_contributors", 0),
            "issue_close_rate": get_activity_attr("issue_closure_ratio", 0) or get_activity_attr("issue_close_rate", 0),
            "issue_close_rate_pct": f"{(get_activity_attr('issue_closure_ratio', 0) or get_activity_attr('issue_close_rate', 0)) * 100:.1f}%",
            "median_pr_merge_days": get_activity_attr("median_pr_merge_days"),
            "median_pr_merge_days_text": f"{get_activity_attr('median_pr_merge_days', 0):.1f}일" if get_activity_attr('median_pr_merge_days') else "N/A",
            "median_issue_close_days": get_activity_attr("median_issue_close_days"),
            "median_issue_close_days_text": f"{get_activity_attr('median_issue_close_days', 0):.1f}일" if get_activity_attr('median_issue_close_days') else "N/A",
            
            # 상세 분석 (데이터클래스는 asdict 사용)
            "documentation": docs_result.__dict__ if hasattr(docs_result, '__dict__') else docs_result,
            "activity": activity_dict,
            "structure": structure_result.__dict__ if structure_result and hasattr(structure_result, '__dict__') else structure_result,
            "dependencies": deps_result.__dict__ if deps_result and hasattr(deps_result, '__dict__') else deps_result,
            
            # 발견사항
            "key_findings": key_findings,
            "warnings": warnings,
            "recommendations": recommendations,
            
            # 요약
            "llm_summary": llm_summary,
            
            # 메타
            "execution_time_ms": execution_time_ms,
            "from_cache": False,
            "_cache_timestamp": time.time()  # 캐시 타임스탬프
        }
        
    except Exception as e:
        logger.error(f"Full path failed: {e}", exc_info=True)
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "type": "full_diagnosis",
            "owner": owner,
            "repo": repo,
            "ref": ref,
            "error": str(e),
            "execution_time_ms": execution_time_ms
        }


async def _fetch_snapshot_async(owner: str, repo: str, ref: str, analysis_depth: str):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        snapshot = await loop.run_in_executor(
            executor,
            fetch_repo_snapshot,
            owner, repo, ref
        )
    return snapshot


async def _analyze_docs_async(snapshot):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, analyze_docs, snapshot)
    return result


async def _analyze_activity_async(snapshot, analysis_depth: str):
    history_days = {
        "quick": 30,
        "standard": 90,
        "thorough": 180
    }.get(analysis_depth, 90)
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            lambda: analyze_activity_optimized(snapshot, None, history_days)
        )
    return result


async def _analyze_structure_async(snapshot):
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, analyze_structure, snapshot)
        return result
    except Exception as e:
        logger.warning(f"Structure analysis failed: {e}")
        return None


async def _parse_dependencies_async(snapshot, analysis_depth: str):
    if analysis_depth == "quick":
        logger.info("Skipping dependencies in quick mode")
        return None
    
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, parse_dependencies, snapshot)
        return result
    except Exception as e:
        logger.warning(f"Dependency parsing failed: {e}")
        return None


async def _generate_summary_async(
    owner: str,
    repo: str,
    scoring_result: Any,  # DiagnosisCoreResult 객체
    docs_result: Any,
    activity_result: Any
) -> Optional[str]:
    """비동기 LLM 요약 생성"""
    try:
        llm_client = fetch_llm_client()
        
        # docs_result와 activity_result에서 안전하게 값 추출
        has_readme = False
        if isinstance(docs_result, dict):
            has_readme = docs_result.get('readme_present', docs_result.get('has_readme', False))
        elif hasattr(docs_result, 'readme_present'):
            has_readme = docs_result.readme_present
        elif hasattr(docs_result, 'has_readme'):
            has_readme = docs_result.has_readme
        
        commits_count = 0
        active_contributors = 0
        if isinstance(activity_result, dict):
            commits_count = activity_result.get('total_commits_in_window', activity_result.get('recent_commits_count', 0))
        elif hasattr(activity_result, 'total_commits_in_window'):
            commits_count = activity_result.total_commits_in_window
            if hasattr(activity_result, 'active_contributors_count'):
                active_contributors = activity_result.active_contributors_count
        elif hasattr(activity_result, 'recent_commits_count'):
            commits_count = activity_result.recent_commits_count
            # If activity_result is not a dict and only has recent_commits_count,
            # active_contributors might not be directly available.
            # We'll default it to 0 or try other attributes if they exist.
            if hasattr(activity_result, 'unique_authors'):
                active_contributors = activity_result.unique_authors
            elif hasattr(activity_result, 'active_contributors'):
                active_contributors = activity_result.active_contributors
            else:
                active_contributors = 0
        else:
            active_contributors = 0 # Default if no activity data
        
        from backend.prompts.loader import render_prompt
        
        prompt = render_prompt(
            "diagnosis_prompts",
            "summary_generation",
            owner=owner,
            repo=repo,
            health_score=getattr(scoring_result, 'health_score', 0),
            health_level=compute_health_level(getattr(scoring_result, 'health_score', 0)),
            onboarding_score=getattr(scoring_result, 'onboarding_score', 0),
            onboarding_level=compute_onboarding_level(getattr(scoring_result, 'onboarding_score', 0)),
            docs_score=getattr(scoring_result, 'documentation_quality', 0),
            activity_score=getattr(scoring_result, 'activity_maintainability', 0),
            has_readme="O" if has_readme else "X",
            commits_count=commits_count,
            active_contributors=active_contributors
        )

        # 비동기 LLM 호출
        loop = asyncio.get_event_loop()
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=500
        )
        response = await loop.run_in_executor(None, llm_client.chat, request)
        return response.content
        
    except Exception as e:
        logger.error(f"LLM summary failed: {e}", exc_info=True)
        return None


def _extract_key_findings(docs_result, activity_result, scoring_result) -> list:
    """주요 발견사항 추출"""
    findings = []
    
    health_score = getattr(scoring_result, 'health_score', 0)
    onboarding_score = getattr(scoring_result, 'onboarding_score', 0)
    
    if health_score >= 80:
        findings.append({
            "category": "health",
            "severity": "info",
            "title": "우수한 건강도",
            "description": f"저장소 건강도가 {health_score}점으로 매우 양호합니다."
        })
    elif health_score < 60:
        findings.append({
            "category": "health",
            "severity": "warning",
            "title": "낮은 건강도",
            "description": f"저장소 건강도가 {health_score}점으로 개선이 필요합니다."
        })
    
    has_readme = getattr(docs_result, 'readme_present', getattr(docs_result, 'has_readme', False))
    if has_readme:
        findings.append({
            "category": "docs",
            "severity": "info",
            "title": "README 문서 존재",
            "description": "README.md 파일이 있어 프로젝트 이해에 도움이 됩니다."
        })
    
    commits = getattr(activity_result, 'total_commits_in_window', getattr(activity_result, 'recent_commits_count', 0))
    if commits:
        if commits > 50:
            findings.append({
                "category": "activity",
                "severity": "info",
                "title": "활발한 개발",
                "description": f"최근 {commits}개의 커밋이 있어 활발히 관리되고 있습니다."
            })
    
    return findings[:5]


def _extract_warnings(docs_result, activity_result, scoring_result) -> list:
    warnings = []
    
    has_readme = getattr(docs_result, 'readme_present', getattr(docs_result, 'has_readme', False))
    if not has_readme:
        warnings.append("README.md 파일이 없습니다.")
    
    # has_license는 DocsCoreResult에 없음 - missing_sections 체크로 대체
    missing = getattr(docs_result, 'missing_sections', [])
    if 'LICENSE' in missing or 'WHO' in missing:
        warnings.append("LICENSE 파일이 없습니다.")
    
    commits = getattr(activity_result, 'total_commits_in_window', 0)
    if commits < 10:
        warnings.append("최근 커밋 활동이 적습니다.")
    
    return warnings[:5]


def _generate_recommendations(scoring_result, docs_result, activity_result) -> list:
    recommendations = []
    
    docs_score = getattr(scoring_result, 'documentation_quality', 0)
    if docs_score < 70:
        recommendations.append("문서화 개선: README, CONTRIBUTING, LICENSE 파일을 추가하세요.")
    
    activity_score = getattr(scoring_result, 'activity_maintainability', 0)
    if activity_score < 60:
        recommendations.append("활동성 향상: 정기적인 커밋과 이슈 관리가 필요합니다.")
    
    if not hasattr(docs_result, 'has_contributing') or not docs_result.has_contributing:
        recommendations.append("CONTRIBUTING.md를 추가하여 기여 가이드를 제공하세요.")
    
    return recommendations[:5]
