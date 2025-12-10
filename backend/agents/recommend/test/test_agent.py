import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from langgraph.graph import StateGraph, END

# [Import] State 및 Core 로직
from backend.agents.recommend.agent.state import RecommendState
from backend.agents.recommend.core.ingest.summarizer import ContentSummarizer
from backend.core.models import RepoSnapshot
# [Import] 검색 엔진 (방금 만든 코드)
from backend.agents.recommend.core.search.vector_search import vector_search_engine

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s | %(message)s')
logger = logging.getLogger("TestRealAgent")

# ------------------------------------------------------------------
# 1. Global Instances
# ------------------------------------------------------------------
try:
    summarizer_instance = ContentSummarizer()
    logger.info("✅ ContentSummarizer initialized.")
except Exception as e:
    logger.error(f"❌ Failed to init ContentSummarizer: {e}")
    exit(1)

# ------------------------------------------------------------------
# 2. Nodes Definition
# ------------------------------------------------------------------

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

async def generate_search_query_node(state: RecommendState) -> Dict[str, Any]:
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
        return {"error": str(e), "failed_step": "generate_search_query_node", "step": state.step + 1}

# =================================================================
# 👇 [NEW] 4. Vector Search Node (DB 조회)
# =================================================================
def vector_search_node(state: RecommendState) -> Dict[str, Any]:
    """생성된 쿼리로 Qdrant 검색 수행"""
    
    # 앞 단계에서 쿼리 생성에 실패했다면 실행 불가
    if not state.search_query:
        logger.warning("No search query found. Skipping vector search.")
        return {"step": state.step + 1}
    
    from backend.agents.recommend.agent.state import RecommendState, CandidateRepo

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
                language=item.get("languages") or [],
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
            "search_results": structured_results, # ⭐️ 이제 객체 리스트가 저장됨
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


def check_ingest_error_node(state: RecommendState) -> Dict[str, Any]:
    """에러 복구 로직"""
    if not state.error: return {"step": state.step + 1}
    
    logger.warning(f"⚠️ Error in {state.failed_step}. Retry {state.retry_count}/{state.max_retry}")
    
    if state.retry_count < state.max_retry:
        return {"error": None, "failed_step": state.failed_step, "retry_count": state.retry_count + 1, "step": state.step + 1}
    
    logger.error("🚫 Max retries reached.")
    return {"step": state.step + 1}

# ------------------------------------------------------------------
# 3. Routing Logic
# ------------------------------------------------------------------

def route_after_fetch(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "analyze_readme_summary_node"

def route_after_analysis(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "generate_search_query_node"

def route_after_query_gen(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    # ✅ [변경] 쿼리 생성 성공 시 -> 검색 노드로 이동
    return "vector_search_node"

def route_after_vector_search(state: RecommendState) -> str:
    """검색 후 라우팅"""
    if state.error: return "check_ingest_error_node"
    # 모든 작업 완료 -> 종료
    return END

def route_after_error_check(state: RecommendState) -> str:
    if state.error: return END 
    
    # 재시도 라우팅
    step_map = {
        "fetch_snapshot_node": "fetch_snapshot_node",
        "analyze_readme_summary_node": "analyze_readme_summary_node",
        "generate_search_query_node": "generate_search_query_node",
        "vector_search_node": "vector_search_node" # 검색 재시도 추가
    }
    return step_map.get(state.failed_step, END)

# ------------------------------------------------------------------
# 4. Graph Construction & Execution
# ------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(RecommendState)
    
    workflow.add_node("fetch_snapshot_node", fetch_snapshot_node)
    workflow.add_node("analyze_readme_summary_node", analyze_readme_summary_node)
    workflow.add_node("generate_search_query_node", generate_search_query_node)
    # 👇 [추가] DB 검색 노드
    workflow.add_node("vector_search_node", vector_search_node)
    workflow.add_node("check_ingest_error_node", check_ingest_error_node)
    
    workflow.set_entry_point("fetch_snapshot_node")
    
    workflow.add_conditional_edges("fetch_snapshot_node", route_after_fetch)
    workflow.add_conditional_edges("analyze_readme_summary_node", route_after_analysis)
    workflow.add_conditional_edges("generate_search_query_node", route_after_query_gen)
    # 👇 [추가] 검색 후 종료 엣지
    workflow.add_conditional_edges("vector_search_node", route_after_vector_search)
    workflow.add_conditional_edges("check_ingest_error_node", route_after_error_check)
    
    return workflow.compile()

async def main():
    target_owner = "Hyeri-hci"
    target_repo = "ODOCAIagent" 
    
    user_request_scenario = "이 프로젝트랑 기능은 비슷한데, 언어는 Python으로 된 프로젝트 찾아줘."

    print(f"\n======== 🧪 TESTING REAL AGENT : {target_owner}/{target_repo} ========")
    print(f"📝 User Request: {user_request_scenario}\n")
    
    graph = build_graph()
    initial_state = RecommendState(
        repo_url=f"https://github.com/{target_owner}/{target_repo}",
        owner=target_owner,
        repo=target_repo,
        user_request=user_request_scenario
    )
    
    final_state = {} 
    
    async for event in graph.astream(initial_state):
        for key, value in event.items():
            print(f" -> Node Completed: {key}")
            # [수정 2] 덮어쓰지 않고 기존 정보에 합칩니다 (State Accumulation)
            final_state.update(value) 

    print("\n======== 📊 FINAL RESULT ========")
    if final_state:
        # 0. README 분석 결과
        summary_data = final_state.get("readme_summary", {})
        print(f"\n📄 [README Analysis]")
        print(f"   - Quality Score: {summary_data.get('documentation_quality', 0)}")
        print(f"   - Summary Result: {summary_data.get('final_summary', 'N/A')}")

        # 1. 쿼리 정보
        print(f"\n🔎 [Generated Search Params]")
        # 이제 누적된 정보 덕분에 Query가 None이 아닐 겁니다.
        print(f"   - Query: {final_state.get('search_query')}") 
        print(f"   - Filters: {final_state.get('search_filters')}")
        
        # 2. 추천 결과 검증
        results = final_state.get("search_results", [])
        print(f"\n🏆 [Recommended Projects] Found: {len(results)}")
        
        for idx, item in enumerate(results, 1):
            # [검증 포인트] 딕셔너리가 아니라 객체이므로 점(.)으로 접근해야 합니다.
            # 만약 여기서 에러가 안 나고 출력된다면 State에 객체로 잘 저장된 것입니다.
            
            print(f"   {idx}. {item.name} (⭐ {item.stars})")  # item['name'] 아님!
            print(f"      - ID: {item.id} | Lang: {item.language}")
            
            # 타입 확인용 로그 (테스트니까 찍어봄)
            # print(f"      - [Type Check]: {type(item)}") 
            
            snippet = item.match_snippet
            clean_snippet = snippet.replace("\n", " ")
            print(f"      - Match: {clean_snippet[:100]}..." if len(clean_snippet) > 100 else f"      - Match: {clean_snippet}")
            print(f"      - Score: {item.score:.4f}")
            print()
            
        print(f"🔹 Timings: {final_state.get('timings')}")
    else:
        print("❌ Analysis Failed.")

if __name__ == "__main__":
    asyncio.run(main())