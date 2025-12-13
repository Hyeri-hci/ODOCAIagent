"""
Onboarding Context Builder
GitHub API를 통해 프로젝트 문서와 구조를 수집하여 OnboardingContext를 생성합니다.
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from backend.agents.onboarding.models import (
    OnboardingContext, DocsIndex, WorkflowHints, CodeMap
)
from backend.common.github_client import (
    fetch_file_content,
    fetch_repo_tree,
    fetch_repo
)

logger = logging.getLogger(__name__)

# 캐시 TTL (1시간)
CONTEXT_CACHE_TTL = 3600
_context_cache: Dict[str, OnboardingContext] = {}


def _get_cache_key(owner: str, repo: str, ref: str) -> str:
    return f"{owner}/{repo}@{ref}"


def _is_cache_valid(ctx: OnboardingContext) -> bool:
    if not ctx.get("cached_at"):
        return False
    cached_at = datetime.fromisoformat(ctx["cached_at"])
    elapsed = (datetime.now() - cached_at).total_seconds()
    return elapsed < ctx.get("cache_ttl_seconds", CONTEXT_CACHE_TTL)


async def build_onboarding_context(
    owner: str,
    repo: str,
    ref: str = "main"
) -> OnboardingContext:
    """
    OnboardingContext 빌드 (캐시 지원)
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        ref: 브랜치/태그
    
    Returns:
        OnboardingContext with docs, workflow, and code structure
    """
    cache_key = _get_cache_key(owner, repo, ref)
    
    # 캐시 확인
    if cache_key in _context_cache:
        cached = _context_cache[cache_key]
        if _is_cache_valid(cached):
            logger.info(f"[ContextBuilder] Using cached context for {cache_key}")
            return cached
    
    logger.info(f"[ContextBuilder] Building context for {owner}/{repo}@{ref}")
    
    # 1. 문서 인덱스 수집
    docs_index = await _build_docs_index(owner, repo, ref)
    
    # 2. 워크플로우 힌트 추출
    workflow_hints = await _extract_workflow_hints(owner, repo, ref, docs_index)
    
    # 3. 코드 맵 생성
    code_map = await _build_code_map(owner, repo, ref)
    
    context: OnboardingContext = {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "docs_index": docs_index,
        "workflow_hints": workflow_hints,
        "code_map": code_map,
        "cached_at": datetime.now().isoformat(),
        "cache_ttl_seconds": CONTEXT_CACHE_TTL
    }
    
    # 캐시 저장
    _context_cache[cache_key] = context
    logger.info(f"[ContextBuilder] Context built and cached for {cache_key}")
    
    return context


async def _build_docs_index(owner: str, repo: str, ref: str) -> DocsIndex:
    """문서 인덱스 생성"""
    docs_files = {
        "readme": ["README.md", "readme.md", "README", "Readme.md"],
        "contributing": ["CONTRIBUTING.md", "contributing.md", ".github/CONTRIBUTING.md"],
        "code_of_conduct": ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"],
        "security": ["SECURITY.md", ".github/SECURITY.md"]
    }
    
    file_paths: Dict[str, str] = {}
    summaries: Dict[str, Optional[str]] = {
        "readme": None,
        "contributing": None,
        "code_of_conduct": None,
        "security": None
    }
    
    for doc_type, possible_paths in docs_files.items():
        for path in possible_paths:
            try:
                content = fetch_file_content(owner, repo, path, ref)
                if content:
                    file_paths[doc_type] = path
                    # 요약 생성 (첫 500자)
                    summaries[doc_type] = content[:500] + "..." if len(content) > 500 else content
                    break
            except Exception:
                continue
    
    # 템플릿 수집
    templates: List[str] = []
    template_paths = [
        ".github/ISSUE_TEMPLATE",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE.md"
    ]
    
    try:
        tree_result = fetch_repo_tree(owner, repo, ref)
        tree = tree_result.get("tree", []) if isinstance(tree_result, dict) else tree_result
        
        for item in tree:
            path = item.get("path", "")
            for tpl_path in template_paths:
                if path.startswith(tpl_path):
                    templates.append(path)
    except Exception as e:
        logger.warning(f"[ContextBuilder] Failed to fetch templates: {e}")
    
    return DocsIndex(
        readme=summaries["readme"],
        contributing=summaries["contributing"],
        code_of_conduct=summaries["code_of_conduct"],
        security=summaries["security"],
        templates=templates,
        file_paths=file_paths
    )


async def _extract_workflow_hints(
    owner: str, 
    repo: str, 
    ref: str,
    docs_index: DocsIndex
) -> WorkflowHints:
    """CONTRIBUTING.md 등에서 워크플로우 힌트 추출"""
    
    hints: WorkflowHints = {
        "fork_required": True,  # 기본값
        "branch_convention": None,
        "commit_convention": None,
        "test_command": None,
        "build_command": None,
        "ci_present": False,
        "review_process": None
    }
    
    # CONTRIBUTING.md 분석
    contributing_content = docs_index.get("contributing", "") or ""
    
    # 브랜치 컨벤션 추출
    branch_patterns = [
        r"branch.*?(?:named?|call(?:ed)?|format).*?[`'\"]([a-z\-/]+)[`'\"]",
        r"(?:feature|bugfix|hotfix)/",
        r"(?:develop|development|dev)\s+branch"
    ]
    for pattern in branch_patterns:
        match = re.search(pattern, contributing_content, re.IGNORECASE)
        if match:
            hints["branch_convention"] = match.group(1) if match.groups() else "feature/xxx"
            break
    
    # 커밋 컨벤션 추출
    commit_keywords = ["conventional commit", "commit message", "semantic commit"]
    for kw in commit_keywords:
        if kw in contributing_content.lower():
            hints["commit_convention"] = "Conventional Commits"
            break
    
    # 테스트/빌드 명령어 추출
    test_patterns = [
        r"(?:run|execute).*?test.*?[`'\"](.+?)[`'\"]",
        r"npm\s+(?:run\s+)?test",
        r"pytest",
        r"cargo\s+test",
        r"go\s+test"
    ]
    for pattern in test_patterns:
        match = re.search(pattern, contributing_content, re.IGNORECASE)
        if match:
            hints["test_command"] = match.group(1) if match.groups() else match.group(0)
            break
    
    build_patterns = [
        r"(?:run|execute).*?build.*?[`'\"](.+?)[`'\"]",
        r"npm\s+run\s+build",
        r"cargo\s+build",
        r"go\s+build"
    ]
    for pattern in build_patterns:
        match = re.search(pattern, contributing_content, re.IGNORECASE)
        if match:
            hints["build_command"] = match.group(1) if match.groups() else match.group(0)
            break
    
    # CI 존재 여부 확인
    try:
        tree_result = fetch_repo_tree(owner, repo, ref)
        tree = tree_result.get("tree", []) if isinstance(tree_result, dict) else tree_result
        
        ci_paths = [".github/workflows", ".circleci", ".travis.yml", "azure-pipelines.yml"]
        for item in tree:
            path = item.get("path", "")
            for ci_path in ci_paths:
                if path.startswith(ci_path):
                    hints["ci_present"] = True
                    break
            if hints["ci_present"]:
                break
    except Exception:
        pass
    
    return hints


async def _build_code_map(owner: str, repo: str, ref: str) -> CodeMap:
    """코드 구조 맵 생성"""
    
    code_map: CodeMap = {
        "main_directories": [],
        "entry_points": [],
        "language": "unknown",
        "package_manager": None
    }
    
    try:
        # 저장소 정보에서 언어 추출
        repo_info = fetch_repo_info(owner, repo)
        if repo_info:
            code_map["language"] = repo_info.get("language", "unknown") or "unknown"
        
        # 파일 트리에서 주요 디렉토리/엔트리포인트 추출
        tree_result = fetch_repo_tree(owner, repo, ref)
        tree = tree_result.get("tree", []) if isinstance(tree_result, dict) else tree_result
        
        # 주요 디렉토리
        common_dirs = ["src", "lib", "app", "pkg", "core", "tests", "test", "spec"]
        for item in tree:
            if item.get("type") == "tree":
                path = item.get("path", "")
                if path in common_dirs:
                    code_map["main_directories"].append(path + "/")
        
        # 엔트리포인트
        entry_files = ["main.py", "index.js", "index.ts", "app.py", "main.go", "main.rs", "lib.rs"]
        for item in tree:
            if item.get("type") == "blob":
                path = item.get("path", "")
                filename = path.split("/")[-1]
                if filename in entry_files:
                    code_map["entry_points"].append(path)
        
        # 패키지 매니저 감지
        pm_files = {
            "package.json": "npm",
            "package-lock.json": "npm",
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
            "requirements.txt": "pip",
            "pyproject.toml": "pip",
            "Cargo.toml": "cargo",
            "go.mod": "go",
            "Gemfile": "bundler"
        }
        for item in tree:
            if item.get("type") == "blob":
                path = item.get("path", "")
                filename = path.split("/")[-1]
                if filename in pm_files:
                    code_map["package_manager"] = pm_files[filename]
                    break
    
    except Exception as e:
        logger.warning(f"[ContextBuilder] Failed to build code map: {e}")
    
    return code_map


def clear_context_cache():
    """캐시 초기화 (테스트용)"""
    global _context_cache
    _context_cache = {}
    logger.info("[ContextBuilder] Context cache cleared")
