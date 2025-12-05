
from typing import Optional
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.core.models import DiagnosisCoreResult, ProjectRules, UserGuidelines
import logging
from backend.agents.supervisor.models import SupervisorInput, SupervisorState
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
    )

def run_supervisor_diagnosis(
    owner: str,
    repo: str,
    ref: str = "main",
    use_llm_summary: bool = True
) -> tuple[Optional[dict], Optional[str]]:
    """
    Supervisor를 통해 저장소 진단을 실행하는 엔트리 포인트.
    """

    task_info = f"task=diagnose_repo owner={owner} repo={repo} ref={ref}"
    logger.info(f"[{task_info}] Starting diagnosis (LLM Summary: {use_llm_summary})")
    
    # 1. 그래프 생성
    graph = get_supervisor_graph()
    
    # 2. 초기 상태 구성
    config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}
    
    # SupervisorInput 생성
    inp = SupervisorInput(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        user_context={"use_llm_summary": use_llm_summary}
    )
    
    initial_state = init_state_from_input(inp)
    
    # 3. 그래프 실행
    # invoke를 사용하여 동기적으로 실행 완료 대기
    result = graph.invoke(initial_state, config=config)
    
    # 4. 결과 추출
    if result.get("error"):
        logger.error(f"[{task_info}] Diagnosis failed: {result.get('error')}")
    else:
        logger.info(f"[{task_info}] Diagnosis completed successfully")

    # SupervisorState에서 diagnosis_result와 error 반환
    return result.get("diagnosis_result"), result.get("error")


def run_supervisor_diagnosis_with_guidelines(
    owner: str,
    repo: str,
    ref: str = "main",
    project_rules: Optional[ProjectRules] = None,
    session_guidelines: Optional[UserGuidelines] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """
    지침(Rules/Guidelines)을 포함하여 Supervisor 진단을 실행하는 확장 엔트리 포인트.
    """
    # 1. 그래프 생성
    graph = get_supervisor_graph()
    
    # 2. 초기 상태 구성
    config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}
    
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
    
    # 3. 그래프 실행
    result = graph.invoke(initial_state, config=config)
    
    # 4. 결과 반환
    return result.get("diagnosis_result"), result.get("error")

def run_supervisor_onboarding(
    owner: str,
    repo: str,
    user_context: dict
) -> tuple[Optional[dict], Optional[str]]:
    """
    온보딩 플랜 생성을 실행하는 엔트리 포인트.
    Returns: (result_dict, error_msg)
    result_dict includes: diagnosis, onboarding_plan, onboarding_summary, candidate_issues
    """
    task_info = f"task=build_onboarding_plan owner={owner} repo={repo}"
    logger.info(f"[{task_info}] Starting onboarding plan generation")
    
    graph = get_supervisor_graph()
    config = {"configurable": {"thread_id": f"{owner}/{repo}@onboarding"}}
    
    inp = SupervisorInput(
        task_type="build_onboarding_plan",
        owner=owner,
        repo=repo,
        user_context=user_context
    )
    
    initial_state = init_state_from_input(inp)
    result = graph.invoke(initial_state, config=config)
    
    if result.get("error"):
        logger.error(f"[{task_info}] Onboarding plan failed: {result.get('error')}")
        return None, result.get("error")
        
    logger.info(f"[{task_info}] Onboarding plan completed successfully")
    
    output = {
        "diagnosis": result.get("diagnosis_result"),
        "onboarding_plan": result.get("onboarding_plan"),
        "onboarding_summary": result.get("onboarding_summary"),
        "candidate_issues": result.get("candidate_issues")
    }
    return output, None
