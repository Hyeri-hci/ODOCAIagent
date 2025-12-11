"""
Dynamic Planner (Validator Logic Fixed)
Validator가 Fallback 도구를 정규 단계로 강제하는 '과잉 교정' 현상을 수정한 최종 버전
"""
import json
import re
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config.setting import settings
from agent.v1.state import RecommendationState, ExecutionPlan

class DynamicPlanner:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0
        )

        # 1. Planner 프롬프트 (Happy Path 강조)
        self.planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 GitHub 추천 에이전트의 **총괄 설계자**입니다.
            사용자의 의도를 분석하여 **가장 효율적인 최적 경로(Happy Path)**를 계획하십시오.

            ### ⛔ [절대 금지] 대안(Fallback)의 단계화 금지
            - 실패 시 사용할 대안 도구는 오직 `fallback` 필드에만 적으십시오.
            - **대안 도구를 별도의 `step`으로 추가하지 마십시오.** (중복 실행 방지)

            ### 🚦 시나리오별 표준 절차 (Standard Procedures):
            
            **Case A: Target Repo 존재 (URL 분석)**
            1. `github_ingest_tool`
            2. `rag_query_generator`
            3. `qdrant_search_executor` (끝)
            
            **Case B: 의미/기능 검색 (Semantic Search)**
            1. `rag_query_generator`
            2. `qdrant_search_executor` (끝)

            **Case C: 조건 검색 (Stars, Language)**
            1. `github_search_query_generator`
            2. `github_search_tool`
            3. `github_filter_tool` (끝)

            ### 🛠️ 도구 정의서:
            (이전과 동일: github_ingest_tool, rag_query_generator, qdrant_search_executor, github_search_query_generator, github_search_tool, github_filter_tool)

            ### 📝 출력 가이드 (JSON Format):
            `parameters` 필드 작성 금지.

            {{
                "steps": [
                    {{
                        "step_number": 1,
                        "action": "도구 이름",
                        "description": "이유",
                        "validation": "성공 기준",
                        "fallback": "대안 (실패 시 실행할 도구 이름)" 
                    }}
                ],
                "reasoning": "왜 이 도구를 선택했는지 설명"
            }}
            """),
            ("user", """
            [입력 데이터]
            - Intent Category: {category}
            - Scope: {scope}
            - Target Repo: {target_repo}
            - Original Request: {user_request}

            위 정보를 바탕으로 **대안 단계가 없는** 최적의 경로를 수립하십시오.
            """)
        ])

        # 2. Validator 프롬프트 (과잉 교정 방지) ✨ 여기가 핵심 수정!
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 **엄격한 논리 검증가**입니다.
            
            ### 🚨 검증 규칙 (Verification Rules):
            1. **Happy Path 준수**: 계획에 **불필요한 대안(Fallback) 단계**가 포함되어 있는지 확인하십시오.
               - (X) Step 1: 벡터검색 -> Step 2: API검색 (잘못됨! Step 1 성공 시 Step 2는 중복임)
               - (O) Step 1: 벡터검색 (끝)
               - 만약 대안이 별도 단계로 있다면 `valid: false`를 반환하고 제거하십시오.

            2. **Fallback 도구의 부재 허용**:
               - `fallback` 필드에 언급된 도구(예: `github_search_tool`)가 `steps` 리스트에 없어도 **정상**입니다.
               - 이를 "누락"으로 간주하고 추가하라고 하지 마십시오.

            3. **필수 흐름**:
               - `rag_query_generator` 다음에는 반드시 `qdrant_search_executor`가 와야 합니다.

            문제가 있다면 `valid: false`와 함께 수정된 계획을 제공하십시오.
            JSON 출력: {{ "valid": true|false, "issues": [], "revised_steps": [] }}
            """),
            ("user", """[의도] {user_intent}\n[계획] {plan_json}""")
        ])

    async def create_plan(self, state: RecommendationState) -> Dict[str, Any]:
        print("\n📅 [Planner] 최적 경로 수립 중 (Validator Fixed)...")
        intent = state.get("parsed_intent")
        if not intent: return self._create_default_plan()

        try:
            chain = self.planning_prompt | self.llm
            response = await chain.ainvoke({
                "category": intent.get("category"),
                "scope": intent.get("scope"),
                "target_repo": intent.get("target_repo"),
                "user_request": intent.get("original_query")
            })
            plan_data = self._robust_json_parse(response.content)
            
            execution_plan: ExecutionPlan = {
                "steps": plan_data.get("steps", []),
                "reasoning": plan_data.get("reasoning", "N/A")
            }

            validation = await self._validate_plan(execution_plan, intent)
            if not validation["valid"]:
                print(f"🔧 [Validator] 수정 사항: {validation['issues']}")
                if validation.get("revised_steps"):
                    execution_plan["steps"] = validation["revised_steps"]

            print(f"📝 [Planner] 계획 확정: {len(execution_plan['steps'])} 단계")
            return {"execution_plan": execution_plan, "plan_valid": True}

        except Exception as e:
            print(f"⚠️ [Planner] Error: {e}")
            return {"execution_plan": self._create_default_plan()["execution_plan"], "plan_valid": False}

    # ... (헬퍼 함수 동일) ...
    async def _validate_plan(self, plan: ExecutionPlan, intent: Dict) -> Dict[str, Any]:
        try:
            chain = self.validation_prompt | self.llm
            response = await chain.ainvoke({
                "user_intent": json.dumps(intent, ensure_ascii=False),
                "plan_json": json.dumps(plan, ensure_ascii=False)
            })
            return self._robust_json_parse(response.content)
        except:
            return {"valid": True}

    async def replan(self, state: RecommendationState, reason: str) -> Dict[str, Any]:
        return {"plan_valid": False} 

    def _create_default_plan(self) -> Dict[str, Any]:
        return {
            "execution_plan": {
                "steps": [{"step_number": 1, "action": "rag_query_generator", "description": "기본", "validation": "", "fallback": ""}],
            },
            "plan_valid": True
        }

    def _robust_json_parse(self, content: str) -> Dict[str, Any]:
        try:
            match = re.search(r'\{.*\}', content.strip(), re.DOTALL)
            if match: content = match.group(0)
            return json.loads(content)
        except:
            return {}

# --- TEST CODE ---
async def run_test_case(planner: DynamicPlanner, case_name: str, intent: Dict[str, Any]):
    print(f"\n{'='*20} [TEST: {case_name}] {'='*20}")
    print(f"💬 요청: \"{intent['original_query']}\"")
    
    state = {"parsed_intent": intent, "user_request": intent['original_query']}
    result = await planner.create_plan(state)
    
    steps = result.get("execution_plan", {}).get("steps", [])
    print(f"💡 근거: {result.get('execution_plan', {}).get('reasoning')}")
    for step in steps:
        print(f"Step {step['step_number']}: {step['action']}")
        print(f"   └─ 🛡️ Fallback: {step['fallback']}")
    print("-" * 60)

async def test_planner_comprehensive():
    planner = DynamicPlanner()
    
    # [CASE 2] Semantic Search (RAG Flow)
    intent_semantic = {
        "category": "semantic_search",
        "scope": "global",
        "target_repo": None,
        "original_query": "RAG 파이프라인 구축을 쉽게 도와주는 파이썬 라이브러리 추천해줘"
    }
    
    await run_test_case(planner, "Semantic RAG Flow", intent_semantic)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_planner_comprehensive())