"""
LLM-Based Dynamic Planner
에이전트가 상황을 이해하고 동적으로 실행 계획을 생성
"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state_v2 import SecurityAnalysisStateV2, TaskIntent, ExecutionPlan
import json
import re


class DynamicPlanner:
    """LLM 기반 동적 계획 생성기"""
    def __init__(
            self,
            llm_base_url: str,
            llm_api_key: str,
            llm_model: str,
            llm_temperature: float = 0.0
    ):
        self.llm = ChatOpenAI(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            temperature=llm_temperature
        )

        # 계획 생성 프롬프트
        self.planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert security analysis planner.

Given a user's intent and available tools, create a detailed execution plan.

Available Tools:
- fetch_repository_info: Get repository metadata
- fetch_file_content: Get specific file contents
- fetch_directory_structure: Get repository structure
- detect_lock_files: Find dependency lock files
- parse_package_json: Parse package.json dependencies
- parse_requirements_txt: Parse requirements.txt
- parse_pipfile: Parse Pipfile/Pipfile.lock
- parse_gemfile: Parse Gemfile/Gemfile.lock
- parse_cargo_toml: Parse Cargo.toml
- search_cve_by_cpe: Search CVE vulnerabilities
- fetch_cve_details: Get CVE details
- assess_severity: Assess vulnerability severity
- check_license_compatibility: Check license compliance
- generate_security_report: Generate final report
- calculate_security_score: Calculate security score

Your task:
1. Analyze the user's intent
2. Break down the task into atomic steps
3. Select appropriate tools for each step
4. Estimate complexity and duration
5. Add validation steps between major phases

Return a JSON object:
{{
    "steps": [
        {{
            "step_number": 1,
            "action": "tool_name",
            "description": "What this step does",
            "parameters": {{}},
            "validation": "How to verify this step succeeded",
            "fallback": "What to do if this step fails"
        }}
    ],
    "estimated_duration": 120,
    "complexity": "moderate",
    "requires_llm": true,
    "reasoning": "Why this plan was chosen"
}}"""),
            ("user", """User Intent:
Primary Action: {primary_action}
Scope: {scope}
Target Files: {target_files}
Conditions: {conditions}
Output Format: {output_format}
Parameters: {parameters}

User Request: {user_request}

Create a detailed execution plan.""")
        ])

        # 계획 검증 프롬프트
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a plan validator for security analysis.

Review the execution plan and check:
1. Are all steps necessary and sufficient?
2. Are steps in the correct order?
3. Are there missing validation steps?
4. Are error handling steps included?
5. Is the plan achievable with available tools?

Return JSON:
{{
    "valid": true/false,
    "issues": ["list of issues found"],
    "suggestions": ["list of improvements"],
    "revised_steps": [...]  // only if changes needed
}}"""),
            ("user", """Review this plan:

{plan_json}

User's original request: {user_request}""")
        ])

    async def create_plan(
        self,
        state: SecurityAnalysisStateV2
    ) -> Dict[str, Any]:
        """
        동적 실행 계획 생성

        Args:
            state: 현재 에이전트 상태

        Returns:
            업데이트할 상태 정보
        """
        print("\n[Planner] Creating dynamic execution plan...")

        intent = state.get("parsed_intent")
        if not intent:
            print("[Planner] No parsed intent, using default plan")
            return self._create_default_plan(state)

        try:
            # LLM을 사용하여 계획 생성
            chain = self.planning_prompt | self.llm
            response = await chain.ainvoke({
                "primary_action": intent["primary_action"],
                "scope": intent["scope"],
                "target_files": intent.get("target_files", []),
                "conditions": intent.get("conditions", []),
                "output_format": intent["output_format"],
                "parameters": intent.get("parameters", {}),
                "user_request": state.get("user_request", "")
            })

            # JSON 파싱
            content = response.content
            plan_data = self._extract_json(content)

            # ExecutionPlan 구조로 변환
            execution_plan: ExecutionPlan = {
                "steps": plan_data.get("steps", []),
                "estimated_duration": plan_data.get("estimated_duration", 60),
                "complexity": plan_data.get("complexity", "moderate"),
                "requires_llm": plan_data.get("requires_llm", True)
            }

            print(f"[Planner] Generated plan with {len(execution_plan['steps'])} steps")
            print(f"[Planner] Complexity: {execution_plan['complexity']}")
            print(f"[Planner] Estimated duration: {execution_plan['estimated_duration']}s")

            # 계획 검증
            validation_result = await self._validate_plan(
                execution_plan,
                state.get("user_request", "")
            )

            if not validation_result["valid"]:
                print(f"[Planner] Plan validation found issues: {validation_result['issues']}")
                # 수정된 계획이 있으면 사용
                if validation_result.get("revised_steps"):
                    execution_plan["steps"] = validation_result["revised_steps"]
                    print("[Planner] Using revised plan")

            return {
                "execution_plan": execution_plan,
                "plan_valid": validation_result["valid"],
                "plan_feedback": "\n".join(validation_result.get("suggestions", [])),
                "current_step": "planning_complete",
                "info_logs": [
                    f"[Planner] Created {execution_plan['complexity']} plan with {len(execution_plan['steps'])} steps",
                    f"[Planner] Reasoning: {plan_data.get('reasoning', 'N/A')}"
                ]
            }

        except Exception as e:
            print(f"[Planner] Error creating plan: {e}")
            return {
                "errors": [f"Planning failed: {str(e)}"],
                "execution_plan": self._create_default_plan(state)["execution_plan"],
                "plan_valid": False
            }

    async def _validate_plan(
        self,
        plan: ExecutionPlan,
        user_request: str
    ) -> Dict[str, Any]:
        """계획 검증"""
        try:
            chain = self.validation_prompt | self.llm
            response = await chain.ainvoke({
                "plan_json": json.dumps(plan, indent=2, ensure_ascii=False),
                "user_request": user_request
            })

            content = response.content
            validation_data = self._extract_json(content)

            return {
                "valid": validation_data.get("valid", True),
                "issues": validation_data.get("issues", []),
                "suggestions": validation_data.get("suggestions", []),
                "revised_steps": validation_data.get("revised_steps", [])
            }

        except Exception as e:
            print(f"[Planner] Validation error: {e}")
            return {
                "valid": True,  # 검증 실패시 계획은 유효한 것으로 간주
                "issues": [],
                "suggestions": []
            }

    def _create_default_plan(self, state: SecurityAnalysisStateV2) -> Dict[str, Any]:
        """기본 계획 생성 (LLM 실패시 폴백)"""
        intent = state.get("parsed_intent")
        primary_action = intent["primary_action"] if intent else "analyze_all"

        if primary_action == "analyze_all":
            steps = [
                {
                    "step_number": 1,
                    "action": "fetch_repository_info",
                    "description": "Fetch repository metadata",
                    "parameters": {"owner": state.get("owner"), "repo": state.get("repository")},
                    "validation": "Check if repo exists",
                    "fallback": "Abort if repo not found"
                },
                {
                    "step_number": 2,
                    "action": "detect_lock_files",
                    "description": "Detect dependency lock files",
                    "parameters": {},
                    "validation": "Check if lock files found",
                    "fallback": "Continue without lock files"
                },
                {
                    "step_number": 3,
                    "action": "parse_dependencies",
                    "description": "Parse all dependencies",
                    "parameters": {},
                    "validation": "Check dependency count > 0",
                    "fallback": "Report no dependencies"
                },
                {
                    "step_number": 4,
                    "action": "search_vulnerabilities",
                    "description": "Search for vulnerabilities",
                    "parameters": {},
                    "validation": "Check CVE search completed",
                    "fallback": "Continue without vulnerability data"
                },
                {
                    "step_number": 5,
                    "action": "calculate_security_score",
                    "description": "Calculate security score",
                    "parameters": {},
                    "validation": "Check score calculated",
                    "fallback": "Use default score"
                },
                {
                    "step_number": 6,
                    "action": "generate_security_report",
                    "description": "Generate final report",
                    "parameters": {},
                    "validation": "Check report generated",
                    "fallback": "Return raw data"
                }
            ]
            complexity = "moderate"
            duration = 180

        elif primary_action == "extract_dependencies":
            steps = [
                {
                    "step_number": 1,
                    "action": "detect_lock_files",
                    "description": "Detect dependency lock files",
                    "parameters": {},
                    "validation": "Check if lock files found",
                    "fallback": "Abort if no lock files"
                },
                {
                    "step_number": 2,
                    "action": "parse_dependencies",
                    "description": "Parse dependencies from lock files",
                    "parameters": {},
                    "validation": "Check dependency count > 0",
                    "fallback": "Report no dependencies"
                }
            ]
            complexity = "simple"
            duration = 30

        elif primary_action == "scan_vulnerabilities":
            steps = [
                {
                    "step_number": 1,
                    "action": "parse_dependencies",
                    "description": "Parse dependencies first",
                    "parameters": {},
                    "validation": "Check dependencies found",
                    "fallback": "Cannot scan without dependencies"
                },
                {
                    "step_number": 2,
                    "action": "search_vulnerabilities",
                    "description": "Search for CVE vulnerabilities",
                    "parameters": {},
                    "validation": "Check CVE search completed",
                    "fallback": "Report no vulnerabilities"
                }
            ]
            complexity = "simple"
            duration = 60

        else:
            # 기타 액션에 대한 기본 계획
            steps = [
                {
                    "step_number": 1,
                    "action": "fetch_repository_info",
                    "description": "Fetch repository information",
                    "parameters": {},
                    "validation": "Check if successful",
                    "fallback": "Abort"
                }
            ]
            complexity = "simple"
            duration = 15

        execution_plan: ExecutionPlan = {
            "steps": steps,
            "estimated_duration": duration,
            "complexity": complexity,
            "requires_llm": False
        }

        return {
            "execution_plan": execution_plan,
            "plan_valid": True,
            "plan_feedback": "Using default plan (LLM unavailable)"
        }

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출"""
        # 마크다운 코드 블록 제거
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif '```' in content:
            content = content.split('```')[1].strip()

        return json.loads(content)

    async def replan(
        self,
        state: SecurityAnalysisStateV2,
        reason: str
    ) -> Dict[str, Any]:
        """
        재계획 (실행 중 문제 발생시)

        Args:
            state: 현재 상태
            reason: 재계획 사유

        Returns:
            업데이트된 계획
        """
        print(f"\n[Planner] Replanning due to: {reason}")

        # 현재까지의 진행 상황 파악
        completed_steps = [
            action for action in state.get("actions", [])
            if action.get("success", False)
        ]

        replan_prompt = f"""Original plan failed. Need to replan.

Reason for replanning: {reason}

Completed steps so far:
{json.dumps(completed_steps, indent=2, ensure_ascii=False)}

Current state:
- Dependencies found: {state.get('dependency_count', 0)}
- Vulnerabilities found: {state.get('vulnerability_count', 0)}
- Errors: {state.get('errors', [])}

Create a new plan that:
1. Skips already completed steps
2. Addresses the failure reason
3. Has fallback strategies
"""

        try:
            response = await self.llm.ainvoke(replan_prompt)
            content = response.content
            plan_data = self._extract_json(content)

            execution_plan: ExecutionPlan = {
                "steps": plan_data.get("steps", []),
                "estimated_duration": plan_data.get("estimated_duration", 60),
                "complexity": "complex",  # 재계획은 항상 복잡함
                "requires_llm": True
            }

            return {
                "execution_plan": execution_plan,
                "plan_valid": True,
                "strategy_changes": [{
                    "timestamp": state.get("created_at", ""),
                    "from": state.get("current_strategy", "initial"),
                    "to": "replanned",
                    "reason": reason
                }],
                "info_logs": [f"[Planner] Created new plan: {reason}"]
            }

        except Exception as e:
            print(f"[Planner] Replan failed: {e}")
            # 재계획 실패시 현재 계획 유지
            return {
                "errors": [f"Replan failed: {str(e)}"],
                "warnings": ["Continuing with original plan"]
            }
