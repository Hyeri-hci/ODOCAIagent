"""sustainability_gate 모듈 테스트."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from backend.agents.diagnosis.tools.readme.sustainability_gate import (
    check_sustainability_gate,
    SustainabilityGateResult,
    _days_since,
    _determine_gate_level,
)


class TestDaysSince:
    """날짜 계산 테스트."""
    
    def test_recent_date(self):
        """최근 날짜."""
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        assert _days_since(recent) == 5
    
    def test_old_date(self):
        """오래된 날짜."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        assert _days_since(old) == 100
    
    def test_none_returns_max(self):
        """None은 최대값 반환."""
        assert _days_since(None) == 999


class TestDetermineGateLevel:
    """게이트 레벨 결정 테스트."""
    
    def test_active_level(self):
        """active 레벨 (최근 커밋, 많은 커밋)."""
        level = _determine_gate_level(
            days_since_commit=10,
            total_commits=50,
            unique_authors=5,
            config={"active_threshold_days": 30, "maintained_threshold_days": 90, "stale_threshold_days": 180},
        )
        assert level == "active"
    
    def test_maintained_level(self):
        """maintained 레벨 (60일 전 커밋)."""
        level = _determine_gate_level(
            days_since_commit=60,
            total_commits=30,
            unique_authors=3,
            config={"active_threshold_days": 30, "maintained_threshold_days": 90, "stale_threshold_days": 180},
        )
        assert level == "maintained"
    
    def test_stale_level(self):
        """stale 레벨 (120일 전 커밋)."""
        level = _determine_gate_level(
            days_since_commit=120,
            total_commits=20,
            unique_authors=2,
            config={"active_threshold_days": 30, "maintained_threshold_days": 90, "stale_threshold_days": 180},
        )
        assert level == "stale"
    
    def test_abandoned_level(self):
        """abandoned 레벨 (200일 전 커밋)."""
        level = _determine_gate_level(
            days_since_commit=200,
            total_commits=10,
            unique_authors=1,
            config={"active_threshold_days": 30, "maintained_threshold_days": 90, "stale_threshold_days": 180},
        )
        assert level == "abandoned"


class TestCheckSustainabilityGate:
    """게이트 체크 통합 테스트."""
    
    def test_active_project(self):
        """활발한 프로젝트."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": (now - timedelta(days=5)).isoformat(),
                "total_commits": 100,
                "unique_authors": 10,
            },
            "issue": {
                "open_issues": 5,
                "closed_in_window": 3,
            },
            "pr": {
                "merged_in_window": 5,
            },
        }
        
        result = check_sustainability_gate(activity_data)
        
        assert result.is_sustainable == True
        assert result.gate_level == "active"
        assert result.sustainability_score >= 80
        assert len(result.warnings) == 0
    
    def test_stale_project(self):
        """정체된 프로젝트."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": (now - timedelta(days=150)).isoformat(),
                "total_commits": 15,
                "unique_authors": 2,
            },
            "issue": {
                "open_issues": 10,
                "closed_in_window": 0,
            },
            "pr": {
                "merged_in_window": 0,
            },
        }
        
        result = check_sustainability_gate(activity_data)
        
        assert result.is_sustainable == True  # 아직 180일 안됨
        assert result.gate_level == "stale"
        assert result.sustainability_score < 60
        assert len(result.warnings) > 0
    
    def test_abandoned_project(self):
        """방치된 프로젝트."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": (now - timedelta(days=365)).isoformat(),
                "total_commits": 5,
                "unique_authors": 1,
            },
            "issue": {
                "open_issues": 20,
                "closed_in_window": 0,
            },
            "pr": {
                "merged_in_window": 0,
            },
        }
        
        result = check_sustainability_gate(activity_data)
        
        assert result.is_sustainable == False
        assert result.gate_level == "abandoned"
        assert result.sustainability_score < 30
    
    def test_missing_commit_data(self):
        """커밋 데이터 없음."""
        activity_data = {
            "commit": {},
            "issue": {},
            "pr": {},
        }
        
        result = check_sustainability_gate(activity_data)
        
        assert result.is_sustainable == False
        assert result.gate_level == "abandoned"
    
    def test_result_serialization(self):
        """결과 직렬화 테스트."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": now.isoformat(),
                "total_commits": 50,
                "unique_authors": 5,
            },
        }
        
        result = check_sustainability_gate(activity_data)
        d = result.to_dict()
        
        assert "is_sustainable" in d
        assert "gate_level" in d
        assert "checks" in d
        assert "sustainability_score" in d


class TestGateChecks:
    """개별 게이트 체크 테스트."""
    
    def test_commit_gate_check(self):
        """커밋 게이트 체크."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": (now - timedelta(days=10)).isoformat(),
                "total_commits": 50,
                "unique_authors": 5,
            },
        }
        
        result = check_sustainability_gate(activity_data)
        
        commit_check = next((c for c in result.checks if c.name == "recent_commit"), None)
        assert commit_check is not None
        assert commit_check.passed == True
        assert commit_check.value == 10
    
    def test_min_commits_check(self):
        """최소 커밋 수 체크."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": now.isoformat(),
                "total_commits": 5,  # 부족
                "unique_authors": 1,
            },
        }
        
        result = check_sustainability_gate(activity_data)
        
        commits_check = next((c for c in result.checks if c.name == "min_commits"), None)
        assert commits_check is not None
        assert commits_check.passed == False
        assert "부족" in result.warnings[0] if result.warnings else True
    
    def test_issue_responsiveness_check(self):
        """이슈 응답성 체크."""
        now = datetime.now(timezone.utc)
        activity_data = {
            "commit": {
                "last_commit_date": now.isoformat(),
                "total_commits": 50,
                "unique_authors": 5,
            },
            "issue": {
                "open_issues": 10,
                "closed_in_window": 0,  # 응답 없음
            },
        }
        
        result = check_sustainability_gate(activity_data)
        
        # 이슈 경고 확인
        issue_warning = [w for w in result.warnings if "이슈" in w]
        assert len(issue_warning) > 0
