"""
Onboarding Recommender LLM 단위 테스트

LLM 보강 및 Fallback 로직 테스트.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.agents.diagnosis.tools.onboarding_tasks import (
    TaskSuggestion,
    OnboardingTasks,
)
from backend.agents.diagnosis.tools.onboarding_recommender_llm import (
    EnrichedTask,
    OnboardingScenario,
    LLMEnrichedTasks,
    _create_fallback_enrichment,
    _create_fallback_scenario,
    _extract_json,
    _estimate_time_from_level,
    _parse_enrichment_response,
    enrich_onboarding_tasks,
)


# ============================================================
# 헬퍼 함수 테스트
# ============================================================

class TestExtractJson:
    """JSON 추출 테스트."""
    
    def test_extract_json_block(self):
        text = '''Here is the result:
```json
{"key": "value"}
```
Done!'''
        result = _extract_json(text)
        assert '{"key": "value"}' == result
    
    def test_extract_plain_json(self):
        text = 'Some text {"key": "value"} more text'
        result = _extract_json(text)
        assert '{"key": "value"}' in result
    
    def test_extract_code_block(self):
        text = '''```
{"key": "value"}
```'''
        result = _extract_json(text)
        assert '{"key": "value"}' == result


class TestEstimateTime:
    """시간 추정 테스트."""
    
    def test_level_1(self):
        assert "30분" in _estimate_time_from_level(1)
    
    def test_level_3(self):
        assert "시간" in _estimate_time_from_level(3)
    
    def test_level_6(self):
        assert "일" in _estimate_time_from_level(6)


# ============================================================
# Fallback 테스트
# ============================================================

class TestFallbackEnrichment:
    """Fallback enrichment 테스트."""
    
    def test_creates_enriched_tasks(self):
        task = TaskSuggestion(
            kind="issue",
            difficulty="beginner",
            level=1,
            id="issue#1",
            title="Test",
            reason_tags=["good_first_issue"],
            meta_flags=[],
            fallback_reason="테스트 이유",
        )
        tasks = OnboardingTasks(
            beginner=[task],
            intermediate=[],
            advanced=[],
        )
        
        result = _create_fallback_enrichment(tasks)
        
        assert "issue#1" in result.enriched_tasks
        assert result.enriched_tasks["issue#1"].reason_text == "테스트 이유"
        assert result.enriched_tasks["issue#1"].priority_rank == 1
        assert len(result.top_3_tasks) == 1
    
    def test_top_3_prefers_beginner(self):
        beginner = TaskSuggestion(kind="issue", difficulty="beginner", level=1, id="b1", title="B", fallback_reason="B")
        intermediate = TaskSuggestion(kind="issue", difficulty="intermediate", level=3, id="i1", title="I", fallback_reason="I")
        
        tasks = OnboardingTasks(
            beginner=[beginner],
            intermediate=[intermediate],
            advanced=[],
        )
        
        result = _create_fallback_enrichment(tasks)
        
        # beginner 우선
        assert result.top_3_tasks[0] == "b1"


class TestFallbackScenario:
    """Fallback scenario 테스트."""
    
    def test_creates_scenario(self):
        task = TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=1,
            id="meta:readme",
            title="README 개선",
            fallback_reason="문서 개선 필요",
        )
        tasks = OnboardingTasks(beginner=[task], intermediate=[], advanced=[])
        enriched = _create_fallback_enrichment(tasks)
        
        scenario = _create_fallback_scenario(tasks, enriched, "owner/repo")
        
        assert "온보딩" in scenario.title or "로드맵" in scenario.title
        assert len(scenario.steps) >= 2
        assert len(scenario.tips) >= 1


# ============================================================
# 모델 테스트
# ============================================================

class TestEnrichedTask:
    """EnrichedTask 모델 테스트."""
    
    def test_to_dict(self):
        task = EnrichedTask(
            task_id="issue#1",
            reason_text="테스트 이유",
            priority_rank=1,
            estimated_time="1시간",
            prerequisites=["환경 설정"],
        )
        
        d = task.to_dict()
        assert d["task_id"] == "issue#1"
        assert d["reason_text"] == "테스트 이유"
        assert d["estimated_time"] == "1시간"


class TestOnboardingScenario:
    """OnboardingScenario 모델 테스트."""
    
    def test_to_dict(self):
        scenario = OnboardingScenario(
            title="테스트 로드맵",
            summary="요약",
            steps=[{"step": "1단계", "task_id": None, "description": "설명"}],
            tips=["팁1"],
        )
        
        d = scenario.to_dict()
        assert d["title"] == "테스트 로드맵"
        assert len(d["steps"]) == 1
        assert len(d["tips"]) == 1


class TestLLMEnrichedTasks:
    """LLMEnrichedTasks 모델 테스트."""
    
    def test_to_dict(self):
        enriched = LLMEnrichedTasks(
            enriched_tasks={
                "issue#1": EnrichedTask(task_id="issue#1", reason_text="이유", priority_rank=1)
            },
            scenario=OnboardingScenario(title="로드맵", summary="요약"),
            top_3_tasks=["issue#1"],
        )
        
        d = enriched.to_dict()
        assert "issue#1" in d["enriched_tasks"]
        assert d["scenario"]["title"] == "로드맵"
        assert d["top_3_tasks"] == ["issue#1"]


# ============================================================
# 응답 파싱 테스트
# ============================================================

class TestParseEnrichmentResponse:
    """LLM 응답 파싱 테스트."""
    
    def test_valid_json(self):
        response = '''```json
{
  "enriched_tasks": [
    {"task_id": "issue#1", "reason_text": "좋은 이슈", "priority_rank": 1}
  ],
  "top_3_tasks": ["issue#1"]
}
```'''
        tasks = [TaskSuggestion(kind="issue", difficulty="beginner", level=1, id="issue#1", title="T")]
        
        result = _parse_enrichment_response(response, tasks)
        
        assert "issue#1" in result.enriched_tasks
        assert result.enriched_tasks["issue#1"].reason_text == "좋은 이슈"
    
    def test_invalid_json_uses_fallback(self):
        response = "invalid json"
        task = TaskSuggestion(
            kind="issue", difficulty="beginner", level=1, 
            id="issue#1", title="T", fallback_reason="기본 이유"
        )
        
        result = _parse_enrichment_response(response, [task])
        
        # Fallback 사용
        assert "issue#1" in result.enriched_tasks
        assert result.enriched_tasks["issue#1"].reason_text == "기본 이유"


# ============================================================
# 통합 테스트 (LLM 모킹)
# ============================================================

class TestEnrichOnboardingTasks:
    """enrich_onboarding_tasks 통합 테스트."""
    
    def test_use_llm_false(self):
        """LLM 비활성화 시 Fallback 사용."""
        task = TaskSuggestion(
            kind="issue",
            difficulty="beginner",
            level=1,
            id="issue#1",
            title="Test",
            fallback_reason="Fallback 이유",
        )
        tasks = OnboardingTasks(beginner=[task], intermediate=[], advanced=[])
        
        result = enrich_onboarding_tasks(
            tasks=tasks,
            repo="owner/repo",
            use_llm=False,
        )
        
        assert "enriched_tasks" in result
        assert "issue#1" in result["enriched_tasks"]
        assert result["enriched_tasks"]["issue#1"]["reason_text"] == "Fallback 이유"
        assert result["scenario"] is not None
    
    @patch("backend.llm.factory.fetch_llm_client")
    def test_llm_failure_uses_fallback(self, mock_fetch):
        """LLM 실패 시 Fallback 사용."""
        mock_fetch.side_effect = Exception("LLM unavailable")
        
        task = TaskSuggestion(
            kind="issue",
            difficulty="beginner",
            level=1,
            id="issue#1",
            title="Test",
            fallback_reason="Fallback 이유",
        )
        tasks = OnboardingTasks(beginner=[task], intermediate=[], advanced=[])
        
        result = enrich_onboarding_tasks(
            tasks=tasks,
            repo="owner/repo",
            use_llm=True,
        )
        
        # Fallback 사용됨
        assert "enriched_tasks" in result
        assert result["enriched_tasks"]["issue#1"]["reason_text"] == "Fallback 이유"
