"""chaoss_metrics.py 단위 테스트"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date, timezone
from unittest.mock import patch
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.agents.diagnosis.tools.scoring.chaoss_metrics import (
    _parse_iso8601,
    _parse_commit_date,
    _extract_author_id,
    compute_commit_activity,
    CommitActivityMetrics,
)


class TestParseISO8601:
    """_parse_iso8601 함수 테스트"""

    def test_utc_z_suffix(self):
        result = _parse_iso8601("2024-11-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 11
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_iso_with_timezone(self):
        result = _parse_iso8601("2024-11-15T10:30:00+09:00")
        assert result is not None
        assert result.year == 2024
        assert result.day == 15

    def test_iso_without_timezone(self):
        result = _parse_iso8601("2024-11-15T10:30:00")
        assert result is not None
        assert result.year == 2024

    def test_empty_string(self):
        assert _parse_iso8601("") is None

    def test_none_input(self):
        assert _parse_iso8601(None) is None

    def test_invalid_format(self):
        assert _parse_iso8601("not-a-date") is None

    def test_whitespace_handling(self):
        result = _parse_iso8601("  2024-11-15T10:30:00Z  ")
        assert result is not None
        assert result.year == 2024


class TestParseCommitDate:
    """_parse_commit_date 함수 테스트"""

    def test_author_date(self):
        commit = {
            "commit": {
                "author": {"date": "2024-11-15T10:30:00Z"},
                "committer": {"date": "2024-11-16T10:30:00Z"},
            }
        }
        result = _parse_commit_date(commit)
        assert result is not None
        assert result == date(2024, 11, 15)

    def test_committer_date_fallback(self):
        commit = {
            "commit": {
                "author": {},
                "committer": {"date": "2024-11-16T10:30:00Z"},
            }
        }
        result = _parse_commit_date(commit)
        assert result is not None
        assert result == date(2024, 11, 16)

    def test_no_date(self):
        commit = {"commit": {"author": {}, "committer": {}}}
        assert _parse_commit_date(commit) is None

    def test_empty_commit(self):
        assert _parse_commit_date({}) is None

    def test_non_dict_input(self):
        assert _parse_commit_date(None) is None
        assert _parse_commit_date("string") is None
        assert _parse_commit_date([]) is None


class TestExtractAuthorId:
    """_extract_author_id 함수 테스트"""

    def test_login_priority(self):
        commit = {
            "author": {"login": "octocat"},
            "commit": {
                "author": {
                    "email": "octocat@github.com",
                    "name": "Octo Cat",
                }
            },
        }
        result = _extract_author_id(commit)
        assert result == "login:octocat"

    def test_email_fallback(self):
        commit = {
            "author": {},
            "commit": {
                "author": {
                    "email": "user@example.com",
                    "name": "User Name",
                }
            },
        }
        result = _extract_author_id(commit)
        assert result == "email:user@example.com"

    def test_email_lowercase(self):
        commit = {
            "author": {},
            "commit": {"author": {"email": "USER@EXAMPLE.COM"}},
        }
        result = _extract_author_id(commit)
        assert result == "email:user@example.com"

    def test_name_fallback(self):
        commit = {
            "author": {},
            "commit": {"author": {"name": "John Doe"}},
        }
        result = _extract_author_id(commit)
        assert result == "name:John Doe"

    def test_no_author_info(self):
        commit = {"author": {}, "commit": {"author": {}}}
        assert _extract_author_id(commit) is None

    def test_whitespace_handling(self):
        commit = {"author": {"login": "  spaced  "}}
        result = _extract_author_id(commit)
        assert result == "login:spaced"

    def test_non_dict_input(self):
        assert _extract_author_id(None) is None
        assert _extract_author_id("string") is None


class TestComputeCommitActivity:
    """compute_commit_activity 함수 테스트"""

    def _make_commit(self, login: str, date_str: str) -> dict:
        """테스트용 커밋 객체 생성"""
        return {
            "author": {"login": login},
            "commit": {
                "author": {"date": date_str},
                "committer": {"date": date_str},
            },
        }

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_basic_metrics(self, mock_fetch):
        mock_fetch.return_value = [
            self._make_commit("user1", "2024-11-15T10:00:00Z"),
            self._make_commit("user2", "2024-11-14T10:00:00Z"),
            self._make_commit("user1", "2024-11-13T10:00:00Z"),
        ]

        result = compute_commit_activity("owner", "repo", days=30)

        assert result.total_commits == 3
        assert result.unique_authors == 2
        assert result.window_days == 30
        assert result.commits_per_day == pytest.approx(0.1, rel=0.01)
        assert result.commits_per_week == pytest.approx(0.7, rel=0.01)

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_first_last_commit_dates(self, mock_fetch):
        mock_fetch.return_value = [
            self._make_commit("user1", "2024-11-20T10:00:00Z"),
            self._make_commit("user2", "2024-11-10T10:00:00Z"),
            self._make_commit("user1", "2024-11-15T10:00:00Z"),
        ]

        result = compute_commit_activity("owner", "repo", days=30)

        assert result.first_commit_date == date(2024, 11, 10)
        assert result.last_commit_date == date(2024, 11, 20)

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_empty_commits(self, mock_fetch):
        mock_fetch.return_value = []

        result = compute_commit_activity("owner", "repo", days=30)

        assert result.total_commits == 0
        assert result.unique_authors == 0
        assert result.commits_per_day == 0.0
        assert result.commits_per_week == 0.0
        assert result.days_since_last_commit is None
        assert result.first_commit_date is None
        assert result.last_commit_date is None

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_api_error_handling(self, mock_fetch):
        mock_fetch.side_effect = Exception("API Error")

        result = compute_commit_activity("owner", "repo", days=30)

        assert result.total_commits == 0
        assert result.unique_authors == 0
        assert result.owner == "owner"
        assert result.repo == "repo"

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_unique_authors_deduplication(self, mock_fetch):
        mock_fetch.return_value = [
            self._make_commit("user1", "2024-11-15T10:00:00Z"),
            self._make_commit("user1", "2024-11-14T10:00:00Z"),
            self._make_commit("user1", "2024-11-13T10:00:00Z"),
            self._make_commit("user2", "2024-11-12T10:00:00Z"),
        ]

        result = compute_commit_activity("owner", "repo", days=30)

        assert result.total_commits == 4
        assert result.unique_authors == 2

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_days_since_last_commit(self, mock_fetch):
        today = datetime.now(timezone.utc).date()
        yesterday = today.replace(day=today.day - 1) if today.day > 1 else today

        mock_fetch.return_value = [
            self._make_commit("user1", f"{yesterday.isoformat()}T10:00:00Z"),
        ]

        result = compute_commit_activity("owner", "repo", days=30)

        assert result.days_since_last_commit is not None
        assert result.days_since_last_commit >= 0
        assert result.days_since_last_commit <= 2

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_minimum_window_days(self, mock_fetch):
        mock_fetch.return_value = []

        result = compute_commit_activity("owner", "repo", days=0)

        assert result.window_days == 1

    @patch("backend.agents.diagnosis.tools.scoring.chaoss_metrics.fetch_recent_commits")
    def test_to_dict(self, mock_fetch):
        mock_fetch.return_value = [
            self._make_commit("user1", "2024-11-15T10:00:00Z"),
        ]

        result = compute_commit_activity("owner", "repo", days=30)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["owner"] == "owner"
        assert result_dict["repo"] == "repo"
        assert result_dict["total_commits"] == 1
        assert "unique_authors" in result_dict
        assert "commits_per_day" in result_dict


class TestIntegration:
    """실제 API 호출 통합 테스트"""

    def test_real_api_call(self):
        result = compute_commit_activity("Hyeri-hci", "OSSDoctor", days=90)

        print(f"\n[Integration Test Result]")
        print(f"  Owner/Repo: {result.owner}/{result.repo}")
        print(f"  Window: {result.window_days} days")
        print(f"  Total Commits: {result.total_commits}")
        print(f"  Unique Authors: {result.unique_authors}")
        print(f"  Commits/Day: {result.commits_per_day:.2f}")
        print(f"  Commits/Week: {result.commits_per_week:.2f}")
        print(f"  Days Since Last: {result.days_since_last_commit}")
        print(f"  First Commit: {result.first_commit_date}")
        print(f"  Last Commit: {result.last_commit_date}")

        assert result.total_commits >= 0
        assert result.unique_authors >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



