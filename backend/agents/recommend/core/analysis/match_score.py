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

# ==============================================================================
# 1. 단일 항목 평가용 프롬프트 (Single Item Prompts)
# ==============================================================================

# (A) 탐색 모드: 이 프로젝트가 요구사항에 맞는가?
SINGLE_SEMANTIC_PROMPT = """
당신은 '소프트웨어 솔루션 아키텍트'입니다.
제시된 GitHub 리포지토리(Candidate)가 사용자의 요구사항(User Request)을 얼마나 완벽하게 충족하는지 심층 분석하세요.

[사용자 요구사항]
"{user_request}"

[분석 대상 프로젝트 (Candidate)]
- 저장소: {repository}
- 주언어: {main_language}
- 사용 언어: {languages}
- 설명: {description}
- 토픽: {topics}
- Stars: {stars}
- Forks: {forks}
- 매칭 근거(Snippet): {match_snippet}

[지시사항]
1. **평가 기준**:
   - 원본의 Readme나 설명이 충분하다면 **기능적 유사성**을 최우선으로 보세요.
   - **(중요) 원본 정보가 부족한 경우(Readme 없음 등)**: 
     - **프로젝트 이름(Repository Name)**의 의미적 유사성 (예: 'Agent', 'Framework' 등 키워드 포함 여부)
     - **토픽(Topics)**의 일치 여부
     - 위 두 가지 메타데이터를 근거로 점수를 매기세요.

2. **점수(ai_score) 차별화**:
   - 모든 후보에게 비슷한 점수를 주지 마세요. 
   - 이름이나 토픽이 원본과 더 직관적으로 연결되는 프로젝트에 가산점을 주세요.

3. **이유(ai_reason) 서술**:
   - 원본 정보가 없을 때는 "원본 설명이 부족하지만, **프로젝트 이름이 '~'로 유사하고**, **토픽 '~'가 일치하여** 대체 가능성이 높음"과 같이 **이름/토픽 매칭**을 명시적으로 언급하세요.

4. 아래 JSON 형식으로 응답하세요.
{{
  "ai_score": 85,
  "ai_reason": "사용자가 요구한 Python 환경을 지원하며, RAG 파이프라인 구축에 필요한 모듈성을 갖추고 있음."
}}
"""

# (B) 비교 모드: 이 프로젝트가 원본과 얼마나 유사하고 대체 가능한가?
SINGLE_COMPARISON_PROMPT = """
당신은 '유사도 분석 AI'입니다.
'후보 프로젝트(Candidate)'가 '원본 프로젝트(Source)'의 **기능과 역할을 얼마나 잘 대체할 수 있는지** 평가하세요.

[원본 프로젝트 정보]
{source_context}

[사용자 제약조건]
"{user_request}"

[분석 대상 프로젝트 (Candidate)]
- 저장소: {repository}
- 주언어: {main_language}
- 사용 언어: {languages}
- 설명: {description}
- 토픽: {topics}
- **핵심 내용**: {match_snippet}

[분석 및 채점 가이드]

1. **언어 필터링 (Language Filter)**:
   - 후보의 [사용 언어 목록]에 사용자 요구 언어(예: Python)가 없다면? -> **0점**.

2. **콘텐츠 기반 유사도 평가 (Content-Based Matching)**:
   - **프로젝트 이름보다 [핵심 내용(Snippet)]과 [설명]이 더 중요합니다.**
   - 원본 프로젝트의 핵심 기능(예: Agent, Orchestration, 분석 도구 등)이 후보 프로젝트의 **텍스트 설명** 속에 나타납니까?
   - 예: 이름이 'My-Tool'이라도, 설명에 "A framework for managing AI Agents"라고 되어 있다면 유사한 것입니다.

3. **스팸 필터 (Context Check)**:
   - 설명이나 스니펫을 읽었을 때, 단순한 '강의 자료(Course)', '링크 모음(List/Awesome)', '책(Book)'인가요?
   - 그렇다면 기능적 대체가 불가능하므로 **30점 이하**로 감점하세요.

4. **점수 산정**:
   - **90~100점**: 언어 일치 + 설명/스니펫에서 원본과 동일한 핵심 기능(키워드)이 확인됨.
   - **70~89점**: 유사한 도메인이지만, 설명이 약간 모호하거나 부가 기능이 다름.
   - **0~40점**: 언어 불일치 또는 단순 자료 모음집, 전혀 다른 기능.

[지시사항]
- 이유(ai_reason) 작성 시, "스타 수가 적어서" 같은 말은 하지 마세요.
- 오직 "기능", "이름의 유사성", "토픽의 일치"를 근거로 드세요.

[응답 형식 (JSON)]
{{
  "ai_score": 88,
  "ai_reason": "사용자 요구 언어(Python)를 만족하며, 원본과 후보 모두 프로젝트 이름에 'Agent'가 포함되어 있고 'LLM' 토픽을 공유하므로 기능적 목적이 동일할 것으로 판단됨."
}}
"""

# ==============================================================================
# 2. Core Class (Parallel Execution)
# ==============================================================================

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
        """
        [Helper] Snapshot 객체를 프롬프트에 넣기 좋은 문자열로 변환
        Readme는 이미 요약되어 들어왔다고 가정합니다.
        """
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
        """
        [내부 함수] 리포지토리 1개를 개별적으로 평가 (비동기 단위 작업)
        """
        try:
            # 1. 상세 정보 포맷팅
            repo_data = {
                "repository": f"{repo.owner}/{repo.name}",
                "main_language": repo.main_language,
                "languages": repo.languages,
                "description": repo.description,
                "topics": ", ".join(repo.topics) if repo.topics else "없음",
                "stars": repo.stars,
                "forks": repo.forks,
                "match_snippet": repo.match_snippet
            }

            # 2. 모드에 따른 프롬프트 선택
            if intent == "semantic_search":
                prompt = ChatPromptTemplate.from_template(SINGLE_SEMANTIC_PROMPT)
                inputs = {
                    "user_request": user_request,
                    **repo_data
                }
            else:
                # url_analysis 모드일 때 Snapshot 객체 포맷팅
                if source_repo:
                    source_context_str = self._format_snapshot(source_repo, readme_summary)
                else:
                    source_context_str = "원본 프로젝트 정보 없음"

                prompt = ChatPromptTemplate.from_template(SINGLE_COMPARISON_PROMPT)
                inputs = {
                    "source_context": source_context_str,
                    "user_request": user_request,
                    **repo_data
                }

            # 3. LLM 호출
            chain = prompt | self.llm | self.parser
            result = await chain.ainvoke(inputs)

            # 4. 결과 반영
            repo.ai_score = int(result.get("ai_score", 0))
            repo.ai_reason = result.get("ai_reason", "이유 없음")
            
            return repo

        except Exception as e:
            logger.error(f"❌ Failed to score repo '{repo.name}': {e}")
            repo.ai_score = 0
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
        
        # 1. Task 리스트 생성
        # source_repo(Snapshot 객체)를 그대로 넘깁니다.
        tasks = [
            self._evaluate_single_repo(repo, user_request, intent, source_repo, readme_summary)
            for repo in candidates
        ]
        
        logger.info(f"🚀 Launching {len(tasks)} parallel scoring tasks (Mode: {intent})...")

        # 2. 병렬 실행
        scored_candidates = await asyncio.gather(*tasks)

        # 3. 정렬 및 반환
        results_list = list(scored_candidates)
        results_list.sort(key=lambda x: x.ai_score, reverse=True)
        
        return results_list