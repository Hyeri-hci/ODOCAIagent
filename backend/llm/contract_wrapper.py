"""
LLM 호출 래퍼 - AnswerContract 강제 및 이벤트 추적.

모든 LLM 호출은 이 모듈을 통해 수행되어야 함.
출처(sources)가 없는 응답은 거부됨.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from backend.agents.shared.contracts import (
    AnswerContract,
    ArtifactRef,
    AgentError,
    ErrorKind,
)
from backend.common.events import (
    EventType,
    emit_event,
    ensure_artifacts_exist,
    get_artifact_store,
    span,
)
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

logger = logging.getLogger(__name__)

# 환경변수로 재시도 횟수 설정
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))
REQUIRE_SOURCES = os.getenv("LLM_REQUIRE_SOURCES", "true").lower() in ("1", "true")


def _build_contract_system_prompt(artifact_refs: List[ArtifactRef]) -> str:
    """AnswerContract 강제를 위한 시스템 프롬프트 생성."""
    artifact_list = "\n".join([
        f"- id: {ref.id}, kind: {ref.kind.value if hasattr(ref.kind, 'value') else ref.kind}"
        for ref in artifact_refs
    ])
    
    return f"""당신은 ODOC 플랫폼의 AI 어시스턴트입니다.

## 응답 규칙 (필수!)
반드시 아래 JSON 스키마로만 응답하세요. 다른 형식은 허용되지 않습니다.

```json
{{
  "text": "사용자에게 보여줄 응답 텍스트 (마크다운 가능)",
  "sources": ["artifact_id_1", "artifact_id_2"],
  "source_kinds": ["artifact_kind_1", "artifact_kind_2"]
}}
```

## 출처 규칙
- sources에는 반드시 참조한 artifact ID를 포함해야 합니다.
- source_kinds에는 해당 artifact의 종류를 포함해야 합니다.
- sources와 source_kinds의 길이는 반드시 동일해야 합니다.
- 출처 없이 응답하면 거부됩니다.

## 사용 가능한 Artifacts
{artifact_list}

## 주의사항
- JSON 외의 텍스트를 포함하지 마세요.
- 코드 블록 마커(```)를 사용하지 마세요.
- 반드시 위 스키마를 준수하세요.
"""


def _parse_contract_response(raw_content: str) -> AnswerContract:
    """LLM 응답을 AnswerContract로 파싱."""
    # JSON 추출 시도
    content = raw_content.strip()
    
    # 코드 블록 제거
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    
    try:
        data = json.loads(content)
        return AnswerContract(**data)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Raw content: {raw_content[:500]}")
        raise AgentError(
            f"LLM 응답 파싱 실패: {e}",
            kind=ErrorKind.INVALID_INPUT
        )
    except Exception as e:
        logger.error(f"Failed to create AnswerContract: {e}")
        raise AgentError(
            f"AnswerContract 생성 실패: {e}",
            kind=ErrorKind.INVALID_INPUT
        )


def generate_answer_with_contract(
    prompt: str,
    context_artifacts: List[ArtifactRef],
    *,
    require_sources: bool = True,
    max_retries: int = MAX_RETRIES,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> AnswerContract:
    """
    AnswerContract를 강제하는 LLM 호출.
    
    Args:
        prompt: 사용자 프롬프트
        context_artifacts: 참조 가능한 artifact 목록
        require_sources: True면 sources가 비어있을 때 에러 발생
        max_retries: 최대 재시도 횟수
        temperature: LLM temperature
        max_tokens: 최대 토큰 수
    
    Returns:
        AnswerContract: 검증된 응답
    
    Raises:
        AgentError: 파싱 실패, 출처 누락, 검증 실패 시
    """
    with span("generate_answer_with_contract", actor="llm"):
        client = fetch_llm_client()
        
        system_prompt = _build_contract_system_prompt(context_artifacts)
        
        emit_event(
            EventType.LLM_CALL_STARTED,
            actor="llm",
            inputs={
                "prompt_length": len(prompt),
                "artifact_count": len(context_artifacts),
                "temperature": temperature,
            }
        )
        
        last_error: Optional[Exception] = None
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                request = ChatRequest(
                    messages=[
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                response = client.chat(request)
                
                # 응답 파싱
                answer = _parse_contract_response(response.content)
                
                # 출처 검증
                if require_sources and REQUIRE_SOURCES:
                    if not answer.sources:
                        raise AgentError(
                            "응답에 출처(sources)가 없습니다.",
                            kind=ErrorKind.INVALID_INPUT
                        )
                    
                    if not answer.validate_sources_match():
                        raise AgentError(
                            f"sources({len(answer.sources)})와 source_kinds({len(answer.source_kinds)}) 길이 불일치",
                            kind=ErrorKind.INVALID_INPUT
                        )
                    
                    # Artifact 존재 검증
                    if not ensure_artifacts_exist(answer.sources):
                        # 경고만 로그, 에러는 발생시키지 않음 (LLM이 생성한 ID일 수 있음)
                        logger.warning(f"Some artifacts not found: {answer.sources}")
                
                duration_ms = (time.time() - start_time) * 1000
                
                emit_event(
                    EventType.LLM_CALL_FINISHED,
                    actor="llm",
                    outputs={
                        "response_length": len(answer.text),
                        "source_count": len(answer.sources),
                    },
                    artifacts_in=[ref.id for ref in context_artifacts],
                    artifacts_out=answer.sources,
                    duration_ms=duration_ms,
                )
                
                emit_event(
                    EventType.ANSWER_VALIDATED,
                    outputs={
                        "sources": answer.sources,
                        "source_kinds": answer.source_kinds,
                    },
                    artifacts_in=answer.sources,
                )
                
                return answer
                
            except AgentError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))  # 백오프
        
        # 모든 재시도 실패
        raise AgentError(
            f"LLM 호출 실패 ({max_retries + 1}회 시도): {last_error}",
            kind=ErrorKind.TIMEOUT
        )


def generate_simple_answer(
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """
    단순 LLM 호출 (Contract 강제 없음).
    
    출처 추적이 필요 없는 간단한 응답에 사용.
    예: 개념 설명, 일반 대화 등
    """
    with span("generate_simple_answer", actor="llm"):
        client = fetch_llm_client()
        
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt))
        
        emit_event(
            EventType.LLM_CALL_STARTED,
            actor="llm",
            inputs={"prompt_length": len(prompt), "has_system": bool(system_prompt)}
        )
        
        start_time = time.time()
        
        request = ChatRequest(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        response = client.chat(request)
        duration_ms = (time.time() - start_time) * 1000
        
        emit_event(
            EventType.LLM_CALL_FINISHED,
            actor="llm",
            outputs={"response_length": len(response.content)},
            duration_ms=duration_ms,
        )
        
        return response.content


def generate_structured_output(
    prompt: str,
    output_schema: Dict[str, Any],
    *,
    system_prompt: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    """
    구조화된 JSON 출력을 강제하는 LLM 호출.
    
    Args:
        prompt: 사용자 프롬프트
        output_schema: 출력 JSON 스키마 (예시 또는 설명)
        system_prompt: 추가 시스템 프롬프트
        temperature: LLM temperature
        max_tokens: 최대 토큰 수
    
    Returns:
        파싱된 JSON 딕셔너리
    """
    schema_str = json.dumps(output_schema, indent=2, ensure_ascii=False)
    
    full_system = f"""반드시 아래 JSON 스키마로만 응답하세요. 다른 형식은 허용되지 않습니다.

스키마:
{schema_str}

주의사항:
- JSON 외의 텍스트를 포함하지 마세요.
- 코드 블록 마커를 사용하지 마세요.
"""
    
    if system_prompt:
        full_system = f"{system_prompt}\n\n{full_system}"
    
    with span("generate_structured_output", actor="llm"):
        client = fetch_llm_client()
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=full_system),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        emit_event(
            EventType.LLM_CALL_STARTED,
            actor="llm",
            inputs={"prompt_length": len(prompt), "schema_keys": list(output_schema.keys())}
        )
        
        start_time = time.time()
        response = client.chat(request)
        duration_ms = (time.time() - start_time) * 1000
        
        # JSON 파싱
        content = response.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse structured output: {e}")
            logger.debug(f"Raw content: {response.content[:500]}")
            raise AgentError(
                f"구조화된 출력 파싱 실패: {e}",
                kind=ErrorKind.INVALID_INPUT
            )
        
        emit_event(
            EventType.LLM_CALL_FINISHED,
            actor="llm",
            outputs={"result_keys": list(result.keys()) if isinstance(result, dict) else "non-dict"},
            duration_ms=duration_ms,
        )
        
        return result
