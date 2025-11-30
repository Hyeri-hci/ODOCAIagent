"""
통합 의존성 추출기
"""
from typing import List
from ..models import Dependency
from .javascript import JavaScriptExtractor
from .python import PythonExtractor
from .ruby import RubyExtractor
from .jvm import JVMExtractor
from .dotnet import DotNetExtractor
from .go import GoExtractor
from .rust import RustExtractor
from .mobile import MobileExtractor
from .cpp import CppExtractor
from .others import OthersExtractor


class DependencyExtractor:
    """모든 언어의 의존성을 추출하는 통합 클래스"""

    def __init__(self):
        self.extractors = [
            JavaScriptExtractor(),
            PythonExtractor(),
            RubyExtractor(),
            JVMExtractor(),
            DotNetExtractor(),
            GoExtractor(),
            RustExtractor(),
            MobileExtractor(),
            CppExtractor(),
            OthersExtractor(),
        ]

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """
        파일 내용과 파일명에 따라 적절한 추출기를 사용하여 의존성 추출

        Args:
            content: 파일 내용
            filename: 파일명

        Returns:
            List[Dependency]: 추출된 의존성 목록
        """
        for extractor in self.extractors:
            dependencies = extractor.extract(content, filename)
            if dependencies:
                return dependencies

        return []


__all__ = ['DependencyExtractor']
