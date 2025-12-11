"""Supervisor planning node."""
from __future__ import annotations
import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


def create_supervisor_plan(state: SupervisorState) -> Dict[str, Any]:
    from backend.agents.supervisor.planner import DynamicPlanner
    
    global_intent = state.global_intent or "chat"
    user_prefs = state.user_preferences or {"focus": [], "ignore": []}
    priority = state.priority or "thoroughness"
    
    try:
        planner = DynamicPlanner()
        context = {
            "owner": state.owner,
            "repo": state.repo,
            "compare_repos": state.user_context.get("compare_repos", []),
            "experience_level": state.user_context.get("experience_level"),
            "branch": state.user_context.get("branch") or state.user_context.get("ref"),
        }
        
        clarification = planner.check_clarification_needed(global_intent, context)
        if clarification and clarification.get("needs_clarification"):
            logger.info(f"Clarification needed: {clarification.get('question')}")
            return {
                "needs_clarification": True,
                "clarification_question": clarification.get("question"),
                "clarification_suggestions": clarification.get("suggestions", []),
                "clarification_missing_info": clarification.get("missing_info"),
                "task_plan": [],
                "step": state.step + 1,
            }
    except Exception as e:
        logger.warning(f"Clarification check failed: {e}")
    
    default_mode = "FULL"
    plan = []
    
    if global_intent == "chat":
        plan.append({
            "step": 1, "agent": "chat", "mode": "AUTO",
            "condition": "always", "description": "일반 채팅"
        })
    elif global_intent == "diagnose":
        # 진단: diagnosis + security (FULL 모드)
        plan.append({
            "step": 1, "agent": "diagnosis", "mode": default_mode,
            "condition": "always", "description": "저장소 진단"
        })
        if "security" not in user_prefs.get("ignore", []):
            plan.append({
                "step": 2, "agent": "security", "mode": "FULL",
                "condition": "always",
                "description": "보안 취약점 분석"
            })
    elif global_intent == "security":
        # 보안 분석 전용
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": "FULL", "condition": "always", "description": "저장소 진단"},
            {"step": 2, "agent": "security", "mode": "FULL", "condition": "always", "description": "보안 취약점 전체 분석"},
        ])
    elif global_intent == "full_audit":
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": "FULL", "condition": "always"},
            {"step": 2, "agent": "security", "mode": "FULL", "condition": "always"},
            {"step": 3, "agent": "onboarding", "mode": "AUTO", "condition": "always"},
        ])
    elif global_intent == "compare":
        # 비교 분석: comparison 에이전트 사용
        compare_repos = state.compare_repos or state.user_context.get("compare_repos", [])
        plan.append({
            "step": 1, "agent": "comparison", "mode": "FULL",
            "condition": "always", 
            "description": f"저장소 비교 분석 ({len(compare_repos)}개)",
            "params": {"repos": compare_repos},
        })
    elif global_intent == "recommend":
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": default_mode, "condition": "always"},
        ])
    elif global_intent == "onboard":
        # 온보딩: diagnosis + onboarding 에이전트
        experience_level = state.user_context.get("experience_level", "beginner")
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": "FAST", "condition": "always", "description": "저장소 구조 파악"},
            {"step": 2, "agent": "onboarding", "mode": "AUTO", "condition": "always", 
             "description": "기여 가이드 생성", "params": {"experience_level": experience_level}},
        ])
    
    logger.info(f"Created plan: {len(plan)} steps for intent={global_intent}")
    return {
        "task_plan": plan,
        "plan_history": [plan],
        "step": state.step + 1,
    }

