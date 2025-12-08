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
            ("system", """당신은 보안 분석 계획 전문가입니다.

사용자의 의도와 사용 가능한 도구를 바탕으로 상세한 실행 계획을 수립하세요.

사용 가능한 도구:
- fetch_repository_info: 레포지토리 메타데이터 가져오기
- fetch_file_content: 특정 파일 내용 가져오기
- fetch_directory_structure: 레포지토리 구조 가져오기
- detect_lock_files: 의존성 락 파일 찾기
- parse_package_json: package.json 의존성 파싱
- parse_requirements_txt: requirements.txt 파싱
- parse_pipfile: Pipfile/Pipfile.lock 파싱
- parse_gemfile: Gemfile/Gemfile.lock 파싱
- parse_cargo_toml: Cargo.toml 파싱
- search_cve_by_cpe: CVE 취약점 검색
- fetch_cve_details: CVE 상세 정보 가져오기
- assess_severity: 취약점 심각도 평가
- check_license_compatibility: 라이센스 호환성 확인
- generate_security_report: 최종 리포트 생성
- calculate_security_score: 보안 점수 계산

작업:
1. 사용자의 의도 분석
2. 작업을 원자적 단계로 분해
3. 각 단계에 적합한 도구 선택
4. 복잡도와 소요 시간 추정
5. 주요 단계 사이에 검증 단계 추가

다음 JSON 객체를 반환하세요:
{{
    "steps": [
        {{
            "step_number": 1,
            "action": "tool_name",
            "description": "이 단계가 수행하는 작업",
            "parameters": {{}},
            "validation": "이 단계의 성공 여부를 확인하는 방법",
            "fallback": "이 단계가 실패할 경우 수행할 작업"
        }}
    ],
    "estimated_duration": 120,
    "complexity": "moderate",
    "requires_llm": true,
    "reasoning": "이 계획을 선택한 이유"
}}"""),
            ("user", """사용자 의도:
Primary Action: {primary_action}
Scope: {scope}
Target Files: {target_files}
Conditions: {conditions}
Output Format: {output_format}
Parameters: {parameters}

사용자 요청: {user_request}

상세한 실행 계획을 수립하세요.""")
        ])

        # 계획 검증 프롬프트
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 보안 분석 계획 검증자입니다.

실행 계획을 검토하고 다음을 확인하세요:
1. 모든 단계가 필요하고 충분한가?
2. 단계들이 올바른 순서로 되어 있는가?
3. 누락된 검증 단계가 있는가?
4. 오류 처리 단계가 포함되어 있는가?
5. 계획이 사용 가능한 도구로 실현 가능한가?

다음 JSON을 반환하세요:
{{
    "valid": true/false,
    "issues": ["발견된 문제 목록"],
    "suggestions": ["개선 제안 목록"],
    "revised_steps": [...]  // 변경이 필요한 경우에만
}}"""),
            ("user", """이 계획을 검토하세요:

{plan_json}

사용자의 원래 요청: {user_request}""")
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
            # 더 자세한 에러 정보 출력
            import traceback
            error_details = traceback.format_exc()
            print(f"[Planner] Error creating plan: {type(e).__name__}: {str(e)}")
            print(f"[Planner] Error details:\n{error_details}")
            return {
                "errors": [f"Planning failed ({type(e).__name__}): {str(e)}"],
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
