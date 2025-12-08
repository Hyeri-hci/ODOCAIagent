"""
Java/JVM dependency extractors (Java, Scala, Clojure)
"""
import re
import xml.etree.ElementTree as ET
from typing import List
from .base import BaseExtractor
from ..models import Dependency


class JVMExtractor(BaseExtractor):
    """JVM 언어 의존성 추출기"""

    def extract(self, content: str, filename: str, is_lockfile: bool = False) -> List[Dependency]:
        """파일명에 따라 적절한 추출 메서드 호출"""
        extractors = {
            'pom.xml': self._extract_pom_xml,
            'build.gradle': self._extract_build_gradle,
            'build.gradle.kts': self._extract_build_gradle,
            'build.sbt': self._extract_build_sbt,
            'project.clj': self._extract_project_clj,
            'deps.edn': self._extract_deps_edn,
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
    def _extract_pom_xml(content: str) -> List[Dependency]:
        """pom.xml에서 의존성 추출"""
        dependencies = []

        root = ET.fromstring(content)
        ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}

        # Find all dependencies
        for dep in root.findall('.//maven:dependency', ns) or root.findall('.//dependency'):
            group_id = dep.findtext('maven:groupId', default='', namespaces=ns) or dep.findtext('groupId', '')
            artifact_id = dep.findtext('maven:artifactId', default='', namespaces=ns) or dep.findtext('artifactId', '')
            version = dep.findtext('maven:version', default=None, namespaces=ns) or dep.findtext('version')
            scope = dep.findtext('maven:scope', default='compile', namespaces=ns) or dep.findtext('scope', 'compile')

            if group_id and artifact_id:
                name = f"{group_id}:{artifact_id}"
                dep_type = 'dev' if scope in ['test', 'provided'] else 'runtime'
                dependencies.append(Dependency(name, version, dep_type, 'maven'))

        return dependencies

    @staticmethod
    def _extract_build_gradle(content: str) -> List[Dependency]:
        """build.gradle에서 의존성 추출"""
        dependencies = []

        # Various dependency configurations
        configs = [
            ('implementation', 'runtime'),
            ('compile', 'runtime'),
            ('api', 'runtime'),
            ('runtimeOnly', 'runtime'),
            ('testImplementation', 'dev'),
            ('testCompile', 'dev'),
            ('androidTestImplementation', 'dev'),
            ('debugImplementation', 'dev'),
            ('releaseImplementation', 'runtime')
        ]

        for config, dep_type in configs:
            # String notation: implementation 'group:name:version'
            pattern = rf"{config}\s+['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]"
            for match in re.finditer(pattern, content):
                name = f"{match.group(1)}:{match.group(2)}"
                version = match.group(3)
                dependencies.append(Dependency(name, version, dep_type, 'gradle'))

            # Map notation: implementation group: 'group', name: 'name', version: 'version'
            pattern = rf"{config}\s+group:\s*['\"]([^'\"]+)['\"]\s*,\s*name:\s*['\"]([^'\"]+)['\"]\s*(?:,\s*version:\s*['\"]([^'\"]+)['\"])?"
            for match in re.finditer(pattern, content):
                name = f"{match.group(1)}:{match.group(2)}"
                version = match.group(3) if match.group(3) else None
                dependencies.append(Dependency(name, version, dep_type, 'gradle'))

        return dependencies

    @staticmethod
    def _extract_build_sbt(content: str) -> List[Dependency]:
        """build.sbt에서 의존성 추출"""
        dependencies = []

        # libraryDependencies += "group" %% "artifact" % "version"
        pattern = r'libraryDependencies\s*\+\+?=\s*"([^"]+)"\s*%%?\s*"([^"]+)"\s*%\s*"([^"]+)"'
        for match in re.finditer(pattern, content):
            group = match.group(1)
            artifact = match.group(2)
            version = match.group(3)
            name = f"{group}:{artifact}"
            dependencies.append(Dependency(name, version, 'runtime', 'maven'))

        # Seq notation
        seq_pattern = r'libraryDependencies\s*\+\+?=\s*Seq\((.*?)\)'
        seq_match = re.search(seq_pattern, content, re.DOTALL)
        if seq_match:
            seq_content = seq_match.group(1)
            dep_pattern = r'"([^"]+)"\s*%%?\s*"([^"]+)"\s*%\s*"([^"]+)"'
            for match in re.finditer(dep_pattern, seq_content):
                group = match.group(1)
                artifact = match.group(2)
                version = match.group(3)
                name = f"{group}:{artifact}"
                dependencies.append(Dependency(name, version, 'runtime', 'maven'))

        return dependencies

    @staticmethod
    def _extract_project_clj(content: str) -> List[Dependency]:
        """project.clj에서 의존성 추출"""
        dependencies = []

        # :dependencies [[group/artifact "version"]]
        deps_match = re.search(r':dependencies\s*\[(.*?)\]', content, re.DOTALL)
        if deps_match:
            deps_str = deps_match.group(1)

            # [group/artifact "version"]
            pattern = r'\[([^\s\]]+)\s+"([^"]+)"'
            for match in re.finditer(pattern, deps_str):
                name = match.group(1)
                version = match.group(2)
                dependencies.append(Dependency(name, version, 'runtime', 'clojars'))

        return dependencies

    @staticmethod
    def _extract_deps_edn(content: str) -> List[Dependency]:
        """deps.edn에서 의존성 추출"""
        dependencies = []

        # Simple regex parsing for EDN format
        # {org.clojure/clojure {:mvn/version "1.10.1"}}
        pattern = r'([a-zA-Z0-9\.\-/]+)\s*\{:mvn/version\s+"([^"]+)"'
        for match in re.finditer(pattern, content):
            name = match.group(1)
            version = match.group(2)
            dependencies.append(Dependency(name, version, 'runtime', 'clojars'))

        return dependencies
