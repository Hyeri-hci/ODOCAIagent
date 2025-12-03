"""리포 구조 성숙도 분석 Core 레이어."""
from __future__ import annotations

from typing import List, Optional
import logging

from backend.common.github_client import GITHUB_API_BASE, GITHUB_TOKEN
from .models import StructureCoreResult, RepoSnapshot

import requests

logger = logging.getLogger(__name__)


# 테스트 파일/폴더 패턴
TEST_PATTERNS = [
    "tests/",
    "test/",
    "__tests__/",
    "spec/",
]

TEST_FILE_PATTERNS = [
    "test_",
    "_test.py",
    ".test.js",
    ".test.ts",
    ".spec.js",
    ".spec.ts",
]

# CI 설정 파일 패턴
CI_PATTERNS = [
    ".github/workflows/",
    ".gitlab-ci.yml",
    ".travis.yml",
    "Jenkinsfile",
    ".circleci/",
    "azure-pipelines.yml",
]

# 빌드 설정 파일 패턴
BUILD_PATTERNS = [
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "go.mod",
    "Makefile",
]

# 문서 폴더 패턴
DOCS_PATTERNS = [
    "docs/",
    "doc/",
    "documentation/",
]


def _build_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def _fetch_repo_tree(owner: str, repo: str, ref: str = "HEAD") -> List[str]:
    """저장소 파일 트리 조회 (경로 목록 반환)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=15)
        if resp.status_code != 200:
            logger.warning("Failed to fetch tree: %s", resp.status_code)
            return []
        data = resp.json()
        return [item.get("path", "") for item in data.get("tree", [])]
    except Exception as e:
        logger.error("Error fetching repo tree: %s", e)
        return []


def analyze_structure(
    owner: str,
    repo: str,
    ref: str = "HEAD",
    file_tree: Optional[List[str]] = None,
) -> StructureCoreResult:
    """리포 구조 성숙도 분석."""
    if file_tree is None:
        file_tree = _fetch_repo_tree(owner, repo, ref)

    test_files: List[str] = []
    ci_files: List[str] = []
    build_files: List[str] = []
    has_docs_folder = False

    for path in file_tree:
        path_lower = path.lower()

        # 테스트 파일/폴더 체크
        for pattern in TEST_PATTERNS:
            if path_lower.startswith(pattern):
                test_files.append(path)
                break
        else:
            for pattern in TEST_FILE_PATTERNS:
                if pattern in path_lower:
                    test_files.append(path)
                    break

        # CI 설정 체크
        for pattern in CI_PATTERNS:
            if path_lower.startswith(pattern) or path_lower == pattern.rstrip("/"):
                ci_files.append(path)
                break

        # 빌드 설정 체크
        for pattern in BUILD_PATTERNS:
            if path_lower.endswith(pattern) or path_lower == pattern:
                build_files.append(path)
                break

        # 문서 폴더 체크
        for pattern in DOCS_PATTERNS:
            if path_lower.startswith(pattern):
                has_docs_folder = True
                break

    has_tests = len(test_files) > 0
    has_ci = len(ci_files) > 0
    has_build_config = len(build_files) > 0

    # 점수 계산 (각 항목 25점)
    score = 0
    if has_tests:
        score += 25
    if has_ci:
        score += 25
    if has_docs_folder:
        score += 25
    if has_build_config:
        score += 25

    return StructureCoreResult(
        has_tests=has_tests,
        has_ci=has_ci,
        has_docs_folder=has_docs_folder,
        has_build_config=has_build_config,
        test_files=test_files[:10],  # 최대 10개만
        ci_files=ci_files[:5],
        build_files=build_files[:5],
        structure_score=score,
    )


def analyze_structure_from_snapshot(snapshot: RepoSnapshot) -> StructureCoreResult:
    """RepoSnapshot 기반 구조 분석."""
    return analyze_structure(snapshot.owner, snapshot.repo, snapshot.ref)
