"""
계획 수립 노드
"""
from typing import Dict, Any
from ..state import SecurityAnalysisState


def planning_node(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    계획 수립 노드: 분석 작업 계획 수립

    Args:
        state: SecurityAnalysisState

    Returns:
        Dict: State 업데이트
    """
    owner = state.get("owner")
    repository = state.get("repository")
    
    # 기본 계획 수립 (규칙 기반)
    plan = [
        "의존성 파일 찾기 및 분석",
        "보안 점수 계산",
        "개선 사항 제안",
        "최종 레포트 생성"
    ]
    
    # 이미 의존성 분석이 완료되었다면 계획 조정
    if state.get("dependencies"):
        plan = [
            "보안 점수 계산",
            "개선 사항 제안",
            "최종 레포트 생성"
        ]
    
    print(f"\n[PLAN] Analysis Plan:")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step}")
    print()
    
    return {
        "plan": plan,
        "current_step": "planned",
        "plan_valid": True,
        "messages": [f"계획 수립 완료: {len(plan)}개 단계"]
    }
