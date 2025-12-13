import json
import logging
from typing import Dict, Any, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from backend.agents.recommend.config.setting import settings

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
    raise e

# ==========================================
# 1. 일반 검색용 프롬프트 (URL 없음)
# ==========================================
basic_search_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    당신은 GitHub RAG 시스템을 위한 검색 쿼리 분석가입니다.
    사용자의 요청을 분석하여 DB 조회를 위한 `query`, `keywords`, `filters`를 추출하십시오.

    ### 입력 데이터
    - 요청: {user_request}

    ### 규칙
    1. **Query**: 
       - 사용자가 찾고자 하는 **핵심 기술/주제**를 영어로 변환하세요.
       - "추천해줘", "찾아줘" 같은 요청 동사는 제거하고 **기술 키워드만** 추출하세요.
       - 예: "자율주행 딥러닝 추천해줘" → "autonomous driving deep learning"
       - 예: "머신러닝 프레임워크 찾아줘" → "machine learning framework"
       - **절대 "similar projects", "recommendation" 같은 메타 표현을 쿼리에 넣지 마세요!**
       
    2. **Keywords**: 핵심 기술 명사 1~3개 (영어).
       - 예: ["autonomous driving", "deep learning", "self-driving"]
       
    3. **Filters**: 사용자가 **명시적**으로 언어, 스타 수, 토픽을 언급한 경우에만 포함. (추측 금지)

    ### 출력 형식 (JSON Only)
    {{
        "query": "string (기술 키워드만, 메타 표현 금지)",
        "keywords": ["str", "str"],
        "filters": {{ "language": "str", "topics": ["str"] }}
    }}
    """),
    ("user", "{user_request}")
])

# ==========================================
# 2. 유사도/맥락 기반 검색용 프롬프트 (URL 분석 데이터 포함)
# ==========================================
# [수정됨] 추론(Inference) 관련 지침 추가
similarity_search_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    당신은 'GitHub 프로젝트 추천 시스템'의 AI 에이전트입니다.
    사용자가 제공한 **[기준 리포지토리 분석 결과]**와 **[사용자 요구사항]**을 결합하여,
    **DB에서 유사한 프로젝트를 찾기 위한 검색 쿼리**를 생성해야 합니다.

    ### 입력 데이터
    1. **기준 리포지토리 정보 (Context)**:
       {repo_context}
    
    2. **사용자 요구사항 (Instruction)**:
       - {user_request}

    ### 작업 목표 및 데이터 처리 전략
    1. **Context가 충분할 경우 (상세 요약 존재)**: 제공된 기능을 바탕으로 정확한 기술적 쿼리를 생성하십시오.
    2. **Context가 부족할 경우 (설명/토픽만 존재)**: 프로젝트 이름과 토픽(Topic)을 보고 이 프로젝트가 수행할 기능을 **논리적으로 추론(Infer)**하여 쿼리를 생성하십시오.

    ### 규칙 (Strict)
    1. **Query (검색어)**:
       - 기준 리포지토리의 이름(예: LangChain) 자체를 검색어로 쓰지 마십시오. (그 프로젝트를 찾는 게 아니라 '비슷한 것'을 찾는 것이므로)
       - 쿼리로 비슷한 프로젝트 이런 내용를 쓰지 마십시오. similar projects(X) 이런 경우는 쿼리를 비워두세요
       - 대신 **그 프로젝트가 무엇인지 정의하는 기술적 명사구**를 만드십시오.
       - 예시 상황:
         - Context: LangChain (LLM framework)
         - User: "이거랑 비슷한데 Java로 된 거"
         - **Result Query**: "LLM orchestration framework for Java applications" (LangChain이라는 단어 대신 기능을 서술)

    2. **Filters (필터)**:
       - **매우 중요**: 사용자가 "Java로 된 거"라고 했다면 `filters: {{ "language": "Java" }}`를 반드시 추가하십시오.
       - 기준 리포지토리의 언어가 Python이어도, 사용자가 Java를 원하면 Java로 필터링해야 합니다.
       - topic, license, language가 직접 언급된 경우가 아니라면 지나치세요.

    ### 출력 형식 (JSON Only)
    {{
        "query": "string (기술적 서술)",
        "keywords": ["핵심기술1", "핵심기술2"],
        "filters": {{ "language": "...", "topics": [...] }}
    }}
    """),
    ("user", "Analyze the context and instruction above, and generate the JSON query.")
])


async def generate_rag_query_and_filters(
    user_request: str,
    category: Literal["semantic_search", "url_analysis"],
    analyzed_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    [핵심 로직] 
    1. URL 분석 데이터가 있으면 -> '유사도/맥락 기반 검색' 모드로 동작 (similarity_prompt)
    2. 없으면 -> '일반 검색' 모드로 동작 (basic_search_prompt)
    """
    
    # --- 1. 모드 결정 및 프롬프트 선택 ---
    if category == "url_analysis" and analyzed_data:
        print(f"⚙️ [RAG Query Gen] Context-Aware Mode (URL Data Found)")
        
        # 데이터 추출
        repo_snapshot = analyzed_data.get("repo_snapshot", {})
        readme_summary = analyzed_data.get("readme_summary", {})
        
        # [수정됨] Fallback Logic을 위한 변수 준비
        name = repo_snapshot.get('full_name', 'Unknown')
        description = repo_snapshot.get('description', '') or "" # None 방지
        topics = repo_snapshot.get('topics', [])
        primary_lang = repo_snapshot.get('primary_language', 'Unknown')
        
        # 요약 데이터 유효성 검사 (너무 짧거나 에러 메시지만 있는 경우 제외)
        raw_summary = readme_summary.get('final_summary', '')
        has_valid_summary = raw_summary and "No summary generated" not in raw_summary and len(raw_summary) > 50

        # === [Fallback Logic 구현] ===
        if has_valid_summary:
            # 1순위: README 요약이 충실한 경우 -> 가장 정확함
            source_info = "[Source: README Summary - High Reliability]"
            content_body = raw_summary
            
        elif description.strip():
            # 2순위: 요약은 없지만 Description은 있는 경우 -> 설명 기반
            source_info = "[Source: Repository Description - Medium Reliability]"
            content_body = description
            
        else:
            # 3순위: 둘 다 없음 -> 이름과 토픽으로 추론 필요
            # 토픽 리스트를 문자열로 변환
            topic_str = ", ".join(topics) if topics else "No topics provided"
            
            source_info = "[Source: Project Name & Topics - Inference Required]"
            content_body = f"""
            Project Name: {name}
            Topics/Tags: {topic_str}
            (No description available. Please infer functionality from the name and topics.)
            """

        # LLM에게 던져줄 최종 Context 구성
        repo_context_str = f"""
        {source_info}
        - Project Name: {name}
        - Main Language: {primary_lang}
        - Context Content:
        {content_body}
        """
        
        # 체인 설정
        chain = similarity_search_prompt | llm
        input_vars = {
            "repo_context": repo_context_str,
            "user_request": user_request if user_request else "Find similar projects based on this architecture."
        }
        
    else:
        print(f"⚙️ [RAG Query Gen] Basic Search Mode (No URL Data)")
        
        # 체인 설정
        chain = basic_search_prompt | llm
        input_vars = {
            "user_request": user_request
        }

    # --- 2. LLM 실행 ---
    try:
        response = await chain.ainvoke(input_vars)
        content = response.content
        
        # 💡 [로그]
        print(f"\n--- 🤖 LLM Generated Query ({category}) ---")
        print(content)
        print("------------------------------------------\n")
        
        # JSON 파싱
        content = content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        result_data = json.loads(content)
        
        return {
            "query": result_data.get("query", user_request),
            "keywords": result_data.get("keywords", []),
            "filters": result_data.get("filters", {})
        }
        
    except Exception as e:
        logger.error(f"[RAGQueryGen] Error: {e}")
        # 실패 시 기본값 반환
        return {"query": user_request, "keywords": [], "filters": {}}