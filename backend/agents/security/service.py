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


async def run_security_analysis(
    owner: str,
    repo: str,
    analysis_type: str = "full",
    execution_mode: str = "auto",
    **kwargs
) -> Dict[str, Any]:
    """
    Security Agent를 통한 보안 분석 실행.
    
    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        analysis_type: 분석 유형 ('dependencies', 'vulnerabilities', 'full')
        execution_mode: 실행 모드 ('fast', 'intelligent', 'auto')
        **kwargs: 추가 옵션 (github_token 등)
    
    Returns:
        Dict[str, Any]: 보안 분석 결과
    """
    from backend.agents.security.agent.security_agent import SecurityAgent
    from backend.common.config import (
        SECURITY_LLM_BASE_URL,
        SECURITY_LLM_API_KEY,
        SECURITY_LLM_MODEL,
        SECURITY_LLM_TEMPERATURE,
    )
    import logging
    
    logger = logging.getLogger(__name__)
    
    # LLM 설정 확인
    if not all([SECURITY_LLM_BASE_URL, SECURITY_LLM_API_KEY]):
        logger.error("Security LLM settings not configured")
        return {"error": "Security LLM settings not configured"}
    
    # 실행 모드 결정
    if analysis_type == "dependencies":
        mode = "fast"
    elif execution_mode != "auto":
        mode = execution_mode
    else:
        mode = "intelligent"
    
    try:
        agent = SecurityAgent(
            llm_base_url=SECURITY_LLM_BASE_URL or "",
            llm_api_key=SECURITY_LLM_API_KEY or "",
            llm_model=SECURITY_LLM_MODEL,
            llm_temperature=SECURITY_LLM_TEMPERATURE,
            execution_mode=mode,
        )
        
        user_request = f"{owner}/{repo} 프로젝트의 보안 분석을 수행해줘"
        result = await agent.analyze(user_request=user_request)
        
        logger.info(f"Security analysis completed for {owner}/{repo}")
        return result
        
    except Exception as e:
        logger.error(f"Security analysis failed: {e}")
        return {"error": str(e)}


__all__ = ['SecurityAnalysisService', 'analyze_repository', 'run_security_analysis']
