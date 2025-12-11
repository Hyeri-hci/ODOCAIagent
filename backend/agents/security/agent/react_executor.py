"""
ReAct Executor
진짜 ReAct 패턴 구현: Think -> Act -> Observe 사이클
"""
from typing import Dict, Any, List, Optional, Callable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state import SecurityAnalysisState, update_thought, update_action, update_observation
from datetime import datetime
import json
import re


class ReActExecutor:
    """ReAct 패턴 기반 실행기"""

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

        # ReAct 사고 프롬프트
        self.thought_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security analysis agent using the ReAct (Reasoning + Acting) pattern.

Current Execution Plan:
{execution_plan}

Progress so far:
- Completed steps: {completed_steps}
- Current step: {current_step}
- Observations: {observations}

Available Tools:
{available_tools}

Current State:
{current_state}

Your task:
1. THINK: Analyze the current situation
2. Decide what to do next
3. Choose the appropriate tool
4. Specify parameters

Return JSON:
{{
    "thought": "Your reasoning about the current situation",
    "reasoning": "Why you're taking this action",
    "next_action": "tool_name",
    "parameters": {{}},
    "expected_outcome": "What you expect to happen",
    "continue": true/false
}}

If the task is complete or stuck, set "continue": false"""),
            ("user", "What should I do next?")
        ])

        # 관찰 분석 프롬프트
        self.observation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are analyzing the result of an action.

Action taken: {action_name}
Parameters: {parameters}
Result: {result}
Success: {success}
Error: {error}

Analyze:
1. What did we learn?
2. Did it meet expectations?
3. What should we do next?

Return JSON:
{{
    "observation": "What you observed",
    "learned": "What you learned from this",
    "meets_expectation": true/false,
    "next_step_suggestion": "What to do next"
}}"""),
            ("user", "Analyze this action result.")
        ])

        # 메타인지 프롬프트 (자기 평가)
        self.reflection_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are reflecting on your overall progress.

Original Goal: {user_request}
Steps Completed: {completed_count}
Steps Remaining: {remaining_count}
Errors Encountered: {errors}
Current Results:
{current_results}

Reflect:
1. Are we making good progress?
2. Should we change strategy?
3. Are we stuck in a loop?
4. Should we ask for human help?

Return JSON:
{{
    "progress_assessment": "good/fair/poor",
    "strategy_change_needed": true/false,
    "new_strategy": "...",
    "stuck_in_loop": true/false,
    "need_human_help": true/false,
    "human_question": "..."
}}"""),
            ("user", "Reflect on current progress.")
        ])

    async def execute_react_cycle(
        self,
        state: SecurityAnalysisState
    ) -> Dict[str, Any]:
        """
        ReAct 사이클 1회 실행
        Think -> Act -> Observe

        Args:
            state: 현재 상태

        Returns:
            업데이트할 상태
        """
        print(f"\n[ReAct] Cycle {state.get('iteration', 0) + 1}")

        # 1. THINK
        thought_result = await self._think(state)

        if not thought_result.get("continue", True):
            print("[ReAct] Agent decided to stop")
            return {
                "completed": True,
                "current_step": "finished",
                **update_thought(state, thought_result["thought"], thought_result["reasoning"])
            }

        # 2. ACT
        action_result = await self._act(
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

        # 상태 업데이트
        updates = {
            "iteration": state.get("iteration", 0) + 1,
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
        # Debug: action_result 구조 출력
        print(f"[ReAct] DEBUG - action_result keys: {list(action_result.keys()) if isinstance(action_result, dict) else 'not a dict'}")
        print(f"[ReAct] DEBUG - action_result.success: {action_result.get('success')}")
        if action_result.get("result"):
            print(f"[ReAct] DEBUG - result type: {type(action_result['result'])}")
            if isinstance(action_result["result"], dict):
                print(f"[ReAct] DEBUG - result keys: {list(action_result['result'].keys())}")

        if action_result.get("success") and action_result.get("result"):
            result = action_result["result"]
            if isinstance(result, dict) and "state_update" in result:
                state_update = result["state_update"]
                print(f"[ReAct] Applying state_update: {list(state_update.keys())}")
                updates.update(state_update)
            else:
                print(f"[ReAct] DEBUG - No state_update in result")

        # 진행률 업데이트
        plan = state.get("execution_plan")
        if plan:
            total_steps = len(plan.get("steps", []))
            completed = len([a for a in state.get("actions", []) if a.get("success")])
            progress = int((completed / total_steps * 100)) if total_steps > 0 else 0
            updates["progress_percentage"] = progress

        # 에러 처리
        if action_result.get("error"):
            updates["errors"] = [action_result["error"]]

        return updates

    async def _think(self, state: SecurityAnalysisState) -> Dict[str, Any]:
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
        state: SecurityAnalysisState,
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
        state: SecurityAnalysisState,
        action_name: str,
        parameters: Dict[str, Any],
        action_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """관찰 단계"""
        print("[ReAct] OBSERVE phase...")

        try:
            chain = self.observation_prompt | self.llm
            response = await chain.ainvoke({
                "action_name": action_name,
                "parameters": json.dumps(parameters, indent=2, ensure_ascii=False),
                "result": json.dumps(action_result.get("result"), indent=2, ensure_ascii=False)[:1000],  # 길이 제한
                "success": action_result.get("success", False),
                "error": action_result.get("error", "None")
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

    async def reflect(self, state: SecurityAnalysisState) -> Dict[str, Any]:
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

            chain = self.reflection_prompt | self.llm
            response = await chain.ainvoke({
                "user_request": state.get("user_request", ""),
                "completed_count": completed,
                "remaining_count": remaining,
                "errors": state.get("errors", [])[-5:],
                "current_results": json.dumps(current_results, indent=2, ensure_ascii=False)
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

    def _fallback_think(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """LLM 실패시 폴백 사고"""
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

        # 다음 미완료 단계 찾기
        completed_actions = {a["tool_name"] for a in state.get("actions", []) if a.get("success")}

        for step in plan.get("steps", []):
            if step["action"] not in completed_actions:
                print(f"[ReAct]   → Following plan: Step {step['step_number']} - {step['action']}")
                return {
                    "thought": f"Following plan: Step {step['step_number']}",
                    "reasoning": "Using predefined plan",
                    "next_action": step["action"],
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

    def should_continue(self, state: SecurityAnalysisState) -> bool:
        """
        계속 실행할지 판단

        Args:
            state: 현재 상태

        Returns:
            계속 실행 여부
        """
        # 최대 반복 횟수 체크
        if state.get("iteration", 0) >= state.get("max_iterations", 20):
            print("[ReAct] Max iterations reached")
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

            if completed >= total_steps:
                print("[ReAct] All planned steps completed")
                return False

        # 치명적 에러 체크
        errors = state.get("errors", [])
        if len(errors) > 5:  # 5개 이상 에러
            print("[ReAct] Too many errors, stopping")
            return False

        return True
