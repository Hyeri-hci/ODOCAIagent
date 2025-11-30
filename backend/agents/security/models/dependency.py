"""
의존성 정보를 담는 데이터 모델
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Dependency:
    """의존성 정보를 담는 데이터 클래스"""
    name: str
    version: Optional[str] = None
    type: str = "runtime"  # runtime, dev, peer, optional
    source: Optional[str] = None  # npm, pypi, maven, etc.


@dataclass
class DependencyFile:
    """의존성 파일 정보"""
    path: str
    sha: str
    size: int
    url: str
    content: Optional[str] = None
    dependencies: List[Dependency] = field(default_factory=list)
