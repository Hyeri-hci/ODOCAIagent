import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from langgraph.graph import END
from pydantic import ValidationError

from backend.agents.recommend.agent.state import RecommendState
from backend.agents.recommend.core.ingest.summarizer import ContentSummarizer
from backend.core.models import RepoSnapshot
from backend.agents.recommend.core.search.vector_search import vector_search_engine
from backend.agents.recommend.core.analysis.match_score import RepoScorer
from backend.agents.recommend.core.intent_parsing import extract_initial_metadata
from backend.agents.recommend.core.trend.get_trend import trend_service
from backend.agents.recommend.agent.state import CandidateRepo
from backend.agents.recommend.core.search.github_search import GitHubSearch

from langchain_openai import ChatOpenAI
from backend.agents.recommend.config.setting import settings

# ⭐️ 수정됨: 불필요한 임포트 제거
# from backend.agents.recommend.core.analysis.final_summary_generator import generate_summary 


# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s | %(message)s')
logger = logging.getLogger("TestRealAgent")

# ------------------------------------------------------------------
# 1. Global Instances
# ------------------------------------------------------------------
try:
    globals()['llm'] = ChatOpenAI(
        base_url=settings.llm.api_base,
        api_key=settings.llm.api_key,
        model=settings.llm.model_name,
        temperature=0
    )

    github_search_instance = GitHubSearch()
    summarizer_instance = ContentSummarizer()
    scorer_instance = RepoScorer()
    logger.info("✅ Global instances initialized.")
except Exception as e:
    logger.error(f"❌ Failed to init global instances: {e}")
    exit(1)

# ------------------------------------------------------------------
# 2. Nodes Definition
# ------------------------------------------------------------------

async def parse_initial_request_node(state: RecommendState) -> Dict[str, Any]:
    """
    [첫 실행 노드] 사용자 요청을 분석하여 의도와 정량적 필터 조건만 추출하고 상태를 업데이트합니다.
    """
    
    user_request = state.user_request
    repo_url = state.repo_url

    try:
        llm_client = globals()['llm'] 
    except KeyError:
        logger.error("❌ LLM client ('llm') not initialized in global scope.")
        return {"user_intent": "semantic_search", "quantitative_filters": []}

    try:
        # 2. 핵심 로직 호출 (Core Logic 실행)
        result = await extract_initial_metadata(
            llm_client=llm_client, 
            user_request=user_request,
            repo_url=repo_url
        )
        
        logger.info(f"✅ Initial Parsing Result: Intent={result.user_intent}, Filters={len(result.quantitative_filters)}")
        
        # 3. LangGraph 상태 업데이트용 맵 반환
        return {
            "user_intent": result.user_intent,
            "quantitative_filters": result.quantitative_filters
        }
    
    except Exception as e:
        logger.error(f"❌ Node Execution Failed (parse_initial_request_node): {e}")
        # 오류 발생 시 폴백 처리
        return {
            "user_intent": "semantic_search",
            "error": f"Initial parsing failed: {e.__class__.__name__}",
            "failed_step": "parse_initial_request_node"
        }

def fetch_snapshot_node(state: RecommendState) -> Dict[str, Any]:
    """GitHub 저장소 스냅샷 수집"""
    if state.repo_snapshot:
        logger.info("Reusing existing repo snapshot")
        return {"step": state.step + 1} 
    
    owner, repo = state.owner, state.repo
    if not owner or not repo:
        return {"error": "Missing owner/repo", "step": state.step + 1}
    
    from backend.core.github_core import fetch_repo_snapshot
    start_time = time.time()
    
    try:
        snapshot = fetch_repo_snapshot(owner, repo, getattr(state, 'ref', 'main'))
        snapshot_dict = snapshot.model_dump() if hasattr(snapshot, "model_dump") else asdict(snapshot)
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["fetch_snapshot"] = elapsed
        
        logger.info(f"Fetched snapshot for {owner}/{repo} in {elapsed}s")
        return {"repo_snapshot": snapshot_dict, "timings": timings, "step": state.step + 1}
        
    except Exception as e:
        logger.error(f"Failed to fetch snapshot: {e}")
        return {"error": str(e), "failed_step": "fetch_snapshot_node", "step": state.step + 1}

async def analyze_readme_summary_node(state: RecommendState) -> Dict[str, Any]:
    """README 분석 및 요약"""
    if state.readme_summary: return {"step": state.step + 1}
    if not state.repo_snapshot: 
        return {"error": "No snapshot", "failed_step": "analyze_readme_summary_node", "step": state.step + 1}
    
    from backend.core.docs_core import analyze_docs, extract_and_structure_summary_input
    start_time = time.time()
    
    try:
        snapshot_dict = state.repo_snapshot
        readme_content = snapshot_dict.get("readme_content") or "" 
        snapshot_obj = RepoSnapshot(**snapshot_dict)

        docs_result = analyze_docs(snapshot_obj)
        docs_result_dict = asdict(docs_result)
        llm_input_text = extract_and_structure_summary_input(readme_content)

        final_summary = "No summary generated."
        if llm_input_text and len(readme_content) > 50:
            final_summary = await summarizer_instance.summarize(llm_input_text)
            logger.info("LLM summary generated successfully.")
        else:
            logger.warning("Skipping LLM summary: README too short/empty.")

        ingest_result = {
            "final_summary": final_summary,
            "docs_analysis": docs_result_dict,
            "readme_word_count": len(readme_content.split()),
            "documentation_quality": docs_result_dict.get("total_score", 0)
        }

        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["analyze_readme_summary"] = elapsed

        return {"readme_summary": ingest_result, "timings": timings, "step": state.step + 1, "error": None}

    except Exception as e:
        logger.error(f"Failed to analyze README: {e}")
        return {"error": str(e), "failed_step": "analyze_readme_summary_node", "step": state.step + 1}

async def generate_rag_search_query_node(state: RecommendState) -> Dict[str, Any]:
    """RAG 쿼리 생성 (Fallback 로직 포함)"""

    from backend.agents.recommend.core.search.rag_query_generator import generate_rag_query_and_filters
    
    start_time = time.time()
    logger.info("🚀 Starting RAG Query Generation")

    # [중요] README가 없어도 기본 정보만 있으면 분석 모드 진입
    if state.repo_snapshot:
        analyzed_data = {
            "repo_snapshot": state.repo_snapshot,
            "readme_summary": state.readme_summary if state.readme_summary else {}
        }
    else:
        analyzed_data = None


    mode = state.user_intent

    user_input = state.user_request if state.user_request.strip() else "Find similar projects."

    try:
        result = await generate_rag_query_and_filters(user_input, mode, analyzed_data)
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["generate_query"] = elapsed
        
        logger.info(f"✅ Query Generated ({mode}): {result['query']}")

        return {
            "search_query": result.get("query", ""),
            "search_keywords": result.get("keywords", []),
            "search_filters": result.get("filters", {}),
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Failed to generate query: {e}")
        return {"error": str(e), "failed_step": "generate_rag_search_query_node", "step": state.step + 1}

# =================================================================
# 👇 4. Vector Search Node (DB 조회)
# =================================================================
def vector_search_node(state: RecommendState) -> Dict[str, Any]:
    """생성된 쿼리로 Qdrant 검색 수행"""
    
    # 앞 단계에서 쿼리 생성에 실패했다면 실행 불가
    if not state.search_query:
        logger.warning("No search query found. Skipping vector search.")
        return {"step": state.step + 1}
    
    from backend.agents.recommend.agent.state import CandidateRepo

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
                rag_query=state.search_query,
                rag_filters=state.search_filters
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
    
# =================================================================
# 👇 5. Scoring Node (LLM 평가)
# =================================================================
async def score_candidates_node(state: RecommendState) -> Dict[str, Any]:
    """LLM을 이용한 후보군 상세 평가 (ai_reason 생성)"""
    
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
        # 이 단계에서 각 CandidateRepo 객체의 ai_score와 ai_reason이 채워집니다.
        scored_results = await scorer_instance.evaluate_candidates(
            candidates=state.search_results,
            user_request=state.user_request,
            intent=state.user_intent,
            source_repo=source_snapshot,
            readme_summary=readme_summary_text
        )

        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["ai_scoring"] = elapsed

        if scored_results:
            logger.info(f"✅ Scoring complete. Top 1: {scored_results[0].name})")

        return {
            "search_results": scored_results[:6], # ai_reason이 포함된 리스트로 업데이트
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Scoring failed: {e}")
        return {"error": str(e), "failed_step": "score_candidates_node", "step": state.step + 1}
    
async def trend_search_node(state: RecommendState) -> Dict[str, Any]:
    """
    [트렌드 검색 노드] 상태의 정량적 필터(TREND_LANGUAGE, TREND_SINCE)를 기반으로 트렌드 검색을 실행합니다.
    """
    start_time = time.time()
    logger.info("🔎 Executing Trend Search via TrendService...")

    try:
        # 1. TrendService 호출 (state에서 quantitative_filters 전달)
        raw_search_results = await trend_service.search_trending_repos(
            filters=state.quantitative_filters
        )
        
        # 2. 결과 매핑 및 변환 (ParsedTrendingRepo -> CandidateRepo)
        structured_results: List[CandidateRepo] = []
        for item in raw_search_results:
            try:
                repo_obj = CandidateRepo(
                    id=0,
                    name=item.name,
                    owner=item.owner,
                    html_url=item.url,
                    description=item.description,
                    main_language=item.language,
                    stars=item.total_stars,
                    rank=item.rank,
                    stars_since=item.stars_since,
                    score=0.0,
                    match_snippet=f"Trending Rank: {item.rank}, Stars this period: {item.stars_since}"
                )
                structured_results.append(repo_obj)
            except (KeyError, ValidationError, AttributeError) as ve:
                logger.warning(f"⚠️ Failed to map Trend result to CandidateRepo: {ve}")


        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["trend_search"] = elapsed
        
        logger.info(f"✅ Trend Search Found {len(structured_results)} candidates in {elapsed}s")

        # 3. 상태 업데이트
        return {
            "search_results": structured_results, # 확장된 CandidateRepo 객체 리스트 저장
            "timings": timings,
            "search_query": f"Trending repositories based on filters.",
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Trend search failed: {e}")
        return {
            "error": str(e), 
            "failed_step": "trend_search_node", 
            "step": state.step + 1
        }
    
async def generate_api_search_query_node(state: RecommendState) -> Dict[str, Any]:
    """
    [쿼리 생성 노드] 사용자 의도(search_criteria)와 필터 조건을 기반으로
    GitHub Search API에 적합한 최종 쿼리 문자열과 필터 파라미터를 생성합니다.
    """
    
    mode = state.user_intent 
    if mode != "search_criteria":
        logger.warning(f"Query generation called for invalid mode: {mode}. Skipping.")
        return {"step": state.step + 1}
    
    if not state.user_request:
        return {"step": state.step + 1}
    
    from backend.agents.recommend.core.search.search_query_generator import search_query_generator
        
    start_time = time.time()
    logger.info(f"🚀 Starting Search Query Generation (Mode: {mode})")
    
    try:
        result_params = await search_query_generator(user_input=state.user_request)
        
        final_query_str = result_params.get("q", "")
        
        final_filters = {
            "q": final_query_str,
            "sort": result_params.get("sort"),
            "order": result_params.get("order")
        }
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["generate_api_query"] = elapsed
        
        logger.info(f"✅ Query Generated ({mode}): Q='{final_filters}...' | Filters set.")

        return {
            "github_seach_query": final_filters,
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Failed to generate query: {e}")
        return {"error": str(e), "failed_step": "generate_api_search_query_node", "step": state.step + 1}
    
async def github_search_node(state: RecommendState) -> Dict[str, Any]:
    """
    [GitHub API 검색 노드] LLM이 생성한 쿼리 파라미터로 GitHub Search API를 호출하고
    결과를 search_results에 저장합니다.
    """
    
    if not state.github_seach_query or not state.github_seach_query.get("q"):
        logger.warning("No valid search query params found. Skipping GitHub API search.")
        return {"step": state.step + 1}
        
    start_time = time.time()
    
    try:
        raw_results = github_search_instance.search_repositories(state.github_seach_query)
        
        structured_results: List[CandidateRepo] = []
        for item in raw_results:
            try:
                repo_obj = CandidateRepo(
                    id=getattr(item, "id", 0),
                    name=getattr(item, "name"),
                    owner=getattr(item, "owner"),
                    html_url=getattr(item, "html_url"),
                    description=getattr(item, "description", "GitHub API search result."),
                    main_language=getattr(item, "main_language", "Unknown"),
                    stars=int(getattr(item, "stars", 0)),
                    match_snippet=getattr(item, "match_snippet", "API result."),
                    search_query=state.github_seach_query
                )
                structured_results.append(repo_obj)
            except Exception as ve:
                logger.error(f"Failed to map API result to CandidateRepo: {ve}")

        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["github_api_search"] = elapsed

        logger.info(f"✅ Found {len(structured_results)} candidates from GitHub API in {elapsed}s")

        return {
            "search_results": structured_results,
            "timings": timings,
            "step": state.step + 1,
            "error": None
        }

    except Exception as e:
        logger.error(f"❌ Node Execution Failed (github_search_node): {e}")
        return {"error": str(e), "failed_step": "github_search_node", "step": state.step + 1}


def check_ingest_error_node(state: RecommendState) -> Dict[str, Any]:
    """에러 발생 시 재시도 횟수를 확인하고 복구 또는 종료합니다."""
    if not state.error: return {"step": state.step + 1}
    if state.retry_count < state.max_retry:
        return {"error": None, "failed_step": state.failed_step, "retry_count": state.retry_count + 1, "step": state.step + 1}
    return {"step": state.step + 1}

# ------------------------------------------------------------------
# 3. Routing Logic (라우팅 로직 - 최종 정리)
# ------------------------------------------------------------------

def route_after_parsing(state: RecommendState) -> str:
    """초기 의도 파악 후 다음 단계를 결정합니다."""
    if state.error: return "check_ingest_error_node"
    intent = state.user_intent
    
    if intent == "url_analysis": return "fetch_snapshot_node" 
    elif intent == "trend_analysis": return "trend_search_node"
    elif intent == "semantic_search": return "generate_rag_query_node"
    elif intent == "search_criteria": return "generate_api_search_query_node"
    else: return "generate_rag_query_node"


def route_after_fetch(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "analyze_readme_summary_node"

def route_after_analysis(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "generate_rag_query_node" 


def route_after_rag_query_gen(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "vector_search_node"

def route_after_api_query_gen(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "github_search_node" 

def route_after_github_search(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "vector_search_node"

def route_after_vector_search(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "score_candidates_node"

# ⭐️ 수정됨: score_candidates_node 후 -> 바로 END
def route_after_scoring(state: RecommendState) -> str:
    """Scoring 후, 개별 ai_reason을 생성했으므로 바로 END로 이동합니다."""
    if state.error: return "check_ingest_error_node"
    return END 

# ⭐️ route_after_final_summary_gen 함수는 삭제되었습니다.


# ⭐️ 수정됨: 트렌드 검색 후 -> score_candidates_node로 이동 (ai_reason 생성)
def route_after_trend_search(state: RecommendState) -> str:
    """트렌드 검색 후 다음 단계를 결정합니다."""
    if state.error: 
        return "check_ingest_error_node"
    return "score_candidates_node"

# ⭐️ 수정됨: 에러 복구 맵에서 generate_final_summary_node 제거
def route_after_error_check(state: RecommendState) -> str:
    if state.error: return END 
    step_map = {
        "parse_initial_request_node": "parse_initial_request_node", 
        "fetch_snapshot_node": "fetch_snapshot_node",
        "analyze_readme_summary_node": "analyze_readme_summary_node",
        "generate_rag_query_node": "generate_rag_query_node",
        "generate_api_search_query_node": "generate_api_search_query_node",
        "github_search_node": "github_search_node",
        "vector_search_node": "vector_search_node",
        "score_candidates_node": "score_candidates_node",
        "trend_search_node": "trend_search_node",
        # generate_final_summary_node 제거됨
    }
    return step_map.get(state.failed_step, END)