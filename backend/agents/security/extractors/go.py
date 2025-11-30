"""
Go dependency extractors
"""
import re
import toml
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class GoExtractor(BaseExtractor):
    """Go 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'go.mod': self._extract_go_mod,
            'go.sum': self._extract_go_sum,
            'Gopkg.toml': self._extract_gopkg_toml,
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
    def _extract_go_mod(content: str) -> List[Dependency]:
        """go.mod에서 의존성 추출"""
        dependencies = []
        in_require_block = False

        for line in content.split('\n'):
            line = line.strip()

            if line.startswith('require'):
                in_require_block = '(' in line
                if not in_require_block:
                    # Single line require
                    match = re.match(r'require\s+([^\s]+)\s+([^\s]+)', line)
                    if match:
                        dependencies.append(Dependency(match.group(1), match.group(2), 'runtime', 'go'))
            elif in_require_block:
                if line == ')':
                    in_require_block = False
                else:
                    match = re.match(r'([^\s]+)\s+([^\s]+)', line)
                    if match and not line.startswith('//'):
                        dependencies.append(Dependency(match.group(1), match.group(2), 'runtime', 'go'))

        return dependencies

    @staticmethod
    def _extract_go_sum(content: str) -> List[Dependency]:
        """go.sum에서 의존성 추출"""
        dependencies = []
        seen = set()

        for line in content.split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    if name not in seen:
                        seen.add(name)
                        dependencies.append(Dependency(name, version, 'runtime', 'go'))

        return dependencies

    @staticmethod
    def _extract_gopkg_toml(content: str) -> List[Dependency]:
        """Gopkg.toml에서 의존성 추출 (dep)"""
        data = toml.loads(content)
        dependencies = []

        for constraint in data.get('constraint', []):
            name = constraint.get('name')
            version = constraint.get('version') or constraint.get('branch')
            if name:
                dependencies.append(Dependency(name, version, 'runtime', 'go'))

        return dependencies
