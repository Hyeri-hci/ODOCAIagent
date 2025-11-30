"""
C/C++ dependency extractors
"""
import re
import json
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class CppExtractor(BaseExtractor):
    """C/C++ 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'conanfile.txt': self._extract_conanfile_txt,
            'conanfile.py': self._extract_conanfile_py,
            'vcpkg.json': self._extract_vcpkg_json,
            'CMakeLists.txt': self._extract_cmake_lists,
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
    def _extract_conanfile_txt(content: str) -> List[Dependency]:
        """conanfile.txt에서 의존성 추출"""
        dependencies = []
        in_requires = False

        for line in content.split('\n'):
            line = line.strip()

            if line == '[requires]':
                in_requires = True
                continue
            elif line.startswith('['):
                in_requires = False

            if in_requires and line:
                # package/version@user/channel
                match = re.match(r'([^/]+)/([^@]+)(?:@(.+))?', line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    dependencies.append(Dependency(name, version, 'runtime', 'conan'))

        return dependencies

    @staticmethod
    def _extract_conanfile_py(content: str) -> List[Dependency]:
        """conanfile.py에서 의존성 추출"""
        dependencies = []

        # Find requires attribute or method
        requires_match = re.search(r'requires\s*=\s*[\[\(]([^\]\)]+)[\]\)]', content, re.DOTALL)
        if requires_match:
            requires = requires_match.group(1)
            for line in requires.split(','):
                line = line.strip().strip('"\'')
                if line:
                    match = re.match(r'([^/]+)/([^@]+)(?:@(.+))?', line)
                    if match:
                        name = match.group(1)
                        version = match.group(2)
                        dependencies.append(Dependency(name, version, 'runtime', 'conan'))

        return dependencies

    @staticmethod
    def _extract_vcpkg_json(content: str) -> List[Dependency]:
        """vcpkg.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        for dep in data.get('dependencies', []):
            if isinstance(dep, str):
                dependencies.append(Dependency(dep, None, 'runtime', 'vcpkg'))
            elif isinstance(dep, dict):
                name = dep.get('name')
                version = dep.get('version-string')
                if name:
                    dependencies.append(Dependency(name, version, 'runtime', 'vcpkg'))

        return dependencies

    @staticmethod
    def _extract_cmake_lists(content: str) -> List[Dependency]:
        """CMakeLists.txt에서 의존성 추출 (기본적인 find_package만)"""
        dependencies = []

        # find_package(PackageName VERSION)
        pattern = r'find_package\s*\(\s*([^\s\)]+)(?:\s+([0-9\.]+))?'
        for match in re.finditer(pattern, content, re.IGNORECASE):
            name = match.group(1)
            version = match.group(2) if match.group(2) else None
            dependencies.append(Dependency(name, version, 'runtime', 'cmake'))

        return dependencies
