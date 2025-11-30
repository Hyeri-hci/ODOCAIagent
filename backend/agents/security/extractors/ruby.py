"""
Ruby dependency extractors
"""
import re
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class RubyExtractor(BaseExtractor):
    """Ruby 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'Gemfile': self._extract_gemfile,
            'Gemfile.lock': self._extract_gemfile_lock,
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
    def _extract_gemfile(content: str) -> List[Dependency]:
        """Gemfile에서 의존성 추출"""
        dependencies = []

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # gem 'name', 'version', group: :development
            match = re.match(r"gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", line)
            if match:
                name = match.group(1)
                version = match.group(2) if match.group(2) else None

                # Check for group
                dep_type = 'runtime'
                if 'group:' in line and ('development' in line or 'test' in line):
                    dep_type = 'dev'

                dependencies.append(Dependency(name, version, dep_type, 'rubygems'))

        return dependencies

    @staticmethod
    def _extract_gemfile_lock(content: str) -> List[Dependency]:
        """Gemfile.lock에서 의존성 추출"""
        dependencies = []
        in_specs = False

        for line in content.split('\n'):
            if 'specs:' in line:
                in_specs = True
                continue
            elif line and not line.startswith(' ') and not line.startswith('\t'):
                in_specs = False

            if in_specs:
                match = re.match(r'\s+([a-zA-Z0-9\-_]+)\s+\(([^)]+)\)', line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    dependencies.append(Dependency(name, version, 'runtime', 'rubygems'))

        return dependencies
