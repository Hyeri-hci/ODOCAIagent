"""
공통 프롬프트 유틸리티 모듈.

모든 에이전트에서 사용할 수 있는 공통 프롬프트 템플릿과 유틸리티를 제공합니다.
"""
from typing import Dict, Any


# 표준 JSON 응답 지시문 (모든 프롬프트에 공통으로 사용)
JSON_RESPONSE_INSTRUCTION = """
응답 형식 제약:
- 반드시 단일 JSON 객체만 반환하세요.
- JSON 앞뒤에 설명, 마크다운, 코드 블록(```), 주석 등 추가 텍스트를 넣지 마세요.
- 모든 문자열 값은 큰따옴표로 감싸세요.
- boolean 값은 true 또는 false (소문자)로 표기하세요.
- null 값은 null (소문자)로 표기하세요.
"""


# JSON 배열 응답 지시문
JSON_ARRAY_INSTRUCTION = """
응답 형식 제약:
- 반드시 유효한 JSON 배열만 반환하세요.
- 마크다운 포맷(```json 등)을 사용하지 마세요. 순수 JSON만 반환하세요.
- 모든 문자열 값은 큰따옴표로 감싸세요.
"""


# 한국어 응답 지시문
KOREAN_RESPONSE_INSTRUCTION = """
응답 언어:
- 모든 응답은 한국어로 작성하세요.
- 기술 용어는 영어를 그대로 사용해도 됩니다.
"""


# 응답 스키마 정의
RESPONSE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "intent_parse": {
        "task_type": "string",
        "user_preferences": {"focus": "list", "ignore": "list"},
        "priority": "string",
        "initial_mode_hint": "string|null",
    },
    "reflection": {
        "should_replan": "boolean",
        "plan_adjustments": "list",
        "reflection_summary": "string",
    },
    "self_reflection": {
        "is_consistent": "boolean",
        "issues": "list",
        "suggestions": "list",
        "confidence": "float",
        "reasoning": "string",
    },
    "planning": {
        "primary_task_type": "string",
        "steps": "list",
        "secondary_tasks": "list",
        "suggested_sequence": "list",
        "estimated_duration": "int",
        "complexity": "string",
    },
    "validation": {
        "is_valid": "boolean",
        "issues": "list",
        "suggestions": "list",
        "confidence": "float",
    },
    "security_analysis": {
        "security_score": "int",
        "security_grade": "string",
        "vulnerabilities": "list",
        "recommendations": "list",
    },
}


def get_schema_description(schema_name: str) -> str:
    """스키마 이름으로 JSON 스키마 설명 반환."""
    schema = RESPONSE_SCHEMAS.get(schema_name, {})
    if not schema:
        return ""
    
    lines = ["예상 JSON 구조:"]
    lines.append("{")
    for key, value_type in schema.items():
        if isinstance(value_type, dict):
            lines.append(f'  "{key}": {{...}},')
        elif value_type == "list":
            lines.append(f'  "{key}": [...],')
        else:
            lines.append(f'  "{key}": <{value_type}>,')
    lines.append("}")
    
    return "\n".join(lines)


def build_json_prompt(base_prompt: str, schema_name: str = None) -> str:
    """기본 프롬프트에 JSON 응답 지시문과 스키마 설명을 추가."""
    parts = [base_prompt]
    
    if schema_name:
        schema_desc = get_schema_description(schema_name)
        if schema_desc:
            parts.append(schema_desc)
    
    parts.append(JSON_RESPONSE_INSTRUCTION)
    
    return "\n\n".join(parts)
