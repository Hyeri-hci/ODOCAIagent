
from typing import Optional, List, Dict, Any
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.core.models import DiagnosisCoreResult, ProjectRules, UserGuidelines
import logging
from backend.agents.supervisor.models import SupervisorInput, SupervisorState
from backend.agents.supervisor.trace import TracingCallbackHandler
from backend.common.logging_config import setup_logging

logger = logging.getLogger(__name__)
# Ensure logging is setup (idempotent-ish)
setup_logging()

def init_state_from_input(inp: SupervisorInput) -> SupervisorState:
    """SupervisorInput을 기반으로 초기 SupervisorState를 생성합니다."""
    return SupervisorState(
        task_type=inp.task_type,
        owner=inp.owner,
        repo=inp.repo,
        user_context=inp.user_context,
        messages=[],
        step=0,
        max_step=10,
        diagnosis_result=None,
        candidate_issues=[],
        onboarding_plan=None,
        last_answer_kind="none",
        last_explain_target=None,
        error=None,
        detected_intent=None,
        intent_confidence=0.0,
        decision_reason=None,
        next_node_override=None,
        rerun_count=0,
        max_rerun=2,
        quality_issues=[],
        use_cache=True,
        cache_hit=False,
    )

def run_supervisor_diagnosis(
    owner: str,
    repo: str,
    ref: str = "main",
    use_llm_summary: bool = True,
    debug_trace: bool = False
) -> tuple[Optional[dict], Optional[str], Optional[List[Dict[str, Any]]]]:
    """
    Supervisor를 통해 저장소 진단을 실행하는 엔트리 포인트.
    
    Args:
        owner: GitHub 저장소 소유자
        repo: 저장소 이름
        ref: 브랜치 또는 커밋 (기본: main)
        use_llm_summary: LLM 요약 사용 여부
        debug_trace: 노드 실행 추적 활성화 여부
        
    Returns:
        tuple: (diagnosis_result, error_msg, trace)
            - trace는 debug_trace=True일 때만 포함됨
    """

    task_info = f"task=diagnose_repo owner={owner} repo={repo} ref={ref}"
    logger.info(f"[{task_info}] Starting diagnosis (LLM Summary: {use_llm_summary}, Trace: {debug_trace})")
    
    # 1. 그래프 생성
    graph = get_supervisor_graph()
    
    # 2. 초기 상태 구성
    config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}
    
    # 3. Trace 모드 설정
    trace_handler = None
    if debug_trace:
        trace_handler = TracingCallbackHandler()
        config["callbacks"] = [trace_handler]
    
    # SupervisorInput 생성
    inp = SupervisorInput(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        user_context={"use_llm_summary": use_llm_summary}
    )
    
    initial_state = init_state_from_input(inp)
    
    # 4. 그래프 실행
    result = graph.invoke(initial_state, config=config)
    
    # 5. 결과 추출
    if result.get("error"):
        logger.error(f"[{task_info}] Diagnosis failed: {result.get('error')}")
    else:
        logger.info(f"[{task_info}] Diagnosis completed successfully")

    # 6. Trace 수집
    trace = trace_handler.get_trace() if trace_handler else None
    
    return result.get("diagnosis_result"), result.get("error"), trace


def run_supervisor_diagnosis_with_guidelines(
    owner: str,
    repo: str,
    ref: str = "main",
    project_rules: Optional[ProjectRules] = None,
    session_guidelines: Optional[UserGuidelines] = None,
    debug_trace: bool = False
) -> tuple[Optional[dict], Optional[str], Optional[List[Dict[str, Any]]]]:
    """
    지침(Rules/Guidelines)을 포함하여 Supervisor 진단을 실행하는 확장 엔트리 포인트.
    """
    # 1. 그래프 생성
    graph = get_supervisor_graph()
    
    # 2. 초기 상태 구성
    config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}
    
    # 3. Trace 모드 설정
    trace_handler = None
    if debug_trace:
        trace_handler = TracingCallbackHandler()
        config["callbacks"] = [trace_handler]
    
    inp = SupervisorInput(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        user_context={
            "project_rules": project_rules,
            "session_guidelines": session_guidelines
        }
    )
    
    initial_state = init_state_from_input(inp)
    
    # 4. 그래프 실행
    result = graph.invoke(initial_state, config=config)
    
    # 5. Trace 수집
    trace = trace_handler.get_trace() if trace_handler else None
    
    return result.get("diagnosis_result"), result.get("error"), trace

def run_supervisor_onboarding(
    owner: str,
    repo: str,
    user_context: dict,
    debug_trace: bool = False
) -> tuple[Optional[dict], Optional[str], Optional[List[Dict[str, Any]]]]:
    """
    온보딩 플랜 생성을 실행하는 엔트리 포인트.
    
    Returns: (result_dict, error_msg, trace)
        result_dict includes: diagnosis, onboarding_plan, onboarding_summary, candidate_issues
    """
    task_info = f"task=build_onboarding_plan owner={owner} repo={repo}"
    logger.info(f"[{task_info}] Starting onboarding plan generation (Trace: {debug_trace})")
    
    graph = get_supervisor_graph()
    config = {"configurable": {"thread_id": f"{owner}/{repo}@onboarding"}}
    
    # Trace 모드 설정
    trace_handler = None
    if debug_trace:
        trace_handler = TracingCallbackHandler()
        config["callbacks"] = [trace_handler]
    
    inp = SupervisorInput(
        task_type="build_onboarding_plan",
        owner=owner,
        repo=repo,
        user_context=user_context
    )
    
    initial_state = init_state_from_input(inp)
    result = graph.invoke(initial_state, config=config)
    
    # Trace 수집
    trace = trace_handler.get_trace() if trace_handler else None
    
    if result.get("error"):
        logger.error(f"[{task_info}] Onboarding plan failed: {result.get('error')}")
        return None, result.get("error"), trace
        
    logger.info(f"[{task_info}] Onboarding plan completed successfully")
    
    output = {
        "diagnosis": result.get("diagnosis_result"),
        "onboarding_plan": result.get("onboarding_plan"),
        "onboarding_summary": result.get("onboarding_summary"),
        "candidate_issues": result.get("candidate_issues")
    }
    return output, None, trace

