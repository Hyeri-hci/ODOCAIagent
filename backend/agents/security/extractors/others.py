"""
Other language dependency extractors (PHP, Elixir, Haskell, Julia, Elm, Crystal, Deno, R, etc.)
"""
import re
import json
import toml
import yaml
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class OthersExtractor(BaseExtractor):
    """기타 언어 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        # .cabal 파일 처리
        if filename.endswith('.cabal'):
            return self._safe_extract(
                self._extract_cabal,
                content,
                f"Error parsing {filename}"
            )

        extractors = {
            # PHP
            'composer.json': self._extract_composer_json,
            'composer.lock': self._extract_composer_lock,
            # Elixir
            'mix.exs': self._extract_mix_exs,
            # Haskell
            'stack.yaml': self._extract_stack_yaml,
            # Julia
            'Project.toml': self._extract_project_toml_julia,
            # Elm
            'elm.json': self._extract_elm_json,
            # Crystal
            'shard.yml': self._extract_shard_yml,
            # Deno
            'deno.json': self._extract_deno_json,
            'deno.jsonc': self._extract_deno_json,
            # R
            'DESCRIPTION': self._extract_description_r,
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
    def _extract_composer_json(content: str) -> List[Dependency]:
        """composer.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        for name, version in data.get('require', {}).items():
            if not name.startswith('php') and not name.startswith('ext-'):
                dependencies.append(Dependency(name, version, 'runtime', 'packagist'))

        for name, version in data.get('require-dev', {}).items():
            dependencies.append(Dependency(name, version, 'dev', 'packagist'))

        return dependencies

    @staticmethod
    def _extract_composer_lock(content: str) -> List[Dependency]:
        """composer.lock에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        for package in data.get('packages', []):
            name = package.get('name')
            version = package.get('version')
            if name:
                dependencies.append(Dependency(name, version, 'runtime', 'packagist'))

        for package in data.get('packages-dev', []):
            name = package.get('name')
            version = package.get('version')
            if name:
                dependencies.append(Dependency(name, version, 'dev', 'packagist'))

        return dependencies

    @staticmethod
    def _extract_mix_exs(content: str) -> List[Dependency]:
        """mix.exs에서 의존성 추출"""
        dependencies = []

        # Find deps function
        deps_match = re.search(r'defp?\s+deps\s+do\s*\[(.*?)\]', content, re.DOTALL)
        if deps_match:
            deps_content = deps_match.group(1)

            # {:dep_name, "~> version"}
            pattern = r'\{:([^,\}]+)\s*,\s*"([^"]+)"'
            for match in re.finditer(pattern, deps_content):
                name = match.group(1)
                version = match.group(2)
                dependencies.append(Dependency(name, version, 'runtime', 'hex'))

        return dependencies

    @staticmethod
    def _extract_cabal(content: str) -> List[Dependency]:
        """*.cabal에서 의존성 추출"""
        dependencies = []

        # build-depends: package >= version
        pattern = r'build-depends:\s*([^\n]+(?:\n\s+[^\n]+)*)'
        for match in re.finditer(pattern, content, re.IGNORECASE):
            deps_str = match.group(1)

            # Parse individual dependencies
            dep_pattern = r'([a-zA-Z0-9\-]+)(?:\s*([><=]+)\s*([0-9\.]+))?'
            for dep_match in re.finditer(dep_pattern, deps_str):
                name = dep_match.group(1)
                if name and name not in ['base', 'and', 'or']:  # Skip keywords
                    version = None
                    if dep_match.group(2) and dep_match.group(3):
                        version = f"{dep_match.group(2)}{dep_match.group(3)}"
                    dependencies.append(Dependency(name, version, 'runtime', 'hackage'))

        return dependencies

    @staticmethod
    def _extract_stack_yaml(content: str) -> List[Dependency]:
        """stack.yaml에서 의존성 추출"""
        data = yaml.safe_load(content)
        dependencies = []

        for dep in data.get('extra-deps', []):
            if isinstance(dep, str):
                # package-version format
                match = re.match(r'([^-]+)-([0-9\.]+)', dep)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    dependencies.append(Dependency(name, version, 'runtime', 'hackage'))
                else:
                    dependencies.append(Dependency(dep, None, 'runtime', 'hackage'))

        return dependencies

    @staticmethod
    def _extract_project_toml_julia(content: str) -> List[Dependency]:
        """Julia Project.toml에서 의존성 추출"""
        data = toml.loads(content)
        dependencies = []

        for name, uuid in data.get('deps', {}).items():
            # Julia uses UUIDs, version info is in Manifest.toml
            dependencies.append(Dependency(name, None, 'runtime', 'julia'))

        return dependencies

    @staticmethod
    def _extract_elm_json(content: str) -> List[Dependency]:
        """elm.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        # Direct dependencies
        for name, version in data.get('dependencies', {}).get('direct', {}).items():
            dependencies.append(Dependency(name, version, 'runtime', 'elm'))

        # Indirect dependencies
        for name, version in data.get('dependencies', {}).get('indirect', {}).items():
            dependencies.append(Dependency(name, version, 'indirect', 'elm'))

        # Test dependencies
        for name, version in data.get('test-dependencies', {}).get('direct', {}).items():
            dependencies.append(Dependency(name, version, 'dev', 'elm'))

        return dependencies

    @staticmethod
    def _extract_shard_yml(content: str) -> List[Dependency]:
        """shard.yml에서 의존성 추출"""
        data = yaml.safe_load(content)
        dependencies = []

        for name, info in data.get('dependencies', {}).items():
            if isinstance(info, dict):
                version = info.get('version')
                dependencies.append(Dependency(name, version, 'runtime', 'shards'))

        for name, info in data.get('development_dependencies', {}).items():
            if isinstance(info, dict):
                version = info.get('version')
                dependencies.append(Dependency(name, version, 'dev', 'shards'))

        return dependencies

    @staticmethod
    def _extract_deno_json(content: str) -> List[Dependency]:
        """deno.json에서 의존성 추출"""
        data = json.loads(content)
        dependencies = []

        # Import map
        for name, url in data.get('imports', {}).items():
            # Extract version from URL if present
            version = None
            if '@' in url:
                version_match = re.search(r'@([0-9\.]+)', url)
                if version_match:
                    version = version_match.group(1)

            dependencies.append(Dependency(name, version, 'runtime', 'deno'))

        return dependencies

    @staticmethod
    def _extract_description_r(content: str) -> List[Dependency]:
        """DESCRIPTION (R package) 파일에서 의존성 추출"""
        dependencies = []

        # Depends, Imports, Suggests 섹션 처리
        sections = ['Depends', 'Imports', 'Suggests']
        for section in sections:
            pattern = rf'{section}:\s*([^\n]+(?:\n\s+[^\n]+)*)'
            match = re.search(pattern, content)
            if match:
                deps_str = match.group(1)
                dep_type = 'dev' if section == 'Suggests' else 'runtime'

                # Parse package names and versions
                for dep_match in re.finditer(r'([a-zA-Z0-9\.]+)(?:\s*\(([^)]+)\))?', deps_str):
                    name = dep_match.group(1)
                    if name not in ['R', 'and']:  # Skip R itself and connector words
                        version = dep_match.group(2) if dep_match.group(2) else None
                        dependencies.append(Dependency(name, version, dep_type, 'cran'))

        return dependencies
