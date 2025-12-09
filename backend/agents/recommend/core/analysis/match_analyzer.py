# core/analysis/match_analyzer.py

import json
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from config.setting import settings

# 1. LLM이 반환할 출력 구조 정의 (Pydantic)
class MatchAnalysisResult(BaseModel):
    match_score: int = Field(description="0 to 100 score indicating how well the repo fits the user request")
    key_matches: List[str] = Field(description="List of features that directly match user requirements")
    missing_points: List[str] = Field(description="List of requirements that seem missing or weak")
    reason: str = Field(description="A persuasive one-sentence reason for recommendation")

class MatchAnalyzer:
    """
    [Core Logic]
    사용자 요구사항(Query)과 프로젝트 상세 정보(Repo Data)를 비교 분석하여
    추천 사유와 적합도 점수를 산출합니다.
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0  # 분석은 냉철해야 하므로 0
        )
        
        self.parser = JsonOutputParser(pydantic_object=MatchAnalysisResult)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a Senior Technical Consultant analyzing open source libraries.
            Compare the User's Request with the Repository Details.
            
            Your Goal:
            1. Identify strictly matching features (Pros).
            2. Identify missing or conflicting features (Cons).
            3. Calculate a relevance score (0-100).
            4. Write a concise recommendation reason.

            Output Format:
            {format_instructions}
            """),
            ("user", """
            [User Request]
            {user_query}

            [Repository Details]
            - Name: {repo_name}
            - Description: {repo_desc}
            - Topics: {repo_topics}
            - Main Language: {repo_lang}
            - README Summary (or Snippet):
            {readme_snippet}
            """)
        ])

    async def analyze(self, user_query: str, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 리포지토리에 대한 적합성 분석 수행
        """
        try:
            # README가 너무 길면 잘라서 넣음 (토큰 절약)
            readme_full = repo_data.get("readme", "") or ""
            readme_snippet = readme_full[:2000] + "..." if len(readme_full) > 2000 else readme_full
            
            # Chain 실행
            chain = self.prompt | self.llm | self.parser
            
            result = await chain.ainvoke({
                "user_query": user_query,
                "repo_name": repo_data.get("name"),
                "repo_desc": repo_data.get("description"),
                "repo_topics": ", ".join(repo_data.get("topics", [])),
                "repo_lang": repo_data.get("main_language"),
                "readme_snippet": readme_snippet,
                "format_instructions": self.parser.get_format_instructions()
            })
            
            return result

        except Exception as e:
            print(f"[MatchAnalyzer] Analysis failed for {repo_data.get('name')}: {e}")
            # 에러 발생 시 기본값 반환
            return {
                "match_score": 50,
                "key_matches": ["Analysis failed"],
                "missing_points": [],
                "reason": "Basic recommendation based on keyword match."
            }