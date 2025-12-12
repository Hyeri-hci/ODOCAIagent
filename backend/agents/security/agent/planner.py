"""
LLM-Based Dynamic Planner
에이전트가 상황을 이해하고 동적으로 실행 계획을 생성
"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state import SecurityAnalysisState, TaskIntent, ExecutionPlan
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

작업 흐름 추천 (4가지 핵심 시나리오):

1. 리포지토리 전체 의존성 조회 (extract_dependencies):
   - parse_dependencies 도구 사용
   - CPE DB 조회 X, NVD API 요청 X
   - 의존성 목록만 반환

2. 특정 파일 의존성 조회 (extract_file_dependencies):
   - parse_file_dependencies 도구 사용
   - 특정 파일만 파싱
   - CPE DB 조회 X, NVD API 요청 X
   - 의존성 목록만 반환

3. 리포지토리 전체 취약점 조회 (scan_vulnerabilities):
   - parse_dependencies 도구로 의존성 추출
   - search_vulnerabilities 도구로 CPE DB 조회 및 NVD API 요청
   - 취약점 정보 + 보안점수 반환

4. 특정 파일 취약점 조회 (scan_file_vulnerabilities):
   - search_file_vulnerabilities 도구 사용
   - 특정 파일의 의존성 추출 → CPE DB 조회 → NVD API 요청
   - 취약점 정보 + 보안점수 반환

**중요**:
- 의존성만 요청 시 절대 CPE DB나 NVD API를 호출하지 않습니다
- 취약점 요청 시에만 CPE DB와 NVD API를 호출합니다
- 특정 파일 요청 시 리포지토리 전체를 분석하지 않습니다

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
        state: SecurityAnalysisState
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

        # intent가 딕셔너리가 아닌 경우 처리
        if not isinstance(intent, dict):
            print(f"[Planner] Invalid intent type: {type(intent)}, using default plan")
            return self._create_default_plan(state)

        try:
            # LLM을 사용하여 계획 생성
            chain = self.planning_prompt | self.llm
            response = await chain.ainvoke({
                "primary_action": intent.get("primary_action") or "scan_vulnerabilities",
                "scope": intent.get("scope") or "full_repository",
                "target_files": intent.get("target_files") or [],
                "conditions": intent.get("conditions") or [],
                "output_format": intent.get("output_format") or "detailed_report",
                "parameters": intent.get("parameters") or {},
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

    def _create_default_plan(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """기본 계획 생성 (LLM 실패시 폴백) - 4가지 시나리오 명확히 구분"""
        intent = state.get("parsed_intent")
        primary_action = intent["primary_action"] if intent else "analyze_all"
        target_files = intent.get("target_files", []) if intent else []

        # 1. 리포지토리 전체 의존성만 조회
        if primary_action == "extract_dependencies":
            steps = [
                {
                    "step_number": 1,
                    "action": "parse_dependencies",
                    "description": "Parse all dependencies (NO vulnerability scan)",
                    "parameters": {},
                    "validation": "Check dependency count > 0",
                    "fallback": "Report no dependencies"
                }
            ]
            complexity = "simple"
            duration = 30
            print("[Planner] Plan: Extract dependencies only (NO CPE/NVD queries)")

        # 2. 특정 파일의 의존성만 조회
        elif primary_action == "extract_file_dependencies":
            file_path = target_files[0] if target_files else "package.json"
            steps = [
                {
                    "step_number": 1,
                    "action": "parse_file_dependencies",
                    "description": f"Parse dependencies from {file_path} (NO vulnerability scan)",
                    "parameters": {"file_path": file_path},
                    "validation": "Check dependencies parsed",
                    "fallback": "Report error"
                }
            ]
            complexity = "simple"
            duration = 15
            print(f"[Planner] Plan: Extract file dependencies for {file_path} (NO CPE/NVD queries)")

        # 3. 리포지토리 전체 의존성 + 취약점 조회
        elif primary_action == "scan_vulnerabilities":
            steps = [
                {
                    "step_number": 1,
                    "action": "parse_dependencies",
                    "description": "Parse all dependencies first",
                    "parameters": {},
                    "validation": "Check dependencies found",
                    "fallback": "Cannot scan without dependencies"
                },
                {
                    "step_number": 2,
                    "action": "search_vulnerabilities",
                    "description": "Search vulnerabilities (CPE DB + NVD API)",
                    "parameters": {},
                    "validation": "Check vulnerability search completed",
                    "fallback": "Report no vulnerabilities"
                }
            ]
            complexity = "moderate"
            duration = 120
            print("[Planner] Plan: Parse dependencies + Search vulnerabilities (CPE DB + NVD API)")

        # 4. 특정 파일의 의존성 + 취약점 조회
        elif primary_action == "scan_file_vulnerabilities":
            file_path = target_files[0] if target_files else "package.json"
            steps = [
                {
                    "step_number": 1,
                    "action": "search_file_vulnerabilities",
                    "description": f"Scan {file_path} for vulnerabilities (CPE DB + NVD API)",
                    "parameters": {"file_path": file_path},
                    "validation": "Check scan completed",
                    "fallback": "Report error"
                }
            ]
            complexity = "moderate"
            duration = 60
            print(f"[Planner] Plan: Scan file vulnerabilities for {file_path} (CPE DB + NVD API)")

        # 5. 전체 보안 분석 (의존성 + 취약점 + 보안점수 + 리포트)
        elif primary_action == "analyze_all":
            steps = [
                {
                    "step_number": 1,
                    "action": "parse_dependencies",
                    "description": "Parse all dependencies",
                    "parameters": {},
                    "validation": "Check dependency count > 0",
                    "fallback": "Report no dependencies"
                },
                {
                    "step_number": 2,
                    "action": "search_vulnerabilities",
                    "description": "Search vulnerabilities (CPE DB + NVD API)",
                    "parameters": {},
                    "validation": "Check vulnerability search completed",
                    "fallback": "Continue without vulnerability data"
                },
                {
                    "step_number": 3,
                    "action": "generate_security_report",
                    "description": "Generate final security report",
                    "parameters": {},
                    "validation": "Check report generated",
                    "fallback": "Return raw data"
                }
            ]
            complexity = "moderate"
            duration = 180
            print("[Planner] Plan: Full analysis (dependencies + vulnerabilities + report)")

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
            print(f"[Planner] Plan: Custom action - {primary_action}")

        execution_plan: ExecutionPlan = {
            "steps": steps,
            "estimated_duration": duration,
            "complexity": complexity,
            "requires_llm": False
        }

        return {
            "execution_plan": execution_plan,
            "plan_valid": True,
            "plan_feedback": f"Using default plan for {primary_action}"
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
        state: SecurityAnalysisState,
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
