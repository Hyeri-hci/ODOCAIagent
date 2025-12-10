import logging
import time
import asyncio
from typing import Dict, Any, Optional
from dataclasses import asdict
from langgraph.graph import StateGraph, END

from backend.agents.recommend.agent.state import RecommendState
from backend.agents.recommend.core.ingest.summarizer import ContentSummarizer
from backend.core.models import RepoSnapshot

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s | %(message)s')
logger = logging.getLogger("TestRealAgent")

# ------------------------------------------------------------------
# 1. Global Instances (LLM 등 무거운 객체는 한 번만 생성)
# ------------------------------------------------------------------
try:
    # 실제 API Key가 설정되어 있어야 실행됩니다.
    summarizer_instance = ContentSummarizer()
    logger.info("✅ ContentSummarizer initialized with Real LLM.")
except Exception as e:
    logger.error(f"❌ Failed to init ContentSummarizer. Check API Keys: {e}")
    exit(1)

# ------------------------------------------------------------------
# 2. Nodes Definition (사용자님의 실제 로직 적용)
# ------------------------------------------------------------------

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
        
        # readme_content가 None일 경우 빈 문자열("")로 변환하여 안전성 확보
        readme_content = snapshot_dict.get("readme_content") or "" 

        # Dict → RepoSnapshot 변환
        snapshot_obj = RepoSnapshot(**snapshot_dict)

        # 3. 문서 분석 (DocsCoreResult dataclass)
        docs_result = analyze_docs(snapshot_obj)

        # dataclass → dict 변환
        docs_result_dict = asdict(docs_result)

        # 4. LLM 입력 구성
        llm_input_text = extract_and_structure_summary_input(readme_content)

        # 5. LLM 요약 실행 (비동기)
        # 내용이 너무 짧으면 요약 스킵
        final_summary = "No summary generated."
        
        if llm_input_text and len(readme_content) > 50:
            final_summary = await summarizer_instance.summarize(llm_input_text)
            logger.info("LLM summary generated successfully.")
        else:
            logger.warning("Skipping LLM summary: README is empty or too short.")

        # 6. 결과 통합
        ingest_result = {
            "final_summary": final_summary,
            "docs_analysis": docs_result_dict,
            # 빈 문자열이어도 에러 안 나게 처리됨
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

    # [수정됨] 1. 모드 결정 및 분석 데이터 준비
    # readme_summary가 없더라도, repo_snapshot(기본 정보)만 있으면 분석 모드로 진입합니다.
    if state.repo_snapshot:
        mode = "url_analysis"
        
        # Core 함수에 넘겨줄 데이터 패키징
        # state.readme_summary가 None일 경우 빈 dict로 처리하여 에러 방지
        analyzed_data = {
            "repo_snapshot": state.repo_snapshot,
            "readme_summary": state.readme_summary if state.readme_summary else {}
        }
    else:
        # 스냅샷조차 없으면 일반 검색 모드
        mode = "semantic_search"
        analyzed_data = None

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
    


def check_ingest_error_node(state: RecommendState) -> Dict[str, Any]:
    """에러 복구 로직"""
    if not state.error:
        return {"step": state.step + 1}
    
    logger.warning(f"⚠️ Error caught in step: {state.failed_step}. Retry {state.retry_count}/{state.max_retry}")
    
    if state.retry_count < state.max_retry:
        return {
            "error": None,
            "failed_step": state.failed_step,
            "retry_count": state.retry_count + 1,
            "step": state.step + 1
        }
    
    logger.error("🚫 Max retries reached. Giving up.")
    return {"step": state.step + 1}

# ------------------------------------------------------------------
# 3. Routing Logic
# ------------------------------------------------------------------

def route_after_fetch(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "analyze_readme_summary_node"

def route_after_analysis(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    # ✅ 성공 시: 쿼리 생성 노드로 이동
    return "generate_search_query_node"

def route_after_query_gen(state: RecommendState) -> str:
    """쿼리 생성 후 라우팅"""
    if state.error: return "check_ingest_error_node"
    # 추후 DB 검색 노드가 있다면 거기로 연결. 지금은 테스트 종료.
    return END

def route_after_error_check(state: RecommendState) -> str:
    if state.error: return END 
    
    # 재시도 라우팅
    if state.failed_step == "fetch_snapshot_node":
        return "fetch_snapshot_node"
    elif state.failed_step == "analyze_readme_summary_node":
        return "analyze_readme_summary_node"
    elif state.failed_step == "generate_search_query_node":
        return "generate_search_query_node"
    
    return END

# ------------------------------------------------------------------
# 4. Graph Construction & Execution
# ------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(RecommendState)
    
    workflow.add_node("fetch_snapshot_node", fetch_snapshot_node)
    workflow.add_node("analyze_readme_summary_node", analyze_readme_summary_node)
    # 👇 [추가] 쿼리 생성 노드 등록
    workflow.add_node("generate_search_query_node", generate_search_query_node)
    workflow.add_node("check_ingest_error_node", check_ingest_error_node)
    
    workflow.set_entry_point("fetch_snapshot_node")
    
    workflow.add_conditional_edges("fetch_snapshot_node", route_after_fetch)
    workflow.add_conditional_edges("analyze_readme_summary_node", route_after_analysis)
    # 👇 [추가] 쿼리 생성 후 엣지
    workflow.add_conditional_edges("generate_search_query_node", route_after_query_gen)
    workflow.add_conditional_edges("check_ingest_error_node", route_after_error_check)
    
    return workflow.compile()

async def main():
    target_owner = "Unani0528"
    target_repo = "ai_cookbook"
    
    # 🧪 [테스트 시나리오]
    # 사용자가 OSSDoctor(분석/대시보드 도구)를 주면서
    # "이거랑 비슷한데 Python으로 된 걸 찾고 싶어" 라고 요청하는 상황
    user_request_scenario = "이 프로젝트랑 기능은 비슷한데, 언어는 Python으로 된 프로젝트 찾아줘."

    print(f"\n======== 🧪 TESTING REAL AGENT : {target_owner}/{target_repo} ========")
    print(f"📝 User Request: {user_request_scenario}\n")
    
    graph = build_graph()
    initial_state = RecommendState(
        repo_url=f"https://github.com/{target_owner}/{target_repo}",
        owner=target_owner,
        repo=target_repo,
        user_request=user_request_scenario # State에 입력 주입
    )
    
    final_state = None
    async for event in graph.astream(initial_state):
        for key, value in event.items():
            print(f" -> Node Completed: {key}")
            final_state = value 

    print("\n======== 📊 FINAL RESULT ========")
    if final_state:
        # 1. 문서 품질 점수
        if final_state.get("readme_summary"):
            summary = final_state["readme_summary"]
            print(f"🔹 Doc Quality Score: {summary.get('documentation_quality')}")
        
        # 2. 생성된 검색 쿼리 결과 (가장 중요)
        print(f"\n🔎 [Generated Search Params]")
        print(f"   - Query: {final_state.get('search_query')}")
        print(f"   - Keywords: {final_state.get('search_keywords')}")
        print(f"   - Filters: {final_state.get('search_filters')}")
        
        print(f"\n🔹 Timings: {final_state.get('timings')}")
    else:
        print("❌ Analysis Failed.")

if __name__ == "__main__":
    asyncio.run(main())