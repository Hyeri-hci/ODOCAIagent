"""
SSE 기반 분석 진행률 스트리밍 API.

분석 진행 상황을 실시간으로 클라이언트에 전달합니다.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sse"])


class StreamAnalyzeRequest(BaseModel):
    """SSE 분석 요청."""
    repo_url: str = Field(..., description="GitHub 저장소 URL")


class ProgressEvent(BaseModel):
    """진행률 이벤트."""
    step: str
    progress: int
    message: str
    data: dict = Field(default_factory=dict)


async def analyze_with_progress(owner: str, repo: str, ref: str) -> AsyncGenerator[str, None]:
    """
    분석 진행 상황을 SSE 이벤트로 스트리밍.
    
    단계:
    - github (10%): GitHub 데이터 수집
    - analyzing (50%): 분석 진행 중
    - complete (100%): 완료
    
    캐시: 동일 저장소는 24시간 동안 캐시됩니다.
    """
    from concurrent.futures import ThreadPoolExecutor
    from backend.common.cache import analysis_cache
    
    def send_event(step: str, progress: int, message: str, data: dict = None) -> str:
        event = ProgressEvent(
            step=step,
            progress=progress,
            message=message,
            data=data or {}
        )
        return f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"
    
    try:
        # 캐시 확인
        cached_result = analysis_cache.get_analysis(owner, repo, ref)
        if cached_result:
            logger.info(f"SSE returning cached analysis for {owner}/{repo}@{ref}")
            yield send_event("github", 10, "캐시된 결과 확인 중...")
            await asyncio.sleep(0.3)
            yield send_event("complete", 100, "분석 완료! (캐시)", {"result": cached_result})
            return
        
        # Step 1: 시작
        yield send_event("github", 10, "GitHub 저장소 확인 중...")
        await asyncio.sleep(0.5)  # UI가 첫 이벤트를 표시할 시간
        
        # Step 2: 분석 진행
        yield send_event("docs", 30, "문서 품질 분석 중...")
        
        # Step 3: 실제 분석 실행 (기존 agent_service 사용)
        yield send_event("activity", 50, "활동성 분석 중...")
        
        from backend.api.agent_service import run_agent_task
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: run_agent_task(
                    task_type="diagnose_repo",
                    owner=owner,
                    repo=repo,
                    ref=ref,
                    use_llm_summary=True
                )
            )
        
        yield send_event("scoring", 80, "건강도 점수 계산 중...")
        await asyncio.sleep(0.3)
        
        if not result.get("ok"):
            error_msg = result.get("error", "분석 실패")
            yield send_event("error", 0, f"분석 실패: {error_msg}", {"error": error_msg})
            return
        
        data = result.get("data", {})
        
        # Step 4: Good First Issues 수집
        yield send_event("llm", 90, "추천 이슈 수집 중...")
        
        try:
            from backend.common.github_client import fetch_beginner_issues
            
            with ThreadPoolExecutor() as executor:
                recommended_issues = await loop.run_in_executor(
                    executor,
                    lambda: fetch_beginner_issues(owner, repo, max_count=5)
                )
            data["recommended_issues"] = recommended_issues
        except Exception:
            data["recommended_issues"] = []
        
        # Step 5: actions 및 risks 생성 (regular API와 동일하게)
        try:
            from backend.api.http_router import _generate_actions_from_issues, _generate_risks_from_issues
            
            # 데이터에서 이슈 정보 추출
            docs_issues = data.get("docs_issues", [])
            activity_issues = data.get("activity_issues", [])
            recommended_issues = data.get("recommended_issues", [])
            
            # actions 및 risks 생성
            data["actions"] = _generate_actions_from_issues(docs_issues, activity_issues, data, recommended_issues)
            data["risks"] = _generate_risks_from_issues(docs_issues, activity_issues, data)
        except Exception as e:
            logger.warning(f"Failed to generate actions/risks: {e}")
            data["actions"] = []
            data["risks"] = []
        
        # 캐시에 저장
        analysis_cache.set_analysis(owner, repo, ref, data)
        
        # 완료
        yield send_event("complete", 100, "분석 완료!", {"result": data})
        
    except Exception as e:
        logger.exception(f"SSE analysis failed: {e}")
        yield send_event("error", 0, f"분석 중 오류 발생: {str(e)}", {"error": str(e)})


@router.get("/analyze/stream")
async def analyze_repository_stream(repo_url: str):
    """
    저장소 분석 SSE 스트리밍 API.
    
    실시간으로 분석 진행 상황을 전달합니다.
    
    이벤트 형식:
    - step: 현재 단계 (github, docs, activity, structure, scoring, llm, complete)
    - progress: 진행률 (0-100)
    - message: 사용자에게 표시할 메시지
    - data: 추가 데이터 (complete 시 전체 결과 포함)
    """
    from backend.api.http_router import parse_github_url
    
    try:
        owner, repo, ref = parse_github_url(repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return StreamingResponse(
        analyze_with_progress(owner, repo, ref),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        }
    )

