"""Supervisor 계획 실행 노드."""
from __future__ import annotations
import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.agent_runners import (
    run_diagnosis_agent,
    run_security_agent,
    run_recommend_agent,
    run_onboarding_agent,
    extract_diagnosis_summary,
    extract_security_summary,
    extract_recommend_summary,
)

logger = logging.getLogger(__name__)


def execute_supervisor_plan(state: SupervisorState) -> Dict[str, Any]:
    """task_plan 순차 실행."""
    task_plan = state.task_plan or []
    task_results = dict(state.task_results) if state.task_results else {}
    
    for step_config in task_plan:
        agent_name = step_config.get("agent")
        mode = step_config.get("mode", "AUTO")
        condition = step_config.get("condition", "always")
        params = step_config.get("params", {})
        
        if not evaluate_condition(condition, task_results):
            logger.info(f"Skip {agent_name}: {condition}")
            continue
        
        logger.info(f"Execute {agent_name} ({mode})")
        
        if agent_name == "chat":
            # Chat 에이전트 실행
            result = run_chat_agent(state, mode)
            task_results["chat"] = {"response": result.get("response", "")}
        elif agent_name == "diagnosis":
            result = run_diagnosis_agent(state, mode)
            task_results["diagnosis"] = extract_diagnosis_summary(result)
        elif agent_name == "security":
            result = run_security_agent(state, mode)
            task_results["security"] = extract_security_summary(result)
        elif agent_name == "recommend":
            result = run_recommend_agent(state, mode)
            task_results["recommend"] = extract_recommend_summary(result)
        elif agent_name == "onboarding":
            # Onboarding 에이전트 실행 (새 서비스 사용)
            result = _run_new_onboarding_agent(state, mode, params)
            task_results["onboarding"] = result
        elif agent_name == "comparison":
            # Comparison 에이전트 실행
            result = run_comparison_agent(state, mode, params)
            task_results["comparison"] = result
    
    logger.info(f"Plan executed: {list(task_results.keys())}")
    return {
        "task_results": task_results,
        "step": state.step + 1,
    }


def run_chat_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """Chat 에이전트 실행."""
    from backend.agents.chat.service import run_chat
    from backend.agents.chat.models import ChatInput
    
    input_data = ChatInput(
        message=state.chat_message or state.user_message or "",
        owner=state.owner,
        repo=state.repo,
        intent=state.detected_intent or "chat",
        diagnosis_result=state.diagnosis_result or {},
        chat_context=state.chat_context or {},
        candidate_issues=list(state.candidate_issues),
    )
    
    result = run_chat(input_data)
    return {"response": result.response, "error": result.error}


def _run_new_onboarding_agent(state: SupervisorState, mode: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Onboarding 에이전트 실행 (새 서비스 사용)."""
    from backend.agents.onboarding.service import run_onboarding
    from backend.agents.onboarding.models import OnboardingInput
    
    params = params or {}
    experience_level = params.get("experience_level", "beginner")
    diagnosis_summary = ""
    if state.diagnosis_result:
        diagnosis_summary = state.diagnosis_result.get("summary_for_user", "")
    
    input_data = OnboardingInput(
        owner=state.owner,
        repo=state.repo,
        experience_level=experience_level,
        diagnosis_summary=diagnosis_summary,
        user_context=state.user_context or {},
    )
    
    result = run_onboarding(input_data)
    return {
        "plan": result.plan,
        "candidate_issues": result.candidate_issues,
        "summary": result.summary,
        "error": result.error,
    }


def run_comparison_agent(state: SupervisorState, mode: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Comparison 에이전트 실행."""
    from backend.agents.comparison.service import run_comparison
    from backend.agents.comparison.models import ComparisonInput
    
    params = params or {}
    repos = params.get("repos", [])
    
    # state에서도 비교 대상 저장소 확인
    if not repos:
        repos = state.compare_repos or state.user_context.get("compare_repos", [])
    
    input_data = ComparisonInput(
        repos=repos,
        ref="main",
        use_cache=True,
    )
    
    result = run_comparison(input_data)
    return {
        "results": result.results,
        "summary": result.comparison_summary,
        "warnings": result.warnings,
    }


def evaluate_condition(condition: str, results: Dict[str, Any]) -> bool:
    """실행 조건 평가."""
    if condition == "always":
        return True
    
    if condition.startswith("if "):
        cond_expr = condition[3:].strip()
        try:
            if "diagnosis.health_score" in cond_expr:
                health_score = results.get("diagnosis", {}).get("health_score")
                if health_score is None:
                    return False
                
                if "<" in cond_expr:
                    threshold = int(cond_expr.split("<")[1].strip())
                    return health_score < threshold
                elif ">" in cond_expr:
                    threshold = int(cond_expr.split(">")[1].strip())
                    return health_score > threshold
        except Exception as e:
            logger.warning(f"Condition eval failed: {e}")
            return False
    
    return False

