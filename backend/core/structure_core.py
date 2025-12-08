"""저장소 구조 분석 Core 레이어 - 테스트, CI, 문서, 빌드 설정 탐지."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from backend.core.models import RepoSnapshot, StructureCoreResult
from backend.core.github_core import fetch_repo_tree

logger = logging.getLogger(__name__)


# 테스트 파일 패턴
TEST_PATTERNS = [
    # Python
    r"^tests?/",
    r"test_.*\.py$",
    r".*_test\.py$",
    r".*_tests\.py$",
    r"pytest\.ini$",
    r"conftest\.py$",
    # JavaScript/TypeScript
    r"__tests__/",
    r"\.spec\.(js|ts|jsx|tsx)$",
    r"\.test\.(js|ts|jsx|tsx)$",
    r"jest\.config\.(js|ts|json)$",
    r"vitest\.config\.(js|ts)$",
    # Java
    r"src/test/",
    r".*Test\.java$",
    # Go
    r".*_test\.go$",
    # Rust
    r"tests/.*\.rs$",
    # Ruby
    r"spec/.*_spec\.rb$",
    r"test/.*_test\.rb$",
    # PHP
    r"tests?/.*Test\.php$",
]

# CI 설정 파일 패턴
CI_PATTERNS = [
    # GitHub Actions
    r"^\.github/workflows/.*\.ya?ml$",
    # GitLab CI
    r"^\.gitlab-ci\.ya?ml$",
    # Jenkins
    r"^Jenkinsfile$",
    # Travis CI
    r"^\.travis\.ya?ml$",
    # CircleCI
    r"^\.circleci/config\.ya?ml$",
    # Azure Pipelines
    r"^azure-pipelines\.ya?ml$",
    # Bitbucket Pipelines
    r"^bitbucket-pipelines\.ya?ml$",
    # Drone CI
    r"^\.drone\.ya?ml$",
    # AppVeyor
    r"^appveyor\.ya?ml$",
    r"^\.appveyor\.ya?ml$",
]

# 문서 폴더 패턴
DOCS_PATTERNS = [
    r"^docs?/",
    r"^documentation/",
    r"^wiki/",
    r"^guide/",
    r"^manual/",
    r"^\.readthedocs\.ya?ml$",
    r"^mkdocs\.ya?ml$",
    r"^book\.toml$",  # mdBook
    r"^docusaurus\.config\.js$",
]

# 빌드 설정 파일 패턴
BUILD_PATTERNS = [
    # Python
    r"^setup\.py$",
    r"^setup\.cfg$",
    r"^pyproject\.toml$",
    r"^Makefile$",
    # JavaScript/TypeScript
    r"^package\.json$",
    r"^webpack\.config\.(js|ts)$",
    r"^vite\.config\.(js|ts)$",
    r"^rollup\.config\.(js|ts)$",
    r"^esbuild\.config\.(js|ts)$",
    r"^tsconfig\.json$",
    # Java/Kotlin
    r"^pom\.xml$",
    r"^build\.gradle(\.kts)?$",
    r"^settings\.gradle(\.kts)?$",
    # Go
    r"^go\.mod$",
    r"^go\.sum$",
    # Rust
    r"^Cargo\.toml$",
    # Ruby
    r"^Gemfile$",
    r"^Rakefile$",
    # C/C++
    r"^CMakeLists\.txt$",
    r"^Makefile$",
    r"^configure\.ac$",
    r"^meson\.build$",
    # Docker
    r"^Dockerfile$",
    r"^docker-compose\.ya?ml$",
]


def _match_patterns(files: List[str], patterns: List[str]) -> List[str]:
    """파일 목록에서 패턴에 매칭되는 파일 반환."""
    matched = []
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    
    for file_path in files:
        for regex in compiled:
            if regex.search(file_path):
                matched.append(file_path)
                break
    
    return matched


def _calculate_structure_score(
    has_tests: bool,
    has_ci: bool,
    has_docs: bool,
    has_build: bool,
    test_count: int,
    ci_count: int,
) -> int:
    """
    구조 성숙도 점수 계산 (0-100).
    
    가중치:
    - 테스트 존재: 30점
    - CI 존재: 25점
    - 문서 폴더: 20점
    - 빌드 설정: 15점
    - 보너스: 테스트 파일 수, CI 워크플로우 수
    """
    score = 0
    
    # 기본 점수
    if has_tests:
        score += 30
    if has_ci:
        score += 25
    if has_docs:
        score += 20
    if has_build:
        score += 15
    
    # 보너스 점수
    if test_count >= 10:
        score += 5
    elif test_count >= 5:
        score += 3
    elif test_count >= 1:
        score += 1
    
    if ci_count >= 3:
        score += 5
    elif ci_count >= 2:
        score += 3
    elif ci_count >= 1:
        score += 0  # 기본 점수에 이미 포함
    
    return min(score, 100)


def analyze_structure(snapshot: RepoSnapshot) -> StructureCoreResult:

    owner = snapshot.owner
    repo = snapshot.repo
    ref = snapshot.ref
    
    # 파일 트리 조회
    try:
        file_tree = fetch_repo_tree(owner, repo, ref)
    except Exception as e:
        logger.warning(f"Failed to fetch file tree for {owner}/{repo}: {e}")
        file_tree = []
    
    if not file_tree:
        logger.info(f"No file tree available for {owner}/{repo}, returning defaults")
        return StructureCoreResult(
            has_tests=False,
            has_ci=False,
            has_docs_folder=False,
            has_build_config=False,
            test_files=[],
            ci_files=[],
            build_files=[],
            structure_score=0,
        )
    
    # 패턴 매칭
    test_files = _match_patterns(file_tree, TEST_PATTERNS)
    ci_files = _match_patterns(file_tree, CI_PATTERNS)
    docs_files = _match_patterns(file_tree, DOCS_PATTERNS)
    build_files = _match_patterns(file_tree, BUILD_PATTERNS)
    
    has_tests = len(test_files) > 0
    has_ci = len(ci_files) > 0
    has_docs = len(docs_files) > 0
    has_build = len(build_files) > 0
    
    # 점수 계산
    structure_score = _calculate_structure_score(
        has_tests=has_tests,
        has_ci=has_ci,
        has_docs=has_docs,
        has_build=has_build,
        test_count=len(test_files),
        ci_count=len(ci_files),
    )
    
    logger.info(
        f"Structure analysis for {owner}/{repo}: "
        f"tests={len(test_files)}, ci={len(ci_files)}, "
        f"docs={len(docs_files)}, build={len(build_files)}, "
        f"score={structure_score}"
    )
    
    return StructureCoreResult(
        has_tests=has_tests,
        has_ci=has_ci,
        has_docs_folder=has_docs,
        has_build_config=has_build,
        test_files=test_files[:20],  # 상위 20개만
        ci_files=ci_files[:10],
        build_files=build_files[:10],
        structure_score=structure_score,
    )


# Alias for backward compatibility
analyze_structure_from_snapshot = analyze_structure
