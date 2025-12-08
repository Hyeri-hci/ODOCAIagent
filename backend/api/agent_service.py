import logging
from typing import Dict, Any, Optional, List
from backend.agents.supervisor.service import run_supervisor_diagnosis, run_supervisor_onboarding
from backend.api.schemas import to_summary_dto

logger = logging.getLogger(__name__)

def run_agent_task(
    task_type: str,
    owner: str,
    repo: str,
    ref: str = "main",
    user_context: Optional[Dict[str, Any]] = None,
    use_llm_summary: bool = True,
    debug_trace: bool = False,
    user_message: Optional[str] = None,
    priority: str = "thoroughness"
) -> Dict[str, Any]:
    """
    Unified entry point for running agent tasks.
    
    메타 에이전트 지원: user_message와 priority로 동적 계획 수립.
    
    Args:
        task_type: "diagnose_repo" or "build_onboarding_plan"
        owner: Repository owner
        repo: Repository name
        ref: Branch or commit hash (default: main)
        user_context: Additional context for the task (e.g. user profile)
        use_llm_summary: Whether to use LLM for summary (for diagnosis)
        debug_trace: Whether to include execution trace (default: False)
        user_message: User analysis request message (meta agent)
        priority: Analysis priority (speed or thoroughness) (meta agent)
        
    Returns:
        Dict with keys:
            - ok: bool
            - data: Dict (if successful)
            - error: str (if failed)
            - task_type: str
            - trace: List[Dict] (if debug_trace=True)
    """
    repo_id = f"{owner}/{repo}@{ref}"
    logger.info(f"Received agent task: {task_type} for {repo_id} (trace={debug_trace}, user_message={user_message}, priority={priority})")
    
    try:
        if task_type in ["diagnose_repo", "general_inquiry"]:
            return _handle_diagnose_repo(owner, repo, ref, use_llm_summary, debug_trace, user_message, priority, task_type)
        elif task_type == "build_onboarding_plan":
            # user_context is required for onboarding plan
            context = user_context or {}
            return _handle_onboarding_plan(owner, repo, context, debug_trace)
        else:
            return {
                "ok": False,
                "task_type": task_type,
                "error": f"Unknown task_type: {task_type}"
            }
            
    except Exception as e:
        logger.exception(f"Agent task failed: {e}")
        return {
            "ok": False,
            "task_type": task_type,
            "error": str(e)
        }

def _handle_diagnose_repo(
    owner: str, 
    repo: str, 
    ref: str, 
    use_llm_summary: bool,
    debug_trace: bool = False,
    user_message: Optional[str] = None,
    priority: str = "thoroughness",
    task_type: str = "diagnose_repo"
) -> Dict[str, Any]:
    result, error_msg, trace = run_supervisor_diagnosis(
        owner=owner,
        repo=repo, 
        ref=ref, 
        use_llm_summary=use_llm_summary,
        debug_trace=debug_trace,
        user_message=user_message,
        priority=priority,
        task_type=task_type
    )
    
    if error_msg:
        response = {"ok": False, "task_type": "diagnose_repo", "error": error_msg}
        if debug_trace and trace:
            response["trace"] = trace
        return response
        
    if not result:
        response = {"ok": False, "task_type": "diagnose_repo", "error": "Diagnosis result is None"}
        if debug_trace and trace:
            response["trace"] = trace
        return response
        
    # DTO Conversion
    repo_id = f"{owner}/{repo}@{ref}"
    dto = to_summary_dto(repo_id, result)
    
    response = {
        "ok": True,
        "task_type": "diagnose_repo",
        "data": dto.to_dict()
    }
    
    if debug_trace and trace:
        response["trace"] = trace
    
    return response

def _handle_onboarding_plan(
    owner: str, 
    repo: str, 
    user_context: Dict[str, Any],
    debug_trace: bool = False
) -> Dict[str, Any]:
    result, error_msg, trace = run_supervisor_onboarding(
        owner, 
        repo, 
        user_context,
        debug_trace=debug_trace
    )
    
    if error_msg:
        response = {"ok": False, "task_type": "build_onboarding_plan", "error": error_msg}
        if debug_trace and trace:
            response["trace"] = trace
        return response
        
    response = {
        "ok": True,
        "task_type": "build_onboarding_plan",
        "data": result
    }
    
    if debug_trace and trace:
        response["trace"] = trace
    
    return response

