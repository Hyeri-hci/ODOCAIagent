"""
.NET/C# dependency extractors
"""
import json
import xml.etree.ElementTree as ET
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class DotNetExtractor(BaseExtractor):
    """.NET/C# 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        # .csproj, .fsproj, .vbproj 파일들
        if filename.endswith(('.csproj', '.fsproj', '.vbproj')):
            return self._safe_extract(
                self._extract_csproj,
                content,
                f"Error parsing {filename}"
            )

        extractors = {
            'packages.config': self._extract_packages_config,
            'project.json': self._extract_project_json,
            'paket.dependencies': self._extract_paket_dependencies,
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
    def _extract_packages_config(content: str) -> List[Dependency]:
        """packages.config에서 의존성 추출"""
        dependencies = []

        root = ET.fromstring(content)

        for package in root.findall('.//package'):
            name = package.get('id')
            version = package.get('version')
            if name:
                dependencies.append(Dependency(name, version, 'runtime', 'nuget'))

        return dependencies

    @staticmethod
    def _extract_csproj(content: str) -> List[Dependency]:
        """*.csproj에서 의존성 추출"""
        dependencies = []

        root = ET.fromstring(content)

        # New SDK-style format
        for ref in root.findall('.//PackageReference'):
            name = ref.get('Include')
            version = ref.get('Version')
            if name:
                dependencies.append(Dependency(name, version, 'runtime', 'nuget'))

        # Old format
        for ref in root.findall('.//Reference'):
            include = ref.get('Include', '')
            if ',' in include:
                name = include.split(',')[0]
                dependencies.append(Dependency(name, None, 'runtime', 'nuget'))

        return dependencies

    @staticmethod
    def _extract_project_json(content: str) -> List[Dependency]:
        """project.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        for name, version in data.get('dependencies', {}).items():
            if isinstance(version, str):
                dependencies.append(Dependency(name, version, 'runtime', 'nuget'))
            elif isinstance(version, dict):
                version_str = version.get('version')
                dep_type = 'dev' if version.get('type') == 'build' else 'runtime'
                dependencies.append(Dependency(name, version_str, dep_type, 'nuget'))

        return dependencies

    @staticmethod
    def _extract_paket_dependencies(content: str) -> List[Dependency]:
        """paket.dependencies에서 의존성 추출"""
        dependencies = []

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('#'):
                continue

            if line.startswith('nuget'):
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[1]
                    version = parts[2] if len(parts) > 2 else None
                    dependencies.append(Dependency(name, version, 'runtime', 'nuget'))

        return dependencies
