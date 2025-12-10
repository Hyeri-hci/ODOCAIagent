# backend/agents/recommend/agent/nodes.py

from __future__ import annotations

import logging
import time
import asyncio
from typing import Any, Dict, Optional, List
from dataclasses import asdict
from backend.agents.recommend.agent.state import RecommendState
from backend.core.github_core import RepoSnapshot
from backend.agents.recommend.core.ingest.summarizer import ContentSummarizer
from backend.agents.recommend.core.analysis.match_score import RepoScorer

logger = logging.getLogger(__name__)

try:
    summarizer_instance = ContentSummarizer()
    scorer_instance = RepoScorer() # Scorer 인스턴스 생성 (비용 절약을 위해 재사용)
    logger.info("✅ Global instances initialized.")
except Exception as e:
    logger.error(f"❌ Failed to init global instances: {e}")
    exit(1)

def fetch_snapshot_node(state: RecommendState) -> Dict[str, Any]:
    """
    GitHub 저장소 스냅샷 수집 노드.
    """
    
    # 1. 재사용 체크
    if state.repo_snapshot:
        logger.info("Reusing existing repo snapshot")
        return {"step": state.step + 1} 
    
    # 2. 필수 입력값 검증
    owner = state.owner
    repo = state.repo
    ref = getattr(state, 'ref', 'main') # ref 필드가 있을 경우 사용

    # owner, repo가 State에 없는 경우 에러 처리
    if not owner or not repo:
        error_msg = "Owner or repository name is missing in state. (Pre-analysis failure)"
        logger.error(f"Failed to fetch details: {error_msg}")
        return {
            "error": error_msg,
            "failed_step": "fetch_snapshot_node",
            "step": state.step + 1,
        }
    
    from backend.core.github_core import fetch_repo_snapshot

    start_time = time.time()
    
    try:
        
        snapshot = fetch_repo_snapshot(state.owner, state.repo, state.ref)
        
        snapshot_dict = snapshot.model_dump() if hasattr(snapshot, "model_dump") else asdict(snapshot)

        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["fetch_snapshot"] = elapsed
        
        logger.info(f"Fetched snapshot for {state.owner}/{state.repo} in {elapsed}s")
        
        return {
            "repo_snapshot": snapshot_dict,
            "timings": timings,
            "step": state.step + 1,
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch snapshot: {e}")
        return { 
            "error": str(e),
            "failed_step": "fetch_snapshot_node",
            "step": state.step + 1,
        }
    
async def analyze_readme_summary_node(state: RecommendState) -> Dict[str, Any]:
    """
    README 분석 및 LLM 요약 노드.
    
    repo_snapshot의 내용을 기반으로 구조화된 LLM 요약을 생성하고 DocsCoreResult를 저장합니다.
    """
    
    # 1. 재사용 체크 및 필수 선행 조건 체크
    if state.readme_summary:
        logger.info("Reusing existing ingest analysis result")
        return {"step": state.step + 1} 
    
    if not state.repo_snapshot:
        error_msg = "No repo_snapshot available for README analysis."
        logger.error(f"Failed to analyze README: {error_msg}")
        return {
            "error": error_msg,
            "failed_step": "analyze_readme_summary_node",
            "step": state.step + 1,
        }
    
    from backend.core.docs_core import analyze_docs, extract_and_structure_summary_input
    
    start_time = time.time()
    
    try:
        # 2. State에서 스냅샷 추출
        snapshot_dict = state.repo_snapshot
        readme_content = snapshot_dict.get("readme_content", "")

        # Dict → RepoSnapshot 변환
        snapshot_obj = RepoSnapshot(**snapshot_dict)

        # 3. 문서 분석 (DocsCoreResult dataclass)
        docs_result = analyze_docs(snapshot_obj)

        # dataclass → dict 변환
        docs_result_dict = asdict(docs_result)

        # 4. LLM 입력 구성
        llm_input_text = extract_and_structure_summary_input(readme_content)

        # 5. LLM 요약 실행 (비동기)
        final_summary = "No summary generated."
        if llm_input_text:
            final_summary = await summarizer_instance.summarize(llm_input_text)
            logger.info("LLM summary generated successfully.")
        else:
            logger.warning("Skipping LLM summary: No structured input generated.")

        # 6. 결과 통합
        ingest_result = {
            "final_summary": final_summary,
            "docs_analysis": docs_result_dict,
            "readme_word_count": len(readme_content.split()),
            "documentation_quality": docs_result_dict.get("total_score", 0)
        }

        # 7. 상태 업데이트 반환
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["analyze_readme_summary"] = elapsed

        return {
            "readme_summary": ingest_result,
            "timings": timings,
            "step": state.step + 1,
            "failed_step": None,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to analyze and summarize README: {e}")
        return {
            "error": str(e),
            "failed_step": "analyze_readme_summary_node",
            "step": state.step + 1,
        }
    

async def generate_search_query_node(state: RecommendState) -> Dict[str, Any]:
    """
    RAG 검색 쿼리 및 필터 생성 노드.
    
    상황에 따라 두 가지 모드로 동작합니다:
    1. URL 분석 데이터(repo_snapshot)가 있음 -> 'url_analysis' 모드 (유사도 검색 + Fallback 로직 적용)
    2. URL 분석 데이터가 없음 -> 'semantic_search' 모드 (일반 검색)
    """

    from backend.agents.recommend.core.search.rag_query_generator import generate_rag_query_and_filters
    
    start_time = time.time()
    logger.info("🚀 Starting RAG Query Generation Node")

    # 1. 모드 결정 및 분석 데이터 준비
    # readme_summary가 없더라도, repo_snapshot(기본 정보)만 있으면 분석 모드로 진입합니다.
    if state.repo_snapshot:
        analyzed_data = {
            "repo_snapshot": state.repo_snapshot,
            "readme_summary": state.readme_summary if state.readme_summary else {}
        }
    else:
        analyzed_data = None

    mode = state.user_intent

    # 2. 사용자 요청 텍스트 (없으면 기본값 설정)
    user_input = state.user_request if state.user_request.strip() else "Find similar projects."

    try:
        # 3. Core 로직 호출 (LLM 수행)
        result = await generate_rag_query_and_filters(
            user_request=user_input,
            category=mode,
            analyzed_data=analyzed_data
        )

        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["generate_query"] = elapsed

        logger.info(f"✅ Query Generated ({mode}): {result['query']} (Time: {elapsed}s)")

        return {
            "search_query": result.get("query", ""),
            "search_keywords": result.get("keywords", []),
            "search_filters": result.get("filters", {}),
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Failed to generate search query: {e}")
        return {
            "error": str(e),
            "failed_step": "generate_search_query_node",
            "step": state.step + 1
        }
    
def vector_search_node(state: RecommendState) -> Dict[str, Any]:
    """생성된 쿼리로 Qdrant 검색 수행"""
    
    # 앞 단계에서 쿼리 생성에 실패했다면 실행 불가
    if not state.search_query:
        logger.warning("No search query found. Skipping vector search.")
        return {"step": state.step + 1}
    
    from backend.agents.recommend.agent.state import CandidateRepo
    from backend.agents.recommend.core.search.vector_search import vector_search_engine

    start_time = time.time()
    logger.info(f"🔎 Executing Vector Search for: '{state.search_query}'")

    try:
        # 1. DB 검색 실행
        result = vector_search_engine.search(
            query=state.search_query,
            filters=state.search_filters,
            target_k=10
        )
        
        raw_recommendations = result.get("final_recommendations", [])
        
        # 2. [핵심] Raw Dict -> CandidateRepo 객체로 변환 (Mapping)
        structured_results: List[CandidateRepo] = []
        
        for item in raw_recommendations:
            # Qdrant/FlashRank 결과에서 필드를 매핑하여 객체 생성
            repo_obj = CandidateRepo(
                id=item.get("project_id"),
                name=item.get("name"),
                owner=item.get("owner"),
                description=item.get("description"),
                stars=int(item.get("stars", 0)),
                forks=int(item.get("forks", 0)),
                main_language=item.get("main_language", "UNKNOWN"),
                languages=item.get("languages") or [],
                topics=item.get("topics") or [],
                html_url=item.get("repo_url") or f"https://github.com/{item.get('owner')}/{item.get('name')}",
                
                # 검색 엔진이 계산한 점수와 스니펫
                score=item.get("rerank_score", 0.0),
                match_snippet=item.get("match_snippet", ""),
            )
            structured_results.append(repo_obj)
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["vector_search"] = elapsed
        
        logger.info(f"✅ Found {len(structured_results)} recommendations in {elapsed}s")

        return {
            "search_results": structured_results,
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Vector search failed: {e}")
        return {
            "error": str(e), 
            "failed_step": "vector_search_node", 
            "step": state.step + 1
        }
    
async def score_candidates_node(state: RecommendState) -> Dict[str, Any]:
    """LLM을 이용한 후보군 상세 평가"""
    
    # 1. 평가할 후보가 없으면 패스
    if not state.search_results:
        logger.info("No candidates to score. Skipping.")
        return {"step": state.step + 1}

    start_time = time.time()
    logger.info(f"🧠 Scoring {len(state.search_results)} candidates...")

    try:
        # 2. State에 있는 Dict 형태의 Snapshot을 객체로 복원 (Scorer가 객체를 요구함)
        source_snapshot = None
        if state.repo_snapshot:
            source_snapshot = RepoSnapshot(**state.repo_snapshot)
        
        # 3. Readme 요약본 텍스트 추출
        readme_summary_text = ""
        if state.readme_summary and isinstance(state.readme_summary, dict):
            readme_summary_text = state.readme_summary.get("final_summary", "")

        # 4. Scorer 실행
        scored_results = await scorer_instance.evaluate_candidates(
            candidates=state.search_results,     # vector_search 결과
            user_request=state.user_request,
            intent=state.user_intent,            # "semantic_search" or "url_analysis"
            source_repo=source_snapshot,         # 원본 객체
            readme_summary=readme_summary_text   # 요약본 스트링
        )

        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["ai_scoring"] = elapsed

        logger.info(f"✅ Scoring complete. Top 1: {scored_results[0].name} (Score: {scored_results[0].ai_score})")

        return {
            "search_results": scored_results, # 점수가 매겨진 리스트로 업데이트
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Scoring failed: {e}")
        # 에러가 나도 프로세스는 계속 진행 (평가만 실패)
        return {"error": str(e), "failed_step": "score_candidates_node", "step": state.step + 1}
    
    
def check_ingest_error_node(state: RecommendState) -> Dict[str, Any]:
    """
    에러 체크 및 복구 노드.
    
    현재 에러 상태를 확인하고 재시도 가능 여부를 결정합니다.
    """
    # 1. 에러가 없으면 다음 단계(여기서는 출력)로 이동
    if not state.error:
        # 에러가 없는데 이 노드에 도착했다면, 일반적으로는 최종 출력 노드로 이동해야 합니다.
        # 하지만, 그래프의 끝이 명확하지 않으므로, 일단 step만 증가시킵니다.
        return {"step": state.step + 1} 
    
    failed_step = state.failed_step or "unknown"
    retry_count = state.retry_count
    
    logger.warning(f"Error detected in {failed_step}: {state.error}, retry={retry_count}/{state.max_retry}")
    
    # 2. 최대 재시도 횟수 확인
    if retry_count >= state.max_retry:
        logger.error(f"Max retries reached for {failed_step}. Cannot recover.")
        # 복구 불가 -> Graph 종료 또는 최종 출력으로 라우팅
        return {"step": state.step + 1} 
    
    # 3. 재시도 가능한 단계 결정
    retryable_steps = ["fetch_snapshot_node", "analyze_readme_summary_node"]
    
    if failed_step in retryable_steps:
        logger.info(f"Scheduling retry for {failed_step}")
        return {
            "error": None,          # 에러 상태 클리어
            "failed_step": failed_step, # 재시도 후 이 단계로 돌아가도록 failed_step 유지 (라우팅용)
            "retry_count": retry_count + 1,
            "step": state.step + 1, 
        }
    
    # 재시도 목록에 없는 에러
    return {"step": state.step + 1}

def route_after_fetch(state: RecommendState) -> str:
    """스냅샷 수집 후 라우팅."""
    if state.error:
        return "check_ingest_error_node"
    # 성공 시: 다음 핵심 단계인 README 분석으로 이동
    return "analyze_readme_summary_node"


def route_after_analysis(state: RecommendState) -> str:
    """README 분석 및 요약 후 라우팅."""
    if state.error:
        return "check_ingest_error_node"
    return "__end__" 


def route_after_error_check(state: RecommendState) -> str:
    """에러 체크 후 라우팅."""
    
    # 1. 에러가 남아있다면 (최대 재시도 횟수 초과)
    if state.error:
        # 복구 불가 -> 그래프 종료
        return "__end__"
    
    # 2. 에러가 클리어되고 재시도가 필요한 단계가 남아있는 경우
    failed_step = state.failed_step
    
    if failed_step == "fetch_snapshot_node":
        # fetch_snapshot_node 노드로 돌아가 재시도
        return "fetch_snapshot_node"
    elif failed_step == "analyze_readme_summary_node":
        # analyze_readme_summary_node 노드로 돌아가 재시도
        return "analyze_readme_summary_node"
    
    # 3. 모든 에러가 복구되었거나 재시도가 불필요한 경우
    return "__end__"