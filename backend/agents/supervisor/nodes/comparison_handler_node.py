
import logging
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.agents.comparison.graph import run_comparison_graph

logger = logging.getLogger(__name__)

async def run_comparison_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """
    Comparison Agent 실행 노드.
    
    State의 `compare_repos`를 사용하여 비교 분석을 수행하고 결과를 반환합니다.
    """
    logger.info("Running Comparison Agent")
    
    repos = state.compare_repos
    if not repos:
        logger.warning("No repositories to compare in state")
        return {
            "agent_result": {
                "error": "비교할 저장소 목록이 없습니다."
            },
            "final_answer": "비교할 저장소를 찾을 수 없습니다."
        }
    
    try:
        # Comparison Graph 실행
        result = await run_comparison_graph(
            repos=repos,
            ref=state.ref or "main",
            use_cache=state.use_cache,
            user_message=state.user_message
        )
        
        # 결과 처리
        comparison_summary = result.get("comparison_summary", "")
        warnings = result.get("warnings", [])
        
        return {
            "agent_result": {
                **result,
                "type": "comparison"
            },
            "final_answer": comparison_summary,
            "warnings": list(state.warnings) + warnings,
            "compare_results": result.get("compare_results", {}), # ComparisonOutput 구조에 따름
            "compare_summary": comparison_summary
        }
        
    except Exception as e:
        logger.error(f"Comparison Agent failed: {e}", exc_info=True)
        return {
            "agent_result": {"error": str(e)},
            "final_answer": f"비교 분석 중 오류가 발생했습니다: {str(e)}",
            "error": str(e)
        }
