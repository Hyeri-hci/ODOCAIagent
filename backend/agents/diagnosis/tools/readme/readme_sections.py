from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import re


@dataclass
class ReadmeSection:
    index: int              # 섹션 순서 인덱스
    heading: Optional[str]  # 섹션 헤딩 텍스트 (없으면 None)
    level: int              # 헤딩 레벨 (1~6), 헤딩이 없으면 0
    content: str            # 섹션 본문 내용


# README 헤딩 패턴
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def split_readme_into_sections(text: str) -> List[ReadmeSection]:
    """
    README 전체를 헤딩 기준으로 섹션 리스트로 분리한다.
    - 헤딩이 하나도 없으면 전체를 하나의 섹션으로 반환
    - 첫 헤딩 이전의 텍스트도 별도 섹션으로 유지
    """
    text = text or ""
    if not text.strip():
        return []

    matches = list(_HEADING_RE.finditer(text))
    sections: List[ReadmeSection] = []

    # 헤딩이 전혀 없는 README
    if not matches:
        sections.append(
            ReadmeSection(
                index=0,
                heading=None,
                level=0,
                content=text.strip(),
            )
        )
        return sections

    idx = 0

    # 첫 헤딩 이전 내용
    first = matches[0]
    if first.start() > 0:
        pre_body = text[: first.start()].strip()
        if pre_body:
            sections.append(
                ReadmeSection(
                    index=idx,
                    heading=None,
                    level=0,
                    content=pre_body,
                )
            )
            idx += 1

    # 각 헤딩과 그 다음 헤딩 사이를 하나의 섹션으로 취급
    for i, m in enumerate(matches):
        hashes = m.group(1)
        heading = (m.group(2) or "").strip()
        level = len(hashes)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        sections.append(
            ReadmeSection(
                index=idx,
                heading=heading,
                level=level,
                content=body,
            )
        )
        idx += 1

    return sections
