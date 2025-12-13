"""
Supervisor Graph - 세션 기반 메타 에이전트
"""

from typing import Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging

from backend.agents.supervisor.models import SupervisorState
from backend.common.session import get_session_store

# Import Nodes
from backend.agents.supervisor.nodes.session_nodes import load_or_create_session_node, update_session_node
from backend.agents.supervisor.nodes.intent_parser_node import parse_intent_node, check_clarification_node, clarification_response_node
from backend.agents.supervisor.nodes.diagnosis_handler_node import run_diagnosis_agent_node
from backend.agents.supervisor.nodes.onboarding_handler_node import run_onboarding_agent_node
from backend.agents.supervisor.nodes.security_handler_node import run_security_agent_node
# DEPRECATED: contributor_handler_node - absorbed into onboarding_handler_node
# from backend.agents.supervisor.nodes.contributor_handler_node import run_contributor_agent_node
from backend.agents.supervisor.nodes.recommend_handler_node import run_recommend_agent_node
from backend.agents.supervisor.nodes.comparison_handler_node import run_comparison_agent_node
from backend.agents.supervisor.nodes.chat_handler_node import chat_response_node
from backend.agents.supervisor.nodes.finalize_handler_node import finalize_answer_node
from backend.agents.supervisor.nodes.parallel_execution_node import run_additional_agents_node

logger = logging.getLogger(__name__)

# === 그래프 빌드 ===

def build_supervisor_graph(enable_hitl: bool = False):
    """
    Supervisor Graph 빌드
    
    Args:
        enable_hitl: Human-in-the-Loop 패턴 활성화.
                     True면 clarification_response 노드 전에 중단.
    """
    
    graph = StateGraph(SupervisorState)
    
    # 노드 추가
    graph.add_node("load_session", load_or_create_session_node)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("clarification_response", clarification_response_node)
    graph.add_node("run_diagnosis_agent", run_diagnosis_agent_node)
    graph.add_node("run_onboarding_agent", run_onboarding_agent_node)
    graph.add_node("run_security_agent", run_security_agent_node)
    graph.add_node("run_recommend_agent", run_recommend_agent_node)
    # DEPRECATED: run_contributor_agent - redirected to run_onboarding_agent
    graph.add_node("run_comparison_agent", run_comparison_agent_node)
    graph.add_node("chat_response", chat_response_node)
    graph.add_node("finalize_answer", finalize_answer_node)
    graph.add_node("update_session", update_session_node)
    
    # 추가 에이전트 실행 노드
    graph.add_node("run_additional_agents", run_additional_agents_node)
    
    # 엣지 연결
    graph.set_entry_point("load_session")
    graph.add_edge("load_session", "parse_intent")
    
    # Clarification 체크 및 Agent 라우팅
    def combined_routing(state: SupervisorState) -> Literal[
        "clarification_response", "run_diagnosis_agent", "run_onboarding_agent", 
        "run_security_agent", "run_recommend_agent", 
        "run_comparison_agent", "chat_response"
    ]:
        """Clarification 체크 후 Agent 라우팅"""
        if state.get("needs_clarification", False):
            return "clarification_response"
        
        # Agent 라우팅
        target = state.get("target_agent")
        if not target:
            return "chat_response"
        
        if target == "diagnosis":
            return "run_diagnosis_agent"
        elif target in ("onboarding", "contributor"):
            # contributor → onboarding 리다이렉트 (Unified Onboarding Agent)
            return "run_onboarding_agent"
        elif target == "security":
            return "run_security_agent"
        elif target == "recommend":
            return "run_recommend_agent"
        elif target == "comparison":
            return "run_comparison_agent"
        else:
            return "chat_response"
    
    graph.add_conditional_edges(
        "parse_intent",
        combined_routing,
        {
            "clarification_response": "clarification_response",
            "run_diagnosis_agent": "run_diagnosis_agent",
            "run_onboarding_agent": "run_onboarding_agent",
            "run_security_agent": "run_security_agent",
            "run_recommend_agent": "run_recommend_agent",
            # DEPRECATED: run_contributor_agent - absorbed into onboarding
            "run_comparison_agent": "run_comparison_agent",
            "chat_response": "chat_response"
        }
    )
    
    # Clarification 응답 → 종료
    graph.add_edge("clarification_response", "update_session")
    
    # 모든 agent → run_additional_agents → finalize
    graph.add_edge("run_diagnosis_agent", "run_additional_agents")
    graph.add_edge("run_onboarding_agent", "run_additional_agents")
    graph.add_edge("run_security_agent", "run_additional_agents")
    graph.add_edge("run_recommend_agent", "run_additional_agents")
    # DEPRECATED: run_contributor_agent edge removed (absorbed into onboarding)
    graph.add_edge("run_comparison_agent", "run_additional_agents")
    graph.add_edge("run_additional_agents", "finalize_answer")
    graph.add_edge("chat_response", "update_session")
    
    # finalize → update_session
    graph.add_edge("finalize_answer", "update_session")
    
    # update_session → END
    graph.add_edge("update_session", END)
    
    return graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["clarification_response"] if enable_hitl else None
    )


# === 싱글톤 그래프 ===
_supervisor_graph = None

def get_supervisor_graph():
    """Supervisor Graph 싱글톤 인스턴스"""
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = build_supervisor_graph()
        logger.info("Supervisor Graph initialized")
    return _supervisor_graph


# === 편의 함수 ===

async def run_supervisor(
    owner: str,
    repo: str,
    user_message: str,
    session_id: Optional[str] = None,
    ref: str = "main"
) -> Dict[str, Any]:
    """
    Supervisor 실행
    
    Returns:
        {
            "session_id": "uuid",
            "final_answer": "...",
            "suggested_actions": [...],
            "awaiting_clarification": False
        }
    """
    
    graph = get_supervisor_graph()
    
    # 세션 ID가 없으면 미리 생성 (LangGraph Checkpointer에 thread_id가 필요함)
    if not session_id:
        from backend.common.session import get_session_store
        session_store = get_session_store()
        session = session_store.create_session(owner=owner, repo=repo, ref=ref)
        session_id = session.session_id
        logger.info(f"Initialized new session in run_supervisor: {session_id}")
    
    from typing import cast
    initial_state: SupervisorState = cast(SupervisorState, {
        "session_id": session_id,
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "user_message": user_message,
        "is_new_session": False,
        "supervisor_intent": None,
        "needs_clarification": False,
        "clarification_questions": [],
        "awaiting_clarification": False,
        "conversation_history": [],
        "accumulated_context": {},
        "target_agent": None,
        "agent_params": {},
        "agent_result": None,
        "final_answer": None,
        "suggested_actions": [],
        "iteration": 0,
        "max_iterations": 10,
        "next_node_override": None,
        "error": None,
        "trace_id": None
    })
    
    # checkpointer 설정 (thread_id 필수)
    config = {"configurable": {"thread_id": session_id}}
    
    final_state = await graph.ainvoke(initial_state, config=config)
    
    # 최종 상태에서 owner/repo 추출 (세션에서 업데이트된 값 사용)
    final_owner = final_state.get("owner") or owner
    final_repo = final_state.get("repo") or repo
    
    return {
        "session_id": final_state.get("session_id"),
        "final_answer": final_state.get("final_answer"),
        "suggested_actions": final_state.get("suggested_actions", []),
        "awaiting_clarification": final_state.get("awaiting_clarification", False),
        "target_agent": final_state.get("target_agent"),
        "agent_result": final_state.get("agent_result"),
        "diagnosis_result": final_state.get("diagnosis_result"),
        "onboarding_result": final_state.get("onboarding_result"),  # 온보딩 결과
        "multi_agent_results": final_state.get("multi_agent_results", {}),
        "security_result": final_state.get("security_result") or final_state.get("multi_agent_results", {}).get("security"),
        "structure_visualization": final_state.get("structure_visualization"),
        "needs_clarification": final_state.get("needs_clarification", False),
        "large_repo_warning": final_state.get("large_repo_warning"),  # 대용량 저장소 경고
        "owner": final_owner,  # 프론트엔드 동기화용
        "repo": final_repo,    # 프론트엔드 동기화용
    }
