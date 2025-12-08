"""
JavaScript/Node.js dependency extractors
"""
import json
import re
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class JavaScriptExtractor(BaseExtractor):
    """JavaScript/Node.js 의존성 추출기"""

    def extract(self, content: str, filename: str, is_lockfile: bool = False) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'package.json': self._extract_package_json,
            'package-lock.json': self._extract_package_lock_json,
            'yarn.lock': self._extract_yarn_lock,
            'bower.json': self._extract_bower_json,
        }

        extractor = extractors.get(filename)
        dependencies = []
        if extractor:
            dependencies = self._safe_extract(
                lambda c: extractor(c),
                content,
                f"Error parsing {filename}"
            )

        # lock 파일 표시
        for dep in dependencies:
            dep.is_from_lockfile = is_lockfile

        return dependencies

    @staticmethod
    def _extract_package_json(content: str) -> List[Dependency]:
        """package.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        for name, version in data.get('dependencies', {}).items():
            dependencies.append(Dependency(name, version, 'runtime', 'npm'))

        for name, version in data.get('devDependencies', {}).items():
            dependencies.append(Dependency(name, version, 'dev', 'npm'))

        for name, version in data.get('peerDependencies', {}).items():
            dependencies.append(Dependency(name, version, 'peer', 'npm'))

        for name, version in data.get('optionalDependencies', {}).items():
            dependencies.append(Dependency(name, version, 'optional', 'npm'))

        return dependencies

    @staticmethod
    def _extract_package_lock_json(content: str) -> List[Dependency]:
        """package-lock.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        # v2 format
        if 'packages' in data:
            for pkg_path, pkg_info in data.get('packages', {}).items():
                if pkg_path and pkg_path != "":  # Skip root
                    name = pkg_path.replace('node_modules/', '')
                    version = pkg_info.get('version')
                    dev = pkg_info.get('dev', False)
                    dependencies.append(Dependency(
                        name, version, 'dev' if dev else 'runtime', 'npm'
                    ))

        # v1 format fallback
        elif 'dependencies' in data:
            for name, info in data.get('dependencies', {}).items():
                version = info.get('version')
                dev = info.get('dev', False)
                dependencies.append(Dependency(
                    name, version, 'dev' if dev else 'runtime', 'npm'
                ))

        return dependencies

    @staticmethod
    def _extract_yarn_lock(content: str) -> List[Dependency]:
        """yarn.lock에서 의존성 추출"""
        dependencies = []
        current_package = None

        for line in content.split('\n'):
            line = line.strip()

            # Package declaration
            if line and not line.startswith('#') and not line.startswith(' '):
                if '@' in line and ':' in line:
                    # Extract package name
                    match = re.match(r'^"?([^@\s]+@[^@\s]+)@', line)
                    if match:
                        current_package = match.group(1)

            # Version line
            elif line.startswith('version') and current_package:
                match = re.match(r'\s*version\s+"([^"]+)"', line)
                if match:
                    version = match.group(1)
                    dependencies.append(Dependency(
                        current_package, version, 'runtime', 'npm'
                    ))
                    current_package = None

        return dependencies

    @staticmethod
    def _extract_bower_json(content: str) -> List[Dependency]:
        """bower.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        for name, version in data.get('dependencies', {}).items():
            dependencies.append(Dependency(name, version, 'runtime', 'bower'))

        for name, version in data.get('devDependencies', {}).items():
            dependencies.append(Dependency(name, version, 'dev', 'bower'))

        return dependencies
