"""성능 메트릭 추적 테스트."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import time
from backend.common.metrics import (
    MetricsTracker,
    TaskMetrics,
    get_metrics_tracker,
)


class TestTaskMetrics:
    """TaskMetrics 데이터 클래스 테스트."""

    def test_create_metrics(self):
        metrics = TaskMetrics(
            task_id="test-1",
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
        )
        assert metrics.task_id == "test-1"
        assert metrics.task_type == "diagnose_repo"
        assert metrics.start_time > 0

    def test_complete_success(self):
        metrics = TaskMetrics(
            task_id="test-1",
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
        )
        time.sleep(0.01)
        metrics.complete(success=True)
        
        assert metrics.success is True
        assert metrics.error is None
        assert metrics.end_time is not None
        assert metrics.duration_ms > 0

    def test_complete_with_error(self):
        metrics = TaskMetrics(
            task_id="test-1",
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
        )
        metrics.complete(success=False, error="Test error")
        
        assert metrics.success is False
        assert metrics.error == "Test error"

    def test_add_step_timing(self):
        metrics = TaskMetrics(
            task_id="test-1",
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
        )
        metrics.add_step_timing("fetch_snapshot", 1.234)
        metrics.add_step_timing("analyze_docs", 0.567)
        
        assert metrics.step_timings["fetch_snapshot"] == 1234.0
        assert metrics.step_timings["analyze_docs"] == 567.0

    def test_add_llm_call(self):
        metrics = TaskMetrics(
            task_id="test-1",
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
        )
        metrics.add_llm_call(0.5)
        metrics.add_llm_call(0.3)
        
        assert metrics.llm_calls == 2
        assert metrics.llm_total_time_ms == 800.0

    def test_to_dict(self):
        metrics = TaskMetrics(
            task_id="test-1",
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="diagnose",
            cache_hit=True,
        )
        data = metrics.to_dict()
        
        assert data["task_id"] == "test-1"
        assert data["detected_intent"] == "diagnose"
        assert data["cache_hit"] is True


class TestMetricsTracker:
    """MetricsTracker 싱글톤 테스트."""

    def setup_method(self):
        MetricsTracker.reset_instance()

    def test_singleton(self):
        tracker1 = get_metrics_tracker()
        tracker2 = get_metrics_tracker()
        assert tracker1 is tracker2

    def test_start_task(self):
        tracker = get_metrics_tracker()
        metrics = tracker.start_task("diagnose_repo", "owner", "repo")
        
        assert metrics.task_type == "diagnose_repo"
        assert metrics.owner == "owner"
        assert metrics.repo == "repo"
        assert "diagnose_repo_owner_repo_" in metrics.task_id

    def test_record_task(self):
        tracker = get_metrics_tracker()
        metrics = tracker.start_task("diagnose_repo", "owner", "repo")
        metrics.detected_intent = "diagnose"
        metrics.complete(success=True)
        
        tracker.record_task(metrics)
        
        recent = tracker.get_recent_metrics(limit=1)
        assert len(recent) == 1
        assert recent[0]["task_type"] == "diagnose_repo"
        assert recent[0]["detected_intent"] == "diagnose"

    def test_get_summary_empty(self):
        tracker = get_metrics_tracker()
        summary = tracker.get_summary()
        assert summary["total_tasks"] == 0

    def test_get_summary_with_data(self):
        tracker = get_metrics_tracker()
        
        for i in range(5):
            metrics = tracker.start_task("diagnose_repo", "owner", f"repo{i}")
            metrics.detected_intent = "diagnose" if i < 3 else "onboard"
            metrics.cache_hit = i % 2 == 0
            metrics.llm_calls = 1
            metrics.llm_total_time_ms = 100.0
            metrics.complete(success=i < 4)
            tracker.record_task(metrics)
        
        summary = tracker.get_summary()
        
        assert summary["total_tasks"] == 5
        assert summary["successful"] == 4
        assert summary["success_rate"] == 80.0
        assert summary["total_llm_calls"] == 5
        assert summary["by_intent"]["diagnose"] == 3
        assert summary["by_intent"]["onboard"] == 2

    def test_clear(self):
        tracker = get_metrics_tracker()
        metrics = tracker.start_task("test", "owner", "repo")
        metrics.complete()
        tracker.record_task(metrics)
        
        tracker.clear()
        
        assert tracker.get_summary()["total_tasks"] == 0

    def test_max_history_limit(self):
        tracker = get_metrics_tracker()
        tracker._max_history = 10
        
        for i in range(15):
            metrics = tracker.start_task("test", "owner", f"repo{i}")
            metrics.complete()
            tracker.record_task(metrics)
        
        recent = tracker.get_recent_metrics(limit=100)
        assert len(recent) == 10


class TestActivityOptimization:
    """활동성 분석 최적화 테스트."""

    def test_analyze_activity_optimized_exists(self):
        from backend.core.activity_core import analyze_activity_optimized
        assert callable(analyze_activity_optimized)

    def test_fetch_activity_summary_import(self):
        from backend.common.github_client import fetch_activity_summary
        assert callable(fetch_activity_summary)

