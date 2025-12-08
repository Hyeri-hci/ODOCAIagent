"""
GitHub 레포지토리 의존성 분석기
"""
import fnmatch
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models import DependencyFile, Dependency
from ..config import DEPENDENCY_FILES, LOCK_FILES
from ..extractors import DependencyExtractor
from .client import GitHubClient


class RepositoryAnalyzer:
    """GitHub 레포지토리의 의존성을 분석하는 클래스"""

    def __init__(self, github_client: GitHubClient = None):
        """
        레포지토리 분석기 초기화

        Args:
            github_client: GitHub API 클라이언트 (없으면 새로 생성)
        """
        self.client = github_client or GitHubClient()
        self.extractor = DependencyExtractor()
        self.dependency_files = DEPENDENCY_FILES

    def is_dependency_file(self, path: str) -> bool:
        """
        파일이 의존성 파일인지 확인

        Args:
            path: 파일 경로

        Returns:
            bool: 의존성 파일이면 True
        """
        filename = path.split('/')[-1]

        for pattern in self.dependency_files:
            if '*' in pattern:
                if fnmatch.fnmatch(filename, pattern):
                    return True
                if fnmatch.fnmatch(path, pattern):
                    return True
            else:
                if filename == pattern:
                    return True
        return False

    def is_lockfile(self, path: str) -> bool:
        """
        파일이 lock 파일인지 확인

        Args:
            path: 파일 경로

        Returns:
            bool: lock 파일이면 True
        """
        filename = path.split('/')[-1]

        for lock_pattern in LOCK_FILES:
            if '*' in lock_pattern:
                if fnmatch.fnmatch(filename, lock_pattern):
                    return True
                if fnmatch.fnmatch(path, lock_pattern):
                    return True
            else:
                if filename == lock_pattern:
                    return True
        return False

    def get_dependency_files(self, owner: str, repo: str) -> List[Dict]:
        """
        레포지토리에서 의존성 파일 목록 가져오기

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름

        Returns:
            List[Dict]: 의존성 파일 정보 목록
        """
        all_files = self.client.get_repository_tree(owner, repo)
        dependency_files = [
            file_info for file_info in all_files
            if self.is_dependency_file(file_info.get('path', ''))
        ]
        return dependency_files

    def fetch_and_analyze_file(self, owner: str, repo: str, file_info: Dict) -> DependencyFile:
        """
        파일을 가져와서 의존성 분석

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름
            file_info: 파일 정보

        Returns:
            DependencyFile: 분석된 의존성 파일
        """
        dep_file = DependencyFile(
            path=file_info['path'],
            sha=file_info['sha'],
            size=file_info['size'],
            url=file_info['url']
        )

        # 파일 내용 가져오기
        content = self.client.get_file_content_with_retry(owner, repo, file_info['path'])
        if content:
            dep_file.content = content

            # 의존성 추출
            filename = file_info['path'].split('/')[-1]
            is_lock = self.is_lockfile(file_info['path'])
            dep_file.dependencies = self.extractor.extract(content, filename, is_lock)

        return dep_file

    def analyze_repository(self, owner: str, repo: str, max_workers: int = 5) -> Dict[str, Any]:
        """
        레포지토리의 모든 의존성 파일을 분석

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름
            max_workers: 병렬 처리 워커 수

        Returns:
            Dict[str, Any]: 분석 결과
        """
        print(f"Analyzing repository: {owner}/{repo}")

        # 1. 의존성 파일 목록 가져오기
        print("Fetching dependency files list...")
        dependency_files = self.get_dependency_files(owner, repo)
        print(f"Found {len(dependency_files)} dependency files")

        if not dependency_files:
            return {
                'owner': owner,
                'repo': repo,
                'total_files': 0,
                'files': [],
                'all_dependencies': [],
                'summary': {}
            }

        # 2. 병렬로 파일 내용 가져오고 의존성 추출
        print("Fetching file contents and extracting dependencies...")
        analyzed_files = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.fetch_and_analyze_file, owner, repo, file_info): file_info
                for file_info in dependency_files
            }

            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    dep_file = future.result()
                    analyzed_files.append(dep_file)

                    if dep_file.dependencies:
                        print(f"  ✓ {dep_file.path}: {len(dep_file.dependencies)} dependencies")
                    else:
                        print(f"  ○ {dep_file.path}: No dependencies extracted")

                except Exception as e:
                    print(f"  ✗ {file_info['path']}: Error - {e}")

        # 3. 결과 정리
        return self._build_result(owner, repo, analyzed_files)

    def _build_result(self, owner: str, repo: str, analyzed_files: List[DependencyFile]) -> Dict[str, Any]:
        """
        분석 결과 구성

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름
            analyzed_files: 분석된 파일 목록

        Returns:
            Dict[str, Any]: 분석 결과
        """
        all_dependencies = []
        source_stats = {}
        lock_file_count = 0

        for file in analyzed_files:
            # Lock 파일 카운트
            if self.is_lockfile(file.path):
                lock_file_count += 1

            if file.dependencies:
                all_dependencies.extend(file.dependencies)

                for dep in file.dependencies:
                    if dep.source:
                        source_stats[dep.source] = source_stats.get(dep.source, 0) + 1

        # 중복 제거 (lock 파일의 의존성을 우선)
        unique_dependencies = {}
        for dep in all_dependencies:
            key = f"{dep.source}:{dep.name}"
            if key not in unique_dependencies:
                unique_dependencies[key] = dep
            else:
                existing = unique_dependencies[key]
                # Lock 파일의 의존성을 우선적으로 사용
                if dep.is_from_lockfile and not existing.is_from_lockfile:
                    unique_dependencies[key] = dep
                # 둘 다 lock 파일이 아닌 경우, 버전이 있는 것을 우선
                elif not dep.is_from_lockfile and not existing.is_from_lockfile:
                    if dep.version and (not existing.version or existing.version == '*'):
                        unique_dependencies[key] = dep

        # Lock 파일에서 추출된 의존성 개수
        lockfile_dependencies_count = len([d for d in unique_dependencies.values() if d.is_from_lockfile])

        # 결과 구성
        result = {
            'owner': owner,
            'repo': repo,
            'total_files': len(analyzed_files),
            'lock_files_count': lock_file_count,
            'total_dependencies': len(unique_dependencies),
            'files': [
                {
                    'path': f.path,
                    'size': f.size,
                    'is_lockfile': self.is_lockfile(f.path),
                    'dependencies_count': len(f.dependencies) if f.dependencies else 0,
                    'dependencies': [
                        {
                            'name': d.name,
                            'version': d.version,
                            'type': d.type,
                            'source': d.source,
                            'is_from_lockfile': d.is_from_lockfile
                        } for d in (f.dependencies or [])
                    ]
                } for f in analyzed_files
            ],
            'all_dependencies': [
                {
                    'name': d.name,
                    'version': d.version,
                    'type': d.type,
                    'source': d.source,
                    'is_from_lockfile': d.is_from_lockfile
                } for d in unique_dependencies.values()
            ],
            'summary': {
                'by_source': source_stats,
                'runtime_dependencies': len([d for d in unique_dependencies.values() if d.type == 'runtime']),
                'dev_dependencies': len([d for d in unique_dependencies.values() if d.type == 'dev']),
                'total_unique': len(unique_dependencies),
                'lockfile_dependencies': lockfile_dependencies_count,
                'non_lockfile_dependencies': len(unique_dependencies) - lockfile_dependencies_count
            }
        }

        return result
