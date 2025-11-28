from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import re

@dataclass
class ReadmeSection:
    index: int              # 섹션 순서 인덱스
    heading: Optional[str]  # 섹션 헤딩 텍스트 (없으면 None)
    level: int             # 헤딩 레벨 (1~6), 헤딩이 없으면 0
    content: str           # 섹션 본문 내용

# Heading과 섹션 분리 함수
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

# README를 섹션 단위로 분리하는 함수
def split_readme_into_sections(text: str) -> List[ReadmeSection]:
    sections: List[ReadmeSection] = []

    matches = list(HEADING_RE.finditer(text))
    if not matches:
        # 헤딩이 없으면 전체를 WHATEVER 섹션으로 처리
        sections.append(ReadmeSection(
            index=0,
            heading=None,
            level=0,
            content=text.strip()
        ))
        return sections
    
    # 첫 섹션: 첫 헤딩 전의 내용
    first = matches[0]
    preamble = text[:first.start()].strip()
    idx = 0
    if preamble:
        sections.append(ReadmeSection(
            index=idx,
            heading=None,
            level=0,
            content=preamble
        ))
        idx += 1
    
    # 헤딩 기준으로 섹션 분리
    for i, m in enumerate(matches):
        hashes = m.group(1)
        heading = m.group(2).strip()
        level = len(hashes)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        sections.append(ReadmeSection(
            index=idx,
            heading=heading,
            level=level,
            content=body
        ))
        idx += 1

    return sections