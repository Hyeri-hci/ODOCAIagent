"""
Supervisor Agent 유틸리티 함수
"""
from typing import Dict, Any, Optional
import logging
import json
import os
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

async def check_repo_size_and_warn(owner: str, repo: str) -> Dict[str, Any]:
    """
    저장소 크기 체크 및 대용량 저장소 경고 생성
    """
    repo_token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if repo_token:
        headers["Authorization"] = f"token {repo_token}"
    
    result = {
        "is_large": False,
        "warning_message": None,
        "estimated_time": 30,  # 기본 30초
        "repo_stats": {}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # 저장소 기본 정보 가져오기
            async with session.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    repo_data = await resp.json()
                    size_kb = repo_data.get("size", 0)  # KB 단위
                    size_mb = size_kb / 1024
                    
                    result["repo_stats"] = {
                        "size_mb": round(size_mb, 2),
                        "stars": repo_data.get("stargazers_count", 0),
                        "forks": repo_data.get("forks_count", 0),
                        "open_issues": repo_data.get("open_issues_count", 0)
                    }
                    
                    # 대용량 기준: 100MB 이상 또는 star 10000개 이상
                    if size_mb > 100 or repo_data.get("stargazers_count", 0) > 10000:
                        result["is_large"] = True
                        
                        # 크기에 따른 예상 시간 문구
                        if size_mb > 500:
                            result["estimated_time"] = 180
                            time_str = "약 3분"
                        elif size_mb > 200:
                            result["estimated_time"] = 120
                            time_str = "약 2분"
                        else:
                            result["estimated_time"] = 60
                            time_str = "약 1분"
                        
                        result["warning_message"] = (
                            f"**{owner}/{repo}**는 대용량 저장소입니다 "
                            f"(크기: {size_mb:.1f}MB, Stars: {repo_data.get('stargazers_count', 0):,}). "
                            f"분석에 {time_str} 정도 소요될 수 있습니다. 잠시만 기다려주세요..."
                        )
                        
                        logger.info(f"Large repo detected: {owner}/{repo} ({size_mb:.1f}MB)")
    except Exception as e:
        logger.warning(f"Failed to check repo size: {e}")
    
    return result


async def enhance_answer_with_context(
    user_message: str,
    base_answer: str,
    referenced_data: Dict[str, Any],
    action: str,
    refers_to: str = "previous data"
) -> str:
    """대명사 참조 시 컨텍스트를 활용하여 답변 보강"""
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage, Role
        
        llm = fetch_llm_client()
        loop = asyncio.get_event_loop()
        
        # 컨텍스트 요약
        context_summary = json.dumps(referenced_data, ensure_ascii=False, indent=2)[:1000]
        
        action_instructions = {
            "refine": "더 자세하고 구체적으로",
            "summarize": "간단하고 핵심적으로",
            "view": "명확하게"
        }
        
        instruction = action_instructions.get(action, "명확하게")
        
        prompt = f"""사용자가 이전 대화에서 생성된 '{refers_to}' 데이터를 참조하여 질문하고 있습니다.

=== 사용자 질문 ===
{user_message}

=== 참조 데이터 ('{refers_to}') ===
{context_summary}

=== 지시사항 ===
사용자의 요청을 {instruction} 설명해주세요.
참조 데이터의 주요 내용을 기반으로 사용자가 원하는 답변을 제공하세요.

답변은 자연스러운 한국어로 작성하되, 참조 데이터의 구체적인 내용을 포함해주세요.
"""
        
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.7,
            max_tokens=1000
        )
        
        response = await loop.run_in_executor(None, llm.chat, request)
        enhanced_answer = response.content
        
        logger.info(f"Enhanced answer with context from '{refers_to}'")
        return enhanced_answer
    
    except Exception as e:
        logger.error(f"Failed to enhance answer: {e}", exc_info=True)
        return base_answer
