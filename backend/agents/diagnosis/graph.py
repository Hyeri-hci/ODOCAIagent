"""
Diagnosis Agent Graph - Hybrid Path
Fast/Full/Reinterpret 3가지 경로를 통합한 LangGraph
"""
from typing import Dict, Any, Optional, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging

logger = logging.getLogger(__name__)

from backend.agents.diagnosis.intent_parser import DiagnosisIntentV2
from backend.agents.diagnosis.state import DiagnosisGraphState
# Modularized Node Imports
from backend.agents.diagnosis.nodes.intent_nodes import parse_diagnosis_intent_node
from backend.agents.diagnosis.nodes.cache_nodes import check_cache_node
from backend.agents.diagnosis.nodes.execution_nodes import fast_path_node, full_path_node, reinterpret_path_node
from backend.agents.diagnosis.nodes.routing_nodes import route_execution_node

def build_diagnosis_graph():
    graph = StateGraph(DiagnosisGraphState)
    
    graph.add_node("parse_intent", parse_diagnosis_intent_node)
    graph.add_node("check_cache", check_cache_node)
    graph.add_node("fast_path_node", fast_path_node)
    graph.add_node("full_path_node", full_path_node)
    graph.add_node("reinterpret_path_node", reinterpret_path_node)
    
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "check_cache")
    
    graph.add_conditional_edges(
        "check_cache",
        route_execution_node,
        {
            "fast_path_node": "fast_path_node",
            "full_path_node": "full_path_node",
            "reinterpret_path_node": "reinterpret_path_node"
        }
    )
    graph.add_edge("fast_path_node", END)
    graph.add_edge("full_path_node", END)
    graph.add_edge("reinterpret_path_node", END)
    
    return graph.compile(checkpointer=MemorySaver())

_diagnosis_graph = None

def get_diagnosis_graph():
    global _diagnosis_graph
    if _diagnosis_graph is None:
        _diagnosis_graph = build_diagnosis_graph()
        logger.info("Diagnosis Graph initialized")
    return _diagnosis_graph

async def run_diagnosis(
    owner: str,
    repo: str,
    ref: str = "main",
    user_message: Optional[str] = None,
    supervisor_intent: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    graph = get_diagnosis_graph()
    initial_state: DiagnosisGraphState = {
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

async def run_diagnosis_stream(
    owner: str,
    repo: str,
    ref: str = "main",
    user_message: Optional[str] = None,
    supervisor_intent: Optional[Dict[str, Any]] = None
):
    """
    Diagnosis 그래프 스트리밍 실행 - 각 노드 완료 시 진행 상황 전달.
    
    Yields:
        Dict with keys: step, node, progress, message, data
    """
    graph = get_diagnosis_graph()
    initial_state: DiagnosisGraphState = {
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
    
    node_progress = {
        "parse_intent": {"progress": 20, "message": "의도 분석 중"},
        "check_cache": {"progress": 40, "message": "캐시 확인 중"},
        "fast_path_node": {"progress": 80, "message": "빠른 분석 실행 중"},
        "full_path_node": {"progress": 80, "message": "전체 분석 실행 중"},
        "reinterpret_path_node": {"progress": 80, "message": "재해석 분석 실행 중"},
    }
    
    step = 0
    final_result = None
    
    async for event in graph.astream(initial_state):
        step += 1
        for node_name, node_output in event.items():
            info = node_progress.get(node_name, {"progress": 50, "message": node_name})
            
            yield {
                "step": step,
                "node": node_name,
                "progress": info["progress"],
                "message": info["message"],
                "data": node_output
            }
            
            if node_output.get("result"):
                final_result = node_output.get("result")
    
    yield {
        "step": step + 1,
        "node": "complete",
        "progress": 100,
        "message": "진단 완료",
        "data": {"result": final_result}
    }
