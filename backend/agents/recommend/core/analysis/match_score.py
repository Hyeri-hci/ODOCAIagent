import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.agents.recommend.config.setting import settings
from backend.core.models import RepoSnapshot
from backend.agents.recommend.agent.state import CandidateRepo

logger = logging.getLogger("RepoScorer")


# ======================================================================
# 1) PROMPTS
# ======================================================================

SINGLE_SEMANTIC_PROMPT = """
당신은 '소프트웨어 솔루션 아키텍트'입니다.
아래 정보는 이 프로젝트가 추천 후보로 선택된 **확정된 이유**입니다.  
따라서 이를 부정하거나 재평가하거나 의심하지 마십시오.
검색 쿼리를 직접 언급하지 마십시오.
간접적으로 쿼리를 사용하세요.

[사용자 요청 의도]
"{user_request}"

[검색 기반 매칭 정보(확정)]
- 검색 쿼리(Search Query): {search_query}
- RAG Query: {rag_query}
- RAG Filters: {rag_filters}

위 조건들은 이미 시스템적으로 충족되었으며,  
당신은 Candidate가 왜 사용자 요구에 잘 맞는지 **긍정적 이유만** 작성해야 합니다.

[분석 대상 프로젝트]
- 저장소: {repository}
- 주언어: {main_language}
- 사용 언어: {languages}
- 설명: {description}
- 토픽: {topics}
- Stars: {stars}
- Forks: {forks}
- 매칭 근거(Snippet): {match_snippet}

[지시사항]
1. 점수는 절대 주지 마세요.
2. 부족한 정보가 있어도 긍정적으로 유추해서 설명하세요.
3. 검색 조건을 기반으로 “왜 선택될 수 있었는지”를 자연스럽게 연결해 주세요.
4. 출력은 JSON 객체 하나만.

[출력 형식(JSON)]
{{
  "ai_reason": string
}}

반드시 JSON만 출력하세요.
"""


SINGLE_COMPARISON_PROMPT = """
당신은 '유사도 분석 AI'입니다.
아래 정보는 후보가 사용자 요청 프로젝트와 기술적으로 유사하거나 대체 가능하다고 판단된  
**검색 기반 확정 조건**입니다.  
따라서 존재 여부, 언어 여부 등을 다시 판단하거나 부정하지 마십시오.
검색 쿼리를 직접 언급하지 마십시오.
간접적으로 쿼리를 사용하세요.

[사용자 요청 의도]
"{user_request}"

[검색 기반 매칭 정보(확정)]
- 검색 쿼리(Search Query): {search_query}
- RAG Query: {rag_query}
- RAG Filters: {rag_filters}

[원본 프로젝트 정보]
{source_context}

[분석 대상 프로젝트]
- 저장소: {repository}
- 주언어: {main_language}
- 사용 언어: {languages}
- 설명: {description}
- 토픽: {topics}
- 핵심 내용: {match_snippet}

[지시사항]
- 점수 절대 금지.
- 기능적 유사성, 기술 스택 호환성, 확장 가능성 등을 **긍정적 이유로만** 작성.
- JSON 객체만 출력.

[출력 형식(JSON)]
{{
  "ai_reason": string
}}

JSON만 출력하세요.
"""


# ======================================================================
# 2) RepoScorer
# ======================================================================

class RepoScorer:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0
        )
        self.parser = JsonOutputParser()

    def _format_snapshot(self, snapshot: RepoSnapshot, readme_summary: str) -> str:
        return f"""- Repository: {snapshot.full_name}
- Description: {snapshot.description}
- Stars: {snapshot.stars}
- Forks: {snapshot.forks}
- Primary Language: {snapshot.primary_language}
- Readme (Summary):
{readme_summary}
"""

    async def _evaluate_single_repo(
        self, 
        repo: CandidateRepo, 
        user_request: str, 
        intent: str, 
        source_repo: Optional[RepoSnapshot],
        readme_summary: str
    ) -> CandidateRepo:

        try:
            # rag_filters는 dict일 가능성 → prompt에 들어가기 전에 문자열로
            rag_filters_str = json.dumps(repo.rag_filters, ensure_ascii=False) \
                if isinstance(repo.rag_filters, dict) else str(repo.rag_filters)

            repo_data = {
                "repository": f"{repo.owner}/{repo.name}",
                "main_language": repo.main_language,
                "languages": repo.languages,
                "description": repo.description,
                "topics": ", ".join(repo.topics) if repo.topics else "없음",
                "stars": repo.stars,
                "forks": repo.forks,
                "match_snippet": repo.match_snippet,
                "search_query": repo.search_query or "",
                "rag_query": repo.rag_query or "",
                "rag_filters": rag_filters_str,
            }

            if intent == "semantic_search":
                prompt = ChatPromptTemplate.from_template(SINGLE_SEMANTIC_PROMPT)
                inputs = {"user_request": user_request, **repo_data}

            else:
                source_context_str = (
                    self._format_snapshot(source_repo, readme_summary)
                    if source_repo else "원본 프로젝트 정보 없음"
                )
                prompt = ChatPromptTemplate.from_template(SINGLE_COMPARISON_PROMPT)
                inputs = {
                    "source_context": source_context_str,
                    "user_request": user_request,
                    **repo_data
                }

            chain = prompt | self.llm | self.parser
            result = await chain.ainvoke(inputs)

            repo.ai_reason = result.get("ai_reason", "이유 없음")

            return repo

        except Exception as e:
            logger.error(f"❌ Failed to score repo '{repo.name}': {e}")
            repo.ai_reason = f"평가 중 에러 발생: {str(e)}"
            return repo

    async def evaluate_candidates(
        self, 
        candidates: List[CandidateRepo], 
        user_request: str, 
        intent: str, 
        source_repo: Optional[RepoSnapshot] = None,
        readme_summary: str = ""
    ) -> List[CandidateRepo]:

        if not candidates:
            return []
        
        tasks = [
            self._evaluate_single_repo(repo, user_request, intent, source_repo, readme_summary)
            for repo in candidates
        ]

        logger.info(f"🚀 Launching {len(tasks)} parallel scoring tasks (Mode: {intent})")

        scored_candidates = await asyncio.gather(*tasks)
        return list(scored_candidates)
