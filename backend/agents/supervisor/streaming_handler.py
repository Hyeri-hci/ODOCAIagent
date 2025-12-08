"""분석 진행 상황 스트리밍 핸들러.

LangGraph 노드 실행 진행 상황을 SSE로 스트리밍하는 핸들러입니다.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProgressEventType(str, Enum):
    """진행 상황 이벤트 타입."""
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"
    ANALYSIS_START = "analysis_start"
    ANALYSIS_COMPLETE = "analysis_complete"
    PROGRESS_UPDATE = "progress_update"
    WARNING = "warning"


@dataclass
class ProgressEvent:
    """진행 상황 이벤트 데이터."""
    event_type: ProgressEventType
    node_name: Optional[str] = None
    message: str = ""
    progress_percent: int = 0
    data: Optional[Dict[str, Any]] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_sse(self) -> str:
        """SSE 형식 문자열로 변환."""
        payload = {
            "type": self.event_type.value,
            "node": self.node_name,
            "message": self.message,
            "progress": self.progress_percent,
            "timestamp": self.timestamp,
        }
        if self.data:
            payload["data"] = self.data
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "type": self.event_type.value,
            "node": self.node_name,
            "message": self.message,
            "progress": self.progress_percent,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# 노드별 진행 메시지 및 진행률 매핑
NODE_PROGRESS_CONFIG = {
    "intent_analysis_node": {
        "start_message": "사용자 의도 분석 중...",
        "complete_message": "의도 분석 완료",
        "progress_percent": 10,
    },
    "decision_node": {
        "start_message": "다음 작업 결정 중...",
        "complete_message": "작업 결정 완료",
        "progress_percent": 15,
    },
    "run_diagnosis_node": {
        "start_message": "저장소 진단 수행 중...",
        "complete_message": "저장소 진단 완료",
        "progress_percent": 60,
    },
    "quality_check_node": {
        "start_message": "결과 품질 검사 중...",
        "complete_message": "품질 검사 완료",
        "progress_percent": 80,
    },
    "fetch_issues_node": {
        "start_message": "추천 이슈 수집 중...",
        "complete_message": "이슈 수집 완료",
        "progress_percent": 70,
    },
    "plan_onboarding_node": {
        "start_message": "온보딩 플랜 생성 중...",
        "complete_message": "온보딩 플랜 생성 완료",
        "progress_percent": 85,
    },
    "summarize_onboarding_plan_node": {
        "start_message": "플랜 요약 생성 중...",
        "complete_message": "플랜 요약 완료",
        "progress_percent": 95,
    },
    "batch_diagnosis_node": {
        "start_message": "여러 저장소 진단 중...",
        "complete_message": "일괄 진단 완료",
        "progress_percent": 70,
    },
    "compare_results_node": {
        "start_message": "비교 분석 생성 중...",
        "complete_message": "비교 분석 완료",
        "progress_percent": 90,
    },
    "chat_response_node": {
        "start_message": "응답 생성 중...",
        "complete_message": "응답 생성 완료",
        "progress_percent": 90,
    },
    "use_cached_result_node": {
        "start_message": "캐시 결과 로드 중...",
        "complete_message": "캐시 결과 로드 완료",
        "progress_percent": 50,
    },
}


class ProgressStreamHandler:
    """분석 진행 상황 스트리밍 핸들러.
    
    Usage:
        handler = ProgressStreamHandler()
        
        # 노드 시작 시
        event = handler.on_node_start("run_diagnosis_node")
        
        # 노드 완료 시
        event = handler.on_node_complete("run_diagnosis_node", {"health_score": 80})
        
        # SSE 스트리밍
        async for sse_data in handler.stream_events():
            yield sse_data
    """
    
    def __init__(self, owner: str = "", repo: str = ""):
        self.owner = owner
        self.repo = repo
        self.events: List[ProgressEvent] = []
        self.current_node: Optional[str] = None
        self._callbacks: List[Callable[[ProgressEvent], None]] = []
    
    def add_callback(self, callback: Callable[[ProgressEvent], None]) -> None:
        """이벤트 발생 시 호출할 콜백 등록."""
        self._callbacks.append(callback)
    
    def _emit(self, event: ProgressEvent) -> ProgressEvent:
        """이벤트 발생 및 콜백 호출."""
        self.events.append(event)
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Callback error: {e}")
        return event
    
    def on_analysis_start(self) -> ProgressEvent:
        """분석 시작 이벤트."""
        repo_id = f"{self.owner}/{self.repo}" if self.owner else "저장소"
        event = ProgressEvent(
            event_type=ProgressEventType.ANALYSIS_START,
            message=f"{repo_id} 분석을 시작합니다...",
            progress_percent=0,
        )
        return self._emit(event)
    
    def on_analysis_complete(self, result: Optional[Dict[str, Any]] = None) -> ProgressEvent:
        """분석 완료 이벤트."""
        repo_id = f"{self.owner}/{self.repo}" if self.owner else "저장소"
        event = ProgressEvent(
            event_type=ProgressEventType.ANALYSIS_COMPLETE,
            message=f"{repo_id} 분석이 완료되었습니다.",
            progress_percent=100,
            data=result,
        )
        return self._emit(event)
    
    def on_node_start(self, node_name: str) -> ProgressEvent:
        """노드 시작 이벤트."""
        self.current_node = node_name
        config = NODE_PROGRESS_CONFIG.get(node_name, {})
        message = config.get("start_message", f"{node_name} 실행 중...")
        
        event = ProgressEvent(
            event_type=ProgressEventType.NODE_START,
            node_name=node_name,
            message=message,
            progress_percent=config.get("progress_percent", 0) - 5,
        )
        logger.debug(f"Node start: {node_name}")
        return self._emit(event)
    
    def on_node_complete(
        self, 
        node_name: str, 
        result: Optional[Dict[str, Any]] = None
    ) -> ProgressEvent:
        """노드 완료 이벤트."""
        config = NODE_PROGRESS_CONFIG.get(node_name, {})
        message = config.get("complete_message", f"{node_name} 완료")
        
        # 결과에서 주요 정보 추출
        summary_data = None
        if result:
            summary_data = self._extract_summary(node_name, result)
        
        event = ProgressEvent(
            event_type=ProgressEventType.NODE_COMPLETE,
            node_name=node_name,
            message=message,
            progress_percent=config.get("progress_percent", 50),
            data=summary_data,
        )
        logger.debug(f"Node complete: {node_name}")
        return self._emit(event)
    
    def on_node_error(self, node_name: str, error: str) -> ProgressEvent:
        """노드 에러 이벤트."""
        event = ProgressEvent(
            event_type=ProgressEventType.NODE_ERROR,
            node_name=node_name,
            message=f"{node_name} 실행 중 오류 발생: {error}",
            data={"error": error},
        )
        logger.warning(f"Node error: {node_name} - {error}")
        return self._emit(event)
    
    def on_warning(self, message: str, node_name: Optional[str] = None) -> ProgressEvent:
        """경고 이벤트."""
        event = ProgressEvent(
            event_type=ProgressEventType.WARNING,
            node_name=node_name,
            message=message,
        )
        return self._emit(event)
    
    def on_progress_update(
        self, 
        message: str, 
        percent: int, 
        node_name: Optional[str] = None
    ) -> ProgressEvent:
        """진행률 업데이트 이벤트."""
        event = ProgressEvent(
            event_type=ProgressEventType.PROGRESS_UPDATE,
            node_name=node_name or self.current_node,
            message=message,
            progress_percent=percent,
        )
        return self._emit(event)
    
    def _extract_summary(self, node_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """노드별 결과 요약 추출."""
        if node_name == "run_diagnosis_node":
            diagnosis = result.get("diagnosis_result", {})
            return {
                "health_score": diagnosis.get("health_score"),
                "health_level": diagnosis.get("health_level"),
                "onboarding_score": diagnosis.get("onboarding_score"),
            }
        elif node_name == "intent_analysis_node":
            return {
                "intent": result.get("detected_intent"),
                "confidence": result.get("intent_confidence"),
                "analysis_depth": result.get("analysis_depth"),
            }
        elif node_name == "decision_node":
            return {
                "next_node": result.get("next_node_override"),
                "cache_hit": result.get("cache_hit"),
            }
        elif node_name == "fetch_issues_node":
            issues = result.get("candidate_issues", [])
            return {"issue_count": len(issues)}
        elif node_name == "batch_diagnosis_node":
            results = result.get("compare_results", {})
            return {"repo_count": len(results)}
        return {}
    
    def get_all_events(self) -> List[Dict[str, Any]]:
        """모든 이벤트를 딕셔너리 리스트로 반환."""
        return [event.to_dict() for event in self.events]
    
    async def stream_events(self) -> AsyncGenerator[str, None]:
        """저장된 모든 이벤트를 SSE 형식으로 스트리밍."""
        for event in self.events:
            yield event.to_sse()


class LangGraphProgressCallback:
    """LangGraph 콜백을 위한 진행 상황 추적기.
    
    LangGraph의 콜백 시스템과 통합하여 노드 실행 상황을 추적합니다.
    """
    
    def __init__(self, handler: ProgressStreamHandler):
        self.handler = handler
    
    def on_chain_start(self, *args, **kwargs) -> None:
        """체인 시작 시 호출."""
        self.handler.on_analysis_start()
    
    def on_chain_end(self, *args, **kwargs) -> None:
        """체인 종료 시 호출."""
        outputs = kwargs.get("outputs", {})
        self.handler.on_analysis_complete(outputs)
    
    def on_tool_start(self, tool_name: str, *args, **kwargs) -> None:
        """도구(노드) 시작 시 호출."""
        self.handler.on_node_start(tool_name)
    
    def on_tool_end(self, tool_name: str, output: Any, *args, **kwargs) -> None:
        """도구(노드) 종료 시 호출."""
        result = output if isinstance(output, dict) else {}
        self.handler.on_node_complete(tool_name, result)
    
    def on_tool_error(self, tool_name: str, error: Exception, *args, **kwargs) -> None:
        """도구(노드) 에러 시 호출."""
        self.handler.on_node_error(tool_name, str(error))
