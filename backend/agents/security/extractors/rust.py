"""
Rust dependency extractors
"""
import toml
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class RustExtractor(BaseExtractor):
    """Rust 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'Cargo.toml': self._extract_cargo_toml,
            'Cargo.lock': self._extract_cargo_lock,
        }

        extractor = extractors.get(filename)
        if extractor:
            return self._safe_extract(
                lambda c: extractor(c),
                content,
                f"Error parsing {filename}"
            )
        return []

    @staticmethod
    def _extract_cargo_toml(content: str) -> List[Dependency]:
        """Cargo.toml에서 의존성 추출"""
        data = toml.loads(content)
        dependencies = []

        for name, info in data.get('dependencies', {}).items():
            if isinstance(info, str):
                version = info
            elif isinstance(info, dict):
                version = info.get('version', '*')
            else:
                version = None
            dependencies.append(Dependency(name, version, 'runtime', 'crates.io'))

        for name, info in data.get('dev-dependencies', {}).items():
            if isinstance(info, str):
                version = info
            elif isinstance(info, dict):
                version = info.get('version', '*')
            else:
                version = None
            dependencies.append(Dependency(name, version, 'dev', 'crates.io'))

        for name, info in data.get('build-dependencies', {}).items():
            if isinstance(info, str):
                version = info
            elif isinstance(info, dict):
                version = info.get('version', '*')
            else:
                version = None
            dependencies.append(Dependency(name, version, 'build', 'crates.io'))

        return dependencies

    @staticmethod
    def _extract_cargo_lock(content: str) -> List[Dependency]:
        """Cargo.lock에서 의존성 추출"""
        data = toml.loads(content)
        dependencies = []

        for package in data.get('package', []):
            name = package.get('name')
            version = package.get('version')
            if name:
                dependencies.append(Dependency(name, version, 'runtime', 'crates.io'))

        return dependencies
