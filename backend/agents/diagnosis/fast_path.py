"""
Diagnosis Agent - Fast Path
빠른 조회 실행 (README, Activity, Dependencies 등)
"""
from typing import Dict, Any, Optional, Literal
from backend.common import github_client
from backend.common.cache_manager import get_cache_manager
import logging

logger = logging.getLogger(__name__)


async def execute_fast_path(
    owner: str,
    repo: str,
    ref: str,
    target: Literal["readme", "activity", "dependencies", "structure"],
    cached_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    import time
    start_time = time.time()
    
    logger.info(f"Fast path execution: {owner}/{repo} - {target}")
    
    # 캐시에서 먼저 찾기
    if cached_result:
        logger.info(f"Using cached result for fast path: {target}")
        
        if target == "readme" and "readme_content" in cached_result:
            return _format_result(
                target=target,
                data={"content": cached_result["readme_content"]},
                from_cache=True,
                start_time=start_time
            )
        
        if target == "activity" and "activity_result" in cached_result:
            return _format_result(
                target=target,
                data=cached_result["activity_result"],
                from_cache=True,
                start_time=start_time
            )
        
        if target == "dependencies" and "deps_result" in cached_result:
            return _format_result(
                target=target,
                data=cached_result["deps_result"],
                from_cache=True,
                start_time=start_time
            )
        
        if target == "structure" and "structure_result" in cached_result:
            return _format_result(
                target=target,
                data=cached_result["structure_result"],
                from_cache=True,
                start_time=start_time
            )
    
    # 캐시 없으면 GitHub에서 가져오기
    try:
        if target == "readme":
            data = await _fetch_readme(owner, repo)
        elif target == "activity":
            data = await _fetch_activity(owner, repo)
        elif target == "dependencies":
            data = await _fetch_dependencies(owner, repo)
        elif target == "structure":
            data = await _fetch_structure(owner, repo)
        else:
            raise ValueError(f"Unsupported target: {target}")
        
        return _format_result(
            target=target,
            data=data,
            from_cache=False,
            start_time=start_time
        )
        
    except Exception as e:
        logger.error(f"Fast path failed for {target}: {e}")
        return {
            "type": "quick_query",
            "target": target,
            "error": str(e),
            "from_cache": False,
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


async def _fetch_readme(owner: str, repo: str) -> Dict[str, Any]:
    """README 가져오기"""
    try:
        # fetch_repo_overview에 README가 포함되어 있음
        overview = github_client.fetch_repo_overview(owner, repo)
        content = overview.get("readme_content")
        
        if not content:
            return {"error": "README not found"}
        
        return {
            "content": content,
            "length": len(content),
            "has_sections": _detect_readme_sections(content),
            "has_readme": overview.get("has_readme", False)
        }
    except Exception as e:
        logger.warning(f"Failed to fetch README: {e}")
        return {"error": str(e)}


async def _fetch_activity(owner: str, repo: str) -> Dict[str, Any]:
    """활동 정보 가져오기"""
    try:
        # fetch_activity_summary 사용 (GraphQL - 한번에 commits, issues, PRs 조회)
        activity = github_client.fetch_activity_summary(owner, repo)
        
        commits = activity.get("commits", [])
        issues = activity.get("issues", [])
        prs = activity.get("prs", [])
        
        return {
            "recent_commits_count": len(commits),
            "recent_commits": commits[:10],
            "open_issues_count": len(issues),
            "open_prs_count": len(prs),
            "last_commit_date": commits[0].get("committed_date") if commits else None
        }
    except Exception as e:
        logger.warning(f"Failed to fetch activity: {e}")
        return {"error": str(e)}


async def _fetch_dependencies(owner: str, repo: str) -> Dict[str, Any]:
    """의존성 정보 가져오기"""
    try:
        contents = github_client.fetch_repo_contents(owner, repo, "")
        
        dep_file_names = [
            "package.json",  # Node.js
            "requirements.txt",  # Python
            "Pipfile",  # Python
            "go.mod",  # Go
            "pom.xml",  # Java Maven
            "build.gradle",  # Java Gradle
            "Cargo.toml",  # Rust
            "composer.json",  # PHP
        ]
        
        found_files = []
        for item in contents:
            filename = item.get("name", "")
            if filename in dep_file_names:
                found_files.append({
                    "file": filename,
                    "type": _detect_dep_type(filename),
                    "size": item.get("size", 0)
                })
        
        return {
            "dependency_files": found_files,
            "total_files": len(found_files)
        }
    except Exception as e:
        logger.warning(f"Failed to fetch dependencies: {e}")
        return {"error": str(e)}


def _detect_dep_type(filename: str) -> str:
    """파일명으로 의존성 타입 감지"""
    mapping = {
        "package.json": "npm",
        "requirements.txt": "pip",
        "Pipfile": "pipenv",
        "go.mod": "go",
        "pom.xml": "maven",
        "build.gradle": "gradle",
        "Cargo.toml": "cargo",
        "composer.json": "composer",
    }
    return mapping.get(filename, "unknown")


async def _fetch_structure(owner: str, repo: str) -> Dict[str, Any]:
    """구조 정보 가져오기"""
    try:
        # fetch_repo_contents 사용하여 루트 디렉토리 확인
        contents = github_client.fetch_repo_contents(owner, repo, "")
        
        files = [item for item in contents if item.get("type") == "file"]
        dirs = [item for item in contents if item.get("type") == "dir"]
        
        return {
            "total_files": len(files),
            "total_dirs": len(dirs),
            "top_level_items": [item.get("name") for item in contents[:20]]
        }
    except Exception as e:
        logger.warning(f"Failed to fetch structure: {e}")
        return {"error": str(e)}


def _detect_readme_sections(content: str) -> list:
    """README 섹션 감지"""
    import re
    headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
    return headers[:10]  # 최대 10개


def _format_result(
    target: str,
    data: Dict[str, Any],
    from_cache: bool,
    start_time: float
) -> Dict[str, Any]:
    """결과 포맷팅"""
    import time
    execution_time_ms = int((time.time() - start_time) * 1000)
    
    return {
        "type": "quick_query",
        "target": target,
        "data": data,
        "from_cache": from_cache,
        "execution_time_ms": execution_time_ms
    }
