from typing import Dict, Any
from backend.api.agent_service import run_agent_task

# Legacy wrapper for backward compatibility
def diagnose_repository(
    owner: str, 
    repo: str, 
    ref: str = "main",
    use_llm_summary: bool = True
) -> Dict[str, Any]:
    """
    [Deprecated] Use agent_service.run_agent_task instead.
    """
    return run_agent_task(
        task_type="diagnose_repo",
        owner=owner,
        repo=repo,
        ref=ref,
        use_llm_summary=use_llm_summary
    )

def generate_onboarding_plan(
    owner: str,
    repo: str,
    user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    [Deprecated] Use agent_service.run_agent_task instead.
    """
    return run_agent_task(
        task_type="build_onboarding_plan",
        owner=owner,
        repo=repo,
        user_context=user_context
    )
