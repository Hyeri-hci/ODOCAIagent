"""Prompts 패키지 - 프롬프트 템플릿 관리."""
from backend.prompts.loader import (
    load_prompt,
    render_prompt,
    get_system_prompt,
    get_parameters,
    list_prompts,
    clear_cache,
)
from backend.prompts.common import (
    JSON_RESPONSE_INSTRUCTION,
    JSON_ARRAY_INSTRUCTION,
    KOREAN_RESPONSE_INSTRUCTION,
    RESPONSE_SCHEMAS,
    get_schema_description,
    build_json_prompt,
)

__all__ = [
    # Loader functions
    "load_prompt",
    "render_prompt",
    "get_system_prompt",
    "get_parameters",
    "list_prompts",
    "clear_cache",
    # Common utilities
    "JSON_RESPONSE_INSTRUCTION",
    "JSON_ARRAY_INSTRUCTION",
    "KOREAN_RESPONSE_INSTRUCTION",
    "RESPONSE_SCHEMAS",
    "get_schema_description",
    "build_json_prompt",
]
