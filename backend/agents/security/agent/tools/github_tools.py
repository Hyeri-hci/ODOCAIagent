"""
GitHub 관련 툴
"""
from langchain_core.tools import tool
from typing import Dict, Any, List, Optional
import os


@tool
def fetch_repository_tree(owner: str, repo: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    GitHub 레포지토리의 파일 트리를 조회합니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        github_token: GitHub Personal Access Token (옵션)

    Returns:
        Dict containing:
        - success: bool
        - files: List[Dict[path, sha, size]]
        - count: int
        - error: str (if failed)
    """
    try:
        from ...github.client import GitHubClient
        
        client = GitHubClient(token=github_token)
        files = client.get_repository_tree(owner, repo)
        
        return {
            "success": True,
            "files": files,
            "count": len(files),
            "owner": owner,
            "repo": repo
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "files": [],
            "count": 0
        }


@tool
def fetch_file_content(owner: str, repo: str, file_path: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    GitHub에서 파일 내용을 가져옵니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        file_path: 파일 경로
        github_token: GitHub Personal Access Token (옵션)

    Returns:
        Dict containing:
        - success: bool
        - content: str (파일 내용)
        - path: str
        - error: str (if failed)
    """
    try:
        from ...github.client import GitHubClient
        
        client = GitHubClient(token=github_token)
        content = client.get_file_content(owner, repo, file_path)
        
        if content is not None:
            return {
                "success": True,
                "content": content,
                "path": file_path
            }
        else:
            return {
                "success": False,
                "error": f"Failed to fetch content for {file_path}",
                "content": "",
                "path": file_path
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": "",
            "path": file_path
        }


@tool
def find_dependency_files(owner: str, repo: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    레포지토리에서 의존성 파일을 찾습니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        github_token: GitHub Personal Access Token (옵션)

    Returns:
        Dict containing:
        - success: bool
        - dependency_files: List[str] (의존성 파일 경로들)
        - lock_files: List[str] (lock 파일 경로들)
        - count: int
        - error: str (if failed)
    """
    try:
        from ...github.analyzer import RepositoryAnalyzer
        
        analyzer = RepositoryAnalyzer(github_token=github_token)
        dep_files = analyzer.get_dependency_files(owner, repo)
        
        # lock 파일 구분
        lock_files = [f for f in dep_files if analyzer.is_lockfile(f)]
        regular_files = [f for f in dep_files if not analyzer.is_lockfile(f)]
        
        return {
            "success": True,
            "dependency_files": dep_files,
            "lock_files": lock_files,
            "regular_files": regular_files,
            "count": len(dep_files),
            "owner": owner,
            "repo": repo
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "dependency_files": [],
            "lock_files": [],
            "regular_files": [],
            "count": 0
        }


@tool
def check_is_lockfile(file_path: str) -> Dict[str, Any]:
    """
    파일이 lock 파일인지 확인합니다.

    Args:
        file_path: 파일 경로

    Returns:
        Dict containing:
        - is_lockfile: bool
        - path: str
    """
    try:
        from ...github.analyzer import RepositoryAnalyzer
        
        analyzer = RepositoryAnalyzer()
        is_lock = analyzer.is_lockfile(file_path)
        
        return {
            "is_lockfile": is_lock,
            "path": file_path
        }
    except Exception as e:
        return {
            "is_lockfile": False,
            "path": file_path,
            "error": str(e)
        }


@tool
def validate_repository_access(owner: str, repo: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    레포지토리 접근 가능 여부를 확인합니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        github_token: GitHub Personal Access Token (옵션)

    Returns:
        Dict containing:
        - success: bool
        - accessible: bool
        - error: str (if failed)
    """
    try:
        from ...github.client import GitHubClient
        
        client = GitHubClient(token=github_token)
        files = client.get_repository_tree(owner, repo)
        
        return {
            "success": True,
            "accessible": len(files) > 0 or files is not None,
            "owner": owner,
            "repo": repo
        }
    except Exception as e:
        return {
            "success": False,
            "accessible": False,
            "error": str(e)
        }
