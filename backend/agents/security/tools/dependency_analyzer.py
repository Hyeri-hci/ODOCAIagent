"""
의존성 분석 툴
AI 에이전트가 사용할 수 있는 독립적인 함수들
"""
from typing import Dict, Any, List, Optional
from dataclasses import asdict
import logging

from ..github import GitHubClient, RepositoryAnalyzer
from ..models import Dependency, DependencyFile

logger = logging.getLogger(__name__)


def analyze_repository_dependencies(
    owner: str,
    repo: str,
    max_workers: int = 10,
    github_token: Optional[str] = None,
    github_base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    GitHub 레포지토리의 의존성을 분석하는 툴

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        max_workers: 병렬 처리 워커 수 (기본값: 10으로 증가)
        github_token: GitHub Personal Access Token (선택)
        github_base_url: GitHub API 기본 URL (선택)

    Returns:
        Dict[str, Any]: 의존성 분석 결과
            - owner: 레포지토리 소유자
            - repo: 레포지토리 이름
            - total_files: 분석된 의존성 파일 수
            - total_dependencies: 전체 고유 의존성 수
            - files: 파일별 의존성 목록
            - all_dependencies: 모든 고유 의존성 목록
            - summary: 요약 통계

    Example:
        >>> result = analyze_repository_dependencies("facebook", "react")
        >>> print(f"Total dependencies: {result['total_dependencies']}")
    """
    try:
        logger.info(f"Starting dependency analysis for {owner}/{repo}")

        # GitHub 클라이언트 및 분석기 초기화
        github_client = GitHubClient(token=github_token, base_url=github_base_url)
        analyzer = RepositoryAnalyzer(github_client=github_client)

        # 레포지토리 분석 실행
        result = analyzer.analyze_repository(owner, repo, max_workers)

        logger.info(f"Analysis completed: {result['total_dependencies']} dependencies found")
        return result

    except Exception as e:
        logger.error(f"Error analyzing repository {owner}/{repo}: {e}")
        return {
            'owner': owner,
            'repo': repo,
            'error': str(e),
            'total_files': 0,
            'total_dependencies': 0,
            'files': [],
            'all_dependencies': [],
            'summary': {}
        }


def get_dependencies_by_source(
    analysis_result: Dict[str, Any],
    source: str
) -> List[Dict[str, Any]]:
    """
    특정 소스(npm, pypi 등)의 의존성만 필터링

    Args:
        analysis_result: analyze_repository_dependencies의 결과
        source: 필터링할 소스 (예: 'npm', 'pypi', 'maven')

    Returns:
        List[Dict[str, Any]]: 필터링된 의존성 목록

    Example:
        >>> result = analyze_repository_dependencies("facebook", "react")
        >>> npm_deps = get_dependencies_by_source(result, "npm")
    """
    all_deps = analysis_result.get('all_dependencies', [])
    return [dep for dep in all_deps if dep.get('source') == source]


def get_dependencies_by_type(
    analysis_result: Dict[str, Any],
    dep_type: str
) -> List[Dict[str, Any]]:
    """
    특정 타입(runtime, dev 등)의 의존성만 필터링

    Args:
        analysis_result: analyze_repository_dependencies의 결과
        dep_type: 필터링할 타입 (예: 'runtime', 'dev', 'peer')

    Returns:
        List[Dict[str, Any]]: 필터링된 의존성 목록

    Example:
        >>> result = analyze_repository_dependencies("facebook", "react")
        >>> runtime_deps = get_dependencies_by_type(result, "runtime")
    """
    all_deps = analysis_result.get('all_dependencies', [])
    return [dep for dep in all_deps if dep.get('type') == dep_type]


def get_outdated_dependencies(
    analysis_result: Dict[str, Any],
    version_pattern: str = "*"
) -> List[Dict[str, Any]]:
    """
    버전이 명시되지 않았거나 특정 패턴과 일치하는 의존성 찾기

    Args:
        analysis_result: analyze_repository_dependencies의 결과
        version_pattern: 찾을 버전 패턴 (기본값: "*" - 버전 미명시)

    Returns:
        List[Dict[str, Any]]: 필터링된 의존성 목록

    Example:
        >>> result = analyze_repository_dependencies("facebook", "react")
        >>> unversioned = get_outdated_dependencies(result)
    """
    all_deps = analysis_result.get('all_dependencies', [])

    if version_pattern == "*":
        # 버전이 없거나 "*"인 경우
        return [
            dep for dep in all_deps
            if not dep.get('version') or dep.get('version') == '*'
        ]
    else:
        # 특정 패턴과 일치하는 경우
        return [
            dep for dep in all_deps
            if dep.get('version') and version_pattern in dep.get('version', '')
        ]


def count_dependencies_by_language(
    analysis_result: Dict[str, Any]
) -> Dict[str, int]:
    """
    언어/패키지 매니저별 의존성 개수 집계

    Args:
        analysis_result: analyze_repository_dependencies의 결과

    Returns:
        Dict[str, int]: 소스별 의존성 개수

    Example:
        >>> result = analyze_repository_dependencies("facebook", "react")
        >>> counts = count_dependencies_by_language(result)
        >>> print(counts)  # {'npm': 150, 'pypi': 20, ...}
    """
    return analysis_result.get('summary', {}).get('by_source', {})


def summarize_dependency_analysis(
    analysis_result: Dict[str, Any]
) -> str:
    """
    의존성 분석 결과를 자연어로 요약

    Args:
        analysis_result: analyze_repository_dependencies의 결과

    Returns:
        str: 자연어 요약 텍스트

    Example:
        >>> result = analyze_repository_dependencies("facebook", "react")
        >>> summary = summarize_dependency_analysis(result)
        >>> print(summary)
    """
    owner = analysis_result.get('owner')
    repo = analysis_result.get('repo')
    total_deps = analysis_result.get('total_dependencies', 0)
    total_files = analysis_result.get('total_files', 0)
    summary = analysis_result.get('summary', {})

    parts = []
    parts.append(f"Repository: {owner}/{repo}")
    parts.append(f"Total dependency files analyzed: {total_files}")
    parts.append(f"Total unique dependencies: {total_deps}")

    runtime_deps = summary.get('runtime_dependencies', 0)
    dev_deps = summary.get('dev_dependencies', 0)
    parts.append(f"Runtime dependencies: {runtime_deps}")
    parts.append(f"Development dependencies: {dev_deps}")

    by_source = summary.get('by_source', {})
    if by_source:
        parts.append("\nDependencies by package manager:")
        for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
            parts.append(f"  - {source}: {count}")

    # 에러가 있는 경우
    if 'error' in analysis_result:
        parts.append(f"\nError: {analysis_result['error']}")

    return "\n".join(parts)


def find_dependency_files(
    owner: str,
    repo: str,
    github_token: Optional[str] = None,
    github_base_url: Optional[str] = None
) -> List[str]:
    """
    레포지토리에서 의존성 파일 경로만 찾기 (분석 없이)

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        github_token: GitHub Personal Access Token (선택)
        github_base_url: GitHub API 기본 URL (선택)

    Returns:
        List[str]: 의존성 파일 경로 목록

    Example:
        >>> files = find_dependency_files("facebook", "react")
        >>> print(files)  # ['package.json', 'yarn.lock', ...]
    """
    try:
        github_client = GitHubClient(token=github_token, base_url=github_base_url)
        analyzer = RepositoryAnalyzer(github_client=github_client)

        dependency_files = analyzer.get_dependency_files(owner, repo)
        return [f['path'] for f in dependency_files]

    except Exception as e:
        logger.error(f"Error finding dependency files for {owner}/{repo}: {e}")
        return []
