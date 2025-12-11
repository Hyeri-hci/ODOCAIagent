import json
import asyncio
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config.setting import settings
from agent.v1.state import RecommendationState, update_action, update_thought
from agent.v1.tool_registry import TOOLS_MAP

# === 대안 도구 매핑 ===
TOOL_ALTERNATIVES = {
    "github_filter_tool": ["pass_through"], 
    "qdrant_search_executor": ["github_search_query_generator"], 
}

# === 다음 단계 자동 연결 (Chain) ===
NEXT_STEPS_CHAIN = {
    "github_search_query_generator": "github_search_tool",
    "github_search_tool": "github_filter_tool"
}

class ToolExecutionTracker:
    """도구 실행 상태 추적기"""
    def __init__(self):
        self.tool_attempts = {} 
        self.consecutive_failures = 0

    def record_attempt(self, tool_name: str, success: bool):
        if tool_name not in self.tool_attempts:
            self.tool_attempts[tool_name] = {"success": 0, "failure": 0}
        
        if success:
            self.tool_attempts[tool_name]["success"] += 1
            self.consecutive_failures = 0
        else:
            self.tool_attempts[tool_name]["failure"] += 1
            self.consecutive_failures += 1

    def should_try_alternative(self, tool_name: str) -> bool:
        failures = self.tool_attempts.get(tool_name, {}).get("failure", 0)
        return failures >= 2

class ReActExecutor:
    """GitHub 추천 에이전트 실행기"""

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0
        )
        self.tools = TOOLS_MAP
        self.tracker = ToolExecutionTracker()

        # Observation Prompt
        self.observation_prompt = ChatPromptTemplate.from_messages([
            ("system", """도구 실행 결과를 분석하십시오.
            [Action]: {action}
            [Result]: {result}
            [Success]: {success}
            JSON 응답: {{ "observation": "결과 요약 (한국어)", "status": "success" | "failure" }}
            """),
            ("user", "결과를 분석해줘.")
        ])

    async def execute_step(self, state: RecommendationState) -> Dict[str, Any]:
        print(f"\n🔄 [Executor] Cycle Start (Iteration {state.get('iteration', 0) + 1})")

        # 1. THINK: 계획표에서 다음 할 일을 찾음
        decision = self._get_next_step_from_plan(state)
        action_name = decision.get("next_action")
        
        if action_name == "FINISH" or not decision.get("continue"):
            print("🛑 [Executor] All steps completed or stopped.")
            return {"completed": True}

        # 2. ACT (입력값 해결)
        tool_inputs = self._resolve_inputs(state, action_name)
        
        # Fallback Check
        current_using_alternative = False
        if self.tracker.should_try_alternative(action_name):
            print(f"⚠️ [Executor] Tool '{action_name}' failing. Checking alternatives...")
            alt_tool = self._get_alternative(action_name)
            if alt_tool:
                print(f"🔀 [Executor] Switching to alternative: {alt_tool}")
                action_name = alt_tool
                tool_inputs = self._resolve_inputs(state, action_name)
                current_using_alternative = True

        # 실행
        action_result = await self._act(action_name, tool_inputs)
        self.tracker.record_attempt(action_name, action_result["success"])

        # 3. OBSERVE
        observation = await self._observe(action_name, action_result)
        
        # 4. State Update (결과 저장 및 계획 수정)
        updates = self._create_state_updates(state, decision, action_name, tool_inputs, action_result, observation)
        
        # 대안 도구 성공 시, 후속 작업(Chain) 계획 자동 추가
        if current_using_alternative and action_result["success"]:
            updates = self._extend_plan_dynamically(state, updates, action_name)

        return updates

    def _get_next_step_from_plan(self, state: RecommendationState) -> Dict[str, Any]:
        """Plan과 Action History를 비교하여 다음 단계를 결정"""
        plan = state.get("execution_plan", {})
        steps = plan.get("steps", [])
        
        completed_tools = [
            action['tool_name'] 
            for action in state.get("actions", []) 
            if action.get("success")
        ]

        for step in steps:
            tool_name = step['action']
            
            # 1. 원래 도구가 성공했으면 Pass
            if tool_name in completed_tools:
                continue
                
            # 2. 대안 도구가 성공했어도 Pass
            alt_tool = self._get_alternative(tool_name)
            if alt_tool and alt_tool in completed_tools:
                print(f"⏩ [Executor] Skipping '{tool_name}' (Alternative '{alt_tool}' completed)")
                continue

            return {
                "thought": f"Executing Plan Step {step['step_number']}: {step['description']}",
                "next_action": tool_name,
                "continue": True
            }
        
        return {
            "thought": "All planned steps are completed.",
            "next_action": "FINISH",
            "continue": False
        }

    def _extend_plan_dynamically(self, state: RecommendationState, updates: Dict, current_tool: str) -> Dict:
        """대안 도구 실행 후, 연결된 후속 도구를 계획에 동적으로 추가"""
        next_tool = NEXT_STEPS_CHAIN.get(current_tool)
        if not next_tool:
            return updates

        current_plan = state.get("execution_plan", {}).copy()
        current_steps = current_plan.get("steps", [])
        
        existing_tools = [s['action'] for s in current_steps]
        if next_tool in existing_tools:
            return updates

        print(f"🔗 [Executor] Dynamic Planning: Appending '{next_tool}' after '{current_tool}'")
        
        new_step_num = len(current_steps) + 1
        new_step = {
            "step_number": new_step_num,
            "action": next_tool,
            "description": f"Automatically added after {current_tool}",
            "validation": "Auto-chained",
            "fallback": "None"
        }
        current_steps.append(new_step)
        current_plan["steps"] = current_steps
        
        updates["execution_plan"] = current_plan
        return updates

    def _resolve_inputs(self, state: RecommendationState, tool_name: str) -> Dict[str, Any]:
        """
        State에서 각 도구에 필요한 입력값을 추출하여 주입
        """
        inputs = {}
        
        # 1. 필터 도구 (InjectedState 사용)
        if tool_name == "github_filter_tool":
            # 💡 [핵심 수정] Tool이 'state' 인자를 받으므로, 딕셔너리로 감싸서 전달
            inputs["state"] = state

        # 2. 검색 쿼리 생성기
        elif tool_name == "github_search_query_generator":
            inputs["user_input"] = state.get("user_request")

        # 3. 트렌드 검색 도구 (쿼리만 전달)
        elif tool_name == "github_trend_search_tool":
            inputs["query"] = state.get("user_request")

        # 4. API 검색 도구
        elif tool_name == "github_search_tool":
            queries = state.get("search_queries", [])
            if queries:
                inputs["params"] = queries[-1] 
            else:
                inputs["params"] = {"query": state.get("user_request")}

        # 5. Ingest 도구
        elif tool_name == "github_ingest_tool":
            intent = state.get("parsed_intent", {})
            target = intent.get("target_repo")
            if target:
                inputs["repo_url"] = target
            else:
                match = re.search(r'(https?://[^\s]+)', state.get("user_request", ""))
                inputs["repo_url"] = match.group(1) if match else ""

        # 6. RAG 쿼리 생성
        elif tool_name == "rag_query_generator":
            intent = state.get("parsed_intent", {})
            inputs["user_request"] = state.get("user_request")
            inputs["category"] = intent.get("category", "semantic_search")
            analyzed = state.get("analyzed_data", {})
            if analyzed:
                first_key = next(iter(analyzed))
                inputs["analyzed_data"] = analyzed[first_key]

        # 7. 벡터 검색
        elif tool_name == "qdrant_search_executor":
            rag_qs = state.get("rag_queries", [])
            if rag_qs:
                last_q = rag_qs[-1]
                inputs["query"] = last_q.get("query")
                inputs["filters"] = last_q.get("filters")
                inputs["keywords"] = last_q.get("keywords")
            else:
                inputs["query"] = state.get("user_request")
        
        return inputs

    async def _act(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        print(f"🛠️ [Act] Executing: {tool_name}")
        tool_func = self.tools.get(tool_name)
        if not tool_func:
            return {"success": False, "error": f"Tool {tool_name} not found", "result": None}

        try:
            # 비동기/동기 호출 분기 처리
            if hasattr(tool_func, "ainvoke"):
                result_str = await tool_func.ainvoke(inputs)
            else:
                if asyncio.iscoroutinefunction(tool_func):
                    result_str = await tool_func(**inputs)
                else:
                    result_str = tool_func(**inputs)
            
            # JSON 결과 파싱 (안전장치)
            try:
                result_data = json.loads(result_str)
            except:
                result_data = result_str # JSON이 아니면 그대로 사용
            
            if isinstance(result_data, dict) and "error" in result_data:
                return {"success": False, "error": result_data["error"], "result": result_data}
            
            return {"success": True, "result": result_data, "error": None}

        except Exception as e:
            return {"success": False, "error": str(e), "result": None}

    async def _observe(self, action_name: str, action_result: Dict) -> Dict[str, Any]:
        """결과 관찰 및 요약"""
        try:
            # 비용 절약을 위해 간단한 로깅만 수행하거나, 필요 시 LLM 요약 활성화
            return {"observation": "Executed", "status": "success" if action_result["success"] else "failure"}
        except:
            return {"observation": "Error observing", "status": "unknown"}

    def _create_state_updates(self, state, decision, action, inputs, result, observation):
        """결과를 State의 적절한 위치에 저장"""
        updates = {
            **update_thought(state, decision.get("thought", "Action executed")),
            **update_action(action, inputs, result.get("result"), result["success"], result.get("error")),
            "observations": state.get("observations", []) + [{
                "timestamp": datetime.now().isoformat(),
                "observation": str(observation),
                "step": state.get("iteration", 0)
            }]
        }
        data = result.get("result")
        if not data: return updates

        # 도구별 데이터 라우팅
        if action == "github_search_query_generator":
            updates["search_queries"] = [data]
        elif action == "github_search_tool":
            updates["raw_candidates"] = data
        elif action == "github_trend_search_tool": # [NEW] 트렌드 결과도 후보군에 저장
            updates["raw_candidates"] = data
        elif action == "github_filter_tool":
            updates["filtered_candidates"] = data
        elif action == "github_ingest_tool":
            url = inputs.get("repo_url", "unknown")
            updates["analyzed_data"] = {url: data}
        elif action == "rag_query_generator":
            updates["rag_queries"] = [data]
        elif action == "qdrant_search_executor":
            updates["raw_candidates"] = data.get("final_recommendations", [])
            
        return updates

    def _get_alternative(self, tool_name: str) -> Optional[str]:
        alts = TOOL_ALTERNATIVES.get(tool_name)
        return alts[0] if alts else None

# =============================================================================
# 🧪 TEST SUITE
# =============================================================================
async def run_executor_test(case_name: str, initial_state: RecommendationState):
    print(f"\n{'='*20} [EXECUTOR TEST: {case_name}] {'='*20}")
    print(f"🎯 Goal: {initial_state['user_request']}")
    
    executor = ReActExecutor()
    current_state = initial_state.copy() 
    
    for i in range(8):
        result = await executor.execute_step(current_state)
        
        # State Update (List Append)
        for key, value in result.items():
            if key in ["actions", "thoughts", "search_queries", "rag_queries", "observations"]:
                current_state[key] = current_state.get(key, []) + value
            elif key == "execution_plan":
                current_state[key] = value
            else:
                current_state[key] = value
        
        current_state["iteration"] = current_state.get("iteration", 0) + 1
        
        if result.get("completed"):
            print("\n✅ Task Completed Successfully!")
            break
            
    print("\n📊 Final State Summary:")
    print(f"- Actions Count: {len(current_state.get('actions', []))}")
    return current_state

async def test_executor_comprehensive():
    # RAG Flow with Fallback Scenario
    plan_rag = {
        "steps": [
            {"step_number": 1, "action": "github_ingest_tool", "description": "URL 분석", "fallback": "N/A"},
            {"step_number": 2, "action": "rag_query_generator", "description": "벡터 쿼리 생성", "fallback": "N/A"},
            {"step_number": 3, "action": "qdrant_search_executor", "description": "벡터 검색", "fallback": "N/A"}
        ],
        "reasoning": "URL Analysis"
    }
    intent_rag = {"category": "url_analysis", "target_repo": "tiangolo/fastapi"}
    state_rag = {
        "user_request": "fastapi랑 비슷한거",
        "parsed_intent": intent_rag,
        "execution_plan": plan_rag,
        "iteration": 0,
        "actions": [],
        "rag_queries": [],
        "search_queries": [],
        "analyzed_data": {}
    }
    await run_executor_test("RAG / Ingest Flow (Simulated Fail)", state_rag)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_executor_comprehensive())
    except Exception as e:
        print(f"❌ Test Failed: {e}")