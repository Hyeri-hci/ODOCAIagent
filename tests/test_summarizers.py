"""Summarizers 모듈 단위 테스트."""
import pytest
from unittest.mock import patch, MagicMock

from backend.agents.supervisor.nodes.summarizers.common import (
    LLMCallResult,
    extract_target_metrics,
    METRIC_NOT_FOUND_MESSAGE,
)


class TestLLMCallResult:
    """LLMCallResult 데이터클래스 테스트."""
    
    def test_success_result(self):
        result = LLMCallResult(content="테스트 응답", success=True)
        assert result.success is True
        assert result.content == "테스트 응답"
        assert result.retried is False
        assert result.degraded is False
    
    def test_failure_result(self):
        result = LLMCallResult(content="", success=False, retried=True, degraded=True)
        assert result.success is False
        assert result.content == ""
        assert result.retried is True
        assert result.degraded is True


class TestExtractTargetMetrics:
    """메트릭 추출 테스트."""
    
    def test_health_score_extraction(self):
        """health_score 추출."""
        query = "health score가 뭐야?"
        metrics = extract_target_metrics(query)
        assert len(metrics) > 0
    
    def test_empty_query(self):
        """빈 쿼리."""
        metrics = extract_target_metrics("")
        assert metrics == []
    
    def test_no_metrics(self):
        """메트릭 없는 쿼리."""
        query = "안녕하세요"
        metrics = extract_target_metrics(query)
        assert metrics == []


class TestMetricNotFoundMessage:
    """메트릭 미발견 메시지 테스트."""
    
    def test_message_format(self):
        """메시지 형식 확인."""
        assert "지표가 계산되지 않은" in METRIC_NOT_FOUND_MESSAGE
        assert "{metrics}" in METRIC_NOT_FOUND_MESSAGE


class TestSummarizerModuleImports:
    """모듈 import 테스트."""
    
    def test_overview_import(self):
        """overview 모듈 import."""
        from backend.agents.supervisor.nodes.summarizers.overview import handle_overview_mode
        assert callable(handle_overview_mode)
    
    def test_followup_import(self):
        """followup 모듈 import."""
        from backend.agents.supervisor.nodes.summarizers.followup import handle_followup_evidence_mode
        assert callable(handle_followup_evidence_mode)
    
    def test_refine_import(self):
        """refine 모듈 import."""
        from backend.agents.supervisor.nodes.summarizers.refine import handle_refine_mode
        assert callable(handle_refine_mode)
    
    def test_summarize_node_import(self):
        """메인 summarize_node import."""
        from backend.agents.supervisor.nodes.summarize_node import summarize_node
        assert callable(summarize_node)
