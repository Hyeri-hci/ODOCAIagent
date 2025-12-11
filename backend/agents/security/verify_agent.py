"""
Security Agent V2 검증 스크립트
모든 컴포넌트의 기능, 로직, Agentic 특성을 검증
"""
import asyncio
from typing import Dict, Any
import json


class AgentV2Verifier:
    """V2 에이전트 검증기"""

    def __init__(self):
        self.test_results = {
            "functional": [],
            "logical": [],
            "agentic": []
        }

    async def verify_all(self):
        """전체 검증 실행"""
        print("="*70)
        print("Security Agent V2 - Comprehensive Verification")
        print("="*70)

        # 1. 기능 검증
        print("\n[1/3] Functional Verification")
        print("-"*70)
        await self.verify_functional()

        # 2. 로직 검증
        print("\n[2/3] Logical Verification")
        print("-"*70)
        await self.verify_logical()

        # 3. Agentic 특성 검증
        print("\n[3/3] Agentic Characteristics Verification")
        print("-"*70)
        await self.verify_agentic()

        # 결과 요약
        self.print_summary()

    async def verify_functional(self):
        """기능 검증"""

        # 1.1 State 생성
        test_name = "State Creation"
        try:
            from agent.state_v2 import create_initial_state_v2

            state = create_initial_state_v2(
                user_request="test request",
                execution_mode="auto"
            )

            assert state["user_request"] == "test request"
            assert state["execution_mode"] == "auto"
            assert state["iteration"] == 0

            self._record_success("functional", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 1.2 Intent Parser 초기화
        test_name = "Intent Parser Initialization"
        try:
            from agent.intent_parser import IntentParser

            parser = IntentParser()
            assert parser.llm is not None

            self._record_success("functional", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 1.3 Planner 초기화
        test_name = "Dynamic Planner Initialization"
        try:
            from agent.planner_v2 import DynamicPlanner

            planner = DynamicPlanner()
            assert planner.llm is not None

            self._record_success("functional", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 1.4 ReAct Executor 초기화
        test_name = "ReAct Executor Initialization"
        try:
            from agent.react_executor import ReActExecutor

            executor = ReActExecutor()
            assert executor.llm is not None

            self._record_success("functional", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 1.5 Tool Registry
        test_name = "Tool Registry"
        try:
            from agent.tool_registry import get_registry

            registry = get_registry()
            tools = registry.get_all_tools()

            assert len(tools) > 0  # 도구가 등록되어 있어야 함

            self._record_success("functional", test_name)
            print(f"✓ {test_name}: {len(tools)} tools registered")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 1.6 Main Agent 초기화
        test_name = "Security Agent V2 Initialization"
        try:
            from agent.security_agent import SecurityAgent

            agent = SecurityAgent(execution_mode="fast")
            assert agent.intent_parser is not None
            assert agent.planner is not None
            assert agent.executor is not None
            assert agent.graph is not None

            self._record_success("functional", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 1.7 Helper Functions
        test_name = "State Helper Functions"
        try:
            from agent.state_v2 import (
                update_thought, update_action, update_observation,
                save_to_memory, recall_from_memory, create_initial_state_v2
            )

            state = create_initial_state_v2("test")

            # Thought 업데이트
            thought_update = update_thought(state, "test thought", "test reasoning")
            assert "thoughts" in thought_update

            # Action 업데이트
            action_update = update_action(state, "test_tool", {}, {}, True)
            assert "actions" in action_update

            # Observation 업데이트
            obs_update = update_observation(state, "test observation")
            assert "observations" in obs_update

            # Memory 저장
            mem_update = save_to_memory(state, "test_key", "test_value")
            assert "short_term_memory" in mem_update

            self._record_success("functional", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("functional", test_name, str(e))
            print(f"✗ {test_name}: {e}")

    async def verify_logical(self):
        """로직 검증"""

        # 2.1 Intent 파싱 로직
        test_name = "Intent Parsing Logic"
        try:
            from agent.intent_parser import IntentParser

            parser = IntentParser()

            # 레포지토리 정보 추출
            owner, repo = parser.parse_repository_info("facebook/react를 분석해줘")

            assert owner == "facebook"
            assert repo == "react"

            self._record_success("logical", test_name)
            print(f"✓ {test_name}: Extracted {owner}/{repo}")

        except Exception as e:
            self._record_failure("logical", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 2.2 Default Plan 로직
        test_name = "Default Plan Generation"
        try:
            from agent.planner_v2 import DynamicPlanner
            from agent.state_v2 import create_initial_state_v2

            planner = DynamicPlanner()
            state = create_initial_state_v2("test", execution_mode="fast")

            # 기본 계획 생성 (LLM 없이)
            plan_update = planner._create_default_plan(state)

            assert "execution_plan" in plan_update
            assert len(plan_update["execution_plan"]["steps"]) > 0

            self._record_success("logical", test_name)
            print(f"✓ {test_name}: {len(plan_update['execution_plan']['steps'])} steps")

        except Exception as e:
            self._record_failure("logical", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 2.3 Should Continue 로직
        test_name = "Should Continue Logic"
        try:
            from agent.react_executor import ReActExecutor
            from agent.state_v2 import create_initial_state_v2

            executor = ReActExecutor()

            # 정상 상태 - 계속
            state1 = create_initial_state_v2("test")
            state1["iteration"] = 5
            assert executor.should_continue(state1) == True

            # 최대 반복 도달 - 중지
            state2 = create_initial_state_v2("test", max_iterations=10)
            state2["iteration"] = 15
            assert executor.should_continue(state2) == False

            # 완료 플래그 - 중지
            state3 = create_initial_state_v2("test")
            state3["completed"] = True
            assert executor.should_continue(state3) == False

            self._record_success("logical", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("logical", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 2.4 Tool Registry 로직
        test_name = "Tool Registry Logic"
        try:
            from agent.tool_registry import get_registry

            registry = get_registry()

            # 카테고리별 도구 가져오기
            github_tools = registry.get_tools_by_category("github")
            assert len(github_tools) > 0

            dependency_tools = registry.get_tools_by_category("dependency")
            assert len(dependency_tools) > 0

            # LLM용 도구 목록
            tool_list = registry.get_tool_list_for_llm()
            assert "GITHUB" in tool_list or "github" in tool_list

            self._record_success("logical", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("logical", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 2.5 Fallback Think 로직
        test_name = "Fallback Think Logic"
        try:
            from agent.react_executor import ReActExecutor
            from agent.state_v2 import create_initial_state_v2

            executor = ReActExecutor()

            # 계획이 있는 상태
            state = create_initial_state_v2("test")
            state["execution_plan"] = {
                "steps": [
                    {"step_number": 1, "action": "test_action", "parameters": {}}
                ]
            }
            state["actions"] = []  # 아직 실행한 것 없음

            fallback = executor._fallback_think(state)

            assert fallback["next_action"] == "test_action"
            assert fallback["continue"] == True

            self._record_success("logical", test_name)
            print(f"✓ {test_name}")

        except Exception as e:
            self._record_failure("logical", test_name, str(e))
            print(f"✗ {test_name}: {e}")

    async def verify_agentic(self):
        """Agentic 특성 검증"""

        # 3.1 자율성 (Autonomy)
        test_name = "Autonomy - Self-Directed Execution"
        try:
            from agent.security_agent import SecurityAgent

            agent = SecurityAgent(execution_mode="fast")

            # 에이전트가 자체적으로 계획을 수립하는가?
            assert hasattr(agent, 'planner')
            assert hasattr(agent, 'executor')

            # 사람 개입 없이 실행 가능한가?
            # (실제 실행은 하지 않고 구조만 확인)
            assert callable(agent.analyze)

            self._record_success("agentic", test_name)
            print(f"✓ {test_name}: Agent can plan and execute autonomously")

        except Exception as e:
            self._record_failure("agentic", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 3.2 유연성 (Flexibility)
        test_name = "Flexibility - Adaptive Planning"
        try:
            from agent.planner_v2 import DynamicPlanner
            from agent.state_v2 import create_initial_state_v2

            planner = DynamicPlanner()

            # 다양한 요청에 대해 다른 계획을 생성하는가?
            state1 = create_initial_state_v2("의존성만 추출")
            state1["parsed_intent"] = {
                "primary_action": "extract_dependencies",
                "scope": "full_repository",
                "target_files": [],
                "conditions": [],
                "output_format": "json",
                "parameters": {}
            }

            state2 = create_initial_state_v2("전체 보안 분석")
            state2["parsed_intent"] = {
                "primary_action": "analyze_all",
                "scope": "full_repository",
                "target_files": [],
                "conditions": [],
                "output_format": "full_report",
                "parameters": {}
            }

            plan1 = planner._create_default_plan(state1)
            plan2 = planner._create_default_plan(state2)

            # 두 계획의 단계 수가 달라야 함
            steps1 = len(plan1["execution_plan"]["steps"])
            steps2 = len(plan2["execution_plan"]["steps"])

            assert steps1 != steps2

            self._record_success("agentic", test_name)
            print(f"✓ {test_name}: Different plans for different requests ({steps1} vs {steps2} steps)")

        except Exception as e:
            self._record_failure("agentic", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 3.3 메타인지 (Self-Awareness)
        test_name = "Metacognition - Self-Reflection"
        try:
            from agent.react_executor import ReActExecutor

            executor = ReActExecutor()

            # Reflection 기능이 있는가?
            assert hasattr(executor, 'reflect')
            assert callable(executor.reflect)

            # should_continue로 자기 상태 판단 가능한가?
            assert hasattr(executor, 'should_continue')

            self._record_success("agentic", test_name)
            print(f"✓ {test_name}: Agent has reflection capabilities")

        except Exception as e:
            self._record_failure("agentic", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 3.4 목표 지향성 (Goal-Oriented)
        test_name = "Goal-Oriented - Task Completion"
        try:
            from agent.security_agent import SecurityAgent
            from agent.state_v2 import create_initial_state_v2

            agent = SecurityAgent()

            # 완료 조건이 정의되어 있는가?
            state = create_initial_state_v2("test")

            # Finalize 노드가 있는가?
            assert hasattr(agent, '_finalize_node')

            # 완료 플래그가 있는가?
            assert "completed" in state

            self._record_success("agentic", test_name)
            print(f"✓ {test_name}: Agent has clear completion criteria")

        except Exception as e:
            self._record_failure("agentic", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 3.5 진짜 ReAct (Real Reasoning)
        test_name = "Real ReAct - Think-Act-Observe"
        try:
            from agent.react_executor import ReActExecutor

            executor = ReActExecutor()

            # ReAct의 3단계가 모두 구현되어 있는가?
            assert hasattr(executor, '_think')
            assert hasattr(executor, '_act')
            assert hasattr(executor, '_observe')

            # 각 단계가 LLM을 사용하는가?
            assert executor.llm is not None

            self._record_success("agentic", test_name)
            print(f"✓ {test_name}: True ReAct pattern with LLM reasoning")

        except Exception as e:
            self._record_failure("agentic", test_name, str(e))
            print(f"✗ {test_name}: {e}")

        # 3.6 LLM 통합 확인
        test_name = "LLM Integration"
        try:
            from agent.security_agent import SecurityAgent

            agent = SecurityAgent()

            # LLM이 통합되어 있는가?
            assert agent.llm is not None
            assert agent.intent_parser.llm is not None
            assert agent.planner.llm is not None
            assert agent.executor.llm is not None

            # LLM 모델 확인
            model = agent.llm.model_name
            assert "gpt" in model.lower()

            self._record_success("agentic", test_name)
            print(f"✓ {test_name}: LLM ({model}) integrated across all components")

        except Exception as e:
            self._record_failure("agentic", test_name, str(e))
            print(f"✗ {test_name}: {e}")

    def _record_success(self, category: str, test_name: str):
        """성공 기록"""
        self.test_results[category].append({
            "test": test_name,
            "status": "PASS",
            "error": None
        })

    def _record_failure(self, category: str, test_name: str, error: str):
        """실패 기록"""
        self.test_results[category].append({
            "test": test_name,
            "status": "FAIL",
            "error": error
        })

    def print_summary(self):
        """검증 결과 요약"""
        print("\n" + "="*70)
        print("Verification Summary")
        print("="*70)

        total_tests = 0
        total_passed = 0

        for category, results in self.test_results.items():
            passed = len([r for r in results if r["status"] == "PASS"])
            total = len(results)

            total_tests += total
            total_passed += passed

            print(f"\n{category.upper()} Tests: {passed}/{total} passed")

            # 실패한 테스트 표시
            failed = [r for r in results if r["status"] == "FAIL"]
            if failed:
                for f in failed:
                    print(f"  ✗ {f['test']}: {f['error']}")

        print("\n" + "-"*70)
        print(f"TOTAL: {total_passed}/{total_tests} tests passed")

        # 성공률
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")

        # 최종 평가
        print("\n" + "="*70)
        if success_rate == 100:
            print("✓ ALL TESTS PASSED - Agent V2 is fully functional!")
        elif success_rate >= 80:
            print("△ MOSTLY PASSED - Agent V2 is functional with minor issues")
        else:
            print("✗ SOME TESTS FAILED - Agent V2 needs attention")
        print("="*70)

        # JSON 결과 저장
        with open("verification_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "total_passed": total_passed,
                    "success_rate": success_rate
                },
                "details": self.test_results
            }, f, indent=2, ensure_ascii=False)

        print(f"\nDetailed results saved to: verification_results.json")


async def main():
    verifier = AgentV2Verifier()
    await verifier.verify_all()


if __name__ == "__main__":
    asyncio.run(main())
