"""
Mobile dependency extractors (Swift/iOS, Dart/Flutter)
"""
import re
import yaml
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class MobileExtractor(BaseExtractor):
    """모바일 플랫폼 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'Package.swift': self._extract_package_swift,
            'Podfile': self._extract_podfile,
            'Cartfile': self._extract_cartfile,
            'pubspec.yaml': self._extract_pubspec_yaml,
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
    def _extract_package_swift(content: str) -> List[Dependency]:
        """Package.swift에서 의존성 추출"""
        dependencies = []

        # Find .package dependencies
        package_pattern = r'\.package\s*\(\s*(?:url|name):\s*"([^"]+)"(?:\s*,\s*from:\s*"([^"]+)")?'
        for match in re.finditer(package_pattern, content):
            url_or_name = match.group(1)
            version = match.group(2) if match.group(2) else None

            # Extract name from URL if it's a GitHub URL
            if '/' in url_or_name:
                name = url_or_name.split('/')[-1].replace('.git', '')
            else:
                name = url_or_name

            dependencies.append(Dependency(name, version, 'runtime', 'swift-pm'))

        return dependencies

    @staticmethod
    def _extract_podfile(content: str) -> List[Dependency]:
        """Podfile에서 의존성 추출"""
        dependencies = []

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # pod 'Name', '~> version'
            match = re.match(r"pod\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", line)
            if match:
                name = match.group(1)
                version = match.group(2) if match.group(2) else None
                dependencies.append(Dependency(name, version, 'runtime', 'cocoapods'))

        return dependencies

    @staticmethod
    def _extract_cartfile(content: str) -> List[Dependency]:
        """Cartfile에서 의존성 추출"""
        dependencies = []

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # github "owner/repo" ~> version
            match = re.match(r'(github|git|binary)\s+"([^"]+)"(?:\s*~>\s*([^\s]+))?', line)
            if match:
                source_type = match.group(1)
                repo = match.group(2)
                version = match.group(3) if match.group(3) else None

                name = repo.split('/')[-1] if '/' in repo else repo
                dependencies.append(Dependency(name, version, 'runtime', 'carthage'))

        return dependencies

    @staticmethod
    def _extract_pubspec_yaml(content: str) -> List[Dependency]:
        """pubspec.yaml에서 의존성 추출"""
        data = yaml.safe_load(content)
        dependencies = []

        for name, version in data.get('dependencies', {}).items():
            if isinstance(version, str):
                dependencies.append(Dependency(name, version, 'runtime', 'pub'))
            elif isinstance(version, dict):
                version_str = version.get('version')
                dependencies.append(Dependency(name, version_str, 'runtime', 'pub'))

        for name, version in data.get('dev_dependencies', {}).items():
            if isinstance(version, str):
                dependencies.append(Dependency(name, version, 'dev', 'pub'))
            elif isinstance(version, dict):
                version_str = version.get('version')
                dependencies.append(Dependency(name, version_str, 'dev', 'pub'))

        return dependencies
