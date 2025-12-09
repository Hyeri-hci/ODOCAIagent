import json
import asyncio
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config.setting import settings # settings 임포트 (설정 파일 사용 가정)
from .state import AgentState # AgentState 임포트

# 1. LLM 초기화 (전역 레벨)
try:
    llm = ChatOpenAI(
        base_url=settings.llm.api_base,
        api_key=settings.llm.api_key,
        model=settings.llm.model_name,
        temperature=0  # 분류 정확도를 위해 온도 0 설정
    )
except Exception as e:
    print(f"❌ LLM Initialization Failed: {e}. Check config.setting.")
    raise e 

# 2. Router Prompt 정의
router_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    당신은 GitHub 프로젝트 추천 에이전트의 라우터입니다. 사용자 질문을 분석하여 다음 4가지 중 하나를 선택하세요.
    
    1. **search**: "별점 1000개 이상", "Python 언어", "최근 업데이트" 등 구체적 스펙, 정량적 조건, 또는 메타데이터로 검색할 때. (GitHub API 사용)
    2. **rag**: "GPU 가속 라이브러리", "보일러플레이트 추천" 등 프로젝트의 내용, 기능, 또는 의미 기반으로 검색하고 싶을 때. (벡터 검색 사용)
    3. **url**: 질문에 "github.com" URL이 있거나 특정 리포지토리(user/repo)와 비슷한 것을 찾되, 사용자의 추가적인 요구 사항을 충족하는 프로젝트를 찾을 때. (URL 분석 후 RAG 경로로 연결)
    4. **trend**: "요즘 뜨는", "트렌드", "인기 순위" 등을 물을 때. (트렌딩 API 사용)
    
    JSON 응답 형식: {{ "category": "search" | "rag" | "url" | "trend" }}
    """),
    ("user", "{query}")
])

# 3. Router Function (LLM 호출 및 Fallback)
async def route_query(state: AgentState) -> dict:
    """LLM을 호출하여 사용자 쿼리를 4가지 카테고리로 분류합니다."""
    
    query = state['user_query']
    print(f"🚦 [Router] Analyzing query: {query}")
    
    chain = router_prompt | llm
    category = "rag" 
    
    try:
        # 1. LLM 호출 시도
        result = await chain.ainvoke({"query": query})
        content = result.content
        
        # 2. JSON 파싱
        content = content.strip()
        if content.startswith("```json"):
            content = content.strip("```json").strip("```").strip()
            
        parsed = json.loads(content)
        category = parsed.get("category", "rag") 
        
    except (json.JSONDecodeError, Exception) as e:
        # 3. LLM 통신/파싱 실패 시 Fallback
        print(f"⚠️ Router LLM Call/Parsing Failed: {e.__class__.__name__}. Falling back to RAG.")
        category = "rag" 
        
    print(f"   👉 Direction: {category}")
    return {"category": category}