
from typing import Optional, List, Dict, Any
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.core.models import DiagnosisCoreResult, ProjectRules, UserGuidelines
import logging
from backend.agents.supervisor.models import SupervisorInput, SupervisorState
from backend.agents.supervisor.trace import TracingCallbackHandler
from backend.agents.supervisor.memory import get_conversation_memory, ConversationMemory
from backend.common.logging_config import setup_logging
from backend.common.metrics import get_metrics_tracker, TaskMetrics

logger = logging.getLogger(__name__)
setup_logging()


def init_state_from_input(
    inp: SupervisorInput,
    session_id: Optional[str] = None,
    load_context: bool = True,
) -> SupervisorState:
    """
    SupervisorInput을 기반으로 초기 SupervisorState를 생성합니다.
    
    Args:
        inp: SupervisorInput 객체
        session_id: 세션 식별자 (None이면 owner/repo 기반 생성)
        load_context: True면 기존 대화 컨텍스트 로드
    """
    effective_session_id = session_id or f"{inp.owner}/{inp.repo}"
    long_term_context = None
    
    if load_context:
        try:
            memory = get_conversation_memory()
            context = memory.get_context(effective_session_id)
            long_term_context = context.summary
        except Exception as e:
            logger.warning(f"Failed to load conversation context: {e}")
    
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
        session_id=effective_session_id,
        long_term_context=long_term_context,
        flow_adjustments=[],
        warnings=[],
        analysis_depth="standard",
        compare_repos=[],
        compare_results={},
        compare_summary=None,
    )


def save_conversation_turn(
    session_id: str,
    user_message: str,
    assistant_message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """대화 턴을 메모리에 저장합니다."""
    try:
        memory = get_conversation_memory()
        memory.add_turn(session_id, user_message, assistant_message, metadata)
    except Exception as e:
        logger.warning(f"Failed to save conversation turn: {e}")


def get_conversation_context(session_id: str) -> Dict[str, Any]:
    """세션의 대화 컨텍스트를 조회합니다."""
    try:
        memory = get_conversation_memory()
        context = memory.get_context(session_id)
        return context.to_dict()
    except Exception as e:
        logger.warning(f"Failed to get conversation context: {e}")
        return {"session_id": session_id, "recent_turns": [], "summary": None}


def check_memory_status() -> Dict[str, Any]:
    """메모리 백엔드 상태를 확인합니다."""
    try:
        memory = get_conversation_memory()
        return {
            "backend_type": memory.backend_type,
            "redis_available": memory.is_redis_available(),
        }
    except Exception as e:
        logger.error(f"Failed to check memory status: {e}")
        return {
            "backend_type": "unknown",
            "redis_available": False,
            "error": str(e),
        }

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
    
    # 메트릭 추적 시작
    tracker = get_metrics_tracker()
    metrics = tracker.start_task("diagnose_repo", owner, repo)
    
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
    
    # 5. 결과 추출 및 메트릭 수집
    error_msg = result.get("error")
    if error_msg:
        logger.error(f"[{task_info}] Diagnosis failed: {error_msg}")
        metrics.complete(success=False, error=error_msg)
    else:
        logger.info(f"[{task_info}] Diagnosis completed successfully")
        metrics.complete(success=True)
    
    # Agent 결정 정보 수집
    metrics.detected_intent = result.get("detected_intent")
    metrics.decision_reason = result.get("decision_reason")
    metrics.flow_adjustments = result.get("flow_adjustments", [])
    metrics.cache_hit = result.get("cache_hit", False)
    metrics.rerun_count = result.get("rerun_count", 0)
    
    # 메트릭 기록
    tracker.record_task(metrics)

    # 6. Trace 수집
    trace = trace_handler.get_trace() if trace_handler else None
    
    # 7. diagnosis_result에 agentic 메타데이터 병합
    diagnosis_result = result.get("diagnosis_result")
    if diagnosis_result and isinstance(diagnosis_result, dict):
        diagnosis_result["warnings"] = result.get("warnings", [])
        diagnosis_result["flow_adjustments"] = result.get("flow_adjustments", [])
    
    return diagnosis_result, error_msg, trace


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

