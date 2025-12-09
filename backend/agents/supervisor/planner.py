"""DynamicPlanner - 동적 실행 계획 생성 클래스."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from backend.common.config import LLM_MODEL_NAME, LLM_API_BASE, LLM_API_KEY

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    """실행 계획 단계."""
    step: int
    agent: str  # diagnosis, security, onboarding, chat
    mode: str  # FAST, FULL, AUTO
    condition: str  # always, if <조건>
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "agent": self.agent,
            "mode": self.mode,
            "condition": self.condition,
            "description": self.description,
        }


@dataclass
class ExecutionPlan:
    """실행 계획."""
    primary_task_type: str
    steps: List[ExecutionStep] = field(default_factory=list)
    secondary_tasks: List[str] = field(default_factory=list)
    suggested_sequence: List[str] = field(default_factory=list)
    estimated_duration: int = 0  # 초 단위
    complexity: str = "moderate"  # simple, moderate, complex
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_task_type": self.primary_task_type,
            "steps": [s.to_dict() for s in self.steps],
            "secondary_tasks": self.secondary_tasks,
            "suggested_sequence": self.suggested_sequence,
            "estimated_duration": self.estimated_duration,
            "complexity": self.complexity,
        }


# DynamicPlanner용 프롬프트 템플릿
PLANNING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 GitHub 저장소 분석 시스템의 계획 수립 전문가입니다.

사용자의 의도와 선호를 기반으로 최적의 실행 계획을 수립하세요.

[사용 가능한 에이전트]
- diagnosis: 저장소 건강/품질 진단
- security: 보안 취약점 분석
- onboarding: 기여자 온보딩 가이드 생성
- chat: 일반 대화/설명

[실행 모드]
- FAST: 빠른 분석 (핵심 지표만)
- FULL: 상세 분석 (모든 지표)
- AUTO: 저장소 크기에 따라 자동 결정

[조건 표현식]
- always: 항상 실행
- if diagnosis.health_score < 50: 조건부 실행
- if security in focus: 사용자 선호에 따라 실행

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "primary_task_type": "diagnose|security|onboard|compare|full_audit",
  "steps": [
    {{"step": 1, "agent": "diagnosis", "mode": "AUTO", "condition": "always", "description": "저장소 진단"}},
    {{"step": 2, "agent": "security", "mode": "FAST", "condition": "if diagnosis.health_score < 50", "description": "보안 분석"}}
  ],
  "secondary_tasks": ["security", "onboarding"],
  "suggested_sequence": ["diagnosis", "security", "onboarding"],
  "estimated_duration": 30,
  "complexity": "moderate"
}}"""),
    ("user", """사용자 의도: {intent}
저장소: {owner}/{repo}
사용자 선호: {user_preferences}
우선순위: {priority}

최적의 실행 계획을 수립해주세요.""")
])


VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 실행 계획 검증 전문가입니다.

주어진 계획이 사용자 의도와 선호에 부합하는지 검증하세요.

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "is_valid": true/false,
  "issues": ["발견된 문제 1", "발견된 문제 2"],
  "suggestions": ["개선 제안 1", "개선 제안 2"],
  "confidence": 0.0-1.0
}}"""),
    ("user", """사용자 의도: {intent}
사용자 선호: {user_preferences}
현재 계획: {plan}

이 계획을 검증해주세요.""")
])


class DynamicPlanner:
    """
    Security Agent 패턴을 적용한 동적 계획 생성 클래스.
    
    LangChain ChatPromptTemplate과 체인 파이프라인을 사용하여
    LangSmith 추적이 가능한 구조화된 계획 생성을 제공합니다.
    """
    
    def __init__(
        self,
        llm_base_url: str = None,
        llm_api_key: str = None,
        llm_model: str = None,
        llm_temperature: float = 0.1,
    ):
        """DynamicPlanner 초기화."""
        self.llm = ChatOpenAI(
            model=llm_model or LLM_MODEL_NAME,
            api_key=llm_api_key or LLM_API_KEY,
            base_url=llm_base_url or LLM_API_BASE,
            temperature=llm_temperature
        )
        self.planning_prompt = PLANNING_PROMPT
        self.validation_prompt = VALIDATION_PROMPT
        
    def create_plan(
        self,
        intent: str,
        owner: str,
        repo: str,
        user_preferences: Dict[str, Any] = None,
        priority: str = "thoroughness",
    ) -> ExecutionPlan:
        """
        사용자 의도와 선호를 기반으로 실행 계획 생성.
        
        Args:
            intent: 사용자 의도 (diagnose, security, onboard, etc.)
            owner: 저장소 소유자
            repo: 저장소 이름
            user_preferences: 사용자 선호 {"focus": [], "ignore": []}
            priority: 우선순위 (speed/thoroughness)
            
        Returns:
            ExecutionPlan 객체
        """
        user_preferences = user_preferences or {"focus": [], "ignore": []}
        
        response = None
        try:
            chain = self.planning_prompt | self.llm
            response = chain.invoke({
                "intent": intent,
                "owner": owner,
                "repo": repo,
                "user_preferences": json.dumps(user_preferences, ensure_ascii=False),
                "priority": priority,
            })
            raw_content = response.content.strip()
            
            # JSON 추출
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(raw_content)
            
            # ExecutionPlan 생성
            steps = []
            for step_data in parsed.get("steps", []):
                steps.append(ExecutionStep(
                    step=step_data.get("step", len(steps) + 1),
                    agent=step_data.get("agent", "diagnosis"),
                    mode=step_data.get("mode", "AUTO"),
                    condition=step_data.get("condition", "always"),
                    description=step_data.get("description", ""),
                ))
            
            return ExecutionPlan(
                primary_task_type=parsed.get("primary_task_type", intent),
                steps=steps,
                secondary_tasks=parsed.get("secondary_tasks", []),
                suggested_sequence=parsed.get("suggested_sequence", []),
                estimated_duration=parsed.get("estimated_duration", 30),
                complexity=parsed.get("complexity", "moderate"),
            )
            
        except Exception as e:
            logger.error(f"DynamicPlanner.create_plan failed: {e}, raw_response={response}")
            # 폴백: 기본 계획 반환
            return self._create_fallback_plan(intent, priority)
    
    def validate_plan(
        self,
        plan: ExecutionPlan,
        intent: str,
        user_preferences: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        실행 계획 검증.
        
        Args:
            plan: 검증할 계획
            intent: 사용자 의도
            user_preferences: 사용자 선호
            
        Returns:
            검증 결과 {"is_valid": bool, "issues": [], "suggestions": [], "confidence": float}
        """
        user_preferences = user_preferences or {"focus": [], "ignore": []}
        
        response = None
        try:
            chain = self.validation_prompt | self.llm
            response = chain.invoke({
                "intent": intent,
                "user_preferences": json.dumps(user_preferences, ensure_ascii=False),
                "plan": json.dumps(plan.to_dict(), ensure_ascii=False),
            })
            raw_content = response.content.strip()
            
            # JSON 추출
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()
            
            return json.loads(raw_content)
            
        except Exception as e:
            logger.error(f"DynamicPlanner.validate_plan failed: {e}, raw_response={response}")
            return {"is_valid": True, "issues": [], "suggestions": [], "confidence": 0.5}
    
    def replan(
        self,
        current_plan: ExecutionPlan,
        execution_results: Dict[str, Any],
        user_preferences: Dict[str, Any] = None,
    ) -> ExecutionPlan:
        """
        실행 결과를 기반으로 계획 재수립.
        
        Args:
            current_plan: 현재 계획
            execution_results: 실행 결과
            user_preferences: 사용자 선호
            
        Returns:
            수정된 ExecutionPlan
        """
        # 실행 결과 분석
        diagnosis_result = execution_results.get("diagnosis", {})
        health_score = diagnosis_result.get("health_score", 100)
        
        new_steps = list(current_plan.steps)
        
        # 조건부 단계 활성화/비활성화
        for step in new_steps:
            if "if diagnosis.health_score" in step.condition:
                # 조건 파싱 (간단한 구현)
                if "< 50" in step.condition and health_score < 50:
                    step.condition = "always"  # 조건 만족, 실행
                elif "> 50" in step.condition and health_score > 50:
                    step.condition = "always"
                else:
                    step.condition = "skip"  # 조건 불만족, 스킵
        
        # 스킵할 단계 제거
        new_steps = [s for s in new_steps if s.condition != "skip"]
        
        # 새 계획 반환
        return ExecutionPlan(
            primary_task_type=current_plan.primary_task_type,
            steps=new_steps,
            secondary_tasks=current_plan.secondary_tasks,
            suggested_sequence=current_plan.suggested_sequence,
            estimated_duration=current_plan.estimated_duration,
            complexity=current_plan.complexity,
        )
    
    def apply_reflection_adjustments(
        self,
        current_plan: ExecutionPlan,
        reflection_result: Dict[str, Any],
        execution_results: Dict[str, Any] = None,
    ) -> ExecutionPlan:
        """
        Reflection 결과에 따라 계획 조정.
        
        plan_adjustments 예시:
        - "add_security_full": Security Agent FULL 모드 추가
        - "upgrade_diagnosis_full": Diagnosis를 FULL로 승급
        - "add_onboarding": Onboarding 에이전트 추가
        
        Args:
            current_plan: 현재 계획
            reflection_result: Reflection 결과 {"should_replan": bool, "plan_adjustments": [...]}
            execution_results: 실행 결과
            
        Returns:
            조정된 ExecutionPlan
        """
        if not reflection_result.get("should_replan", False):
            return current_plan
        
        adjustments = reflection_result.get("plan_adjustments", [])
        new_steps = list(current_plan.steps)
        new_secondary = list(current_plan.secondary_tasks)
        
        for adj in adjustments:
            # 문자열 형태의 조정 처리
            if isinstance(adj, str):
                adj_lower = adj.lower()
                
                # Security FULL 추가
                if "add_security_full" in adj_lower or "security_full" in adj_lower:
                    new_steps.append(ExecutionStep(
                        step=len(new_steps) + 1,
                        agent="security",
                        mode="FULL",
                        condition="always",
                        description="Reflection 기반 보안 심층 분석",
                    ))
                    if "security" not in new_secondary:
                        new_secondary.append("security")
                
                # Diagnosis FULL 승급
                elif "upgrade_diagnosis_full" in adj_lower or "diagnosis_full" in adj_lower:
                    for step in new_steps:
                        if step.agent == "diagnosis" and step.mode != "FULL":
                            step.mode = "FULL"
                            step.description = "FAST→FULL 승급됨"
                
                # Onboarding 추가
                elif "add_onboarding" in adj_lower:
                    new_steps.append(ExecutionStep(
                        step=len(new_steps) + 1,
                        agent="onboarding",
                        mode="AUTO",
                        condition="always",
                        description="Reflection 기반 온보딩 분석 추가",
                    ))
                    if "onboarding" not in new_secondary:
                        new_secondary.append("onboarding")
                
                # Security FAST 추가
                elif "add_security" in adj_lower:
                    new_steps.append(ExecutionStep(
                        step=len(new_steps) + 1,
                        agent="security",
                        mode="FAST",
                        condition="always",
                        description="Reflection 기반 보안 분석 추가",
                    ))
                    
            # Dict 형태의 조정 처리 (LLM에서 직접 step 정의)
            elif isinstance(adj, dict):
                action = adj.get("action", "")
                step_data = adj.get("step", {})
                
                if action == "append" and step_data:
                    new_steps.append(ExecutionStep(
                        step=len(new_steps) + 1,
                        agent=step_data.get("agent", "diagnosis"),
                        mode=step_data.get("mode", "AUTO"),
                        condition=step_data.get("condition", "always"),
                        description=step_data.get("description", "동적 추가됨"),
                    ))
        
        logger.info(f"Applied {len(adjustments)} plan adjustments, new step count: {len(new_steps)}")
        
        return ExecutionPlan(
            primary_task_type=current_plan.primary_task_type,
            steps=new_steps,
            secondary_tasks=new_secondary,
            suggested_sequence=[s.agent for s in new_steps],
            estimated_duration=len(new_steps) * 15,
            complexity=current_plan.complexity,
        )
    
    def should_escalate_to_full(
        self,
        current_step: ExecutionStep,
        execution_result: Dict[str, Any],
        user_preferences: Dict[str, Any] = None,
        confidence_threshold: float = 0.7,
        score_threshold: int = 50,
    ) -> bool:
        """
        FAST→FULL 승급 여부 판단.
        
        승급 조건:
        1. 결과 confidence가 낮음
        2. user_preferences.focus에 포함된 영역 점수가 낮음
        3. 결과가 불확실함 (이상치 감지)
        
        Args:
            current_step: 현재 실행 단계
            execution_result: 실행 결과
            user_preferences: 사용자 선호
            confidence_threshold: confidence 임계값
            score_threshold: 점수 임계값
            
        Returns:
            승급 필요 여부
        """
        if current_step.mode == "FULL":
            return False  # 이미 FULL
        
        user_preferences = user_preferences or {"focus": [], "ignore": []}
        focus_areas = user_preferences.get("focus", [])
        
        # 1. Confidence 체크
        confidence = execution_result.get("confidence", 1.0)
        if confidence < confidence_threshold:
            logger.info(f"Escalate to FULL: low confidence ({confidence})")
            return True
        
        # 2. Focus 영역 점수 체크
        if current_step.agent == "diagnosis":
            for focus in focus_areas:
                if focus == "health" and execution_result.get("health_score", 100) < score_threshold:
                    logger.info(f"Escalate to FULL: low health_score in focus")
                    return True
                if focus == "security" and execution_result.get("security_score", 100) < score_threshold:
                    logger.info(f"Escalate to FULL: low security_score in focus")
                    return True
                if focus == "onboarding" and execution_result.get("onboarding_score", 100) < score_threshold:
                    logger.info(f"Escalate to FULL: low onboarding_score in focus")
                    return True
        
        # 3. 이상치 감지
        if execution_result.get("has_anomalies", False):
            logger.info("Escalate to FULL: anomalies detected")
            return True
        
        return False
    
    def escalate_step_to_full(self, step: ExecutionStep) -> ExecutionStep:
        """단계를 FULL 모드로 승급."""
        return ExecutionStep(
            step=step.step,
            agent=step.agent,
            mode="FULL",
            condition=step.condition,
            description=f"{step.description} (FAST→FULL 승급)",
        )
    
    def check_clarification_needed(
        self,
        intent: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        사용자에게 명확화 요청이 필요한지 확인.
        
        반환 예시:
        {
            "needs_clarification": True,
            "question": "비교할 다른 저장소를 알려주세요.",
            "missing_info": "compare_target",
            "suggestions": ["facebook/react", "vuejs/vue"]
        }
        
        Args:
            intent: 사용자 의도
            context: 컨텍스트 정보 {"owner": ..., "repo": ..., "compare_repos": [...]}
            
        Returns:
            명확화 요청 정보 또는 None
        """
        # 비교 분석인데 대상이 1개뿐
        if intent == "compare":
            compare_repos = context.get("compare_repos", [])
            if len(compare_repos) < 2:
                return {
                    "needs_clarification": True,
                    "question": "비교 분석을 하려면 다른 저장소도 알려주세요. 어떤 저장소와 비교할까요?",
                    "missing_info": "compare_target",
                    "suggestions": self._suggest_popular_repos(context.get("owner"), context.get("repo")),
                }
        
        # 보안 분석인데 branch 정보 없음
        if intent == "security":
            if not context.get("branch") and not context.get("ref"):
                return {
                    "needs_clarification": False,  # 기본값 main 사용
                    "info": "브랜치가 지정되지 않아 main/master를 분석합니다.",
                    "default_used": "main",
                }
        
        # 온보딩인데 경험 수준 불명확
        if intent == "onboard":
            if not context.get("experience_level"):
                return {
                    "needs_clarification": False,  # 기본값 사용
                    "info": "경험 수준이 지정되지 않아 초보자 기준으로 가이드를 생성합니다.",
                    "default_used": "beginner",
                }
        
        return None
    
    def _suggest_popular_repos(self, owner: str = None, repo: str = None) -> List[str]:
        """비교용 인기 저장소 제안."""
        # 간단한 구현: 하드코딩된 인기 저장소
        popular = [
            "facebook/react",
            "vuejs/vue",
            "angular/angular",
            "microsoft/vscode",
            "tensorflow/tensorflow",
        ]
        # 현재 저장소 제외
        current = f"{owner}/{repo}" if owner and repo else ""
        return [r for r in popular if r != current][:3]
    
    def create_sequence_from_plan(self, plan: ExecutionPlan) -> List[str]:
        """
        ExecutionPlan에서 실행 시퀀스 문자열 생성.
        
        예: ["diagnosis_FAST", "security_FAST", "onboarding_AUTO"]
        """
        sequence = []
        for step in plan.steps:
            if step.condition != "skip":
                sequence.append(f"{step.agent}_{step.mode}")
        return sequence
    
    def _create_fallback_plan(self, intent: str, priority: str) -> ExecutionPlan:
        """폴백 계획 생성."""
        mode = "FAST" if priority == "speed" else "AUTO"
        
        if intent == "diagnose":
            steps = [ExecutionStep(step=1, agent="diagnosis", mode=mode, condition="always")]
        elif intent == "security":
            steps = [
                ExecutionStep(step=1, agent="diagnosis", mode="FAST", condition="always"),
                ExecutionStep(step=2, agent="security", mode=mode, condition="always"),
            ]
        elif intent == "onboard":
            steps = [
                ExecutionStep(step=1, agent="diagnosis", mode="FAST", condition="always"),
                ExecutionStep(step=2, agent="onboarding", mode=mode, condition="always"),
            ]
        elif intent == "full_audit":
            steps = [
                ExecutionStep(step=1, agent="diagnosis", mode="FULL", condition="always"),
                ExecutionStep(step=2, agent="security", mode="FULL", condition="always"),
                ExecutionStep(step=3, agent="onboarding", mode="FULL", condition="always"),
            ]
        else:
            steps = [ExecutionStep(step=1, agent="chat", mode="AUTO", condition="always")]
        
        return ExecutionPlan(
            primary_task_type=intent,
            steps=steps,
            secondary_tasks=[],
            suggested_sequence=[s.agent for s in steps],
            estimated_duration=len(steps) * 15,
            complexity="moderate" if len(steps) <= 2 else "complex",
        )
    
    async def create_plan_async(
        self,
        intent: str,
        owner: str,
        repo: str,
        user_preferences: Dict[str, Any] = None,
        priority: str = "thoroughness",
    ) -> ExecutionPlan:
        """
        사용자 의도와 선호를 기반으로 실행 계획 생성 (비동기 버전).
        """
        user_preferences = user_preferences or {"focus": [], "ignore": []}
        
        response = None
        try:
            chain = self.planning_prompt | self.llm
            response = await chain.ainvoke({
                "intent": intent,
                "owner": owner,
                "repo": repo,
                "user_preferences": json.dumps(user_preferences, ensure_ascii=False),
                "priority": priority,
            })
            raw_content = response.content.strip()
            
            # JSON 추출
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(raw_content)
            
            # ExecutionPlan 생성
            steps = []
            for step_data in parsed.get("steps", []):
                steps.append(ExecutionStep(
                    step=step_data.get("step", len(steps) + 1),
                    agent=step_data.get("agent", "diagnosis"),
                    mode=step_data.get("mode", "AUTO"),
                    condition=step_data.get("condition", "always"),
                    description=step_data.get("description", ""),
                ))
            
            return ExecutionPlan(
                primary_task_type=parsed.get("primary_task_type", intent),
                steps=steps,
                secondary_tasks=parsed.get("secondary_tasks", []),
                suggested_sequence=parsed.get("suggested_sequence", []),
                estimated_duration=parsed.get("estimated_duration", 30),
                complexity=parsed.get("complexity", "moderate"),
            )
            
        except Exception as e:
            logger.error(f"DynamicPlanner.create_plan_async failed: {e}, raw_response={response}")
            return self._create_fallback_plan(intent, priority)
    
    async def validate_plan_async(
        self,
        plan: ExecutionPlan,
        intent: str,
        user_preferences: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        실행 계획 검증 (비동기 버전).
        """
        user_preferences = user_preferences or {"focus": [], "ignore": []}
        
        response = None
        try:
            chain = self.validation_prompt | self.llm
            response = await chain.ainvoke({
                "intent": intent,
                "user_preferences": json.dumps(user_preferences, ensure_ascii=False),
                "plan": json.dumps(plan.to_dict(), ensure_ascii=False),
            })
            raw_content = response.content.strip()
            
            # JSON 추출
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()
            
            return json.loads(raw_content)
            
        except Exception as e:
            logger.error(f"DynamicPlanner.validate_plan_async failed: {e}, raw_response={response}")
            return {"is_valid": True, "issues": [], "suggestions": [], "confidence": 0.5}


class AgenticPlanExecutor:
    """
    Agentic 계획 실행기.
    
    DynamicPlanner와 함께 사용하여 동적 계획 조정,
    FAST→FULL 승급, Clarification 루프를 구현합니다.
    """
    
    def __init__(self, planner: DynamicPlanner = None):
        """AgenticPlanExecutor 초기화."""
        self.planner = planner or DynamicPlanner()
        self.execution_history: List[Dict[str, Any]] = []
        self.clarification_pending: Optional[Dict[str, Any]] = None
    
    def execute_plan(
        self,
        plan: ExecutionPlan,
        agent_runners: Dict[str, callable],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        계획 실행.
        
        Args:
            plan: 실행할 계획
            agent_runners: 에이전트별 실행 함수 {"diagnosis": run_diagnosis, ...}
            context: 실행 컨텍스트
            
        Returns:
            실행 결과 {"results": {...}, "escalations": [...], "plan_changed": bool}
        """
        results = {}
        escalations = []
        user_preferences = context.get("user_preferences", {})
        
        for step in plan.steps:
            if step.condition == "skip":
                continue
            
            runner = agent_runners.get(step.agent)
            if not runner:
                logger.warning(f"No runner for agent: {step.agent}")
                continue
            
            # 실행
            logger.info(f"Executing step {step.step}: {step.agent} ({step.mode})")
            result = runner(context, mode=step.mode)
            results[step.agent] = result
            
            # FAST→FULL 승급 체크
            if step.mode != "FULL" and self.planner.should_escalate_to_full(
                step, result, user_preferences
            ):
                escalations.append({
                    "step": step.step,
                    "agent": step.agent,
                    "from_mode": step.mode,
                    "to_mode": "FULL",
                    "reason": "low_confidence_or_score",
                })
                
                # FULL 모드로 재실행
                logger.info(f"Escalating {step.agent} to FULL mode")
                full_result = runner(context, mode="FULL")
                results[step.agent] = full_result
            
            self.execution_history.append({
                "step": step.step,
                "agent": step.agent,
                "mode": step.mode,
                "result_keys": list(result.keys()) if isinstance(result, dict) else None,
            })
        
        return {
            "results": results,
            "escalations": escalations,
            "plan_changed": len(escalations) > 0,
        }
    
    def handle_reflection(
        self,
        plan: ExecutionPlan,
        reflection_result: Dict[str, Any],
        execution_results: Dict[str, Any],
    ) -> Tuple[ExecutionPlan, bool]:
        """
        Reflection 결과 처리.
        
        Returns:
            (조정된 계획, 재실행 필요 여부)
        """
        if not reflection_result.get("should_replan", False):
            return plan, False
        
        new_plan = self.planner.apply_reflection_adjustments(
            plan, reflection_result, execution_results
        )
        
        # 새 단계가 추가되었는지 확인
        needs_rerun = len(new_plan.steps) > len(plan.steps)
        
        return new_plan, needs_rerun
    
    def request_clarification(
        self,
        clarification_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        사용자에게 명확화 요청.
        
        Returns:
            사용자에게 전달할 메시지
        """
        self.clarification_pending = clarification_info
        
        return {
            "type": "clarification_request",
            "question": clarification_info.get("question", ""),
            "suggestions": clarification_info.get("suggestions", []),
            "missing_info": clarification_info.get("missing_info", ""),
        }
    
    def apply_clarification(
        self,
        user_response: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        사용자 응답을 컨텍스트에 적용.
        
        Returns:
            업데이트된 컨텍스트
        """
        if not self.clarification_pending:
            return context
        
        missing_info = self.clarification_pending.get("missing_info", "")
        
        if missing_info == "compare_target":
            # 비교 대상 저장소 추가
            compare_repos = context.get("compare_repos", [])
            compare_repos.append(user_response.strip())
            context["compare_repos"] = compare_repos
        
        self.clarification_pending = None
        return context

