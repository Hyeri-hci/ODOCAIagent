from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import base64
import re

from backend.common.github_client import fetch_readme, fetch_repo_overview

@dataclass
class ReadmeContent:
    length_chars: int           # README 전체 문자 수
    heading_count: int          # #, ##, ### 등 헤딩 개수
    code_block_count: int       # ```로 감싸인 코드 블록 개수
    link_count: int             # [text](url) 형식 링크 개수
    image_count: int            # ![alt](url) 형식 이미지 개수
    list_item_count: int        # - , * , + 등 리스트 아이템 개수
    external_doc_count: int     # 외부 문서(예: Wiki) 링크 개수  

# README 디코딩 함수 (REST API 하위 호환용)
def _decode_readme_content(readme_data: Dict[str, Any]) -> str:
    content_base64 = readme_data.get("content", "")
    if not content_base64:
        return ""
    try:
        raw_bytes = base64.b64decode(content_base64)
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""

# README 내용 가져오기 함수 (GraphQL 우선, REST API 폴백)
def fetch_readme_content(owner: str, repo: str) -> Optional[str]:
    """GraphQL로 README 내용 조회 (단독 호출시)."""
    overview = fetch_repo_overview(owner, repo)
    readme_text = overview.get("readme_content")
    if readme_text:
        return readme_text
    
    # GraphQL에서 가져오지 못한 경우 REST API 폴백
    readme_data = fetch_readme(owner, repo)
    if not readme_data:
        return None
    return _decode_readme_content(readme_data)

# README 메트릭 계산 함수
def compute_readme_metrics(readme_text: str) -> ReadmeContent:
    # Heading 개수 (#, ##, ### 등)
    heading_pattern = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
    headings: List[str] = heading_pattern.findall(readme_text)

    # Code block 개수 (```로 감싸인 블록)
    code_block_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    code_markers = code_block_pattern.findall(readme_text)
    code_blocks = len(code_markers) // 2

    # Link 개수 ([text](url) 형식)
    link_pattern = re.compile(r"\[([^\]]+)\]\((http[s]?://[^\)]+)\)")
    links = link_pattern.findall(readme_text)

    # Image 개수 (![alt](url) 형식)
    image_pattern = re.compile(r"!\[([^\]]*)\]\((http[s]?://[^\)]+)\)")
    images = image_pattern.findall(readme_text)

    # List item 개수 (- , * , + 등)
    list_pattern = re.compile(r"^\s*[-\*\+]\s+", re.MULTILINE)
    list_items = list_pattern.findall(readme_text)

    # External document 링크 개수 (예: docs/ 링크, wiki, readthedocs 등)
    external_doc_pattern = re.compile(
        r"\((https?://[^\)]+(readthedocs\.io|github\.io|/docs/|/wiki/)[^\)]*)\)"
    )
    external_docs = external_doc_pattern.findall(readme_text)

    return ReadmeContent(
        length_chars=len(readme_text),
        heading_count=len(headings),
        code_block_count=code_blocks,
        link_count=len(links),
        image_count=len(images),
        list_item_count=len(list_items),
        external_doc_count=len(external_docs)
    )