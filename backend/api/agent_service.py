import logging
from typing import Dict, Any, Optional
from backend.agents.supervisor.service import run_supervisor_diagnosis, run_supervisor_onboarding
from backend.api.schemas import to_summary_dto

logger = logging.getLogger(__name__)

def run_agent_task(
    task_type: str,
    owner: str,
    repo: str,
    ref: str = "main",
    user_context: Optional[Dict[str, Any]] = None,
    use_llm_summary: bool = True
) -> Dict[str, Any]:
    """
    Unified entry point for running agent tasks.
    
    Args:
        task_type: "diagnose_repo" or "build_onboarding_plan"
        owner: Repository owner
        repo: Repository name
        ref: Branch or commit hash (default: main)
        user_context: Additional context for the task (e.g. user profile)
        use_llm_summary: Whether to use LLM for summary (for diagnosis)
        
    Returns:
        Dict with keys:
            - ok: bool
            - data: Dict (if successful)
            - error: str (if failed)
            - task_type: str
    """
    repo_id = f"{owner}/{repo}@{ref}"
    logger.info(f"Received agent task: {task_type} for {repo_id}")
    
    try:
        if task_type == "diagnose_repo":
            return _handle_diagnose_repo(owner, repo, ref, use_llm_summary)
        elif task_type == "build_onboarding_plan":
            # user_context is required for onboarding plan
            context = user_context or {}
            return _handle_onboarding_plan(owner, repo, context)
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

def _handle_diagnose_repo(owner: str, repo: str, ref: str, use_llm_summary: bool) -> Dict[str, Any]:
    result, error_msg = run_supervisor_diagnosis(
        owner=owner, 
        repo=repo, 
        ref=ref, 
        use_llm_summary=use_llm_summary
    )
    
    if error_msg:
        return {"ok": False, "task_type": "diagnose_repo", "error": error_msg}
        
    if not result:
        return {"ok": False, "task_type": "diagnose_repo", "error": "Diagnosis result is None"}
        
    # DTO Conversion
    repo_id = f"{owner}/{repo}@{ref}"
    dto = to_summary_dto(repo_id, result)
    
    return {
        "ok": True,
        "task_type": "diagnose_repo",
        "data": dto.to_dict()
    }

def _handle_onboarding_plan(owner: str, repo: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
    result, error_msg = run_supervisor_onboarding(owner, repo, user_context)
    
    if error_msg:
        return {"ok": False, "task_type": "build_onboarding_plan", "error": error_msg}
        
    return {
        "ok": True,
        "task_type": "build_onboarding_plan",
        "data": result
    }
