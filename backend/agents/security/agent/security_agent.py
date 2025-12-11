from typing import Dict, Any, Optional, Literal
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from .state import (
    SecurityAnalysisState,
    create_initial_state,
    update_thought,
    update_observation,
    save_to_memory,
    recall_from_memory
)
from .intent_parser import IntentParser
from .planner import DynamicPlanner
from .react_executor_improved import ReActExecutor
from .tool_registry import get_registry
from datetime import datetime
import json

# SecurityAgent 클래스
class SecurityAgent:
    def __init__(
        self,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        llm_temperature: float,
        execution_mode: Literal["fast", "intelligent", "auto"] = "auto",
            # 실행모드 : fast-규칙기반, intelligent-LLM기반, auto-자동
        max_iterations: int = 20,
            # 최대 반복 횟수-ReAct 패턴에서 사용될 최대 반복 횟수
        enable_reflection: bool = True,
            # 반성을 할 것인지 아닌지 활성화
    ):
        # LLM 선언을 위한 파라미터
        self.LLM_BASE_URL = llm_base_url
        self.LLM_API_KEY = llm_api_key
        self.LLM_MODEL = llm_model
        self.LLM_TEMPERATURE = llm_temperature

        # LLM 선언
        self.llm = ChatOpenAI(
            api_key=self.LLM_API_KEY,
            base_url=self.LLM_BASE_URL,
            model=self.LLM_MODEL,
            temperature=self.LLM_TEMPERATURE,
        )

        # 클래스 내부 필드 선언
        self.execution_mode = execution_mode
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection

        # 컴포넌트 초기화
        self.intent_parser = IntentParser(
            llm_model=self.LLM_MODEL,
            llm_base_url=self.LLM_BASE_URL,
            llm_api_key=self.LLM_API_KEY,
            llm_temperature=self.LLM_TEMPERATURE
        )

        self.planner = DynamicPlanner(
            llm_model=self.LLM_MODEL,
            llm_base_url=self.LLM_BASE_URL,
            llm_api_key=self.LLM_API_KEY,
            llm_temperature=self.LLM_TEMPERATURE
        )

        # 도구 레지스트리 가져오기
        self.tool_registry = get_registry()

        # ReAct 실행기 초기화
        self.executor = ReActExecutor(
            llm_model=self.LLM_MODEL,
            llm_base_url=self.LLM_BASE_URL,
            llm_api_key=self.LLM_API_KEY,
            llm_temperature=self.LLM_TEMPERATURE,
            tools=self.tool_registry.get_all_tools()
        )

        # 그래프 생성
        self.graph = self._build_graph()

        print(f"[SecurityAgent] Initialized with mode: {execution_mode}")
        print(f"[SecurityAgent] Max iterations: {max_iterations}")
        print(f"[SecurityAgent] Reflection enabled: {enable_reflection}")


    def _build_graph(self) -> StateGraph:
        """LangGraph 구조 생성"""
        workflow = StateGraph(SecurityAnalysisState)

        # 노드 추가
        workflow.add_node("parse_intent", self._parse_intent_node)
        workflow.add_node("create_plan", self._create_plan_node)
        workflow.add_node("execute_react", self._execute_react_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("finalize", self._finalize_node)

        # 엣지 설정
        workflow.set_entry_point("parse_intent")

        workflow.add_edge("parse_intent", "create_plan")
        workflow.add_edge("create_plan", "execute_react")

        # 조건부 라우팅: 계속 실행 vs 반성 vs 완료
        workflow.add_conditional_edges(
            "execute_react",
            self._should_continue,
            {
                "continue": "execute_react",  # 계속 실행
                "reflect": "reflect",          # 반성 단계
                "finalize": "finalize"         # 완료
            }
        )

        workflow.add_conditional_edges(
            "reflect",
            self._after_reflection,
            {
                "replan": "create_plan",       # 재계획
                "continue": "execute_react",   # 계속 실행
                "finalize": "finalize"         # 완료
            }
        )

        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def _parse_intent_node(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """의도 파싱 노드"""
        print("\n" + "="*50)
        print("[Node: 의도 파악/Parse Intent]")
        print("="*50)

        user_request = state.get("user_request", "")
        print(f"User Request: {user_request}")

        # 자연어 요청 파싱
        intent = await self.intent_parser.parse_intent(user_request)
        parameters = await self.intent_parser.extract_parameters(user_request)

        # 레포지토리 정보 추출
        owner, repo = self.intent_parser.parse_repository_info(user_request)

        # 복잡도 평가
        complexity = await self.intent_parser.assess_complexity(user_request)

        print(f"Parsed Intent: {intent['primary_action']}")
        print(f"Scope: {intent['scope']}")
        print(f"Repository: {owner}/{repo}" if owner and repo else "No repository specified")
        print(f"Complexity: {complexity}")

        updates = {
            "parsed_intent": intent,
            "current_step": "intent_parsed",
            **update_observation(state, f"User wants to: {intent['primary_action']} with scope: {intent['scope']}")
        }

        # 레포지토리 정보 업데이트
        if owner:
            updates["owner"] = owner
        if repo:
            updates["repository"] = repo

        # 파라미터 업데이트
        if parameters:
            updates.setdefault("parsed_intent", {})["parameters"] = parameters

        return updates

    async def _create_plan_node(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """계획 수립 노드"""
        print("\n" + "="*50)
        print("[Node: 계획 수립/Create Plan]")
        print("="*50)

        # 동적 계획 생성
        plan_updates = await self.planner.create_plan(state)

        print(f"Plan created: {len(plan_updates.get('execution_plan', {}).get('steps', []))} steps")

        return plan_updates

    async def _execute_react_node(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """ReAct 실행 노드"""
        print("\n" + "="*50)
        print(f"[Node: ReAct 실행/Execute ReAct] Iteration {state.get('iteration', 0) + 1}")
        print("="*50)

        # ReAct 사이클 실행
        react_updates = await self.executor.execute_react_cycle(state)

        return react_updates

    async def _reflect_node(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """반성/메타인지 노드"""
        print("\n" + "="*50)
        print("[Node: 반성|메타인지/Reflect]")
        print("="*50)

        # 메타인지 실행
        reflection = await self.executor.reflect(state)

        print(f"Progress: {reflection.get('progress_assessment')}")
        print(f"Strategy change needed: {reflection.get('strategy_change_needed')}")

        updates = {
            **update_thought(
                state,
                f"Reflection: {reflection.get('progress_assessment')} progress",
                reflection.get('new_strategy', 'continue current strategy')
            )
        }

        # 전략 변경이 필요한 경우
        if reflection.get("strategy_change_needed"):
            updates["current_strategy"] = reflection.get("new_strategy", "adjusted")
            updates["strategy_changes"] = [{
                "timestamp": datetime.now().isoformat(),
                "reason": "reflection",
                "new_strategy": reflection.get("new_strategy")
            }]

        # Human-in-the-Loop
        if reflection.get("need_human_help"):
            updates["needs_human_input"] = True
            updates["human_question"] = reflection.get("human_question", "Need guidance")

        # 메모리에 반성 결과 저장
        memory_update = save_to_memory(
            state,
            key="last_reflection",
            value=reflection,
            persist=False
        )
        updates.update(memory_update)

        return updates

    async def _finalize_node(self, state: SecurityAnalysisState) -> Dict[str, Any]:
        """최종화 노드"""
        print("\n" + "="*50)
        print("[Node: 최종(결과)/Finalize]")
        print("="*50)

        # 보안점수가 없으면 자동으로 계산 (취약점 정보가 있는 경우)
        security_score = state.get("security_score")
        security_grade = state.get("security_grade")
        risk_level = state.get("risk_level")

        if security_score is None and state.get("vulnerability_count", 0) >= 0:
            print("[Finalize] Security score not found, calculating...")
            from .tool_registry import calculate_security_score
            score_result = await calculate_security_score(state)

            if score_result.get("success"):
                security_score = score_result.get("score")
                security_grade = score_result.get("grade")
                risk_level = score_result.get("risk_level")

                # State 업데이트
                state["security_score"] = security_score
                state["security_grade"] = security_grade
                state["risk_level"] = risk_level

                print(f"[Finalize] Security score calculated: {security_score}/100 (Grade: {security_grade})")

        # 최종 결과 생성
        final_result = {
            "session_id": state.get("session_id"),
            "user_request": state.get("user_request"),
            "intent": state.get("parsed_intent"),
            "execution_summary": {
                "total_iterations": state.get("iteration", 0),
                "steps_completed": len([a for a in state.get("actions", []) if a.get("success")]),
                "errors": len(state.get("errors", [])),
                "warnings": len(state.get("warnings", []))
            },
            "results": {
                "security_score": state.get("security_score"),
                "dependencies": {
                    "total": state.get("dependency_count", 0),
                    "details": state.get("dependencies", {})
                },
                "vulnerabilities": {
                    "total": state.get("vulnerability_count", 0),
                    "critical": state.get("critical_count", 0),
                    "high": state.get("high_count", 0),
                    "medium": state.get("medium_count", 0),
                    "low": state.get("low_count", 0),
                    "details": state.get("vulnerabilities", [])
                },
                "security_score": security_score,
                "security_grade": security_grade,
                "risk_level": risk_level
            },
            "report": state.get("report"),
            "recommendations": state.get("recommendations", [])
        }

        # 성공 여부 판단
        success = (
            len(state.get("errors", [])) == 0 or
            state.get("dependency_count", 0) > 0 or
            state.get("vulnerability_count", 0) >= 0
        )

        print(f"Analysis completed: {'Success' if success else 'Partial'}")
        print(f"Dependencies found: {state.get('dependency_count', 0)}")
        print(f"Vulnerabilities found: {state.get('vulnerability_count', 0)}")

        # 보안점수 로그 출력
        if security_score is not None:
            print(f"Security Score: {security_score}/100 (Grade: {security_grade}, Risk: {risk_level})")

        return {
            "completed": True,
            "success": success,
            "final_result": final_result,
            "end_time": datetime.now().isoformat(),
            "current_step": "completed"
        }

    def _should_continue(self, state: SecurityAnalysisState) -> str:
        """계속 실행할지 판단"""
        # 완료 플래그 체크
        if state.get("completed", False):
            return "finalize"

        # ReAct 실행기의 판단 사용
        if not self.executor.should_continue(state):
            return "finalize"

        # 반성 주기 체크 (매 10번째 반복으로 변경 - 성능 최적화)
        if self.enable_reflection and state.get("iteration", 0) % 10 == 0 and state.get("iteration", 0) > 0:
            return "reflect"

        return "continue"

    def _after_reflection(self, state: SecurityAnalysisState) -> str:
        """반성 후 다음 액션 결정"""
        # 전략 변경이 있었다면 재계획
        if state.get("current_strategy") == "adjusted":
            return "replan"

        # Human input 필요
        if state.get("needs_human_input"):
            return "finalize"  # 일단 멈추고 사람 입력 대기

        return "continue"

    async def analyze(
        self,
        user_request: str,
        owner: Optional[str] = None,
        repository: Optional[str] = None,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        자연어 요청으로 보안 분석 실행

        Args:
            user_request: 자연어 요청 (예: "facebook/react의 보안 취약점 찾아줘")
            owner: 레포지토리 소유자 (선택, 자연어에서 추출 가능)
            repository: 레포지토리 이름 (선택, 자연어에서 추출 가능)
            github_token: GitHub API 토큰

        Returns:
            분석 결과

        Examples:
            >>> agent = SecurityAgent()
            >>> result = await agent.analyze("facebook/react의 보안 취약점을 찾아줘")
            >>> print(result["results"]["vulnerabilities"]["total"])
        """
        print("\n" + "="*70)
        print("Security Agent V2 - Autonomous Security Analysis")
        print("="*70)
        print(f"Request: {user_request}")
        print(f"Mode: {self.execution_mode}")
        print("="*70)

        # 초기 상태 생성
        initial_state = create_initial_state(
            user_request=user_request,
            owner=owner,
            repository=repository,
            github_token=github_token,
            execution_mode=self.execution_mode,
            max_iterations=self.max_iterations
        )

        # 그래프 실행
        try:
            final_state = await self.graph.ainvoke(initial_state)

            print("\n" + "="*70)
            print("Analysis Complete")
            print("="*70)

            return final_state.get("final_result", {})

        except Exception as e:
            print(f"\n[SecurityAgent] Error during execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "partial_results": {
                    "dependencies": initial_state.get("dependencies"),
                    "vulnerabilities": initial_state.get("vulnerabilities")
                }
            }

    async def analyze_simple(
        self,
        primary_action: str,
        owner: str,
        repository: str,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        단순 액션 실행 (후방 호환성)

        Args:
            primary_action: 액션 종류
            owner: 소유자
            repository: 레포지토리
            github_token: 토큰

        Returns:
            결과
        """
        # 자연어 요청 생성
        action_map = {
            "analyze_all": f"{owner}/{repository}의 전체 보안 분석을 수행해줘",
            "extract_dependencies": f"{owner}/{repository}의 의존성만 추출해줘",
            "scan_vulnerabilities": f"{owner}/{repository}의 취약점만 스캔해줘",
            "check_license": f"{owner}/{repository}의 라이센스를 체크해줘"
        }

        user_request = action_map.get(primary_action, f"{owner}/{repository}를 분석해줘")

        return await self.analyze(
            user_request=user_request,
            owner=owner,
            repository=repository,
            github_token=github_token
        )

    def get_conversation_history(self, state: SecurityAnalysisState) -> str:
        """대화 히스토리 가져오기"""
        history = state.get("conversation_history", [])
        lines = []
        for turn in history:
            lines.append(f"User: {turn['user_input']}")
            lines.append(f"Agent: {turn['agent_response']}")
        return "\n".join(lines)

    def export_state(self, state: SecurityAnalysisState, format: str = "json") -> str:
        """상태 내보내기"""
        if format == "json":
            return json.dumps(state, indent=2, ensure_ascii=False, default=str)
        else:
            return str(state)


# 편의 함수
async def quick_analysis(
    user_request: str,
    github_token: Optional[str] = None,
    mode: Literal["fast", "intelligent", "auto"] = "auto"
) -> Dict[str, Any]:
    """
    빠른 분석 실행

    Args:
        user_request: 자연어 요청
        github_token: GitHub 토큰
        mode: 실행 모드

    Returns:
        분석 결과

    Example:
        >>> result = await quick_analysis("facebook/react 보안 분석")
    """
    agent = SecurityAgent(execution_mode=mode)
    return await agent.analyze(user_request, github_token=github_token)
