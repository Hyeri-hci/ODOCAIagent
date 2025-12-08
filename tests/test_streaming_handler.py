"""스트리밍 진행 상황 핸들러 테스트."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import json
from backend.agents.supervisor.streaming_handler import (
    ProgressStreamHandler,
    ProgressEvent,
    ProgressEventType,
    NODE_PROGRESS_CONFIG,
    LangGraphProgressCallback,
)


class TestProgressEvent:
    """ProgressEvent 클래스 테스트."""

    def test_to_sse_format(self):
        """SSE 형식 변환 테스트."""
        event = ProgressEvent(
            event_type=ProgressEventType.NODE_START,
            node_name="run_diagnosis_node",
            message="저장소 진단 수행 중...",
            progress_percent=60,
        )
        sse = event.to_sse()
        
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        
        # JSON 파싱 가능 확인
        json_str = sse[6:-2]  # "data: " 제거, "\n\n" 제거
        data = json.loads(json_str)
        
        assert data["type"] == "node_start"
        assert data["node"] == "run_diagnosis_node"
        assert data["message"] == "저장소 진단 수행 중..."
        assert data["progress"] == 60

    def test_to_dict(self):
        """딕셔너리 변환 테스트."""
        event = ProgressEvent(
            event_type=ProgressEventType.NODE_COMPLETE,
            node_name="intent_analysis_node",
            message="의도 분석 완료",
            progress_percent=10,
            data={"intent": "diagnose"},
        )
        d = event.to_dict()
        
        assert d["type"] == "node_complete"
        assert d["node"] == "intent_analysis_node"
        assert d["data"] == {"intent": "diagnose"}

    def test_auto_timestamp(self):
        """타임스탬프 자동 생성 테스트."""
        event = ProgressEvent(
            event_type=ProgressEventType.ANALYSIS_START,
            message="분석 시작",
        )
        assert event.timestamp is not None
        assert len(event.timestamp) > 0


class TestProgressStreamHandler:
    """ProgressStreamHandler 클래스 테스트."""

    def test_on_analysis_start(self):
        """분석 시작 이벤트 테스트."""
        handler = ProgressStreamHandler(owner="facebook", repo="react")
        event = handler.on_analysis_start()
        
        assert event.event_type == ProgressEventType.ANALYSIS_START
        assert "facebook/react" in event.message
        assert event.progress_percent == 0

    def test_on_analysis_complete(self):
        """분석 완료 이벤트 테스트."""
        handler = ProgressStreamHandler(owner="facebook", repo="react")
        result = {"health_score": 85}
        event = handler.on_analysis_complete(result)
        
        assert event.event_type == ProgressEventType.ANALYSIS_COMPLETE
        assert event.progress_percent == 100
        assert event.data == result

    def test_on_node_start(self):
        """노드 시작 이벤트 테스트."""
        handler = ProgressStreamHandler()
        event = handler.on_node_start("run_diagnosis_node")
        
        assert event.event_type == ProgressEventType.NODE_START
        assert event.node_name == "run_diagnosis_node"
        assert "진단" in event.message

    def test_on_node_complete(self):
        """노드 완료 이벤트 테스트."""
        handler = ProgressStreamHandler()
        result = {"diagnosis_result": {"health_score": 80}}
        event = handler.on_node_complete("run_diagnosis_node", result)
        
        assert event.event_type == ProgressEventType.NODE_COMPLETE
        assert event.node_name == "run_diagnosis_node"
        assert event.data is not None

    def test_on_node_error(self):
        """노드 에러 이벤트 테스트."""
        handler = ProgressStreamHandler()
        event = handler.on_node_error("run_diagnosis_node", "Connection timeout")
        
        assert event.event_type == ProgressEventType.NODE_ERROR
        assert "오류" in event.message
        assert event.data["error"] == "Connection timeout"

    def test_on_warning(self):
        """경고 이벤트 테스트."""
        handler = ProgressStreamHandler()
        event = handler.on_warning("프로젝트 건강 점수가 낮습니다.")
        
        assert event.event_type == ProgressEventType.WARNING
        assert "건강 점수" in event.message

    def test_on_progress_update(self):
        """진행률 업데이트 이벤트 테스트."""
        handler = ProgressStreamHandler()
        event = handler.on_progress_update("분석 중...", 50, "run_diagnosis_node")
        
        assert event.event_type == ProgressEventType.PROGRESS_UPDATE
        assert event.progress_percent == 50

    def test_events_accumulated(self):
        """이벤트 누적 테스트."""
        handler = ProgressStreamHandler()
        
        handler.on_analysis_start()
        handler.on_node_start("intent_analysis_node")
        handler.on_node_complete("intent_analysis_node", {})
        handler.on_analysis_complete({})
        
        events = handler.get_all_events()
        assert len(events) == 4

    def test_callback_invocation(self):
        """콜백 호출 테스트."""
        handler = ProgressStreamHandler()
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        handler.add_callback(callback)
        
        handler.on_analysis_start()
        handler.on_node_start("test_node")
        
        assert len(received_events) == 2


class TestNodeProgressConfig:
    """노드별 진행 설정 테스트."""

    def test_all_main_nodes_have_config(self):
        """주요 노드들의 설정이 존재하는지 확인."""
        expected_nodes = [
            "intent_analysis_node",
            "decision_node",
            "run_diagnosis_node",
            "quality_check_node",
            "fetch_issues_node",
            "plan_onboarding_node",
            "chat_response_node",
        ]
        
        for node in expected_nodes:
            assert node in NODE_PROGRESS_CONFIG, f"Missing config for {node}"
            config = NODE_PROGRESS_CONFIG[node]
            assert "start_message" in config
            assert "complete_message" in config
            assert "progress_percent" in config

    def test_progress_increases(self):
        """진행률이 순차적으로 증가하는지 확인."""
        # 진단 플로우에서 진행률이 증가해야 함
        intent_progress = NODE_PROGRESS_CONFIG["intent_analysis_node"]["progress_percent"]
        decision_progress = NODE_PROGRESS_CONFIG["decision_node"]["progress_percent"]
        diagnosis_progress = NODE_PROGRESS_CONFIG["run_diagnosis_node"]["progress_percent"]
        quality_progress = NODE_PROGRESS_CONFIG["quality_check_node"]["progress_percent"]
        
        assert intent_progress < decision_progress < diagnosis_progress < quality_progress


class TestLangGraphProgressCallback:
    """LangGraph 콜백 통합 테스트."""

    def test_chain_start_triggers_analysis_start(self):
        """체인 시작 시 분석 시작 이벤트 발생."""
        handler = ProgressStreamHandler()
        callback = LangGraphProgressCallback(handler)
        
        callback.on_chain_start()
        
        events = handler.get_all_events()
        assert len(events) == 1
        assert events[0]["type"] == "analysis_start"

    def test_chain_end_triggers_analysis_complete(self):
        """체인 종료 시 분석 완료 이벤트 발생."""
        handler = ProgressStreamHandler()
        callback = LangGraphProgressCallback(handler)
        
        callback.on_chain_end(outputs={"result": "success"})
        
        events = handler.get_all_events()
        assert len(events) == 1
        assert events[0]["type"] == "analysis_complete"

    def test_tool_lifecycle(self):
        """도구 시작/종료 이벤트 테스트."""
        handler = ProgressStreamHandler()
        callback = LangGraphProgressCallback(handler)
        
        callback.on_tool_start("run_diagnosis_node")
        callback.on_tool_end("run_diagnosis_node", {"health_score": 80})
        
        events = handler.get_all_events()
        assert len(events) == 2
        assert events[0]["type"] == "node_start"
        assert events[1]["type"] == "node_complete"

    def test_tool_error(self):
        """도구 에러 이벤트 테스트."""
        handler = ProgressStreamHandler()
        callback = LangGraphProgressCallback(handler)
        
        callback.on_tool_error("run_diagnosis_node", Exception("Test error"))
        
        events = handler.get_all_events()
        assert len(events) == 1
        assert events[0]["type"] == "node_error"
