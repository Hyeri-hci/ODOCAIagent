"""
Planner 노드 - Agentic Planning 구현.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from backend.agents.shared.contracts import (
    AgentType,
    ErrorAction,
    PlanStep,
    SupervisorPlanOutput,
    InferenceHints,
)
from backend.common.events import (
    EventType,
    emit_event,
    persist_artifact,
    span,
)
from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)

# Intent 분류 최소 신뢰도 임계값
INTENT_MIN_CONFIDENCE = float(os.getenv("INTENT_MIN_CONF", "0.6"))


def _build_diagnosis_plan(
    state: SupervisorState,
    mode: str = "full",
    reuse_cache: bool = True,
) -> List[PlanStep]:
    """진단 관련 Plan 생성."""
    steps = [
        PlanStep(
            id="fetch_repo_info",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "repo_info", "reuse_cache": reuse_cache},
            needs=[],
            on_error=ErrorAction.FALLBACK,
        ),
        PlanStep(
            id="fetch_readme",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "readme"},
            needs=["fetch_repo_info"],
            on_error=ErrorAction.FALLBACK,
        ),
    ]
    
    if mode in ("full", "activity"):
        steps.extend([
            PlanStep(
                id="compute_activity",
                agent=AgentType.DIAGNOSIS,
                params={"phase": "activity"},
                needs=["fetch_repo_info"],
                on_error=ErrorAction.FALLBACK,
            ),
        ])
    
    # 점수 계산
    steps.append(
        PlanStep(
            id="calc_scores",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "scoring"},
            needs=["fetch_readme", "compute_activity"] if mode in ("full", "activity") else ["fetch_readme"],
            on_error=ErrorAction.FALLBACK,
        )
    )
    
    # 온보딩 Task 생성
    steps.append(
        PlanStep(
            id="generate_tasks",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "onboarding"},
            needs=["calc_scores"],
            on_error=ErrorAction.FALLBACK,
        )
    )
    
    return steps


def _build_compare_plan(state: SupervisorState) -> List[PlanStep]:
    """비교 분석 Plan 생성."""
    return [
        # 첫 번째 저장소 진단
        PlanStep(
            id="diagnose_repo_1",
            agent=AgentType.DIAGNOSIS,
            params={"repo_index": 0},
            needs=[],
            on_error=ErrorAction.FALLBACK,
        ),
        # 두 번째 저장소 진단 (병렬 가능)
        PlanStep(
            id="diagnose_repo_2",
            agent=AgentType.DIAGNOSIS,
            params={"repo_index": 1},
            needs=[],  # 병렬 실행
            on_error=ErrorAction.FALLBACK,
        ),
        # 비교 분석
        PlanStep(
            id="compare_results",
            agent=AgentType.COMPARE,
            params={"style": "detailed"},
            needs=["diagnose_repo_1", "diagnose_repo_2"],
            on_error=ErrorAction.ABORT,
        ),
    ]


def _build_explain_plan(state: SupervisorState) -> List[PlanStep]:
    """점수 해설 Plan 생성."""
    return [
        # 이전 결과가 없으면 진단 먼저
        PlanStep(
            id="ensure_diagnosis",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "full", "reuse_cache": True},
            needs=[],
            on_error=ErrorAction.FALLBACK,
        ),
        # 해설 생성
        PlanStep(
            id="generate_explanation",
            agent=AgentType.RECOMMENDATION,
            params={"style": "explain"},
            needs=["ensure_diagnosis"],
            on_error=ErrorAction.FALLBACK,
        ),
    ]


def _build_refine_plan(state: SupervisorState) -> List[PlanStep]:
    """Task 재필터링 Plan 생성."""
    return [
        PlanStep(
            id="ensure_diagnosis",
            agent=AgentType.DIAGNOSIS,
            params={"phase": "full", "reuse_cache": True},
            needs=[],
            on_error=ErrorAction.FALLBACK,
        ),
        PlanStep(
            id="refine_tasks",
            agent=AgentType.RECOMMENDATION,
            params={"style": "refine"},
            needs=["ensure_diagnosis"],
            on_error=ErrorAction.FALLBACK,
        ),
    ]


def build_plan(state: SupervisorState) -> SupervisorPlanOutput:
    """
    Intent와 SubIntent를 기반으로 실행 계획 수립.
    
    Returns:
        SupervisorPlanOutput: 계획 및 추론 로그
    """
    with span("build_plan", actor="supervisor"):
        intent = state.get("intent", "analyze")
        sub_intent = state.get("sub_intent", "health")
        confidence = state.get("_intent_confidence", 1.0)
        
        emit_event(
            EventType.SUPERVISOR_INTENT_DETECTED,
            outputs={"intent": intent, "sub_intent": sub_intent, "confidence": confidence}
        )
        
        # 신뢰도가 낮으면 disambiguation으로 전환
        if confidence < INTENT_MIN_CONFIDENCE:
            output = SupervisorPlanOutput(
                reasoning_trace=f"신뢰도 {confidence:.2f} < {INTENT_MIN_CONFIDENCE}: 의도 불명확 → disambiguation",
                intent="disambiguation",
                plan=[],
                confidence=confidence,
            )
            
            emit_event(
                EventType.SUPERVISOR_PLAN_BUILT,
                outputs={"plan_len": 0, "intent": "disambiguation", "reason": "low_confidence"}
            )
            
            return output
        
        # Intent별 Plan 생성
        reasoning_parts = []
        plan: List[PlanStep] = []
        artifacts_required: List[str] = []
        mapped_intent = "explain"  # 기본값
        
        if intent == "analyze":
            if sub_intent == "health":
                reasoning_parts.append("건강 분석 요청 → 전체 진단 파이프라인 실행")
                plan = _build_diagnosis_plan(state, mode="full")
                mapped_intent = "explain"
                artifacts_required = ["diagnosis_raw", "activity_metrics"]
                
            elif sub_intent == "onboarding":
                reasoning_parts.append("온보딩 분석 요청 → 진단 + Task 생성 중점")
                plan = _build_diagnosis_plan(state, mode="full")
                mapped_intent = "task_recommendation"
                artifacts_required = ["diagnosis_raw", "onboarding_tasks"]
                
            elif sub_intent == "compare":
                reasoning_parts.append("비교 분석 요청 → 두 저장소 병렬 진단")
                plan = _build_compare_plan(state)
                mapped_intent = "compare"
                artifacts_required = ["diagnosis_raw"]
        
        elif intent == "followup":
            if sub_intent == "explain":
                reasoning_parts.append("점수 해설 요청 → 이전 결과 확인 후 설명 생성")
                plan = _build_explain_plan(state)
                mapped_intent = "explain"
                artifacts_required = ["diagnosis_raw", "python_metrics"]
                
            elif sub_intent == "refine":
                reasoning_parts.append("Task 재필터링 요청 → 조건에 맞는 Task 재정렬")
                plan = _build_refine_plan(state)
                mapped_intent = "task_recommendation"
                artifacts_required = ["onboarding_tasks"]
        
        elif intent == "general_qa":
            # 진단 없이 바로 응답
            reasoning_parts.append("일반 QA 요청 → 진단 없이 LLM 응답")
            plan = []
            mapped_intent = "explain"
        
        # 사용자 컨텍스트 반영
        user_context = state.get("user_context") or {}
        user_level = user_context.get("level", "beginner")
        if user_level == "beginner":
            reasoning_parts.append(f"초보자 → 온보딩 가중치 상향")
        elif user_level == "advanced":
            reasoning_parts.append(f"고급자 → 심화 분석 포함")
        
        reasoning_trace = " | ".join(reasoning_parts)
        
        output = SupervisorPlanOutput(
            reasoning_trace=reasoning_trace,
            intent=mapped_intent,
            plan=plan,
            artifacts_required=artifacts_required,
            confidence=confidence,
        )
        
        # 이벤트 발행
        emit_event(
            EventType.SUPERVISOR_PLAN_BUILT,
            outputs={
                "plan_len": len(plan),
                "intent": mapped_intent,
                "artifacts_required": artifacts_required,
            }
        )
        
        # Artifact로 저장 (추적용)
        persist_artifact(
            kind="plan",
            content={
                "reasoning_trace": reasoning_trace,
                "intent": mapped_intent,
                "plan_steps": [step.model_dump() for step in plan],
            }
        )
        
        return output


def planner_node(state: SupervisorState) -> Dict[str, Any]:
    """LangGraph 노드 함수 - Plan 수립."""
    try:
        plan_output = build_plan(state)
        
        return {
            "plan_output": plan_output,
            "_reasoning_trace": plan_output.reasoning_trace,
            "_plan_steps": plan_output.plan,
            "_mapped_intent": plan_output.intent,
        }
        
    except Exception as e:
        logger.error(f"Plan building failed: {e}")
        emit_event(
            EventType.ERROR_OCCURRED,
            actor="supervisor",
            outputs={"error": str(e), "node": "planner"}
        )
        
        return {
            "error_message": f"계획 수립 중 오류 발생: {e}",
        }
