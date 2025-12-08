"""
Base extractor class for dependency extraction
"""
from abc import ABC, abstractmethod
from typing import List
from ..models import Dependency


class BaseExtractor(ABC):
    """모든 의존성 추출기의 베이스 클래스"""

    @abstractmethod
    def extract(self, content: str, filename: str, is_lockfile: bool = False) -> List[Dependency]:
        """
        파일 내용에서 의존성 추출

        Args:
            content: 파일 내용
            filename: 파일명
            is_lockfile: lock 파일 여부

        Returns:
            List[Dependency]: 추출된 의존성 목록
        """
        pass

    @staticmethod
    def _safe_extract(extract_func, content: str, error_msg: str = None) -> List[Dependency]:
        """
        안전하게 의존성을 추출하는 헬퍼 메서드

        Args:
            extract_func: 실행할 추출 함수
            content: 파일 내용
            error_msg: 에러 메시지 (선택)

        Returns:
            List[Dependency]: 추출된 의존성 목록 (에러 시 빈 리스트)
        """
        try:
            return extract_func(content)
        except Exception as e:
            if error_msg:
                print(f"{error_msg}: {e}")
            return []
