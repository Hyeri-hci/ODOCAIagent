import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, ValidationError

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
    scorer_instance = RepoScorer() # Scorer 인스턴스 생성 (비용 절약을 위해 재사용)
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
    (핵심 로직은 core/intent_parsing.py의 extract_initial_metadata를 호출)
    """
    
    user_request = state.user_request
    repo_url = state.repo_url
    
    try:
        llm_client = globals()['llm'] 
    except KeyError:
        logger.error("❌ LLM client ('llm') not initialized in global scope.")
        return {"user_intent": "semantic_search", "quantitative_filters": []}

    if not user_request and not repo_url:
        logger.warning("Request is empty. Defaulting to semantic_search.")
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
        # 반환된 딕셔너리의 키(user_intent, quantitative_filters)가 RecommendState의 필드를 업데이트합니다.
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
# 👇 [NEW] 4. Vector Search Node (DB 조회)
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
# 👇 [NEW] 5. Scoring Node (LLM 평가)
# =================================================================
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
            # item은 ParsedTrendingRepo 객체이거나 Dict 형태입니다.
            # CandidateRepo가 rank, stars_since 필드를 포함하도록 확장되었으므로 직접 변환 가능합니다.
            try:
                # 필드가 일치한다고 가정하고 변환 (stars=total_stars, score=stars_since를 임시로 사용)
                repo_obj = CandidateRepo(
                    id=0,
                    name=item.name,
                    owner=item.owner,
                    html_url=item.url,
                    description=item.description,
                    main_language=item.language,
                    stars=item.total_stars,
                    # 트렌드 필드 매핑
                    rank=item.rank,
                    stars_since=item.stars_since,
                    
                    # RAG 필드는 0 또는 빈 값
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
    
    # ⭐️ 쿼리 생성이 필요 없는 의도는 이 노드로 라우팅되지 않아야 합니다.
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
        
        # 결과 추출 및 상태 업데이트 준비
        final_query_str = result_params.get("q", "")
        
        # ⭐️ search_filters 딕셔너리에 API 호출에 필요한 모든 파라미터를 저장합니다.
        final_filters = {
            "q": final_query_str, # 이 필드는 GitHub API 검색에 사용됩니다.
            "sort": result_params.get("sort"),
            "order": result_params.get("order")
        }
        
        elapsed = round(time.time() - start_time, 3)
        timings = dict(state.timings)
        timings["generate_api_query"] = elapsed
        
        logger.info(f"✅ Query Generated ({mode}): Q='{final_filters}...' | Filters set.")

        return {
            # ⭐️ search_query는 LLM이 생성한 최종 쿼리 문자열 (API 검색용)
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
    
    # 1. 필수 입력값 체크
    if not state.github_seach_query or not state.github_seach_query.get("q"):
        logger.warning("No valid search query params found. Skipping GitHub API search.")
        return {"step": state.step + 1}
        
    start_time = time.time()
    
    # 2. GitHub Search 호출 (동기 코드를 async 노드에서 호출)
    try:
        raw_results = github_search_instance.search_repositories(state.github_seach_query)
        
        # 3. 결과 파싱 및 CandidateRepo로 변환
        structured_results: List[CandidateRepo] = []
        for item in raw_results:
            # 🚨 NOTE: 이 부분은 GitHubSearch의 Step 3 (GitHubParser)이 담당해야 함
            # 여기서는 DUMMY 매핑을 사용합니다.
            try:
                repo_obj = CandidateRepo(
                    id=getattr(item, "id", 0),
                    name=getattr(item, "name"),
                    owner=getattr(item, "owner"),
                    html_url=getattr(item, "html_url"),
                    description=getattr(item, "description", "GitHub API search result."),
                    main_language=getattr(item, "main_language", "Unknown"),
                    stars=int(getattr(item, "stars", 0)),
                    match_snippet=getattr(item, "match_snippet", "API result.")
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
    # ... (check_ingest_error_node 구현 유지) ...
    if not state.error: return {"step": state.step + 1}
    if state.retry_count < state.max_retry:
        return {"error": None, "failed_step": state.failed_step, "retry_count": state.retry_count + 1, "step": state.step + 1}
    return {"step": state.step + 1}

# ------------------------------------------------------------------
# 3. Routing Logic (라우팅 로직)
# ------------------------------------------------------------------

# ⭐️ 새로운 라우터: parse_initial_request_node 이후
def route_after_parsing(state: RecommendState) -> str:
    """초기 의도 파악 후 다음 단계를 결정합니다."""
    if state.error:
        return "check_ingest_error_node"
        
    intent = state.user_intent
    
    if intent == "url_analysis":
        logger.info("🚦 Intent: url_analysis. Routing to fetch_snapshot_node.")
        return "fetch_snapshot_node" 
    
    elif intent == "trend_analysis":
        logger.info("🚦 Intent: trend_analysis. Routing to trend_search_node.")
        return "trend_search_node"
    
    elif intent == "semantic_search":
        # ⭐️ semantic_search: RAG 쿼리 생성으로 이동
        logger.info(f"🚦 Intent: {intent}. Routing directly to generate_rag_query_node.")
        return "generate_rag_query_node"
    
    elif intent == "search_criteria":
        # ⭐️ search_criteria: API 쿼리 생성으로 이동
        logger.info(f"🚦 Intent: search_criteria. Routing directly to generate_api_search_query_node.")
        return "generate_api_search_query_node"
    
    else:
        logger.warning(f"🚦 Unknown intent ({intent}). Defaulting to RAG query.")
        return "generate_rag_query_node"


def route_after_fetch(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "analyze_readme_summary_node"

def route_after_analysis(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    # url_analysis 흐름: 분석 후 RAG 쿼리 생성으로 이동
    return "generate_rag_query_node" # ⭐️ 수정


# ⭐️ route_after_rag_query_gen (RAG 쿼리 생성 후 Vector DB로 직행)
def route_after_rag_query_gen(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "vector_search_node"

# ⭐️ route_after_api_query_gen (API 쿼리 생성 후 GitHub Search로 직행)
def route_after_api_query_gen(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "github_search_node" # ⭐️ GitHub API 검색으로 이동

# ⭐️ route_after_github_search (GitHub API 검색 후 Vector DB로 합류)
def route_after_github_search(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "vector_search_node"

def route_after_vector_search(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "score_candidates_node"

def route_after_scoring(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return END

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
        "score_candidates_node": "score_candidates_node"
    }
    return step_map.get(state.failed_step, END)

def route_after_trend_search(state: RecommendState) -> str:
    """트렌드 검색 후 다음 단계를 결정합니다."""
    if state.error: 
        return "check_ingest_error_node"
    return END


# ------------------------------------------------------------------
# 4. Graph Construction & Execution (build_graph 수정)
# ------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(RecommendState)
    
    # 노드 등록
    workflow.add_node("parse_initial_request_node", parse_initial_request_node)
    workflow.add_node("fetch_snapshot_node", fetch_snapshot_node)
    workflow.add_node("analyze_readme_summary_node", analyze_readme_summary_node)
    
    # ⭐️ RAG 쿼리 노드와 API 쿼리 노드를 분리 등록
    workflow.add_node("generate_rag_query_node", generate_rag_search_query_node)
    workflow.add_node("generate_api_search_query_node", generate_api_search_query_node) 
    
    # ⭐️ github_search_node 등록
    workflow.add_node("github_search_node", github_search_node) 
    
    workflow.add_node("vector_search_node", vector_search_node)
    workflow.add_node("score_candidates_node", score_candidates_node)
    workflow.add_node("check_ingest_error_node", check_ingest_error_node)
    workflow.add_node("trend_search_node", trend_search_node)
    
    # 진입점 설정
    workflow.set_entry_point("parse_initial_request_node")
    
    # 엣지 연결
    workflow.add_conditional_edges("parse_initial_request_node", route_after_parsing)
    workflow.add_conditional_edges("fetch_snapshot_node", route_after_fetch)
    workflow.add_conditional_edges("analyze_readme_summary_node", route_after_analysis)
    
    # ⭐️ RAG 쿼리 라우팅: RAG 쿼리 생성 후 Vector DB로 직행
    workflow.add_conditional_edges("generate_rag_query_node", route_after_rag_query_gen) 
    
    # ⭐️ API 쿼리 라우팅: API 쿼리 생성 후 GitHub Search로 직행
    workflow.add_conditional_edges("generate_api_search_query_node", route_after_api_query_gen) 
    
    # ⭐️ GitHub Search 후 Vector DB로 합류
    workflow.add_conditional_edges("github_search_node", route_after_github_search)
    
    workflow.add_conditional_edges("vector_search_node", route_after_vector_search)
    workflow.add_conditional_edges("score_candidates_node", route_after_scoring) 
    workflow.add_conditional_edges("check_ingest_error_node", route_after_error_check)
    
    workflow.add_conditional_edges("trend_search_node", route_after_trend_search)
    
    return workflow.compile()