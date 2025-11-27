from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re

@dataclass
class ReadmeSection:
    title: str
    level: int
    content: str

SECTION_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)', re.MULTILINE)

def extract_sections(markdown_text: str) -> List[ReadmeSection]:
    """
      GitHub Markdown 형식의 README에서 섹션 리스트 추출
      - h1~h6 헤딩 인식
      - heading 없는 경우 전체를 level=1, title="" 로 간주
    """

    text = markdown_text or ""
    matches = list(SECTION_HEADING_RE.finditer(text))

    if not matches:
        # heading 없는 경우 전체를 하나의 섹션으로 간주
        return [ReadmeSection(title="", level=1, content=text.strip())]
    
    sections: List[ReadmeSection] = []
    for i, match in enumerate(matches):
        hashes, title = match.groups(1), match.group(2).strip()
        level = len(hashes)
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start_pos:end_pos].strip()
        sections.append(ReadmeSection(title=title, level=level, content=content))
    return sections