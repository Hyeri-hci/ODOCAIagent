"""Consilience 모듈 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from backend.agents.diagnosis.tools.consilience import (
    check_path_refs,
    PathCheckResult,
    check_badge_refs,
    BadgeCheckResult,
    check_link_refs,
    LinkCheckResult,
    check_command_refs,
    CommandCheckResult,
)


class TestPathChecker:
    """경로 검증기 테스트."""
    
    def test_empty_refs_returns_empty_result(self):
        """빈 경로 목록 처리."""
        result = check_path_refs("owner", "repo", [])
        assert result.total == 0
        assert result.valid == 0
        assert result.broken == 0
    
    @patch("backend.agents.diagnosis.tools.consilience.path_checker.fetch_repo_tree")
    def test_valid_paths_detected(self, mock_fetch):
        """유효한 경로 검증."""
        mock_fetch.return_value = {
            "tree": [
                {"path": "src/main.py", "type": "blob"},
                {"path": "src", "type": "tree"},
                {"path": "README.md", "type": "blob"},
            ]
        }
        
        result = check_path_refs("owner", "repo", ["src/main.py", "README.md"])
        
        assert result.total == 2
        assert result.valid == 2
        assert result.broken == 0
    
    @patch("backend.agents.diagnosis.tools.consilience.path_checker.fetch_repo_tree")
    def test_broken_paths_detected(self, mock_fetch):
        """끊어진 경로 검출."""
        mock_fetch.return_value = {
            "tree": [
                {"path": "src/main.py", "type": "blob"},
            ]
        }
        
        result = check_path_refs("owner", "repo", ["nonexistent.py", "missing/"])
        
        assert result.total == 2
        assert result.valid == 0
        assert result.broken == 2
    
    @patch("backend.agents.diagnosis.tools.consilience.path_checker.fetch_repo_tree")
    def test_empty_tree_returns_unchecked(self, mock_fetch):
        """트리를 가져올 수 없으면 unchecked 처리."""
        mock_fetch.return_value = {"tree": []}
        
        result = check_path_refs("owner", "repo", ["path1", "path2"])
        
        assert result.total == 2
        assert result.valid == 0
        assert result.broken == 0
        assert all(d["status"] == "unchecked" for d in result.details)
    
    @patch("backend.agents.diagnosis.tools.consilience.path_checker.fetch_repo_tree")
    def test_path_normalization(self, mock_fetch):
        """경로 정규화 (./prefix, 백틱 등)."""
        mock_fetch.return_value = {
            "tree": [
                {"path": "config.yaml", "type": "blob"},
            ]
        }
        
        # ./config.yaml → config.yaml로 정규화
        result = check_path_refs("owner", "repo", ["./config.yaml", "`config.yaml`"])
        
        assert result.valid == 2


class TestBadgeChecker:
    """배지 검증기 테스트."""
    
    def test_empty_badges_returns_empty_result(self):
        """빈 배지 목록 처리."""
        result = check_badge_refs("owner", "repo", [])
        assert result.total == 0
    
    @patch("backend.agents.diagnosis.tools.consilience.badge_checker.fetch_workflows")
    def test_valid_actions_badge(self, mock_fetch):
        """유효한 GitHub Actions 배지 검증."""
        mock_fetch.return_value = [
            {"path": ".github/workflows/ci.yml"},
        ]
        
        badge_url = "https://github.com/owner/repo/actions/workflows/ci.yml/badge.svg"
        result = check_badge_refs("owner", "repo", [badge_url])
        
        assert result.total == 1
        assert result.valid == 1
    
    @patch("backend.agents.diagnosis.tools.consilience.badge_checker.fetch_workflows")
    def test_broken_actions_badge(self, mock_fetch):
        """워크플로 없는 배지 → broken."""
        mock_fetch.return_value = []  # 워크플로 없음
        
        badge_url = "https://github.com/owner/repo/actions/workflows/missing.yml/badge.svg"
        result = check_badge_refs("owner", "repo", [badge_url])
        
        assert result.total == 1
        assert result.broken == 1
    
    @patch("backend.agents.diagnosis.tools.consilience.badge_checker.fetch_workflows")
    def test_non_actions_badge_unchecked(self, mock_fetch):
        """Actions 배지가 아닌 경우 → unchecked."""
        mock_fetch.return_value = []
        
        badge_url = "https://img.shields.io/badge/license-MIT-blue.svg"
        result = check_badge_refs("owner", "repo", [badge_url])
        
        assert result.unchecked == 1


class TestLinkChecker:
    """링크 검증기 테스트."""
    
    def test_empty_links_returns_empty_result(self):
        """빈 링크 목록 처리."""
        result = check_link_refs([])
        assert result.total == 0
    
    def test_skip_localhost_links(self):
        """localhost 링크는 건너뜀."""
        result = check_link_refs(["http://localhost:3000"])
        assert result.unchecked == 1
    
    def test_skip_example_domains(self):
        """example.com 등은 건너뜀."""
        result = check_link_refs(["https://example.com/path"])
        assert result.unchecked == 1
    
    def test_skip_mailto_and_anchors(self):
        """mailto:, # 앵커는 건너뜀."""
        result = check_link_refs(["mailto:test@example.com", "#section"])
        assert result.unchecked == 2


class TestCommandChecker:
    """명령 검증기 테스트."""
    
    def test_empty_commands_returns_empty_result(self):
        """빈 명령 목록 처리."""
        result = check_command_refs("owner", "repo", {})
        assert result.total == 0
    
    @patch("backend.agents.diagnosis.tools.consilience.command_checker.fetch_repo_contents")
    def test_pip_install_checks_setup_files(self, mock_fetch):
        """pip install → setup.py/pyproject.toml 확인."""
        mock_fetch.return_value = [
            {"name": "pyproject.toml", "type": "file"},
            {"name": "README.md", "type": "file"},
        ]
        
        result = check_command_refs("owner", "repo", {"pip_install": 1})
        
        # setup.py(broken) + pyproject.toml(valid)
        assert result.valid >= 1
    
    @patch("backend.agents.diagnosis.tools.consilience.command_checker.fetch_repo_contents")
    def test_npm_checks_package_json(self, mock_fetch):
        """npm → package.json 확인."""
        mock_fetch.return_value = [
            {"name": "package.json", "type": "file"},
        ]
        
        result = check_command_refs("owner", "repo", {"npm_install": 1})
        
        assert result.valid == 1
    
    @patch("backend.agents.diagnosis.tools.consilience.command_checker.fetch_repo_contents")
    def test_missing_entrypoint_unchecked(self, mock_fetch):
        """리포 내용을 가져올 수 없으면 unchecked."""
        mock_fetch.return_value = []  # 빈 디렉토리 또는 가져올 수 없음
        
        result = check_command_refs("owner", "repo", {"npm_install": 1})
        
        # 빈 응답은 unchecked로 처리됨
        assert result.unchecked == 1


class TestResultSerialization:
    """결과 직렬화 테스트."""
    
    def test_path_result_to_dict(self):
        """PathCheckResult.to_dict() 테스트."""
        result = PathCheckResult(valid=2, broken=1, total=3)
        d = result.to_dict()
        
        assert d["valid"] == 2
        assert d["broken"] == 1
        assert d["total"] == 3
    
    def test_badge_result_to_dict(self):
        """BadgeCheckResult.to_dict() 테스트."""
        result = BadgeCheckResult(valid=1, broken=0, unchecked=2, total=3)
        d = result.to_dict()
        
        assert d["valid"] == 1
        assert d["unchecked"] == 2
