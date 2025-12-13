"""
Comparison Agent Validation Nodes
입력 검증 및 안전한 노드 실행 데코레이터를 정의합니다.
"""

import logging
from typing import Dict, Any, Callable
from functools import wraps

from backend.agents.comparison.models import ComparisonState

logger = logging.getLogger(__name__)

# === 예외 처리 데코레이터 ===

def safe_node(default_updates: Dict[str, Any] = None):
    """
    노드 함수에 안전한 예외 처리를 추가하는 데코레이터
    
    Args:
        default_updates: 예외 발생 시 반환할 기본 상태 업데이트
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: ComparisonState) -> Dict[str, Any]:
            node_name = func.__name__.replace("_node", "")
            try:
                return await func(state)
            except Exception as e:
                logger.error(f"[Comparison Agent] {node_name} failed: {e}", exc_info=True)
                
                # 기본 업데이트 값 설정
                updates = default_updates.copy() if default_updates else {}
                updates["error"] = str(e)
                updates["execution_path"] = (state.get("execution_path") or "") + f" → {node_name}(ERROR)"
                
                return updates
        return wrapper
    return decorator


@safe_node(default_updates={"validated_repos": [], "warnings": []})
async def validate_input_node(state: ComparisonState) -> Dict[str, Any]:
    """입력 검증 - 최소 2개 저장소 필요"""
    logger.info(f"[Comparison Agent] Validating input: {len(state.get('repos', []))} repos")
    
    repos = state.get("repos", [])
    warnings = []
    validated_repos = []
    
    if len(repos) < 2:
        return {
            "error": "비교 분석에는 최소 2개의 저장소가 필요합니다.",
            "warnings": ["비교 분석에는 최소 2개의 저장소가 필요합니다."],
            "validated_repos": [],
            "execution_path": "comparison_graph:validate_input(ERROR)"
        }
    
    # 저장소 형식 검증
    for repo in repos:
        if "/" in repo:
            validated_repos.append(repo)
        else:
            warnings.append(f"잘못된 저장소 형식: {repo}")
    
    if len(validated_repos) < 2:
        return {
            "error": "유효한 저장소가 2개 이상 필요합니다.",
            "warnings": warnings,
            "validated_repos": validated_repos,
            "execution_path": "comparison_graph:validate_input(ERROR)"
        }
    
    logger.info(f"[Comparison Agent] Validated {len(validated_repos)} repos")
    
    return {
        "validated_repos": validated_repos,
        "warnings": warnings,
        "execution_path": "comparison_graph:validate_input",
        "error": None
    }
