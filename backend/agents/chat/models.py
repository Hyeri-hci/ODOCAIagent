"""Chat Agent 데이터 모델."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


ChatIntent = Literal["chat", "explain", "onboard", "unknown"]


class ChatInput(BaseModel):
    """채팅 입력 모델."""
    message: str = Field(..., description="사용자 메시지")
    owner: str = Field(default="", description="저장소 소유자")
    repo: str = Field(default="", description="저장소 이름")
    intent: ChatIntent = Field(default="chat", description="감지된 의도")
    diagnosis_result: Dict[str, Any] = Field(default_factory=dict, description="진단 결과 (있으면)")
    chat_context: Dict[str, Any] = Field(default_factory=dict, description="채팅 컨텍스트")
    candidate_issues: List[Dict[str, Any]] = Field(default_factory=list, description="추천 이슈")


class ChatOutput(BaseModel):
    """채팅 출력 모델."""
    response: str = Field(default="", description="생성된 응답")
    intent: ChatIntent = Field(default="chat", description="처리된 의도")
    error: Optional[str] = Field(default=None, description="에러 메시지")
