"""
관찰 및 반성 노드
"""
from typing import Dict, Any
from ..state import SecurityAnalysisState


def observe_and_reflect_node(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    관찰 및 반성 노드: 실행 결과를 관찰하고 다음 행동 결정

    Args:
        state: SecurityAnalysisState

    Returns:
        Dict: State 업데이트
    """
    plan = state.get("plan", [])
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 10)
    
    dependencies = state.get("dependencies")
    security_score = state.get("security_score")
    recommendations = state.get("recommendations", [])
    errors = state.get("errors", [])
    
    print(f"\n[REFLECT] Reflection:")
    print(f"  - Progress: {iteration}/{len(plan)} steps completed")
    print(f"  - Dependencies analyzed: {'[OK]' if dependencies else '[ERROR]'}")
    print(f"  - Security score calculated: {'[OK]' if security_score else '[ERROR]'}")
    print(f"  - Recommendations generated: {'[OK]' if recommendations else '[ERROR]'}")
    print(f"  - Errors: {len(errors)}")
    
    # 결정 로직
    decision = None
    reason = ""
    
    # 1. 에러가 너무 많으면 중단
    if len(errors) >= 3:
        decision = "COMPLETE"
        reason = "Too many errors occurred"
        print(f"\n[WARNING]  Decision: {decision} ({reason})")
        return {
            "current_step": "completed",
            "completed": True,
            "messages": [f"분석 중단: {reason}"]
        }
    
    # 2. 모든 계획 완료
    if iteration >= len(plan):
        decision = "COMPLETE"
        reason = "All planned steps completed"
        print(f"\n[OK] Decision: {decision} ({reason})")
        return {
            "current_step": "completed",
            "completed": False,  # 레포트 생성 남음
            "messages": ["모든 분석 단계 완료"]
        }
    
    # 3. 최대 반복 횟수 도달
    if iteration >= max_iterations:
        decision = "COMPLETE"
        reason = "Max iterations reached"
        print(f"\n[WARNING]  Decision: {decision} ({reason})")
        return {
            "current_step": "completed",
            "completed": False,
            "messages": [f"최대 반복 횟수 도달: {max_iterations}"]
        }
    
    # 4. 계속 진행
    decision = "CONTINUE"
    reason = "More steps to complete"
    print(f"\n[CONTINUE]  Decision: {decision} ({reason})\n")
    
    return {
        "current_step": "continue",
        "messages": ["다음 단계 진행"]
    }
