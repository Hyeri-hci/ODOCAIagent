"""
Recommendation Agent (Final Integrated Graph)
최종 단계에서 추천 사유(Reasoning)를 생성하여 리포트의 품질을 높인 버전
"""
import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from config.setting import settings
from agent.v1.state import (
    RecommendationState,
    create_initial_state,
    update_thought,
)
from .intent_parser import IntentParser
from .planner import DynamicPlanner
from .executor import ReActExecutor

class RecommendationAgent:
    """GitHub 추천 에이전트 (LangGraph 기반)"""

    def __init__(self):
        # 1. 컴포넌트 초기화
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0
        )
        
        self.intent_parser = IntentParser()
        self.planner = DynamicPlanner()
        self.executor = ReActExecutor()

        # [NEW] 추천 사유 생성용 프롬프트
        self.reasoning_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 IT 기술 전문 컨설턴트입니다.
            사용자의 요청(User Request)과 검색된 GitHub 프로젝트 정보(Candidate)를 비교하여,
            **이 프로젝트를 추천하는 핵심 이유**를 한 문장으로 작성하십시오.

            데이터를 보고 다음 내용을 강조하십시오:
            - 사용자의 목적과 얼마나 일치하는지
            - 프로젝트의 강점 (별점, 최근 업데이트, 특정 기술 스택 등)

            형식: "~~해서 추천합니다." 또는 "~~ 기능이 있어 목적에 부합합니다."
            """),
            ("user", """
            [사용자 요청] {user_request}
            [프로젝트 정보]
            - 이름: {name}
            - 설명: {description}
            - 주요 토픽: {topics}
            - 언어: {language}
            - 별점: {stars}

            추천 이유를 한 문장으로 작성해줘 (한국어).
            """)
        ])

        # 2. 그래프 빌드
        self.graph = self._build_graph()
        print(f"🤖 [RecommendationAgent] Initialized.")

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(RecommendationState)
        workflow.add_node("parse_intent", self._parse_intent_node)
        workflow.add_node("create_plan", self._create_plan_node)
        workflow.add_node("execute_react", self._execute_react_node)
        workflow.add_node("finalize", self._finalize_node)

        workflow.set_entry_point("parse_intent")
        workflow.add_edge("parse_intent", "create_plan")
        workflow.add_edge("create_plan", "execute_react")
        
        workflow.add_conditional_edges(
            "execute_react",
            self._should_continue,
            {"continue": "execute_react", "finalize": "finalize"}
        )
        workflow.add_edge("finalize", END)
        return workflow.compile()

    # ... (parse_intent, create_plan, execute_react 노드는 이전과 동일) ...
    # 지면 관계상 생략하고, 변경된 _finalize_node만 보여드립니다.

    async def _parse_intent_node(self, state: RecommendationState) -> Dict[str, Any]:
        print("\n🔹 [Step 1] Intent Parsing...")
        user_request = state.get("user_request", "")
        intent = await self.intent_parser.parse_intent(user_request)
        return {
            "parsed_intent": intent,
            "current_step": "intent_parsed",
            **update_thought(state, f"User Intent: {intent['category']}")
        }

    async def _create_plan_node(self, state: RecommendationState) -> Dict[str, Any]:
        print("\n🔹 [Step 2] Dynamic Planning...")
        plan_result = await self.planner.create_plan(state)
        return {
            "execution_plan": plan_result.get("execution_plan"),
            "current_step": "plan_created",
            **update_thought(state, "Plan Created")
        }

    async def _execute_react_node(self, state: RecommendationState) -> Dict[str, Any]:
        iteration = state.get("iteration", 0) + 1
        print(f"\n🔹 [Step 3] ReAct Execution (Iter {iteration})...")
        return await self.executor.execute_step(state)

    # =================================================================
    # ✨ [핵심 수정] Finalize Node (추천 사유 생성 로직 추가)
    # =================================================================
    async def _finalize_node(self, state: RecommendationState) -> Dict[str, Any]:
        """[Node] 최종 결과 정리 및 추천 사유 생성"""
        print("\n🔹 [Step 4] Finalizing Results with Reasoning...")
        
        # 1. 후보군 선정 (필터링된 결과 우선, 없으면 검색 결과)
        candidates = state.get("filtered_candidates") or state.get("raw_candidates") or []
        
        # 상위 5개만 선택 (LLM 비용 및 속도 고려)
        top_candidates = candidates[:3] 
        enriched_results = []

        # 2. 각 후보별 추천 사유 생성 (병렬 처리 가능하지만 여기선 순차 처리)
        user_req = state.get("user_request")
        
        print(f"   Writing reasons for {len(top_candidates)} projects...")
        
        for repo in top_candidates:
            try:
                # LLM에게 추천 사유 작성 요청
                chain = self.reasoning_prompt | self.llm
                response = await chain.ainvoke({
                    "user_request": user_req,
                    "name": repo.get("full_name") or repo.get("name"),
                    "description": repo.get("description", "설명 없음"),
                    "topics": ", ".join(repo.get("topics", [])[:5]), # 토픽 5개까지만
                    "language": repo.get("language", "Unknown"),
                    "stars": repo.get("stargazers_count", 0)
                })
                
                # 기존 repo 정보에 'reason' 필드 추가
                repo_with_reason = repo.copy()
                repo_with_reason["recommendation_reason"] = response.content.strip()
                enriched_results.append(repo_with_reason)
                
            except Exception as e:
                print(f"⚠️ Reasoning generation failed for {repo.get('name')}: {e}")
                enriched_results.append(repo) # 실패 시 원본 그대로 추가

        # 3. 최종 리포트 구성
        query_count = len(state.get("search_queries", []) + state.get("rag_queries", []))
        summary = f"""
        Analysis Completed.
        - Total Steps: {state.get('iteration')}
        - Candidates Found: {len(candidates)}
        - Top Recommendations: {len(enriched_results)}
        """
        
        final_report = {
            "status": "success" if enriched_results else "no_results",
            "count": len(enriched_results),
            "top_candidates": enriched_results, # 사유가 포함된 리스트
            "summary": summary.strip()
        }

        return {
            "final_report": final_report,
            "completed": True,
            "current_step": "finished"
        }

    def _should_continue(self, state: RecommendationState) -> str:
        if state.get("completed"): return "finalize"
        if state.get("iteration", 0) >= state.get("max_iterations", 10): return "finalize"
        return "continue"

    async def run(self, user_request: str) -> Dict[str, Any]:
        print("\n" + "="*60)
        print(f"🚀 GitHub Recommendation Agent Started")
        print(f"📝 Request: {user_request}")
        print("="*60)
        
        initial_state = create_initial_state(user_request)
        try:
            final_state = await self.graph.ainvoke(initial_state)
            print("\n" + "="*60)
            print("✅ Analysis Workflow Completed")
            print("="*60)
            return final_state
        except Exception as e:
            print(f"❌ [Agent Error] {e}")
            return {"error": str(e), "state": initial_state}

# --- TEST CODE ---
async def test_agent():
    agent = RecommendationAgent()
    # Test: API Search
    request = "Django 프레임워크 기반 프로젝트 추천, 최근 커밋 많은 걸로"
    result = await agent.run(request)
    
    print("\n📊 [Final Report with Reasoning]")
    report = result.get("final_report", {})
    
    # 결과 예쁘게 출력
    for idx, repo in enumerate(report.get("top_candidates", [])):
        print(f"\n🏆 Rank {idx+1}: {repo.get('full_name', repo.get('name'))}")
        print(f"   ⭐ Stars: {repo.get('stargazers_count')}")
        print(f"   💡 Reason: {repo.get('recommendation_reason')}") # 추천 사유 출력
        print("-" * 40)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent())