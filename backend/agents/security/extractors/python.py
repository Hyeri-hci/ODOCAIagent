"""
Python dependency extractors
"""
import re
import toml
import yaml
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class PythonExtractor(BaseExtractor):
    """Python 의존성 추출기"""

    def extract(self, content: str, filename: str) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        # requirements 계열 파일들
        if 'requirements' in filename and filename.endswith('.txt'):
            return self._safe_extract(
                self._extract_requirements_txt,
                content,
                f"Error parsing {filename}"
            )
        elif filename == 'requirements.in':
            return self._safe_extract(
                self._extract_requirements_txt,
                content,
                f"Error parsing {filename}"
            )

        extractors = {
            'Pipfile': self._extract_pipfile,
            'pyproject.toml': self._extract_pyproject_toml,
            'setup.py': self._extract_setup_py,
            'poetry.lock': self._extract_poetry_lock,
            'conda.yaml': self._extract_conda_yaml,
            'conda.yml': self._extract_conda_yaml,
            'environment.yml': self._extract_conda_yaml,
            'environment.yaml': self._extract_conda_yaml,
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
    def _extract_requirements_txt(content: str) -> List[Dependency]:
        """requirements.txt에서 의존성 추출"""
        dependencies = []

        for line in content.split('\n'):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Skip options
            if line.startswith('-'):
                continue

            # Extract package and version
            match = re.match(r'^([a-zA-Z0-9\-_\.\[\]]+)\s*([><=!~]+.*)?$', line)
            if match:
                name = match.group(1)
                # Remove extras like package[extra]
                name = re.sub(r'\[.*\]', '', name)
                version = match.group(2) if match.group(2) else None
                dependencies.append(Dependency(name, version, 'runtime', 'pypi'))

        return dependencies

    @staticmethod
    def _extract_pipfile(content: str) -> List[Dependency]:
        """Pipfile에서 의존성 추출"""
        data = toml.loads(content)
        dependencies = []

        for name, version_info in data.get('packages', {}).items():
            if isinstance(version_info, str):
                version = version_info
            elif isinstance(version_info, dict):
                version = version_info.get('version', '*')
            else:
                version = '*'
            dependencies.append(Dependency(name, version, 'runtime', 'pypi'))

        for name, version_info in data.get('dev-packages', {}).items():
            if isinstance(version_info, str):
                version = version_info
            elif isinstance(version_info, dict):
                version = version_info.get('version', '*')
            else:
                version = '*'
            dependencies.append(Dependency(name, version, 'dev', 'pypi'))

        return dependencies

    @staticmethod
    def _extract_pyproject_toml(content: str) -> List[Dependency]:
        """pyproject.toml에서 의존성 추출"""
        data = toml.loads(content)
        dependencies = []

        # Poetry style
        if 'tool' in data and 'poetry' in data['tool']:
            poetry = data['tool']['poetry']
            for name, version in poetry.get('dependencies', {}).items():
                if name != 'python':
                    if isinstance(version, dict):
                        version = version.get('version', '*')
                    dependencies.append(Dependency(name, version, 'runtime', 'pypi'))

            for name, version in poetry.get('dev-dependencies', {}).items():
                if isinstance(version, dict):
                    version = version.get('version', '*')
                dependencies.append(Dependency(name, version, 'dev', 'pypi'))

        # PEP 621 style
        if 'project' in data:
            project = data['project']
            for dep in project.get('dependencies', []):
                match = re.match(r'^([a-zA-Z0-9\-_\.]+)\s*(.*)$', dep)
                if match:
                    name = match.group(1)
                    version = match.group(2) if match.group(2) else None
                    dependencies.append(Dependency(name, version, 'runtime', 'pypi'))

            for group, deps in project.get('optional-dependencies', {}).items():
                for dep in deps:
                    match = re.match(r'^([a-zA-Z0-9\-_\.]+)\s*(.*)$', dep)
                    if match:
                        name = match.group(1)
                        version = match.group(2) if match.group(2) else None
                        dependencies.append(Dependency(name, version, 'optional', 'pypi'))

        return dependencies

    @staticmethod
    def _extract_setup_py(content: str) -> List[Dependency]:
        """setup.py에서 의존성 추출"""
        dependencies = []

        # Find install_requires
        install_match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if install_match:
            requires = install_match.group(1)
            for line in requires.split(','):
                line = line.strip().strip('"\'')
                if line:
                    match = re.match(r'^([a-zA-Z0-9\-_\.]+)\s*(.*)$', line)
                    if match:
                        name = match.group(1)
                        version = match.group(2) if match.group(2) else None
                        dependencies.append(Dependency(name, version, 'runtime', 'pypi'))

        # Find extras_require
        extras_match = re.search(r'extras_require\s*=\s*\{(.*?)\}', content, re.DOTALL)
        if extras_match:
            extras = extras_match.group(1)
            # Simple parsing - might need improvement for complex cases
            for match in re.finditer(r'"([^"]+)"\s*:\s*\[(.*?)\]', extras, re.DOTALL):
                extra_name = match.group(1)
                deps = match.group(2)
                for dep in deps.split(','):
                    dep = dep.strip().strip('"\'')
                    if dep:
                        dep_match = re.match(r'^([a-zA-Z0-9\-_\.]+)\s*(.*)$', dep)
                        if dep_match:
                            name = dep_match.group(1)
                            version = dep_match.group(2) if dep_match.group(2) else None
                            dependencies.append(Dependency(name, version, 'optional', 'pypi'))

        return dependencies

    @staticmethod
    def _extract_poetry_lock(content: str) -> List[Dependency]:
        """poetry.lock에서 의존성 추출"""
        data = toml.loads(content)
        dependencies = []

        for package in data.get('package', []):
            name = package.get('name')
            version = package.get('version')
            category = package.get('category', 'main')
            if name:
                dep_type = 'dev' if category == 'dev' else 'runtime'
                dependencies.append(Dependency(name, version, dep_type, 'pypi'))

        return dependencies

    @staticmethod
    def _extract_conda_yaml(content: str) -> List[Dependency]:
        """conda.yaml/environment.yml에서 의존성 추출"""
        data = yaml.safe_load(content)
        dependencies = []

        for dep in data.get('dependencies', []):
            if isinstance(dep, str):
                # conda package
                match = re.match(r'^([^=<>]+)\s*([=<>].*)$', dep)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                else:
                    name = dep
                    version = None
                dependencies.append(Dependency(name, version, 'runtime', 'conda'))
            elif isinstance(dep, dict) and 'pip' in dep:
                # pip packages
                for pip_dep in dep['pip']:
                    match = re.match(r'^([^=<>]+)\s*([=<>].*)$', pip_dep)
                    if match:
                        name = match.group(1)
                        version = match.group(2)
                    else:
                        name = pip_dep
                        version = None
                    dependencies.append(Dependency(name, version, 'runtime', 'pypi'))

        return dependencies
