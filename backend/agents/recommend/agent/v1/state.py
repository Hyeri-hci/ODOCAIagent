# agent/state.py

from typing import TypedDict, List, Dict, Any, Optional, Annotated, Literal
from operator import add
from datetime import datetime
import uuid

# =============================================================================
# 1. Sub-Types Definition (데이터 구조 정의)
# =============================================================================

class TaskIntent(TypedDict):
    """IntentParser가 분석한 사용자 의도"""
    category: Literal["search_criteria", "semantic_search", "url_analysis", "trend_analysis"]
    scope: Literal["global", "similar_to_repo"]
    target_repo: Optional[str]
    original_query: str

class PlanStep(TypedDict):
    """DynamicPlanner가 생성한 개별 실행 단계"""
    step_number: int
    action: str
    description: str
    validation: str
    fallback: str

class ExecutionPlan(TypedDict):
    """전체 실행 계획"""
    steps: List[PlanStep]
    reasoning: str

class ThoughtRecord(TypedDict):
    """에이전트 사고 기록"""
    timestamp: str
    thought: str
    step: int

class ActionRecord(TypedDict):
    """도구 실행 기록"""
    timestamp: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Any
    success: bool
    error: Optional[str]

class ObservationRecord(TypedDict):  # <--- [NEW] 추가됨
    """관찰(Observation) 기록"""
    timestamp: str
    observation: str
    step: int

# =============================================================================
# 2. Main State Definition (메인 상태 정의)
# =============================================================================

class RecommendationState(TypedDict, total=False):
    """GitHub 추천 에이전트 통합 상태"""

    # --- 기본 정보 ---
    session_id: str
    created_at: str
    user_request: str
    
    # --- 분석 및 계획 ---
    parsed_intent: Optional[TaskIntent]
    execution_plan: Optional[ExecutionPlan]
    
    # --- 실행 제어 ---
    iteration: int
    max_iterations: int
    current_step: str
    completed: bool
    
    # --- 기록 (Logs) ---
    thoughts: Annotated[List[ThoughtRecord], add]
    actions: Annotated[List[ActionRecord], add]
    observations: Annotated[List[ObservationRecord], add] # <--- [NEW] 추가됨
    
    # --- 데이터 컨텍스트 ---
    search_queries: Annotated[List[Dict], add]
    raw_candidates: List[Dict]
    analyzed_data: Dict[str, Any]
    rag_queries: Annotated[List[Dict], add]
    filtered_candidates: List[Dict]
    final_report: Dict[str, Any] # <--- str에서 Dict로 변경 (Graph에서 Dict로 넣음)

# =============================================================================
# 3. Helper Functions
# =============================================================================

def create_initial_state(user_request: str, session_id: str = None) -> RecommendationState:
    return RecommendationState(
        session_id=session_id or str(uuid.uuid4()),
        created_at=datetime.now().isoformat(),
        user_request=user_request,
        parsed_intent=None,
        execution_plan=None,
        iteration=0,
        max_iterations=10,
        current_step="init",
        completed=False,
        thoughts=[],
        actions=[],
        observations=[], # <--- [NEW] 초기화
        search_queries=[],
        raw_candidates=[],
        analyzed_data={},
        rag_queries=[],
        filtered_candidates=[],
        final_report={}
    )

def update_thought(state: RecommendationState, thought: str) -> Dict[str, Any]:
    """사고 기록 업데이트"""
    return {
        "thoughts": [{
            "timestamp": datetime.now().isoformat(),
            "thought": thought,
            "step": state.get("iteration", 0)
        }]
    }

def update_action(tool_name: str, parameters: Dict, result: Any, success: bool = True, error: str = None) -> Dict:
    """행동 기록 업데이트"""
    return {
        "actions": [{
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "success": success,
            "error": error
        }]
    }

def update_observation(state: RecommendationState, observation: str) -> Dict[str, Any]: # <--- [NEW] 함수 추가
    """관찰 기록 업데이트"""
    return {
        "observations": [{
            "timestamp": datetime.now().isoformat(),
            "observation": str(observation),
            "step": state.get("iteration", 0)
        }]
    }