"""구조 분석 Core 테스트."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch, MagicMock
from backend.core.structure_core import (
    analyze_structure,
    _match_patterns,
    _calculate_structure_score,
    TEST_PATTERNS,
    CI_PATTERNS,
    DOCS_PATTERNS,
    BUILD_PATTERNS,
)
from backend.core.models import RepoSnapshot


class TestPatternMatching:
    """패턴 매칭 테스트."""

    def test_python_test_files(self):
        files = [
            "tests/test_main.py",
            "test_utils.py",
            "utils_test.py",
            "conftest.py",
            "pytest.ini",
            "src/main.py",
        ]
        matched = _match_patterns(files, TEST_PATTERNS)
        assert "tests/test_main.py" in matched
        assert "test_utils.py" in matched
        assert "utils_test.py" in matched
        assert "conftest.py" in matched
        assert "pytest.ini" in matched
        assert "src/main.py" not in matched

    def test_javascript_test_files(self):
        files = [
            "__tests__/app.test.js",
            "src/utils.spec.ts",
            "components/Button.test.tsx",
            "jest.config.js",
            "vitest.config.ts",
            "src/index.js",
        ]
        matched = _match_patterns(files, TEST_PATTERNS)
        assert "__tests__/app.test.js" in matched
        assert "src/utils.spec.ts" in matched
        assert "components/Button.test.tsx" in matched
        assert "jest.config.js" in matched
        assert "src/index.js" not in matched

    def test_ci_files(self):
        files = [
            ".github/workflows/ci.yml",
            ".github/workflows/deploy.yaml",
            ".gitlab-ci.yml",
            "Jenkinsfile",
            ".travis.yml",
            ".circleci/config.yml",
            "README.md",
        ]
        matched = _match_patterns(files, CI_PATTERNS)
        assert ".github/workflows/ci.yml" in matched
        assert ".github/workflows/deploy.yaml" in matched
        assert ".gitlab-ci.yml" in matched
        assert "Jenkinsfile" in matched
        assert ".travis.yml" in matched
        assert "README.md" not in matched

    def test_docs_patterns(self):
        files = [
            "docs/index.md",
            "documentation/guide.md",
            "mkdocs.yml",
            ".readthedocs.yaml",
            "src/main.py",
        ]
        matched = _match_patterns(files, DOCS_PATTERNS)
        assert "docs/index.md" in matched
        assert "documentation/guide.md" in matched
        assert "mkdocs.yml" in matched
        assert "src/main.py" not in matched

    def test_build_files(self):
        files = [
            "setup.py",
            "pyproject.toml",
            "package.json",
            "webpack.config.js",
            "Dockerfile",
            "docker-compose.yml",
            "go.mod",
            "Cargo.toml",
            "pom.xml",
            "build.gradle",
            "README.md",
        ]
        matched = _match_patterns(files, BUILD_PATTERNS)
        assert "setup.py" in matched
        assert "pyproject.toml" in matched
        assert "package.json" in matched
        assert "webpack.config.js" in matched
        assert "Dockerfile" in matched
        assert "go.mod" in matched
        assert "Cargo.toml" in matched
        assert "pom.xml" in matched
        assert "build.gradle" in matched
        assert "README.md" not in matched


class TestScoreCalculation:
    """점수 계산 테스트."""

    def test_no_structure(self):
        score = _calculate_structure_score(
            has_tests=False,
            has_ci=False,
            has_docs=False,
            has_build=False,
            test_count=0,
            ci_count=0,
        )
        assert score == 0

    def test_full_structure(self):
        score = _calculate_structure_score(
            has_tests=True,
            has_ci=True,
            has_docs=True,
            has_build=True,
            test_count=10,
            ci_count=3,
        )
        assert score == 100

    def test_partial_structure(self):
        score = _calculate_structure_score(
            has_tests=True,
            has_ci=True,
            has_docs=False,
            has_build=True,
            test_count=5,
            ci_count=1,
        )
        # 30 (tests) + 25 (ci) + 15 (build) + 3 (5 tests bonus) = 73
        assert score == 73

    def test_tests_only(self):
        score = _calculate_structure_score(
            has_tests=True,
            has_ci=False,
            has_docs=False,
            has_build=False,
            test_count=1,
            ci_count=0,
        )
        # 30 (tests) + 1 (1 test bonus) = 31
        assert score == 31


class TestAnalyzeStructure:
    """analyze_structure 통합 테스트."""

    def _create_mock_snapshot(self, owner="test", repo="repo", ref="main"):
        return RepoSnapshot(
            owner=owner,
            repo=repo,
            ref=ref,
            full_name=f"{owner}/{repo}",
            description="Test repo",
            stars=100,
            forks=10,
            open_issues=5,
            primary_language="Python",
            created_at=None,
            pushed_at=None,
            is_archived=False,
            is_fork=False,
            readme_content="# Test",
            has_readme=True,
            license_spdx="MIT",
        )

    @patch("backend.core.structure_core.fetch_repo_tree")
    def test_analyze_with_full_structure(self, mock_fetch):
        mock_fetch.return_value = [
            "tests/test_main.py",
            "tests/test_utils.py",
            "conftest.py",
            ".github/workflows/ci.yml",
            ".github/workflows/deploy.yml",
            "docs/index.md",
            "setup.py",
            "pyproject.toml",
            "src/main.py",
        ]
        
        snapshot = self._create_mock_snapshot()
        result = analyze_structure(snapshot)
        
        assert result.has_tests is True
        assert result.has_ci is True
        assert result.has_docs_folder is True
        assert result.has_build_config is True
        assert len(result.test_files) == 3
        assert len(result.ci_files) == 2
        assert len(result.build_files) == 2
        assert result.structure_score > 0

    @patch("backend.core.structure_core.fetch_repo_tree")
    def test_analyze_empty_repo(self, mock_fetch):
        mock_fetch.return_value = []
        
        snapshot = self._create_mock_snapshot()
        result = analyze_structure(snapshot)
        
        assert result.has_tests is False
        assert result.has_ci is False
        assert result.has_docs_folder is False
        assert result.has_build_config is False
        assert result.structure_score == 0

    @patch("backend.core.structure_core.fetch_repo_tree")
    def test_analyze_minimal_repo(self, mock_fetch):
        mock_fetch.return_value = [
            "README.md",
            "main.py",
            "requirements.txt",
        ]
        
        snapshot = self._create_mock_snapshot()
        result = analyze_structure(snapshot)
        
        assert result.has_tests is False
        assert result.has_ci is False
        assert result.has_docs_folder is False
        assert result.has_build_config is False
        assert result.structure_score == 0

    @patch("backend.core.structure_core.fetch_repo_tree")
    def test_analyze_fetch_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("API Error")
        
        snapshot = self._create_mock_snapshot()
        result = analyze_structure(snapshot)
        
        assert result.has_tests is False
        assert result.structure_score == 0

