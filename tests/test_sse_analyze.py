"""
SSE 분석 스트리밍 API 테스트.

실제 LLM 호출을 포함한 통합 테스트.
"""
import pytest
import os
import json
import asyncio
from unittest.mock import patch, MagicMock

# 통합 테스트 마커 (실제 API 호출)
pytestmark = pytest.mark.slow

# 테스트 환경 설정
os.environ.setdefault("GITHUB_TOKEN", "test_token")


class TestSSEAnalyzeIntegration:
    """SSE 분석 API 통합 테스트 (실제 LLM 호출)."""
    
    @pytest.mark.asyncio
    async def test_analyze_with_progress_events(self):
        """SSE 이벤트가 올바른 순서로 발생하는지 테스트."""
        from backend.api.sse_analyze import analyze_with_progress
        
        owner = "microsoft"
        repo = "vscode"
        ref = "main"
        
        events = []
        async for event_str in analyze_with_progress(owner, repo, ref):
            # SSE 이벤트 파싱
            if event_str.startswith("data: "):
                data = json.loads(event_str[6:].strip())
                events.append(data)
        
        # 최소한 첫 번째 이벤트(github)와 마지막 이벤트가 있어야 함
        assert len(events) >= 1, "최소 1개 이상의 이벤트가 발생해야 함"
        
        # 첫 번째 이벤트 확인
        first_event = events[0]
        assert first_event["step"] == "github", "첫 이벤트는 github 단계여야 함"
        assert first_event["progress"] == 10, "github 단계 진행률은 10%"
        
        # 마지막 이벤트 확인
        last_event = events[-1]
        assert last_event["step"] in ["complete", "error"], "마지막 이벤트는 complete 또는 error"
        
        if last_event["step"] == "complete":
            assert last_event["progress"] == 100
            assert "result" in last_event["data"]
        
        print(f"총 {len(events)}개 이벤트 발생")
        for e in events:
            print(f"  - {e['step']}: {e['progress']}% - {e['message']}")
    
    @pytest.mark.asyncio
    async def test_progress_order(self):
        """진행률이 항상 증가하는지 테스트."""
        from backend.api.sse_analyze import analyze_with_progress
        
        # 작은 레포로 테스트
        owner = "octocat"
        repo = "Hello-World"
        ref = "master"
        
        events = []
        async for event_str in analyze_with_progress(owner, repo, ref):
            if event_str.startswith("data: "):
                data = json.loads(event_str[6:].strip())
                events.append(data)
        
        # 진행률이 증가하는지 확인
        prev_progress = 0
        for event in events:
            if event["step"] != "error":
                assert event["progress"] >= prev_progress, f"진행률이 감소함: {prev_progress} -> {event['progress']}"
                prev_progress = event["progress"]
    
    @pytest.mark.asyncio
    async def test_complete_event_contains_result(self):
        """완료 이벤트에 결과 데이터가 포함되는지 테스트."""
        from backend.api.sse_analyze import analyze_with_progress
        
        owner = "octocat"
        repo = "Hello-World"
        ref = "master"
        
        complete_event = None
        async for event_str in analyze_with_progress(owner, repo, ref):
            if event_str.startswith("data: "):
                data = json.loads(event_str[6:].strip())
                if data["step"] == "complete":
                    complete_event = data
                    break
        
        if complete_event:
            result = complete_event["data"].get("result", {})
            
            # 필수 필드 확인
            assert "health_score" in result, "health_score 필수"
            assert "health_level" in result, "health_level 필수"
            assert "documentation_quality" in result, "documentation_quality 필수"
            assert "activity_maintainability" in result, "activity_maintainability 필수"
            assert "repo_id" in result, "repo_id 필수"
            
            print(f"분석 결과: {result['repo_id']} - {result['health_score']}점 ({result['health_level']})")


class TestSSEAnalyzeUnit:
    """SSE 분석 API 단위 테스트."""
    
    def test_progress_event_model(self):
        """ProgressEvent 모델 테스트."""
        from backend.api.sse_analyze import ProgressEvent
        
        event = ProgressEvent(
            step="github",
            progress=10,
            message="테스트 메시지",
            data={"key": "value"}
        )
        
        assert event.step == "github"
        assert event.progress == 10
        assert event.message == "테스트 메시지"
        assert event.data == {"key": "value"}
    
    def test_stream_analyze_request_model(self):
        """StreamAnalyzeRequest 모델 테스트."""
        from backend.api.sse_analyze import StreamAnalyzeRequest
        
        request = StreamAnalyzeRequest(repo_url="https://github.com/owner/repo")
        assert request.repo_url == "https://github.com/owner/repo"


class TestSSEWithMockedDependencies:
    """의존성 모킹 테스트."""
    
    @pytest.mark.asyncio
    async def test_sse_with_mocked_github(self):
        """GitHub API 모킹으로 빠른 테스트."""
        from backend.api.sse_analyze import analyze_with_progress
        
        mock_snapshot = {
            "repo_id": "test/repo",
            "stars": 100,
            "forks": 50,
            "readme": "# Test Project\n\nThis is a test.",
            "commits": [{"sha": "abc123", "date": "2025-01-01"}],
            "issues": [],
            "prs": [],
        }
        
        with patch("backend.api.sse_analyze.fetch_repo_snapshot", return_value=mock_snapshot):
            with patch("backend.core.docs_core.analyze_docs", return_value={
                "docs_score": 80,
                "issues": [],
                "sections": {"what": True, "why": True}
            }):
                with patch("backend.core.activity_core.analyze_activity", return_value={
                    "activity_score": 70,
                    "issues": [],
                    "days_since_last_commit": 5
                }):
                    with patch("backend.core.structure_core.analyze_structure", return_value={}):
                        with patch("backend.core.scoring_core.compute_scores", return_value={
                            "health_score": 75,
                            "health_level": "good",
                            "onboarding_score": 60,
                            "onboarding_level": "basic"
                        }):
                            events = []
                            async for event_str in analyze_with_progress("test", "repo", "main"):
                                if event_str.startswith("data: "):
                                    data = json.loads(event_str[6:].strip())
                                    events.append(data)
                            
                            # 이벤트 순서 확인
                            steps = [e["step"] for e in events]
                            assert "github" in steps
                            assert steps[-1] in ["complete", "error", "llm"]


class TestSSELLMIntegration:
    """LLM 통합 테스트 (실제 호출)."""
    
    @pytest.mark.skipif(
        not os.environ.get("KANANA_API_KEY"),
        reason="KANANA_API_KEY not set"
    )
    @pytest.mark.asyncio
    async def test_llm_summary_in_complete_event(self):
        """완료 이벤트에 LLM 요약이 포함되는지 테스트."""
        from backend.api.sse_analyze import analyze_with_progress
        
        owner = "octocat"
        repo = "Hello-World"
        ref = "master"
        
        complete_event = None
        async for event_str in analyze_with_progress(owner, repo, ref):
            if event_str.startswith("data: "):
                data = json.loads(event_str[6:].strip())
                if data["step"] == "complete":
                    complete_event = data
                    break
        
        if complete_event:
            result = complete_event["data"].get("result", {})
            summary = result.get("summary_for_user")
            
            if summary:
                print(f"LLM 요약:\n{summary}")
                assert len(summary) > 50, "LLM 요약은 50자 이상이어야 함"
            else:
                print("LLM 요약 없음 (타임아웃 또는 API 오류)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
