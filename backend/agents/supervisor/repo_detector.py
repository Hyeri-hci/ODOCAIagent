"""
LLM 기반 저장소 감지 모듈

룰 베이스 키워드 리스트 대신 LLM이 문맥을 이해하여 판단.
"""

from __future__ import annotations

import logging
import json
import re
from typing import Any, Dict, Optional, Tuple

from backend.common.config import LLM_MODEL_NAME, LLM_API_KEY, LLM_API_BASE
from backend.common.github_client import search_repositories

logger = logging.getLogger(__name__)


async def detect_repository_from_message(
    user_message: str,
    session_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    LLM을 사용하여 메시지에서 저장소 정보 감지
    
    Args:
        user_message: 사용자 메시지
        session_context: 세션 컨텍스트 (기존 저장소 정보 포함)
    
    Returns:
        Tuple[owner, repo, reasoning]: 감지된 저장소 정보 및 판단 근거
    """
    
    # 1. 명시적 패턴 먼저 확인 (owner/repo 형식)
    explicit_match = _detect_explicit_repo_pattern(user_message)
    if explicit_match:
        owner, repo = explicit_match
        logger.info(f"[REPO_DETECT] Explicit pattern found: {owner}/{repo}")
        return owner, repo, "명시적 owner/repo 패턴 감지"
    
    # 2. 세션에서 기존 저장소 확인
    existing_repo = _get_existing_repo_from_session(session_context)
    
    # 3. LLM으로 저장소 언급 여부 판단
    detected = await _llm_detect_repository(user_message, existing_repo)
    
    if detected:
        logger.info(f"[REPO_DETECT] LLM detected: {detected.get('type')} - {detected.get('value')}")
        
        if detected["type"] == "existing":
            # 세션의 기존 저장소 사용
            if existing_repo:
                return existing_repo["owner"], existing_repo["repo"], detected.get("reasoning", "기존 저장소 사용")
        
        elif detected["type"] == "project_name":
            # 프로젝트명으로 GitHub 검색
            project_name = detected["value"]
            search_result = await _search_and_match_repository(project_name)
            if search_result:
                return search_result["owner"], search_result["repo"], f"'{project_name}'으로 검색하여 매칭"
        
        elif detected["type"] == "explicit":
            # 명시적 저장소명 (이미 위에서 처리했지만 fallback)
            parts = detected["value"].split("/")
            if len(parts) == 2:
                return parts[0], parts[1], "명시적 저장소명"
    
    # 4. 저장소 언급 없음 - 기존 세션 저장소 사용
    if existing_repo:
        logger.info(f"[REPO_DETECT] Using existing session repo: {existing_repo['owner']}/{existing_repo['repo']}")
        return existing_repo["owner"], existing_repo["repo"], "세션의 기존 저장소 사용 (메시지에 새 저장소 언급 없음)"
    
    logger.info("[REPO_DETECT] No repository detected")
    return None, None, "저장소 정보 없음"


def _detect_explicit_repo_pattern(message: str) -> Optional[Tuple[str, str]]:
    """명시적 owner/repo 패턴 감지"""
    
    # GitHub URL 패턴
    github_url_pattern = r'github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
    match = re.search(github_url_pattern, message)
    if match:
        return match.group(1), match.group(2).replace(".git", "")
    
    # owner/repo 패턴 (URL 없이)
    simple_pattern = r'\b([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)\b'
    matches = re.findall(simple_pattern, message)
    for owner, repo in matches:
        # 일반적인 경로가 아닌지 확인
        if owner.lower() not in ["http", "https", "file", "api", "www"]:
            # 2글자 이상
            if len(owner) >= 2 and len(repo) >= 2:
                return owner, repo
    
    return None


def _get_existing_repo_from_session(session_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """세션에서 기존 저장소 정보 가져오기"""
    if not session_context:
        return None
    
    # unknown은 유효한 저장소가 아님
    def is_valid_repo(owner: str, repo: str) -> bool:
        if not owner or not repo:
            return False
        if owner.lower() == "unknown" or repo.lower() == "unknown":
            return False
        return True
    
    # accumulated_context에서 last_mentioned_repo 확인
    acc_context = session_context.get("accumulated_context") or {}
    last_repo = acc_context.get("last_mentioned_repo") or {}
    
    if last_repo.get("owner") and last_repo.get("repo"):
        if is_valid_repo(last_repo["owner"], last_repo["repo"]):
            return {
                "owner": last_repo["owner"],
                "repo": last_repo["repo"],
            }
    
    # 최상위 owner/repo 확인
    if session_context.get("owner") and session_context.get("repo"):
        if is_valid_repo(session_context["owner"], session_context["repo"]):
            return {
                "owner": session_context["owner"],
                "repo": session_context["repo"],
            }
    
    return None


async def _llm_detect_repository(
    message: str,
    existing_repo: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    LLM을 사용하여 메시지에서 저장소 언급 감지
    
    Returns:
        {
            "type": "explicit" | "project_name" | "existing" | "none",
            "value": "owner/repo" | "project_name" | null,
            "reasoning": "판단 근거"
        }
    """
    from openai import AsyncOpenAI
    
    # 한글 프로젝트명 변환은 LLM에게 위임 (확장성 위해 룰 베이스 제거)
    
    existing_info = ""
    if existing_repo:
        existing_info = f"\n현재 세션에서 {existing_repo['owner']}/{existing_repo['repo']} 저장소를 분석 중입니다."
    
    prompt = f"""사용자 메시지에서 GitHub 오픈소스 프로젝트/저장소 이름을 감지하세요.
{existing_info}

사용자 메시지: "{message}"

다음 JSON 형식으로 응답하세요:
{{
    "type": "explicit" | "project_name" | "existing" | "none",
    "value": "감지된 값 또는 null",
    "reasoning": "판단 근거 (한 줄)"
}}

판단 기준:
- "explicit": owner/repo 형식이 명시됨 (예: "facebook/react", "pallets/flask")
- "project_name": 오픈소스 프로젝트명만 언급됨
  - 예: "flask 분석해줘" → value: "flask"
  - 예: "리액트 진단해줘" → value: "react" (한글→영문 변환)
  - 예: "장고 보안 분석" → value: "django"
  - 반드시 실제 오픈소스 프로젝트명만 해당 (react, flask, django, pytorch, tensorflow 등)
- "existing": 새 프로젝트 언급 없이 현재 저장소에 대한 추가 요청
  - 예: "보안도 확인해줘", "온보딩 가이드 줘"
- "none": 프로젝트/저장소 관련 언급 없음

주의사항:
1. 일반 한국어 단어는 프로젝트명이 아닙니다:
   - "기여하다", "분석", "진단", "추천", "코드", "구조" 등은 명령어/동사
   - "고" 같은 조사/어미도 Go 언어가 아님 (단, "Go 언어", "고랭"은 Go)
2. 한글 프로젝트명은 반드시 영문으로 변환:
   - 장고→django, 리액트→react, 플라스크→flask, 파이토치→pytorch
   - 텐서플로우→tensorflow, 쿠버네티스→kubernetes, 도커→docker
3. 문맥을 파악하여 실제 프로젝트명인지 판단하세요."""

    try:
        client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE)
        
        response = await client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 추출
        json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            logger.info(f"[REPO_DETECT] LLM response: {result}")
            return result
        
    except Exception as e:
        logger.warning(f"[REPO_DETECT] LLM detection failed: {e}")
    
    return None


async def _search_and_match_repository(project_name: str) -> Optional[Dict[str, str]]:
    """프로젝트명으로 GitHub 검색 및 매칭"""
    try:
        results = search_repositories(project_name, max_results=5)
        
        if not results:
            return None
        
        # 정확한 이름 매칭 우선
        for r in results:
            if r["repo"].lower() == project_name.lower():
                logger.info(f"[REPO_DETECT] Exact match: {r['owner']}/{r['repo']}")
                return {"owner": r["owner"], "repo": r["repo"]}
        
        # 정확 매칭 없으면 첫 번째 결과 반환 (별이 가장 많은 것)
        first = results[0]
        logger.info(f"[REPO_DETECT] Best match: {first['owner']}/{first['repo']}")
        return {"owner": first["owner"], "repo": first["repo"]}
        
    except Exception as e:
        logger.warning(f"[REPO_DETECT] Search failed: {e}")
        return None
