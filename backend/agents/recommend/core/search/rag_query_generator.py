import json
import logging
from typing import Dict, Any, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config.setting import settings

logger = logging.getLogger(__name__)

try:
    llm = ChatOpenAI(
        base_url=settings.llm.api_base,
        api_key=settings.llm.api_key,
        model=settings.llm.model_name,
        temperature=0
    )
except Exception as e:
    logger.error(f"RAG Query Gen LLM Initialization Failed: {e}")
    # 초기화 실패 시 함수가 호출되는 것을 방지하기 위해 재발생시킵니다.
    raise e

router_prompt= ChatPromptTemplate.from_messages([
        ("system", """
        당신은 GitHub RAG 시스템을 위한 엄격한 검색 쿼리 분석가입니다.
        사용자의 요청을 분석하여 `query`(검색어), `keywords`(핵심 키워드), `filters`(메타데이터 필터)를 추출하십시오.

        ### 입력 데이터
        - 요청: {user_request}
        
        ### 규칙 (엄격히 준수)

        1. **Query (의미 기반 검색용)**: 
           - 사용자의 의도를 **간결하고 명확한 영어 명사구(Phrase)**로 변환하십시오.
           - "I am looking for...", "Can you recommend..." 같은 **대화체 서술어를 제거**하십시오.
           - **찾고자 하는 프로젝트의 README 제목이나 한 줄 설명**과 유사한 형태로 만드십시오.
           - 예시: "PyTorch 같은 딥러닝 라이브러리" -> **"Deep learning framework with GPU acceleration similar to PyTorch"**

        2. **Keywords (키워드 매칭용)**:
           - 도메인이나 특정 작업을 정의하는 **1~3개의 핵심 명사**를 추출하십시오.
           - **포함 대상**: "deep learning", "neural network", "autograd", "tensor" 등.
           - **제외 대상**: "project", "open source", "oss"
           - **주의**: 사용자가 '대안(Alternative)'을 찾을 때, 기준이 되는 기술명(예: PyTorch)은 키워드에서 **제외하거나 신중히 포함**하십시오. (다른 라이브러리 설명에 PyTorch가 없을 수도 있음)

        3. **Filters (메타데이터 제약조건) - 환각 금지(NO HALLUCINATION)**:
           - **매우 중요**: 사용자가 **명시적으로 언급한 경우에만** 필터를 추가하십시오.
           - 사용자가 특정 **프레임워크, 라이브러리, 기술 스택**을 언급했다면 `topics` 리스트에 추가하십시오.
           
           #### 🚨 [중요] 대안/유사 검색 시 예외 규칙:
           - 사용자가 "**~같은 것**", "**~대안**", "**~와 비슷한**" (Alternative/Similar to)을 요청한 경우, **기준이 되는 그 기술명을 `topics` 필터에 절대 넣지 마십시오.**
           - 이유: 필터에 넣으면 그 기술이 태그된 프로젝트만 검색되어, 정작 경쟁 프로젝트(대안)는 검색되지 않습니다.
           
           #### 필터 추출 로직 예시:
           - **User**: "PyTorch 프로젝트 찾아줘" -> **Filters: {{ "topics": ["pytorch"] }}** (PyTorch를 사용하는 프로젝트를 원함 -> 필터 추가 O)
           - **User**: "**PyTorch 같은** 다른 라이브러리 있어?" -> **Filters: {{ "topics": [] }}** (PyTorch가 아닌 다른걸 원함 -> 필터 추가 X)
           - **User**: "React 대안 프레임워크" -> **Filters: {{ "topics": [] }}** (React 필터 X, Query로 검색)

        ### 출력 형식 (JSON Only)
        반드시 아래 JSON 형식으로만 응답하십시오.
        {{
            "query": "...",
            "keywords": ["...", "..."], 
            "filters": {{
                "language": "...",
                "min_stars": 0,
                "topics": ["...", "..."]
            }}
        }}
        """),
        ("user", "User Request: {user_request}")
    ])

async def generate_rag_query_and_filters(
    user_request: str,
    category: Literal["semantic_search", "url_analysis"],
    analyzed_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    [핵심 로직] 사용자 요청을 분석하여 RAG 검색에 필요한 쿼리, 키워드, 필터를 추출합니다.
    """
    query = user_request # 로그 출력을 위한 변수
    print(f"⚙️ [RAG Query Gen] Analyzing request for vector search: '{query}'")
    
    chain = router_prompt | llm
    
    try:
        # 💡 [수정] ainvoke 사용 (비동기 환경) 및 입력 변수를 {user_request}만 전달
        response = await chain.ainvoke({
            "user_request": user_request,
            # 'category', 'summary'는 prompt에 변수로 정의되어 있지 않으므로 제거합니다.
        })
        
        content = response.content
        
        # 💡 [로그 추가] LLM의 원본 응답을 디버깅용으로 출력
        print("\n--- 🤖 LLM Raw Response Log (RAG Query Gen) ---")
        print(content)
        print("--------------------------------------------------\n")
        
        # JSON 파싱 (마크다운 코드 블록 제거)
        content = content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        result_data = json.loads(content)
        
        logger.info(f"[RAGQueryGen] Extracted Query: {result_data.get('query')}")
        
        return {
            "query": result_data.get("query", user_request),
            "keywords": result_data.get("keywords", []),
            "filters": result_data.get("filters", {})
        }
        
    except Exception as e:
        logger.error(f"[RAGQueryGen] Critical Error during LLM call or parsing: {e}")
        # 실패 시 Fallback 쿼리 반환 (원본 쿼리 사용)
        return {"query": user_request, "keywords": [], "filters": {}}