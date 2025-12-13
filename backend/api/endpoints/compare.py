"""
Compare 엔드포인트 - 저장소 비교 분석
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class CompareRequest(BaseModel):
    """비교 분석 요청."""
    repositories: List[str] = Field(
        ..., 
        description="비교할 저장소 목록 (예: ['owner1/repo1', 'owner2/repo2'])",
        min_length=2,
        max_length=5,
    )


class CompareResponse(BaseModel):
    """비교 분석 응답."""
    ok: bool
    comparison: Optional[Dict[str, Any]] = None
    individual_results: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    warnings: List[str] = []
    error: Optional[str] = None


def parse_github_url(url: str) -> tuple[str, str, str]:
    """GitHub URL에서 owner, repo, ref 추출."""
    import re
    
    # https://github.com/owner/repo 형식
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?", url)
    if match:
        return match.group(1), match.group(2).rstrip(".git"), match.group(3) or "main"
    
    # owner/repo 형식
    if "/" in url and not url.startswith("http"):
        parts = url.split("/")
        if len(parts) == 2:
            return parts[0], parts[1], "main"
        elif len(parts) == 3:
            return parts[0], parts[1], parts[2]
    
    raise ValueError(f"Invalid GitHub URL format: {url}")


@router.post("/analyze/compare", response_model=CompareResponse)
async def compare_repositories(request: CompareRequest) -> CompareResponse:
    """저장소 비교 분석."""
    from backend.agents.supervisor.graph import get_supervisor_graph
    from backend.agents.supervisor.models import SupervisorInput, SupervisorState
    from backend.agents.supervisor.service import init_state_from_input
    
    repos = request.repositories
    
    if len(repos) < 2:
        raise HTTPException(status_code=400, detail="최소 2개의 저장소가 필요합니다.")
    
    if len(repos) > 5:
        raise HTTPException(status_code=400, detail="최대 5개의 저장소까지 비교 가능합니다.")
    
    try:
        first_repo = repos[0]
        try:
            owner, repo, _ = parse_github_url(first_repo)
        except ValueError:
            if "/" in first_repo:
                owner, repo = first_repo.split("/", 1)
            else:
                raise HTTPException(status_code=400, detail=f"잘못된 저장소 형식: {first_repo}")
        
        graph = get_supervisor_graph()
        config = {"configurable": {"thread_id": f"compare_{owner}/{repo}"}}
        
        inp = SupervisorInput(
            task_type="general_inquiry",
            owner=owner,
            repo=repo,
            user_context={"intent": "compare"},
            user_message=f"Compare repositories: {', '.join(repos)}"
        )
        
        initial_state = init_state_from_input(inp)
        initial_state_dict = initial_state.model_dump()
        initial_state_dict["detected_intent"] = "compare"
        initial_state_dict["compare_repos"] = repos
        
        # 비동기 노드를 사용하므로 ainvoke 사용 필수
        result = await graph.ainvoke(SupervisorState(**initial_state_dict), config=config)
        
        comparison_data = {
            "repositories": {},
        }
        
        for repo_str, data in result.get("compare_results", {}).items():
            comparison_data["repositories"][repo_str] = {
                "health_score": data.get("health_score", 0),
                "onboarding_score": data.get("onboarding_score", 0),
                "health_level": data.get("health_level", "unknown"),
                "onboarding_level": data.get("onboarding_level", "unknown"),
                "documentation_quality": data.get("documentation_quality", 0),
                "activity_maintainability": data.get("activity_maintainability", 0),
            }
        
        if comparison_data["repositories"]:
            scores = [(r, d["health_score"]) for r, d in comparison_data["repositories"].items()]
            scores.sort(key=lambda x: x[1], reverse=True)
            comparison_data["ranking"] = [r for r, _ in scores]
            comparison_data["best_health"] = scores[0][0] if scores else None
            
            onboard_scores = [(r, d["onboarding_score"]) for r, d in comparison_data["repositories"].items()]
            onboard_scores.sort(key=lambda x: x[1], reverse=True)
            comparison_data["best_onboarding"] = onboard_scores[0][0] if onboard_scores else None
        
        return CompareResponse(
            ok=True,
            comparison=comparison_data,
            individual_results=result.get("compare_results", {}),
            summary=result.get("compare_summary"),
            warnings=result.get("warnings", []),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Compare analysis failed: {e}")
        return CompareResponse(
            ok=False,
            error=str(e),
            warnings=[],
        )
