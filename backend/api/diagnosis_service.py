from typing import Dict, Any, Optional
from backend.agents.supervisor.service import run_supervisor_diagnosis
from backend.api.schemas import to_summary_dto

def diagnose_repository(
    owner: str, 
    repo: str, 
    ref: str = "main",
    use_llm_summary: bool = True
) -> Dict[str, Any]:
    """
    저장소를 진단하고 프론트엔드에서 사용하기 쉬운 형태의 결과를 반환합니다.
    
    Returns:
        Dict: {
            "ok": bool,
            "data": Dict (성공 시),
            "error": str (실패 시)
        }
    """
    repo_id = f"{owner}/{repo}@{ref}"
    
    try:
        result, error_msg = run_supervisor_diagnosis(
            owner=owner, 
            repo=repo, 
            ref=ref, 
            use_llm_summary=use_llm_summary
        )
        
        if error_msg:
            return {
                "ok": False,
                "repo_id": repo_id,
                "error": error_msg
            }
            
        if not result:
            return {
                "ok": False,
                "repo_id": repo_id,
                "error": "Unknown error: Diagnosis result is None"
            }
            
        # DTO 변환
        dto = to_summary_dto(repo_id, result)
        
        return {
            "ok": True,
            "data": dto.to_dict()
        }
        
    except Exception as e:
        return {
            "ok": False,
            "repo_id": repo_id,
            "error": str(e)
        }
