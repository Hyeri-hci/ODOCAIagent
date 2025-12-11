"""Security analysis service - 레포지토리 의존성 분석."""
import json
from typing import Dict, Any, Optional

from .github import GitHubClient, RepositoryAnalyzer


class SecurityAnalysisService:
    """보안 분석 서비스."""

    def __init__(self, github_token: Optional[str] = None, github_base_url: Optional[str] = None):
        self.github_client = GitHubClient(token=github_token, base_url=github_base_url)
        self.analyzer = RepositoryAnalyzer(github_client=self.github_client)

    def analyze_repository(self, owner: str, repo: str, max_workers: int = 10) -> Dict[str, Any]:
        """GitHub 레포지토리 의존성 분석 (기본값: 10 workers)."""
        return self.analyzer.analyze_repository(owner, repo, max_workers)

    def save_results(self, results: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """분석 결과를 JSON 파일로 저장."""
        if not output_file:
            output_file = f"{results['owner']}_{results['repo']}_dependencies.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: {output_file}")
        return output_file

    def print_summary(self, results: Dict[str, Any]) -> None:
        """분석 결과 요약 출력."""
        print("\n" + "=" * 60)
        print(f"Repository: {results['owner']}/{results['repo']}")
        print("=" * 60)
        print(f"Total dependency files: {results['total_files']}")
        print(f"Total unique dependencies: {results['total_dependencies']}")
        print(f"Runtime dependencies: {results['summary']['runtime_dependencies']}")
        print(f"Dev dependencies: {results['summary']['dev_dependencies']}")
        print("\nDependencies by source:")
        for source, count in results['summary']['by_source'].items():
            print(f"  - {source}: {count}")
        print("=" * 60)


# 편의 함수들
def analyze_repository(owner: str, repo: str, **kwargs) -> Dict[str, Any]:
    """GitHub 레포지토리 의존성 분석 (단축 함수)."""
    service = SecurityAnalysisService(
        github_token=kwargs.get('github_token'),
        github_base_url=kwargs.get('github_base_url')
    )
    return service.analyze_repository(owner, repo, max_workers=kwargs.get('max_workers', 10))


__all__ = ['SecurityAnalysisService', 'analyze_repository']
