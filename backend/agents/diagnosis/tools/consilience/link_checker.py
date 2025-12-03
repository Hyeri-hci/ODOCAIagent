"""링크 검증기: 외부 링크 유효성 확인."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import httpx

from backend.agents.diagnosis.config import get_consilience_config


@dataclass
class LinkCheckResult:
    """링크 검증 결과."""
    valid: int = 0
    broken: int = 0
    unchecked: int = 0
    total: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 건너뛸 도메인 (로컬, 예시 등)
SKIP_DOMAINS = {
    "localhost",
    "127.0.0.1",
    "example.com",
    "example.org",
    "your-domain.com",
}

# 건너뛸 패턴
SKIP_PATTERNS = [
    r"^mailto:",
    r"^tel:",
    r"^#",  # 앵커
    r"^\$",  # 변수
    r"\{.*\}",  # 플레이스홀더
]


def _should_skip(url: str) -> bool:
    """검사를 건너뛸 URL인지 확인."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, url):
            return True
    
    # 도메인 체크
    for domain in SKIP_DOMAINS:
        if domain in url:
            return True
    
    return False


@lru_cache(maxsize=500)
def _check_single_link(url: str, timeout: float) -> str:
    """
    단일 링크 확인 (캐시됨).
    
    Returns:
        str: "valid" | "broken" | "unchecked"
    """
    if _should_skip(url):
        return "unchecked"
    
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            # HEAD 요청 먼저 시도
            try:
                response = client.head(url)
                if response.status_code < 400:
                    return "valid"
                elif response.status_code == 405:
                    # HEAD 미지원 → GET 시도
                    pass
                else:
                    return "broken"
            except httpx.HTTPError:
                pass
            
            # GET 요청으로 재시도
            response = client.get(url)
            if response.status_code < 400:
                return "valid"
            else:
                return "broken"
                
    except httpx.TimeoutException:
        return "unchecked"  # 타임아웃은 unchecked
    except httpx.HTTPError:
        return "broken"
    except Exception:
        return "unchecked"


def check_link_refs(
    links: List[str],
    max_checks: int = 20,
) -> LinkCheckResult:
    """
    외부 링크 유효성 확인.
    
    Args:
        links: 확인할 URL 목록
        max_checks: 최대 확인 개수 (성능 제한)
        
    Returns:
        LinkCheckResult: 검증 결과
    """
    if not links:
        return LinkCheckResult()
    
    config = get_consilience_config()
    timeout = config.get("link_timeout_seconds", 1.5)
    
    # 중복 제거 및 필터링
    unique_links = list(dict.fromkeys(links))[:max_checks]
    
    result = LinkCheckResult(total=len(unique_links))
    
    # 병렬 확인 (최대 5개 동시)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_check_single_link, link, timeout): link
            for link in unique_links
        }
        
        for future in futures:
            link = futures[future]
            try:
                status = future.result(timeout=timeout + 1)
            except (FuturesTimeoutError, Exception):
                status = "unchecked"
            
            if status == "valid":
                result.valid += 1
            elif status == "broken":
                result.broken += 1
            else:
                result.unchecked += 1
            
            result.details.append({"url": link, "status": status})
    
    return result


def extract_links_from_readme(readme_content: str) -> List[str]:
    """README에서 외부 링크 추출."""
    # 마크다운 링크 패턴
    md_link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    
    links = []
    for match in md_link_pattern.finditer(readme_content):
        url = match.group(2)
        # http/https로 시작하는 외부 링크만
        if url.startswith(("http://", "https://")):
            # 배지 URL은 제외
            if "badge" not in url and "shields.io" not in url:
                links.append(url)
    
    return links


def clear_cache():
    """캐시 초기화."""
    _check_single_link.cache_clear()
