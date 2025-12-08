"""
ReAct Executor (Improved)
진짜 ReAct 패턴 구현: Think -> Act -> Observe 사이클
개선사항: 재시도 로직, 대안 도구 시도, 연속 실패 추적
"""
from typing import Dict, Any, List, Optional, Callable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state_v2 import SecurityAnalysisStateV2, update_thought, update_action, update_observation
from datetime import datetime
import json
import re


# 대안 도구 매핑 (도구 실패 시 시도할 대안)
TOOL_ALTERNATIVES = {
    "fetch_repository_info": ["fetch_directory_structure", "detect_lock_files"],
    "detect_lock_files": ["fetch_directory_structure"],
    "parse_package_json": ["fetch_file_content"],
    "parse_requirements_txt": ["fetch_file_content"],
    "analyze_dependencies_full": ["detect_lock_files", "parse_package_json"],
}

# 최소 시도 횟수 설정
MIN_ATTEMPTS_BEFORE_STOP = 5  # 최소 5회는 시도
MAX_CONSECUTIVE_FAILURES = 3  # 연속 3회 실패 시 대안 시도
MAX_SAME_TOOL_RETRIES = 2     # 같은 도구 최대 2회 재시도


class ToolExecutionTracker:
    """도구 실행 추적"""

    def __init__(self):
        self.tool_attempts = {}  # {tool_name: {"success": int, "failure": int}}
        self.consecutive_failures = 0
        self.last_tool = None
        self.last_success = None

    def record_attempt(self, tool_name: str, success: bool):
        """도구 실행 결과 기록"""
        if tool_name not in self.tool_attempts:
            self.tool_attempts[tool_name] = {"success": 0, "failure": 0}

        if success:
            self.tool_attempts[tool_name]["success"] += 1
            self.consecutive_failures = 0
            self.last_success = tool_name
        else:
            self.tool_attempts[tool_name]["failure"] += 1
            self.consecutive_failures += 1

        self.last_tool = tool_name

    def should_try_alternative(self, tool_name: str) -> bool:
        """대안 도구를 시도해야 하는지 판단"""
        if tool_name not in self.tool_attempts:
            return False

        failures = self.tool_attempts[tool_name]["failure"]
        return failures >= MAX_SAME_TOOL_RETRIES

    def should_stop_early(self) -> bool:
        """조기 종료해야 하는지 판단"""
        return self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES

    def get_summary(self) -> Dict[str, Any]:
        """실행 요약"""
        return {
            "tool_attempts": self.tool_attempts,
            "consecutive_failures": self.consecutive_failures,
            "last_tool": self.last_tool,
            "last_success": self.last_success
        }


class ReActExecutor:
    """ReAct 패턴 기반 실행기 (개선 버전)"""

    def __init__(
        self,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        llm_temperature: float = 0.0,
        tools: Optional[Dict[str, Callable]] = None
    ):
        self.llm = ChatOpenAI(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            temperature=llm_temperature
        )
        self.tools = tools or {}
        self.tracker = ToolExecutionTracker()  # 추적기 추가

        # ReAct 사고 프롬프트 (개선)
        self.thought_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 ReAct (Reasoning + Acting) 패턴을 사용하는 보안 분석 에이전트입니다.

현재 실행 계획:
{execution_plan}

지금까지의 진행:
- 완료된 단계: {completed_steps}
- 현재 단계: {current_step}
- 관찰 결과: {observations}
- 실패한 도구: {failed_tools}

사용 가능한 도구:
{available_tools}

현재 상태:
{current_state}

중요한 규칙:
1. 도구가 여러 번 실패했다면, 대체 도구를 시도하세요
2. 조기에 포기하지 마세요 - 최소 5-10가지 다른 접근 방식을 시도하세요
3. 막힌 경우, 다른 카테고리의 도구를 시도하세요 (예: GitHub API 실패 시 파일 파싱 시도)
4. "continue": false는 모든 합리적인 옵션을 소진한 경우에만 설정하세요

작업:
1. THINK: 현재 상황 분석
2. 다음에 할 일 결정
3. 적절한 도구 선택 (최근 실패한 도구 제외)
4. 파라미터 지정

다음 JSON을 반환하세요:
{{
    "thought": "현재 상황에 대한 당신의 추론",
    "reasoning": "이 액션을 수행하는 이유",
    "next_action": "tool_name",
    "parameters": {{}},
    "expected_outcome": "예상되는 결과",
    "continue": true/false
}}

"continue": false는 작업이 진정으로 완료되었거나 모든 옵션이 소진된 경우에만 설정하세요."""),
            ("user", "다음에 무엇을 해야 하나요?")
        ])

        # 관찰 분석 프롬프트
        self.observation_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 액션 결과를 분석하고 있습니다.

수행한 액션: {action_name}
파라미터: {parameters}
결과: {result}
성공: {success}
에러: {error}

분석:
1. 무엇을 배웠나요?
2. 예상대로 되었나요?
3. 다음에 무엇을 해야 하나요?
4. 실패한 경우, 어떤 대안 접근 방식을 시도해야 하나요?

다음 JSON을 반환하세요:
{{
    "observation": "관찰한 내용",
    "learned": "이것에서 배운 것",
    "meets_expectation": true/false,
    "next_step_suggestion": "다음에 할 일",
    "alternative_tool": "tool_name 또는 null"
}}"""),
            ("user", "이 액션 결과를 분석하세요.")
        ])

        # 메타인지 프롬프트 (자기 평가)
        self.reflection_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 전체 진행 상황을 반성하고 있습니다.

원래 목표: {user_request}
완료한 단계: {completed_count}
남은 단계: {remaining_count}
발생한 에러: {errors}
현재 결과:
{current_results}

실행 요약:
{execution_summary}

반성:
1. 진행이 잘 되고 있나요?
2. 전략을 변경해야 하나요?
3. 루프에 갇혀 있나요?
4. 사람의 도움을 요청해야 하나요?

다음 JSON을 반환하세요:
{{
    "progress_assessment": "good/fair/poor",
    "strategy_change_needed": true/false,
    "new_strategy": "...",
    "stuck_in_loop": true/false,
    "need_human_help": true/false,
    "human_question": "..."
}}"""),
            ("user", "현재 진행 상황을 반성하세요.")
        ])

    async def execute_react_cycle(
        self,
        state: SecurityAnalysisStateV2
    ) -> Dict[str, Any]:
        """
        ReAct 사이클 1회 실행 (개선)
        Think -> Act -> Observe
        재시도 로직 포함

        Args:
            state: 현재 상태

        Returns:
            업데이트할 상태
        """
        print(f"\n[ReAct] Cycle {state.get('iteration', 0) + 1}")

        # 1. THINK
        thought_result = await self._think(state)

        # 조기 종료 체크 (개선)
        iteration = state.get("iteration", 0)
        if not thought_result.get("continue", True):
            # 최소 시도 횟수 미달 시 계속 진행
            if iteration < MIN_ATTEMPTS_BEFORE_STOP:
                print(f"[ReAct] Agent wants to stop but only {iteration} attempts made (min: {MIN_ATTEMPTS_BEFORE_STOP})")
                print(f"[ReAct] Forcing continuation...")
                thought_result["continue"] = True
            else:
                print(f"[ReAct] Agent decided to stop after {iteration} attempts")
                return {
                    "completed": True,
                    "current_step": "finished",
                    **update_thought(state, thought_result["thought"], thought_result["reasoning"])
                }

        # 2. ACT (대안 도구 시도 포함)
        action_result = await self._act_with_fallback(
            state,
            thought_result["next_action"],
            thought_result["parameters"]
        )

        # 3. OBSERVE
        observation_result = await self._observe(
            state,
            thought_result["next_action"],
            thought_result["parameters"],
            action_result
        )

        # 실행 추적
        self.tracker.record_attempt(
            thought_result["next_action"],
            action_result.get("success", False)
        )

        # 연속 실패 경고
        if self.tracker.consecutive_failures >= 2:
            print(f"[ReAct] ⚠️ {self.tracker.consecutive_failures} consecutive failures detected")

        # 상태 업데이트
        updates = {
            "iteration": iteration + 1,
            **update_thought(state, thought_result["thought"], thought_result["reasoning"]),
            **update_action(
                state,
                tool_name=thought_result["next_action"],
                parameters=thought_result["parameters"],
                result=action_result.get("result"),
                success=action_result.get("success", False),
                error=action_result.get("error")
            ),
            **update_observation(state, observation_result["observation"])
        }

        # 도구가 반환한 state_update 반영
        if action_result.get("success") and action_result.get("result"):
            result = action_result["result"]
            if isinstance(result, dict) and "state_update" in result:
                state_update = result["state_update"]
                print(f"[ReAct] Applying state_update: {list(state_update.keys())}")
                updates.update(state_update)

        # 진행률 업데이트
        plan = state.get("execution_plan")
        if plan:
            total_steps = len(plan.get("steps", []))
            completed = len([a for a in state.get("actions", []) if a.get("success")])
            progress = int((completed / total_steps * 100)) if total_steps > 0 else 0
            updates["progress_percentage"] = progress

        # 에러 처리
        if action_result.get("error"):
            errors = state.get("errors", [])
            errors.append({
                "tool": thought_result["next_action"],
                "error": action_result["error"],
                "iteration": iteration + 1
            })
            updates["errors"] = errors

        return updates

    async def _act_with_fallback(
        self,
        state: SecurityAnalysisStateV2,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        도구 실행 (실패 시 대안 시도)

        Args:
            state: 현재 상태
            tool_name: 도구 이름
            parameters: 파라미터

        Returns:
            실행 결과
        """
        # 1차 시도
        result = await self._act(state, tool_name, parameters)

        if result["success"]:
            return result

        # 실패 시 대안 도구 시도
        if tool_name in TOOL_ALTERNATIVES:
            alternatives = TOOL_ALTERNATIVES[tool_name]
            print(f"[ReAct] Tool '{tool_name}' failed, trying alternatives...")

            for alt_tool in alternatives:
                # 이미 여러 번 실패한 도구는 건너뛰기
                if self.tracker.should_try_alternative(alt_tool):
                    print(f"[ReAct]   ✗ Skipping '{alt_tool}' (already failed {MAX_SAME_TOOL_RETRIES} times)")
                    continue

                print(f"[ReAct]   → Trying alternative: '{alt_tool}'")
                alt_result = await self._act(state, alt_tool, parameters)

                if alt_result["success"]:
                    print(f"[ReAct]   ✓ Alternative '{alt_tool}' succeeded!")
                    # 추적기 업데이트
                    self.tracker.record_attempt(alt_tool, True)
                    return alt_result
                else:
                    print(f"[ReAct]   ✗ Alternative '{alt_tool}' also failed")
                    self.tracker.record_attempt(alt_tool, False)

            print(f"[ReAct] All alternatives exhausted for '{tool_name}'")

        return result

    async def _think(self, state: SecurityAnalysisStateV2) -> Dict[str, Any]:
        """사고 단계"""
        print("[ReAct] THINK phase...")

        try:
            # 현재 상황 요약
            execution_plan = state.get("execution_plan", {})
            completed_steps = [
                f"Step {a['tool_name']}: {'Success' if a.get('success') else 'Failed'}"
                for a in state.get("actions", [])
            ]
            observations = state.get("observations", [])[-5:]  # 최근 5개

            # 실패한 도구 목록
            failed_tools = [
                tool for tool, stats in self.tracker.tool_attempts.items()
                if stats["failure"] > 0
            ]

            # 사용 가능한 도구 목록
            available_tools = "\n".join([
                f"- {name}: {tool.__doc__ if hasattr(tool, '__doc__') else 'No description'}"
                for name, tool in self.tools.items()
            ])

            # 현재 상태 요약
            current_state_summary = {
                "dependencies_count": state.get("dependency_count", 0),
                "vulnerabilities_count": state.get("vulnerability_count", 0),
                "lock_files_found": state.get("lock_files_found", []),
                "errors": state.get("errors", [])[-3:]  # 최근 3개
            }

            chain = self.thought_prompt | self.llm
            response = await chain.ainvoke({
                "execution_plan": json.dumps(execution_plan, indent=2, ensure_ascii=False),
                "completed_steps": "\n".join(completed_steps) or "None",
                "current_step": state.get("current_step", "unknown"),
                "observations": "\n".join(observations) or "None",
                "failed_tools": ", ".join(failed_tools) if failed_tools else "None",
                "available_tools": available_tools,
                "current_state": json.dumps(current_state_summary, indent=2, ensure_ascii=False)
            })

            content = response.content
            thought_data = self._extract_json(content)

            print(f"[ReAct]   Thought: {thought_data.get('thought', 'N/A')[:150]}...")
            print(f"[ReAct]   Reasoning: {thought_data.get('reasoning', 'N/A')[:150]}...")
            print(f"[ReAct]   → Selected Tool: '{thought_data.get('next_action', 'N/A')}'")

            return thought_data

        except Exception as e:
            print(f"[ReAct] Think phase error: {e}")
            # 폴백: 계획의 다음 단계 실행
            return self._fallback_think(state)

    async def _act(
        self,
        state: SecurityAnalysisStateV2,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """행동 단계"""
        print(f"\n[ReAct] ACT phase: Calling tool '{tool_name}'")

        # 파라미터 출력 (state 제외)
        display_params = {k: v for k, v in parameters.items() if k != "state"}
        if display_params:
            print(f"[ReAct]   Parameters: {json.dumps(display_params, ensure_ascii=False, default=str)[:200]}")
        else:
            print(f"[ReAct]   Parameters: (using state only)")

        try:
            # 도구 실행
            if tool_name not in self.tools:
                error_msg = f"Tool '{tool_name}' not found"
                print(f"[ReAct]   ✗ Error: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "result": None
                }

            tool = self.tools[tool_name]

            # 상태를 파라미터에 포함
            if "state" not in parameters:
                parameters["state"] = state

            # 도구 실행
            result = await tool(**parameters) if hasattr(tool, '__call__') else None

            # 결과 요약 출력
            if isinstance(result, dict):
                # 결과의 주요 정보만 출력
                result_summary = {}
                for key in ["success", "count", "total", "total_count", "lock_files", "vulnerabilities"]:
                    if key in result:
                        result_summary[key] = result[key]

                if result_summary:
                    print(f"[ReAct]   ✓ Result: {json.dumps(result_summary, ensure_ascii=False, default=str)[:200]}")
                else:
                    print(f"[ReAct]   ✓ Completed successfully")
            else:
                print(f"[ReAct]   ✓ Completed successfully")

            return {
                "success": True,
                "result": result,
                "error": None
            }

        except Exception as e:
            print(f"[ReAct]   ✗ Error: {str(e)[:200]}")
            return {
                "success": False,
                "error": str(e),
                "result": None
            }

    async def _observe(
        self,
        state: SecurityAnalysisStateV2,
        action_name: str,
        parameters: Dict[str, Any],
        action_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """관찰 단계"""
        print("[ReAct] OBSERVE phase...")

        try:
            # 결과를 요약하여 컨텍스트 길이 줄이기
            result = action_result.get("result", {})

            # 결과 요약: 중요한 정보만 추출
            result_summary = {}
            if isinstance(result, dict):
                # 중요한 키만 추출
                important_keys = ["success", "count", "total", "total_count", "lock_files",
                                "vulnerabilities", "dependencies", "error", "summary"]
                for key in important_keys:
                    if key in result:
                        value = result[key]
                        # 리스트나 딕셔너리는 길이만 표시
                        if isinstance(value, list):
                            result_summary[key] = f"[{len(value)} items]"
                        elif isinstance(value, dict):
                            result_summary[key] = f"{{...}} ({len(value)} keys)"
                        else:
                            result_summary[key] = value
            else:
                result_summary = str(result)[:200]  # 문자열인 경우 200자로 제한

            # 파라미터도 요약
            params_summary = {k: v for k, v in parameters.items() if k != "state"}

            chain = self.observation_prompt | self.llm
            response = await chain.ainvoke({
                "action_name": action_name,
                "parameters": json.dumps(params_summary, indent=2, ensure_ascii=False)[:300],
                "result": json.dumps(result_summary, indent=2, ensure_ascii=False)[:500],  # 500자로 제한
                "success": action_result.get("success", False),
                "error": str(action_result.get("error", "None"))[:200]  # 에러 메시지도 200자로 제한
            })

            content = response.content
            observation_data = self._extract_json(content)

            print(f"[ReAct]   Observation: {observation_data.get('observation', 'N/A')[:150]}...")
            print(f"[ReAct]   Learned: {observation_data.get('learned', 'N/A')[:100]}...")

            return observation_data

        except Exception as e:
            print(f"[ReAct] Observe phase error: {e}")
            # 폴백 관찰
            fallback_obs = {
                "observation": f"Executed {action_name}: {'Success' if action_result.get('success') else 'Failed'}",
                "learned": "Action completed",
                "meets_expectation": action_result.get("success", False),
                "next_step_suggestion": "Continue with plan"
            }
            print(f"[ReAct]   Observation (fallback): {fallback_obs['observation']}")
            return fallback_obs

    async def reflect(self, state: SecurityAnalysisStateV2) -> Dict[str, Any]:
        """
        메타인지: 진행 상황 반성 및 전략 조정

        Args:
            state: 현재 상태

        Returns:
            반성 결과 및 전략 변경 제안
        """
        print("\n[ReAct] REFLECT phase (metacognition)...")

        try:
            plan = state.get("execution_plan", {})
            total_steps = len(plan.get("steps", []))
            completed = len([a for a in state.get("actions", []) if a.get("success")])
            remaining = total_steps - completed

            current_results = {
                "dependencies": state.get("dependency_count", 0),
                "vulnerabilities": state.get("vulnerability_count", 0),
                "errors": len(state.get("errors", [])),
                "warnings": len(state.get("warnings", []))
            }

            # 실행 요약 추가
            execution_summary = self.tracker.get_summary()

            chain = self.reflection_prompt | self.llm
            response = await chain.ainvoke({
                "user_request": state.get("user_request", ""),
                "completed_count": completed,
                "remaining_count": remaining,
                "errors": state.get("errors", [])[-5:],
                "current_results": json.dumps(current_results, indent=2, ensure_ascii=False),
                "execution_summary": json.dumps(execution_summary, indent=2, ensure_ascii=False)
            })

            content = response.content
            reflection_data = self._extract_json(content)

            print(f"[ReAct] Progress Assessment: {reflection_data.get('progress_assessment')}")
            print(f"[ReAct] Strategy Change Needed: {reflection_data.get('strategy_change_needed')}")

            return reflection_data

        except Exception as e:
            print(f"[ReAct] Reflect phase error: {e}")
            return {
                "progress_assessment": "fair",
                "strategy_change_needed": False,
                "stuck_in_loop": False,
                "need_human_help": False
            }

    def _fallback_think(self, state: SecurityAnalysisStateV2) -> Dict[str, Any]:
        """LLM 실패시 폴백 사고 (개선)"""
        print("[ReAct]   Using fallback thinking (rule-based)...")

        plan = state.get("execution_plan")
        if not plan:
            print("[ReAct]   → No plan available, cannot proceed")
            return {
                "thought": "No plan available",
                "reasoning": "Cannot proceed without plan",
                "next_action": "none",
                "parameters": {},
                "continue": False
            }

        # 다음 미완료 단계 찾기 (실패한 도구 제외)
        completed_actions = {a["tool_name"] for a in state.get("actions", []) if a.get("success")}
        failed_actions = {a["tool_name"] for a in state.get("actions", []) if not a.get("success")}

        for step in plan.get("steps", []):
            action_name = step["action"]

            # 이미 성공한 단계는 건너뛰기
            if action_name in completed_actions:
                continue

            # 여러 번 실패한 도구는 대안 시도
            if self.tracker.should_try_alternative(action_name):
                if action_name in TOOL_ALTERNATIVES:
                    alternatives = TOOL_ALTERNATIVES[action_name]
                    for alt in alternatives:
                        if alt not in completed_actions and not self.tracker.should_try_alternative(alt):
                            print(f"[ReAct]   → Using alternative '{alt}' instead of '{action_name}'")
                            return {
                                "thought": f"Using alternative tool {alt}",
                                "reasoning": f"{action_name} failed multiple times",
                                "next_action": alt,
                                "parameters": step.get("parameters", {}),
                                "expected_outcome": f"Alternative to {action_name}",
                                "continue": True
                            }

            # 정상적으로 다음 단계 실행
            print(f"[ReAct]   → Following plan: Step {step['step_number']} - {action_name}")
            return {
                "thought": f"Following plan: Step {step['step_number']}",
                "reasoning": "Using predefined plan",
                "next_action": action_name,
                "parameters": step.get("parameters", {}),
                "expected_outcome": step.get("description", ""),
                "continue": True
            }

        # 모든 단계 완료
        print("[ReAct]   → All planned steps completed")
        return {
            "thought": "All planned steps completed",
            "reasoning": "Plan execution finished",
            "next_action": "finish",
            "parameters": {},
            "continue": False
        }

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출"""
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif '```' in content:
            parts = content.split('```')
            if len(parts) >= 2:
                content = parts[1].strip()

        # JSON 파싱
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # JSON이 아닌 경우 텍스트로 반환
            return {"raw_response": content}

    def should_continue(self, state: SecurityAnalysisStateV2) -> bool:
        """
        계속 실행할지 판단 (개선)

        Args:
            state: 현재 상태

        Returns:
            계속 실행 여부
        """
        iteration = state.get("iteration", 0)

        # 최대 반복 횟수 체크
        if iteration >= state.get("max_iterations", 20):
            print(f"[ReAct] Max iterations reached ({iteration})")
            return False

        # 완료 플래그 체크
        if state.get("completed", False):
            print("[ReAct] Task marked as completed")
            return False

        # 계획의 모든 단계가 완료되었는지 체크
        plan = state.get("execution_plan")
        if plan:
            total_steps = len(plan.get("steps", []))
            completed = len([a for a in state.get("actions", []) if a.get("success")])

            if completed >= total_steps and iteration >= MIN_ATTEMPTS_BEFORE_STOP:
                print(f"[ReAct] All planned steps completed ({completed}/{total_steps})")
                return False

        # 치명적 에러 체크 (개선)
        errors = state.get("errors", [])
        if len(errors) > 10:  # 10개 이상 에러 (5개에서 증가)
            print(f"[ReAct] Too many errors ({len(errors)}), stopping")
            return False

        # 최소 시도 횟수 미달 시 계속 진행
        if iteration < MIN_ATTEMPTS_BEFORE_STOP:
            print(f"[ReAct] Continuing (min attempts: {MIN_ATTEMPTS_BEFORE_STOP}, current: {iteration})")
            return True

        return True

    def get_execution_stats(self) -> Dict[str, Any]:
        """실행 통계 반환"""
        return {
            "tracker_summary": self.tracker.get_summary(),
            "tool_success_rates": {
                tool: {
                    "success": stats["success"],
                    "failure": stats["failure"],
                    "success_rate": stats["success"] / (stats["success"] + stats["failure"]) * 100
                    if (stats["success"] + stats["failure"]) > 0 else 0
                }
                for tool, stats in self.tracker.tool_attempts.items()
            }
        }
