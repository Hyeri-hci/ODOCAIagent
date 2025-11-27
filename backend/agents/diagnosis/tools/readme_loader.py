from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import base64
import re

from backend.common.github_client import fetch_readme

@dataclass
class ReadmeContent:
    length_chars: int
    heading_count: int
    code_block_count: int
    link_count: int
    image_count: int

def _decode_readme_content(readme_data: Dict[str, Any]) -> str:
    """GitHub API readme 응답에서 Base64로 인코딩된 내용 utf-8 문자열로 디코딩"""
    content_base64 = readme_data.get("content", "")
    if not content_base64:
        return ""
    try:
        raw_bytes = base64.b64decode(content_base64)
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""
    
def fetch_readme_content(owner: str, repo: str) -> Optional[str]:
    """README 파일 내용을 전체 반환, 없으면 None 반환"""
    readme_data = fetch_readme(owner, repo)
    if not readme_data:
        return None
    return _decode_readme_content(readme_data)

def compute_reademe_metrics(readme_text: str) -> ReadmeContent:
    """README 텍스트에서 간단한 메트릭 계산"""

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

    return ReadmeContent(
        length_chars=len(readme_text),
        heading_count=len(headings),
        code_block_count=code_blocks,
        link_count=len(links),
        image_count=len(images),
    )