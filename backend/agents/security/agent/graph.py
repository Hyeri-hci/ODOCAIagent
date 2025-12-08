"""
LangGraph 그래프 정의
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from .state import SecurityAnalysisState
from .nodes import (
    initialize_node,
    planning_node,
    validate_plan_node,
    execute_tools_node,
    observe_and_reflect_node,
    generate_report_node
)


def route_after_validation(state: SecurityAnalysisState) -> Literal["execute", "plan"]:
    """
    계획 검증 후 라우팅

    Args:
        state: SecurityAnalysisState

    Returns:
        str: 다음 노드 이름
    """
    if state.get("plan_valid"):
        return "execute"
    else:
        return "plan"


def route_after_observation(state: SecurityAnalysisState) -> Literal["execute", "report", END]:
    """
    관찰 후 라우팅

    Args:
        state: SecurityAnalysisState

    Returns:
        str: 다음 노드 이름
    """
    current_step = state.get("current_step", "")
    iteration = state.get("iteration", 0)
    plan = state.get("plan", [])
    completed = state.get("completed", False)
    
    # 완료됨
    if completed:
        return END
    
    # 레포트 준비
    if current_step == "ready_for_report" or iteration >= len(plan):
        return "report"
    
    # 계속 실행
    if current_step == "continue":
        return "execute"
    
    # 완료
    return "report"


def create_security_analysis_graph() -> StateGraph:
    """
    보안 분석 에이전트 그래프 생성

    Returns:
        StateGraph: 컴파일된 그래프
    """
    # 그래프 생성
    workflow = StateGraph(SecurityAnalysisState)
    
    # 노드 추가
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("plan", planning_node)
    workflow.add_node("validate", validate_plan_node)
    workflow.add_node("execute", execute_tools_node)
    workflow.add_node("observe", observe_and_reflect_node)
    workflow.add_node("report", generate_report_node)
    
    # 엣지 연결
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "plan")
    workflow.add_edge("plan", "validate")
    
    # 조건부 엣지
    workflow.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "execute": "execute",
            "plan": "plan"
        }
    )
    
    workflow.add_edge("execute", "observe")
    
    workflow.add_conditional_edges(
        "observe",
        route_after_observation,
        {
            "execute": "execute",
            "report": "report",
            END: END
        }
    )
    
    workflow.add_edge("report", END)
    
    # 그래프 컴파일
    app = workflow.compile()
    
    return app


# 그래프 시각화 함수 (디버깅용)
def visualize_graph():
    """그래프 구조를 ASCII로 출력"""
    print("""
Security Analysis Agent Graph:

        START
          │
          ▼
    ┌──────────┐
    │Initialize│
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │   Plan   │◀────┐
    └────┬─────┘     │
         │           │
         ▼           │
    ┌──────────┐     │
    │ Validate │     │
    └────┬─────┘     │
         │           │
      [Valid?]       │
         │           │
    ┌────┴────┐      │
    │         │      │
  [Yes]     [No]─────┘
    │
    ▼
┌─────────┐
│ Execute │◀────┐
└────┬────┘     │
     │          │
     ▼          │
┌─────────┐     │
│ Observe │     │
└────┬────┘     │
     │          │
  [Continue?]   │
     │          │
 ┌───┴───┐      │
 │       │      │
[Yes]  [No]     │
 │       │      │
 └───────┘      │
         │
         ▼
    ┌────────┐
    │ Report │
    └────┬───┘
         │
         ▼
        END
    """)
