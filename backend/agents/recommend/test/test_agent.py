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
            "docs_analysis": docs_result_dict,   # dict로 넣음
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


def check_ingest_error_node(state: RecommendState) -> Dict[str, Any]:
    """[3단계] 에러 복구 로직"""
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
    return {"step": state.step + 1} # 종료

# ------------------------------------------------------------------
# 3. Routing Logic
# ------------------------------------------------------------------

def route_after_fetch(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return "analyze_readme_summary_node"

def route_after_analysis(state: RecommendState) -> str:
    if state.error: return "check_ingest_error_node"
    return END

def route_after_error_check(state: RecommendState) -> str:
    if state.error: return END # 복구 실패
    
    # 재시도 로직
    if state.failed_step == "fetch_snapshot_node":
        return "fetch_snapshot_node"
    elif state.failed_step == "analyze_readme_summary_node":
        return "analyze_readme_summary_node"
    
    return END

# ------------------------------------------------------------------
# 4. Graph Construction & Execution
# ------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(RecommendState)
    
    workflow.add_node("fetch_snapshot_node", fetch_snapshot_node)
    workflow.add_node("analyze_readme_summary_node", analyze_readme_summary_node)
    workflow.add_node("check_ingest_error_node", check_ingest_error_node)
    
    workflow.set_entry_point("fetch_snapshot_node")
    
    workflow.add_conditional_edges("fetch_snapshot_node", route_after_fetch)
    workflow.add_conditional_edges("analyze_readme_summary_node", route_after_analysis)
    workflow.add_conditional_edges("check_ingest_error_node", route_after_error_check)
    
    return workflow.compile()

async def main():
    # 🧪 테스트할 리포지토리 설정 (실제 존재하는 리포지토리여야 함)
    target_owner = "Hyeri-hci"
    target_repo = "OSSDoctor"
    
    print(f"\n======== 🧪 TESTING REAL AGENT : {target_owner}/{target_repo} ========")
    
    graph = build_graph()
    initial_state = RecommendState(
        repo_url=f"https://github.com/{target_owner}/{target_repo}",
        owner=target_owner,
        repo=target_repo
    )
    
    # 그래프 실행
    final_state = None
    async for event in graph.astream(initial_state):
        for key, value in event.items():
            print(f" -> Node Completed: {key}")
            final_state = value # 상태 업데이트

    print("\n======== 📊 FINAL RESULT ========")
    if final_state and final_state.get("readme_summary"):
        summary = final_state["readme_summary"]
        print(f"🔹 Quality Score: {summary.get('documentation_quality')}")
        print(f"🔹 LLM Summary:\n{summary.get('final_summary')}")
        print(f"🔹 Timings: {final_state.get('timings')}")
    else:
        print("❌ Analysis Failed.")
        print(f"Error: {final_state.get('error') if final_state else 'Unknown'}")

if __name__ == "__main__":
    asyncio.run(main())