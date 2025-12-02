"""PlanBuilder: Generates execution plans based on intent and context."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from backend.agents.supervisor.planner.models import (
    Plan,
    PlanStep,
    ErrorPolicy,
)

logger = logging.getLogger(__name__)


# Plan Templates: pre-defined step sequences for each intent
PLAN_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    # analyze.health: 저장소 건강 진단
    "analyze.health": [
        {
            "id": "fetch_repo",
            "runner": "diagnosis",
            "params": {"task_type": "full"},
            "needs": [],
            "on_error": "fallback",
            "timeout_sec": 30.0,
        },
    ],
    
    # analyze.onboarding: 온보딩 중심 진단
    "analyze.onboarding": [
        {
            "id": "fetch_repo",
            "runner": "diagnosis",
            "params": {"task_type": "full", "focus": "onboarding"},
            "needs": [],
            "on_error": "fallback",
            "timeout_sec": 30.0,
        },
    ],
    
    # analyze.compare: 두 저장소 비교
    "analyze.compare": [
        {
            "id": "fetch_repo_a",
            "runner": "diagnosis",
            "params": {"repo_key": "repo_a"},
            "needs": [],
            "on_error": "fallback",
        },
        {
            "id": "fetch_repo_b",
            "runner": "diagnosis",
            "params": {"repo_key": "repo_b"},
            "needs": [],
            "on_error": "fallback",
        },
        {
            "id": "compare",
            "runner": "compare",
            "params": {},
            "needs": ["fetch_repo_a", "fetch_repo_b"],
            "on_error": "ask_user",
        },
    ],
    
    # followup.explain: 점수 설명
    "followup.explain": [
        {
            "id": "explain",
            "runner": "followup",
            "params": {"mode": "explain"},
            "needs": [],
            "on_error": "fallback",
            "timeout_sec": 15.0,
        },
    ],
    
    # followup.evidence: 근거 제시
    "followup.evidence": [
        {
            "id": "evidence",
            "runner": "followup",
            "params": {"mode": "evidence"},
            "needs": [],
            "on_error": "fallback",
            "timeout_sec": 15.0,
        },
    ],
    
    # overview.repo: 저장소 개요
    "overview.repo": [
        {
            "id": "fetch_overview",
            "runner": "overview",
            "params": {},
            "needs": [],
            "on_error": "fallback",
            "timeout_sec": 20.0,
        },
    ],
    
    # smalltalk/help: 경량 경로 (단일 스텝)
    "smalltalk.greeting": [
        {
            "id": "respond",
            "runner": "smalltalk",
            "params": {"mode": "greeting"},
            "needs": [],
            "on_error": "abort",
            "timeout_sec": 5.0,
        },
    ],
    
    "smalltalk.chitchat": [
        {
            "id": "respond",
            "runner": "smalltalk",
            "params": {"mode": "chitchat"},
            "needs": [],
            "on_error": "abort",
            "timeout_sec": 5.0,
        },
    ],
    
    "help.getting_started": [
        {
            "id": "respond",
            "runner": "help",
            "params": {},
            "needs": [],
            "on_error": "abort",
            "timeout_sec": 5.0,
        },
    ],
    
    "general_qa.chat": [
        {
            "id": "respond",
            "runner": "chat",
            "params": {},
            "needs": [],
            "on_error": "abort",
            "timeout_sec": 10.0,
        },
    ],
}

# Artifacts required by each plan template
ARTIFACTS_REQUIRED: Dict[str, List[str]] = {
    "analyze.health": ["diagnosis_raw", "activity_metrics", "readme_analysis"],
    "analyze.onboarding": ["diagnosis_raw", "onboarding_tasks", "readme_analysis"],
    "analyze.compare": ["diagnosis_raw_a", "diagnosis_raw_b"],
    "followup.explain": ["diagnosis_raw", "prev_answer"],
    "followup.evidence": ["diagnosis_raw", "prev_answer"],
    "overview.repo": ["repo_metadata", "readme_raw"],
    "smalltalk.greeting": [],
    "smalltalk.chitchat": [],
    "help.getting_started": [],
    "general_qa.chat": [],
}


class PlanBuilder:
    """Builds execution plans from intent and context."""
    
    def __init__(
        self,
        intent: str,
        sub_intent: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.intent = intent
        self.sub_intent = sub_intent
        self.context = context or {}
        self._reasoning_parts: List[str] = []
    
    def build(self) -> Plan:
        """Generates a Plan based on intent and context."""
        start_time = time.time()
        
        plan_key = f"{self.intent}.{self.sub_intent}"
        self._log(f"Building plan for {plan_key}")
        
        # Get template
        template = PLAN_TEMPLATES.get(plan_key)
        if not template:
            self._log(f"No template for {plan_key}, using fallback")
            template = self._create_fallback_template()
        
        # Create steps from template
        steps = self._create_steps_from_template(template)
        
        # Inject context params
        self._inject_context_params(steps)
        
        # Get required artifacts
        artifacts = ARTIFACTS_REQUIRED.get(plan_key, [])
        
        # Generate plan ID
        plan_id = self._generate_plan_id()
        
        elapsed = (time.time() - start_time) * 1000
        self._log(f"Plan built in {elapsed:.1f}ms: {len(steps)} steps")
        
        return Plan(
            id=plan_id,
            intent=self.intent,
            sub_intent=self.sub_intent,
            steps=steps,
            artifacts_required=artifacts,
            reasoning_trace="\n".join(self._reasoning_parts),
        )
    
    def _create_steps_from_template(self, template: List[Dict]) -> List[PlanStep]:
        """Converts template dicts to PlanStep objects."""
        steps = []
        for t in template:
            on_error = ErrorPolicy(t.get("on_error", "fallback"))
            step = PlanStep(
                id=t["id"],
                runner=t["runner"],
                params=dict(t.get("params", {})),
                needs=list(t.get("needs", [])),
                on_error=on_error,
                timeout_sec=t.get("timeout_sec", 30.0),
                max_retries=t.get("max_retries", 1),
            )
            steps.append(step)
        return steps
    
    def _inject_context_params(self, steps: List[PlanStep]) -> None:
        """Injects context values into step params."""
        repo = self.context.get("repo")
        user_context = self.context.get("user_context", {})
        
        for step in steps:
            # Inject repo info
            if repo and "repo" not in step.params:
                step.params["repo"] = repo
            
            # Inject user context
            if user_context and "user_context" not in step.params:
                step.params["user_context"] = user_context
            
            # Handle compare: inject both repos
            if step.runner == "compare":
                if "repo_a" not in step.params:
                    step.params["repo_a"] = repo
                if "repo_b" not in step.params:
                    step.params["repo_b"] = self.context.get("compare_repo")
    
    def _create_fallback_template(self) -> List[Dict]:
        """Creates a minimal fallback template."""
        self._log("Using generic fallback template")
        return [
            {
                "id": "fallback_respond",
                "runner": "chat",
                "params": {"fallback": True},
                "needs": [],
                "on_error": "abort",
                "timeout_sec": 10.0,
            }
        ]
    
    def _generate_plan_id(self) -> str:
        """Generates unique plan ID."""
        content = f"{self.intent}.{self.sub_intent}.{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def _log(self, msg: str) -> None:
        """Adds to reasoning trace and logs."""
        self._reasoning_parts.append(msg)
        logger.debug(f"[PlanBuilder] {msg}")


def build_plan(
    intent: str,
    sub_intent: str,
    context: Optional[Dict[str, Any]] = None,
) -> Plan:
    """Convenience function to build a plan."""
    builder = PlanBuilder(intent, sub_intent, context)
    return builder.build()


def get_plan_template(intent: str, sub_intent: str) -> Optional[List[Dict]]:
    """Returns plan template for the given intent."""
    return PLAN_TEMPLATES.get(f"{intent}.{sub_intent}")
