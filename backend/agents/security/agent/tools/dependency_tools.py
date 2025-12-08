"""
의존성 분석 툴
"""
from langchain_core.tools import tool
from typing import Dict, Any, List, Optional


@tool
def analyze_dependencies(owner: str, repo: str, max_workers: int = 5, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    GitHub 레포지토리의 전체 의존성을 분석합니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        max_workers: 병렬 처리 워커 수 (기본값: 5)
        github_token: GitHub Personal Access Token (옵션)

    Returns:
        Dict containing:
        - success: bool
        - owner: str
        - repo: str
        - total_files: int
        - total_dependencies: int
        - files: List[Dict] (파일별 의존성)
        - all_dependencies: List[Dict] (전체 의존성 목록)
        - summary: Dict (요약 정보)
        - error: str (if failed)
    """
    try:
        from ...tools.dependency_analyzer import analyze_repository_dependencies
        
        result = analyze_repository_dependencies(
            owner=owner,
            repo=repo,
            max_workers=max_workers,
            github_token=github_token
        )
        
        if "error" not in result:
            return {
                "success": True,
                **result
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                **result
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total_dependencies": 0,
            "total_files": 0
        }


@tool
def extract_dependencies_from_file(content: str, filename: str, is_lockfile: bool = False) -> Dict[str, Any]:
    """
    단일 파일에서 의존성을 추출합니다.

    Args:
        content: 파일 내용
        filename: 파일명
        is_lockfile: lock 파일 여부

    Returns:
        Dict containing:
        - success: bool
        - dependencies: List[Dict]
        - count: int
        - filename: str
        - error: str (if failed)
    """
    try:
        from ...extractors import DependencyExtractor
        
        extractor = DependencyExtractor()
        dependencies = extractor.extract(content, filename, is_lockfile)
        
        # Dependency 객체를 dict로 변환
        deps_dict = [
            {
                "name": dep.name,
                "version": dep.version,
                "type": dep.type,
                "source": dep.source,
                "is_from_lockfile": dep.is_from_lockfile
            }
            for dep in dependencies
        ]
        
        return {
            "success": True,
            "dependencies": deps_dict,
            "count": len(deps_dict),
            "filename": filename
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "dependencies": [],
            "count": 0,
            "filename": filename
        }


@tool
def filter_by_source(analysis_result: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    소스별로 의존성을 필터링합니다.

    Args:
        analysis_result: analyze_dependencies의 결과
        source: 패키지 소스 (예: "npm", "pypi", "maven")

    Returns:
        Dict containing:
        - success: bool
        - dependencies: List[Dict]
        - count: int
        - source: str
    """
    try:
        from ...tools.dependency_analyzer import get_dependencies_by_source
        
        dependencies = get_dependencies_by_source(analysis_result, source)
        
        return {
            "success": True,
            "dependencies": dependencies,
            "count": len(dependencies),
            "source": source
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "dependencies": [],
            "count": 0,
            "source": source
        }


@tool
def filter_by_type(analysis_result: Dict[str, Any], dep_type: str) -> Dict[str, Any]:
    """
    타입별로 의존성을 필터링합니다.

    Args:
        analysis_result: analyze_dependencies의 결과
        dep_type: 의존성 타입 (예: "runtime", "dev", "peer")

    Returns:
        Dict containing:
        - success: bool
        - dependencies: List[Dict]
        - count: int
        - type: str
    """
    try:
        from ...tools.dependency_analyzer import get_dependencies_by_type
        
        dependencies = get_dependencies_by_type(analysis_result, dep_type)
        
        return {
            "success": True,
            "dependencies": dependencies,
            "count": len(dependencies),
            "type": dep_type
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "dependencies": [],
            "count": 0,
            "type": dep_type
        }


@tool
def find_outdated_deps(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    버전이 명시되지 않은 의존성을 찾습니다.

    Args:
        analysis_result: analyze_dependencies의 결과

    Returns:
        Dict containing:
        - success: bool
        - outdated_dependencies: List[Dict]
        - count: int
    """
    try:
        from ...tools.dependency_analyzer import get_outdated_dependencies
        
        outdated = get_outdated_dependencies(analysis_result)
        
        return {
            "success": True,
            "outdated_dependencies": outdated,
            "count": len(outdated)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "outdated_dependencies": [],
            "count": 0
        }


@tool
def count_by_language(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    언어별로 의존성 개수를 집계합니다.

    Args:
        analysis_result: analyze_dependencies의 결과

    Returns:
        Dict containing:
        - success: bool
        - counts: Dict[str, int] (언어별 개수)
    """
    try:
        from ...tools.dependency_analyzer import count_dependencies_by_language
        
        counts = count_dependencies_by_language(analysis_result)
        
        return {
            "success": True,
            "counts": counts
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "counts": {}
        }


@tool
def summarize_analysis(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    의존성 분석 결과를 요약합니다.

    Args:
        analysis_result: analyze_dependencies의 결과

    Returns:
        Dict containing:
        - success: bool
        - summary: str (텍스트 요약)
    """
    try:
        from ...tools.dependency_analyzer import summarize_dependency_analysis
        
        summary = summarize_dependency_analysis(analysis_result)
        
        return {
            "success": True,
            "summary": summary
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": ""
        }
