"""
계획 검증 노드
"""
from typing import Dict, Any
from ..state import SecurityAnalysisState


def validate_plan_node(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    계획 검증 노드: 계획의 타당성 검증

    Args:
        state: SecurityAnalysisState

    Returns:
        Dict: State 업데이트
    """
    plan = state.get("plan", [])
    
    if not plan or len(plan) == 0:
        return {
            "plan_valid": False,
            "plan_feedback": "계획이 비어 있습니다.",
            "current_step": "plan_invalid"
        }
    
    # 필수 단계 확인
    required_keywords = ["의존성", "보안", "레포트"]
    plan_text = " ".join(plan).lower()
    
    feedback = []
    for keyword in required_keywords:
        if keyword not in plan_text:
            feedback.append(f"필수 단계 누락: {keyword} 관련 작업")
    
    is_valid = len(feedback) == 0
    
    if is_valid:
        print("[OK] Plan validation: PASSED\n")
    else:
        print("[WARNING]  Plan validation: FAILED")
        for fb in feedback:
            print(f"  - {fb}")
        print()
    
    return {
        "plan_valid": is_valid,
        "plan_feedback": "\n".join(feedback) if feedback else "계획이 타당합니다.",
        "current_step": "plan_validated" if is_valid else "plan_invalid"
    }
