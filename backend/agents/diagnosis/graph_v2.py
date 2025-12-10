"""
Diagnosis Agent V2 - Hybrid Graph
Fast/Full/Reinterpret 3가지 경로를 통합한 LangGraph
"""

from typing import Dict, Any, Optional, TypedDict, Literal
from langgraph.graph import StateGraph, END
import logging

from backend.agents.diagnosis.intent_parser import DiagnosisIntentParser, DiagnosisIntentV2
from backend.agents.diagnosis.router import route_diagnosis_request, determine_cache_strategy
from backend.agents.diagnosis.fast_path import execute_fast_path
from backend.agents.diagnosis.full_path import execute_full_path
from backend.agents.diagnosis.reinterpret_path import execute_reinterpret_path
from backend.common.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)


# === State 정의 ===
class DiagnosisStateV2(TypedDict):
    """Diagnosis Agent V2 State"""
    
    # 필수 필드
    owner: str
    repo: str
    ref: str
    use_cache: bool
    execution_time_ms: int
    
    # 선택 필드
    user_message: Optional[str]
    supervisor_intent: Optional[Dict[str, Any]]
    diagnosis_intent: Optional[DiagnosisIntentV2]
    cache_key: Optional[str]
    cached_result: Optional[Dict[str, Any]]
    execution_path: Optional[Literal["fast_path", "full_path", "reinterpret_path"]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


# === 노드 함수들 ===
async def parse_diagnosis_intent_node(state: DiagnosisStateV2) -> Dict[str, Any]:
    """Diagnosis 의도 파싱"""
    logger.info("Parsing diagnosis intent")
    
    parser = DiagnosisIntentParser()
    
    user_msg = state.get("user_message") or ""
    supervisor_int = state.get("supervisor_intent") or {}
    
    intent = await parser.parse(
        user_message=user_msg,
        supervisor_intent=supervisor_int,
        cached_diagnosis=state.get("cached_result")
    )
    
    return {
        "diagnosis_intent": intent
    }


async def check_cache_node(state: DiagnosisStateV2) -> Dict[str, Any]:
    """캐시 확인"""
    logger.info("Checking cache")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    cache_manager = get_cache_manager()
    
    # 캐시 전략 결정
    strategy = determine_cache_strategy(
        intent=intent,
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main")
    )
    
    cache_key = strategy["cache_key"]
    use_cache = strategy["use_cache"]
    
    # 캐시 조회
    cached_result = None
    if use_cache:
        cached_result = cache_manager.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit: {cache_key}")
        else:
            logger.info(f"Cache miss: {cache_key}")
    
    return {
        "cache_key": cache_key,
        "cached_result": cached_result,
        "use_cache": use_cache
    }


def route_execution_node(state: DiagnosisStateV2) -> Literal["fast_path_node", "full_path_node", "reinterpret_path_node"]:
    """실행 경로 라우팅"""
    intent = state.get("diagnosis_intent")
    if not intent:
        return "fast_path_node"  # 기본값
    
    cached_result = state.get("cached_result")
    path = route_diagnosis_request(intent, cached_result)
    
    logger.info(f"Routed to: {path}")
    
    # 노드 이름으로 매핑
    if path == "fast_path":
        return "fast_path_node"
    elif path == "full_path":
        return "full_path_node"
    else:
        return "reinterpret_path_node"


async def fast_path_node(state: DiagnosisStateV2) -> Dict[str, Any]:
    """Fast Path 실행"""
    logger.info("Executing fast path")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    target = intent.quick_query_target or "readme"
    result = await execute_fast_path(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main"),
        target=target,
        cached_result=state.get("cached_result")
    )
    
    return {
        "result": result,
        "execution_path": "fast_path"
    }


async def full_path_node(state: DiagnosisStateV2) -> Dict[str, Any]:
    """Full Path 실행"""
    logger.info("Executing full path")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    analysis_depth = intent.analysis_depth or 2
    force_refresh = intent.force_refresh or False
    
    result = await execute_full_path(
        owner=state["owner"],
        repo=state["repo"],
        ref=state.get("ref", "main"),
        analysis_depth=analysis_depth,
        use_llm_summary=True,
        force_refresh=force_refresh
    )
    
    # 캐시 저장
    cache_key = state.get("cache_key")
    if not result.get("error") and cache_key and intent:
        cache_manager = get_cache_manager()
        strategy = determine_cache_strategy(
            intent=intent,
            owner=state["owner"],
            repo=state["repo"],
            ref=state.get("ref", "main")
        )
        cache_manager.set(
            key=cache_key,
            data=result,
            ttl_hours=strategy["ttl_hours"]
        )
        logger.info(f"Result cached: {cache_key}")
    
    return {
        "result": result,
        "execution_path": "full_path"
    }


async def reinterpret_path_node(state: DiagnosisStateV2) -> Dict[str, Any]:
    """Reinterpret Path 실행"""
    logger.info("Executing reinterpret path")
    
    intent = state.get("diagnosis_intent")
    if not intent:
        return {"error": "Missing diagnosis intent"}
    
    cached_result = state.get("cached_result")
    if not cached_result:
        logger.error("Reinterpret path requires cached result")
        return {
            "result": {
                "type": "reinterpret",
                "error": "No cached result available"
            },
            "execution_path": "reinterpret_path",
            "error": "No cached result"
        }
    
    perspective = intent.reinterpret_perspective or "beginner"
    detail_level = intent.reinterpret_detail_level or "standard"
    
    result = await execute_reinterpret_path(
        cached_result=cached_result,
        perspective=perspective,
        detail_level=detail_level,
        user_question=state.get("user_message")
    )
    
    return {
        "result": result,
        "execution_path": "reinterpret_path"
    }


# === 그래프 빌드 ===
def build_diagnosis_graph_v2():
    """Diagnosis Agent V2 그래프 빌드"""
    
    graph = StateGraph(DiagnosisStateV2)
    
    # 노드 추가
    graph.add_node("parse_intent", parse_diagnosis_intent_node)
    graph.add_node("check_cache", check_cache_node)
    graph.add_node("fast_path_node", fast_path_node)
    graph.add_node("full_path_node", full_path_node)
    graph.add_node("reinterpret_path_node", reinterpret_path_node)
    
    # 엣지 연결
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "check_cache")
    
    # 라우팅
    graph.add_conditional_edges(
        "check_cache",
        route_execution_node,
        {
            "fast_path_node": "fast_path_node",
            "full_path_node": "full_path_node",
            "reinterpret_path_node": "reinterpret_path_node"
        }
    )
    
    # 종료
    graph.add_edge("fast_path_node", END)
    graph.add_edge("full_path_node", END)
    graph.add_edge("reinterpret_path_node", END)
    
    return graph.compile()


# === 싱글톤 그래프 ===
_diagnosis_graph_v2 = None

def get_diagnosis_graph_v2():
    """Diagnosis Graph V2 싱글톤 인스턴스"""
    global _diagnosis_graph_v2
    if _diagnosis_graph_v2 is None:
        _diagnosis_graph_v2 = build_diagnosis_graph_v2()
        logger.info("Diagnosis Graph V2 initialized")
    return _diagnosis_graph_v2


# === 편의 함수 ===
async def run_diagnosis_v2(
    owner: str,
    repo: str,
    ref: str = "main",
    user_message: Optional[str] = None,
    supervisor_intent: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Diagnosis Agent V2 실행
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        ref: 브랜치/태그
        user_message: 사용자 메시지
        supervisor_intent: Supervisor가 파싱한 의도
    
    Returns:
        진단 결과
    """
    
    graph = get_diagnosis_graph_v2()
    
    initial_state: DiagnosisStateV2 = {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "user_message": user_message or f"{owner}/{repo} 저장소를 진단해주세요",
        "supervisor_intent": supervisor_intent,
        "use_cache": True,
        "execution_time_ms": 0,
        "diagnosis_intent": None,
        "cache_key": None,
        "cached_result": None,
        "execution_path": None,
        "result": None,
        "error": None
    }
    
    final_state = await graph.ainvoke(initial_state)
    
    return final_state.get("result", {})
