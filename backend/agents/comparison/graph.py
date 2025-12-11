"""
Comparison Agent Graph - 하이브리드 패턴 (LangGraph + 안전한 예외 처리)

향상된 에이전트 흐름:
validate_input → batch_diagnosis → compare → summarize
       ↓ (에러 시)        ↓ (에러 시)    ↓ (에러 시)
   error_handler     error_handler  error_handler

특징:
- 모든 노드에 @safe_node 데코레이터로 예외 처리
- 조건부 라우팅으로 에러 발생 시 빠른 종료
- Core scoring 활용 (health_score, onboarding_score, levels)
- 레포지토리 랭킹 및 추천
- 목적별 최적 저장소 판단
"""
from typing import Dict, Any, Optional, List, Callable, Literal
from langgraph.graph import StateGraph, END
import logging
from functools import wraps

from backend.agents.comparison.models import ComparisonState, ComparisonOutput
from backend.core.scoring_core import (
    compute_health_level,
    compute_onboarding_level,
    HEALTH_GOOD_THRESHOLD,
    HEALTH_WARNING_THRESHOLD,
    ONBOARDING_EASY_THRESHOLD,
    ONBOARDING_NORMAL_THRESHOLD,
)

logger = logging.getLogger(__name__)


# === 예외 처리 데코레이터 ===

def safe_node(default_updates: Dict[str, Any] = None):
    """
    노드 함수에 안전한 예외 처리를 추가하는 데코레이터
    
    Args:
        default_updates: 예외 발생 시 반환할 기본 상태 업데이트
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: ComparisonState) -> Dict[str, Any]:
            node_name = func.__name__.replace("_node", "")
            try:
                return await func(state)
            except Exception as e:
                logger.error(f"[Comparison Agent] {node_name} failed: {e}", exc_info=True)
                
                # 기본 업데이트 값 설정
                updates = default_updates.copy() if default_updates else {}
                updates["error"] = str(e)
                updates["execution_path"] = (state.get("execution_path") or "") + f" → {node_name}(ERROR)"
                
                return updates
        return wrapper
    return decorator


# === 에이전트 결정 로직 ===

def _analyze_repo_strengths(
    health_score: int,
    onboarding_score: int,
    docs_score: int,
    activity_score: int,
) -> List[str]:
    """저장소의 강점 분석"""
    strengths = []
    
    if health_score >= HEALTH_GOOD_THRESHOLD:
        strengths.append("excellent_maintenance")
    elif health_score >= HEALTH_WARNING_THRESHOLD:
        strengths.append("decent_maintenance")
    
    if onboarding_score >= ONBOARDING_EASY_THRESHOLD:
        strengths.append("beginner_friendly")
    elif onboarding_score >= ONBOARDING_NORMAL_THRESHOLD:
        strengths.append("moderate_learning_curve")
    
    if docs_score >= 70:
        strengths.append("well_documented")
    if activity_score >= 70:
        strengths.append("actively_maintained")
    
    return strengths


def _determine_best_for_purpose(comparison_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """목적별 최적 저장소 결정"""
    if not comparison_data:
        return {}
    
    recommendations = {
        "for_learning": None,
        "for_contribution": None,
        "for_production_reference": None,
        "overall_winner": None,
    }
    
    # 학습용: 온보딩 점수 최고
    learning_sorted = sorted(comparison_data, key=lambda x: x.get("onboarding_score", 0), reverse=True)
    if learning_sorted:
        recommendations["for_learning"] = {
            "repo": learning_sorted[0]["repo"],
            "reason": f"온보딩 점수 {learning_sorted[0].get('onboarding_score', 0)}점으로 가장 학습하기 좋음"
        }
    
    # 기여용: 활동성 + 문서화 균형
    contribution_sorted = sorted(
        comparison_data, 
        key=lambda x: x.get("activity_score", 0) * 0.6 + x.get("docs_score", 0) * 0.4, 
        reverse=True
    )
    if contribution_sorted:
        recommendations["for_contribution"] = {
            "repo": contribution_sorted[0]["repo"],
            "reason": f"활발한 유지보수와 문서화로 기여하기 좋음"
        }
    
    # 프로덕션 참고용: 전체 건강도 최고
    health_sorted = sorted(comparison_data, key=lambda x: x.get("health_score", 0), reverse=True)
    if health_sorted:
        recommendations["for_production_reference"] = {
            "repo": health_sorted[0]["repo"],
            "reason": f"건강도 점수 {health_sorted[0].get('health_score', 0)}점으로 가장 안정적"
        }
    
    # 전체 우승자: 종합 점수
    overall_sorted = sorted(
        comparison_data,
        key=lambda x: x.get("health_score", 0) * 0.5 + x.get("onboarding_score", 0) * 0.5,
        reverse=True
    )
    if overall_sorted:
        recommendations["overall_winner"] = {
            "repo": overall_sorted[0]["repo"],
            "health_score": overall_sorted[0].get("health_score", 0),
            "onboarding_score": overall_sorted[0].get("onboarding_score", 0),
        }
    
    return recommendations


# === 노드 함수들 (안전한 예외 처리 포함) ===

@safe_node(default_updates={"validated_repos": [], "warnings": []})
async def validate_input_node(state: ComparisonState) -> Dict[str, Any]:
    """입력 검증 - 최소 2개 저장소 필요"""
    logger.info(f"[Comparison Agent] Validating input: {len(state.get('repos', []))} repos")
    
    repos = state.get("repos", [])
    warnings = []
    validated_repos = []
    
    if len(repos) < 2:
        return {
            "error": "비교 분석에는 최소 2개의 저장소가 필요합니다.",
            "warnings": ["비교 분석에는 최소 2개의 저장소가 필요합니다."],
            "validated_repos": [],
            "execution_path": "comparison_graph:validate_input(ERROR)"
        }
    
    # 저장소 형식 검증
    for repo in repos:
        if "/" in repo:
            validated_repos.append(repo)
        else:
            warnings.append(f"잘못된 저장소 형식: {repo}")
    
    if len(validated_repos) < 2:
        return {
            "error": "유효한 저장소가 2개 이상 필요합니다.",
            "warnings": warnings,
            "validated_repos": validated_repos,
            "execution_path": "comparison_graph:validate_input(ERROR)"
        }
    
    logger.info(f"[Comparison Agent] Validated {len(validated_repos)} repos")
    
    return {
        "validated_repos": validated_repos,
        "warnings": warnings,
        "execution_path": "comparison_graph:validate_input",
        "error": None
    }


@safe_node(default_updates={"batch_results": {}, "cache_hits": [], "cache_misses": []})
async def batch_diagnosis_node(state: ComparisonState) -> Dict[str, Any]:
    """여러 저장소를 순차적으로 분석 (캐시 활용)"""
    logger.info("[Comparison Agent] Running batch diagnosis")
    
    # 에러가 있으면 스킵
    if state.get("error"):
        return {}
    
    from backend.agents.comparison.nodes import batch_diagnosis
    
    validated_repos = state.get("validated_repos", [])
    ref = state.get("ref", "main")
    use_cache = state.get("use_cache", True)
    
    # batch_diagnosis는 이제 비동기 함수
    batch_result = await batch_diagnosis(
        repos=validated_repos,
        ref=ref,
        use_cache=use_cache,
    )
    
    logger.info(
        f"[Comparison Agent] Batch diagnosis complete: {len(batch_result.get('results', {}))} results, "
        f"cache_hits={len(batch_result.get('cache_hits', []))}, "
        f"cache_misses={len(batch_result.get('cache_misses', []))}"
    )
    
    return {
        "batch_results": batch_result.get("results", {}),
        "cache_hits": batch_result.get("cache_hits", []),
        "cache_misses": batch_result.get("cache_misses", []),
        "warnings": (state.get("warnings") or []) + batch_result.get("warnings", []),
        "execution_path": state.get("execution_path", "") + " → batch_diagnosis"
    }


@safe_node(default_updates={"comparison_data": [], "agent_analysis": {}})
async def compare_node(state: ComparisonState) -> Dict[str, Any]:
    """Core scoring을 활용한 비교 데이터 준비 및 분석"""
    logger.info("[Comparison Agent] Analyzing and comparing results")
    
    # 에러가 있으면 스킵
    if state.get("error"):
        return {}
    
    batch_results = state.get("batch_results", {})
    
    if not batch_results or len(batch_results) < 2:
        return {
            "error": "비교할 결과가 2개 이상 필요합니다.",
            "comparison_data": [],
            "execution_path": state.get("execution_path", "") + " → compare(ERROR)"
        }
    
    # 비교 데이터 준비 및 강점 분석
    comparison_data = []
    for repo_str, data in batch_results.items():
        health_score = data.get("health_score", 0)
        if health_score == 0 and data.get("health_level") == "unknown":
            logger.warning(f"[Comparison Agent] Skipping invalid result for {repo_str}")
            continue
        
        onboarding_score = data.get("onboarding_score", 0)
        docs_score = data.get("documentation_quality", data.get("docs", {}).get("total_score", 0))
        activity_score = data.get("activity_maintainability", data.get("activity", {}).get("total_score", 0))
        
        # Core scoring 레벨 재계산 (일관성 보장)
        health_level = compute_health_level(health_score)
        onboarding_level = compute_onboarding_level(onboarding_score)
        
        # 강점 분석
        strengths = _analyze_repo_strengths(health_score, onboarding_score, docs_score, activity_score)
        
        comparison_data.append({
            "repo": repo_str,
            "health_score": health_score,
            "onboarding_score": onboarding_score,
            "docs_score": docs_score,
            "activity_score": activity_score,
            "health_level": health_level,
            "onboarding_level": onboarding_level,
            "strengths": strengths,
        })
    
    # 점수 내림차순 정렬
    comparison_data.sort(key=lambda x: x["health_score"], reverse=True)
    
    # 목적별 추천 결정
    recommendations = _determine_best_for_purpose(comparison_data)
    
    logger.info(f"[Comparison Agent] Analyzed {len(comparison_data)} repos, overall winner: {recommendations.get('overall_winner', {}).get('repo', 'N/A')}")
    
    # 에이전트 분석 결과
    agent_analysis = {
        "comparison_data": comparison_data,
        "recommendations": recommendations,
        "total_repos_compared": len(comparison_data),
        "reasoning": f"Compared {len(comparison_data)} repositories based on health_score and onboarding_score",
    }
    
    return {
        "comparison_data": comparison_data,
        "agent_analysis": agent_analysis,
        "error": None,
        "execution_path": state.get("execution_path", "") + " → compare"
    }


@safe_node(default_updates={"comparison_summary": "", "result": {}})
async def summarize_node(state: ComparisonState) -> Dict[str, Any]:
    """LLM을 사용하여 비교 분석 요약 생성 - 에이전트 추천 포함"""
    logger.info("[Comparison Agent] Generating comparison summary with recommendations")
    
    # 에러가 있으면 에러 결과 반환
    if state.get("error"):
        return {
            "result": ComparisonOutput(
                warnings=state.get("warnings", []) + [state.get("error", "")]
            ).dict(),
            "execution_path": state.get("execution_path", "") + " → summarize(ERROR)"
        }
    
    from backend.agents.comparison.nodes import compare_results
    
    batch_results = state.get("batch_results", {})
    agent_analysis = state.get("agent_analysis", {})
    
    # compare_results 호출하여 LLM 요약 생성 (비동기)
    comparison_result = await compare_results(batch_results)
    summary = comparison_result.get("summary", "")
    
    # 에이전트 추천 정보 추가
    recommendations = agent_analysis.get("recommendations", {})
    if recommendations:
        rec_section = "\n\n📊 **에이전트 추천**:\n"
        
        if recommendations.get("for_learning"):
            rec = recommendations["for_learning"]
            rec_section += f"- 🎓 **학습용**: `{rec['repo']}` - {rec['reason']}\n"
        
        if recommendations.get("for_contribution"):
            rec = recommendations["for_contribution"]
            rec_section += f"- 🤝 **기여용**: `{rec['repo']}` - {rec['reason']}\n"
        
        if recommendations.get("for_production_reference"):
            rec = recommendations["for_production_reference"]
            rec_section += f"- 🏭 **참고용**: `{rec['repo']}` - {rec['reason']}\n"
        
        if recommendations.get("overall_winner"):
            winner = recommendations["overall_winner"]
            rec_section += f"\n🏆 **종합 1위**: `{winner['repo']}` (건강도: {winner['health_score']}점, 온보딩: {winner['onboarding_score']}점)"
        
        summary += rec_section
    
    logger.info("[Comparison Agent] Comparison summary generated with agent recommendations")
    
    # 최종 결과 조립 - 에이전트 분석 결과 포함
    result = ComparisonOutput(
        results=batch_results,
        comparison_summary=summary,
        warnings=state.get("warnings", []),
        cache_hits=state.get("cache_hits", []),
        cache_misses=state.get("cache_misses", []),
    )
    
    result_dict = result.dict()
    result_dict["agent_analysis"] = agent_analysis
    
    return {
        "comparison_summary": summary,
        "result": result_dict,
        "execution_path": state.get("execution_path", "") + " → summarize"
    }


# === 에러 핸들러 노드 ===

async def error_handler_node(state: ComparisonState) -> Dict[str, Any]:
    """에러 발생 시 안전한 결과 반환"""
    logger.warning(f"[Comparison Agent] Error handler triggered: {state.get('error')}")
    
    error_msg = state.get("error", "Unknown error occurred")
    warnings = state.get("warnings", []) + [error_msg]
    
    # 에러 결과 생성
    result = ComparisonOutput(
        results=state.get("batch_results", {}),
        comparison_summary=f"비교 분석 중 오류가 발생했습니다: {error_msg}",
        warnings=warnings,
        cache_hits=state.get("cache_hits", []),
        cache_misses=state.get("cache_misses", []),
    )
    
    return {
        "result": result.dict(),
        "execution_path": (state.get("execution_path") or "") + " → error_handler"
    }


# === 조건부 라우팅 (하이브리드 패턴 핵심) ===

def check_error_after_validate(state: ComparisonState) -> Literal["continue", "error_handler"]:
    """validate_input 후 에러 체크"""
    if state.get("error"):
        return "error_handler"
    return "continue"


def check_error_after_batch(state: ComparisonState) -> Literal["continue", "error_handler"]:
    """batch_diagnosis 후 에러 체크"""
    if state.get("error"):
        return "error_handler"
    return "continue"


def check_error_after_compare(state: ComparisonState) -> Literal["continue", "error_handler"]:
    """compare 후 에러 체크"""
    if state.get("error"):
        return "error_handler"
    return "continue"


# === 그래프 빌드 (하이브리드 패턴) ===

def build_comparison_graph():
    """
    Comparison StateGraph 빌드 (하이브리드 패턴)
    
    흐름: 
    validate_input → [check] → batch_diagnosis → [check] → compare → [check] → summarize
         ↓ (에러)              ↓ (에러)               ↓ (에러)
    error_handler ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    
    특징:
    - 모든 노드에 @safe_node 데코레이터로 예외 처리
    - 각 주요 노드 후 에러 체크 → 빠른 종료 (LangGraph 장점 활용)
    - compare 노드가 Core scoring을 활용하여 독립적인 분석 및 추천 수행
    """
    
    graph = StateGraph(ComparisonState)
    
    # 노드 추가
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("batch_diagnosis", batch_diagnosis_node)
    graph.add_node("compare", compare_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("error_handler", error_handler_node)  # 에러 핸들러 추가
    
    # 엔트리 포인트
    graph.set_entry_point("validate_input")
    
    # validate_input 후 조건부 분기
    graph.add_conditional_edges(
        "validate_input",
        check_error_after_validate,
        {
            "continue": "batch_diagnosis",
            "error_handler": "error_handler"
        }
    )
    
    # batch_diagnosis 후 조건부 분기
    graph.add_conditional_edges(
        "batch_diagnosis",
        check_error_after_batch,
        {
            "continue": "compare",
            "error_handler": "error_handler"
        }
    )
    
    # compare 후 조건부 분기
    graph.add_conditional_edges(
        "compare",
        check_error_after_compare,
        {
            "continue": "summarize",
            "error_handler": "error_handler"
        }
    )
    
    # 종료 엣지
    graph.add_edge("summarize", END)
    graph.add_edge("error_handler", END)
    
    return graph.compile()


# === 싱글톤 그래프 ===
_comparison_graph = None


def get_comparison_graph():
    """Comparison Graph 싱글톤 인스턴스"""
    global _comparison_graph
    if _comparison_graph is None:
        _comparison_graph = build_comparison_graph()
        logger.info("Comparison Graph initialized (hybrid pattern with error handling)")
    return _comparison_graph


# === 편의 함수 ===

async def run_comparison_graph(
    repos: list,
    ref: str = "main",
    use_cache: bool = True,
    user_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Comparison Graph 실행
    
    Args:
        repos: 비교할 저장소 목록 ["owner/repo", ...]
        ref: 분석할 브랜치/태그
        use_cache: 캐시 사용 여부
        user_message: 사용자 메시지 (있으면)
    
    Returns:
        ComparisonOutput dict with agent_analysis
    """
    graph = get_comparison_graph()
    
    initial_state: ComparisonState = {
        "repos": repos,
        "ref": ref,
        "use_cache": use_cache,
        "user_message": user_message,
        "validated_repos": None,
        "batch_results": None,
        "comparison_data": None,
        # 에이전트 분석 필드 초기화
        "agent_analysis": None,
        # 캐시 관련
        "cache_hits": None,
        "cache_misses": None,
        "warnings": None,
        # 결과 필드
        "comparison_summary": None,
        "result": None,
        "error": None,
        "execution_path": None
    }
    
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state.get("result", {})
    except Exception as e:
        logger.error(f"[Comparison Agent] Graph execution failed: {e}", exc_info=True)
        # 최상위 예외 처리 - 안전한 결과 반환
        return ComparisonOutput(
            results={},
            comparison_summary=f"비교 그래프 실행 중 오류가 발생했습니다: {e}",
            warnings=[str(e)]
        ).dict()
