"""
LLM call wrapper to enforce AnswerContract and track events.

All LLM calls should be made through this module.
Responses without sources will be rejected.
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

# Set max retries from environment variable
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))
REQUIRE_SOURCES = os.getenv("LLM_REQUIRE_SOURCES", "true").lower() in ("1", "true")


def _build_contract_system_prompt(artifact_refs: List[ArtifactRef]) -> str:
    """Builds the system prompt to enforce the AnswerContract."""
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
    """Parses the LLM response into an AnswerContract."""
    # Attempt to extract JSON
    content = raw_content.strip()
    
    # Remove code blocks
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
            f"Failed to parse LLM response: {e}",
            kind=ErrorKind.INVALID_INPUT
        )
    except Exception as e:
        logger.error(f"Failed to create AnswerContract: {e}")
        raise AgentError(
            f"Failed to create AnswerContract: {e}",
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
    Makes an LLM call that enforces the AnswerContract.
    
    Args:
        prompt: The user prompt.
        context_artifacts: A list of artifacts that can be referenced.
        require_sources: If True, raises an error if sources are empty.
        max_retries: The maximum number of retries.
        temperature: The LLM temperature.
        max_tokens: The maximum number of tokens.
    
    Returns:
        A validated AnswerContract.
    
    Raises:
        AgentError: If parsing fails, sources are missing, or validation fails.
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
                
                # Parse the response
                answer = _parse_contract_response(response.content)
                
                # Validate sources
                if require_sources and REQUIRE_SOURCES:
                    if not answer.sources:
                        raise AgentError(
                            "Response is missing sources.",
                            kind=ErrorKind.INVALID_INPUT
                        )
                    
                    if not answer.validate_sources_match():
                        raise AgentError(
                            f"sources({len(answer.sources)}) and source_kinds({len(answer.source_kinds)}) length mismatch",
                            kind=ErrorKind.INVALID_INPUT
                        )
                    
                    # Validate that artifacts exist
                    if not ensure_artifacts_exist(answer.sources):
                        # Log a warning only, don't raise an error (LLM might hallucinate IDs)
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
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        raise AgentError(
            f"LLM call failed after {max_retries + 1} attempts: {last_error}",
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
    Makes a simple LLM call without enforcing a contract.
    
    Used for simple responses where source tracking is not needed.
    (e.g., concept explanations, general chat).
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
    Makes an LLM call that enforces a structured JSON output.
    
    Args:
        prompt: The user prompt.
        output_schema: The output JSON schema (as an example or description).
        system_prompt: An additional system prompt.
        temperature: The LLM temperature.
        max_tokens: The maximum number of tokens.
    
    Returns:
        A parsed JSON dictionary.
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
        
        # Parse JSON
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
                f"Failed to parse structured output: {e}",
                kind=ErrorKind.INVALID_INPUT
            )
        
        emit_event(
            EventType.LLM_CALL_FINISHED,
            actor="llm",
            outputs={"result_keys": list(result.keys()) if isinstance(result, dict) else "non-dict"},
            duration_ms=duration_ms,
        )
        
        return result
