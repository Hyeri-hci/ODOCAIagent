"""
초기화 노드
"""
from typing import Dict, Any
from ..state import SecurityAnalysisState


def initialize_node(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    초기화 노드: 입력 검증 및 초기 설정

    Args:
        state: SecurityAnalysisState

    Returns:
        Dict: State 업데이트
    """
    owner = state.get("owner")
    repository = state.get("repository")
    
    # 입력 검증
    if not owner or not repository:
        return {
            "errors": ["Repository owner and name are required"],
            "completed": True,
            "current_step": "error"
        }
    
    # 초기 메시지
    init_message = f"[START] Starting security analysis for {owner}/{repository}"

    print(f"\n{'='*60}")
    print(init_message)
    print(f"{'='*60}\n")
    
    return {
        "current_step": "initialized",
        "messages": [init_message],
        "iteration": 0
    }
