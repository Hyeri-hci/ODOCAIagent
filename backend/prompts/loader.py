"""
프롬프트 로더 - YAML 파일에서 프롬프트 템플릿을 로드합니다.

사용 예시:
    from backend.prompts.loader import load_prompt, render_prompt
    
    prompt = load_prompt("diagnosis_summary")
    rendered = render_prompt("diagnosis_summary", "user_prompt_template", 
                             repo_id="test/repo", health_score=85, ...)
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# 프롬프트 디렉토리 경로
PROMPTS_DIR = Path(__file__).parent

# 캐시 (로드된 프롬프트)
_cache: Dict[str, Dict[str, Any]] = {}


def load_prompt(name: str, reload: bool = False) -> Dict[str, Any]:
    """
    YAML 프롬프트 파일 로드.
    
    Args:
        name: 프롬프트 이름 (확장자 제외)
        reload: True면 캐시 무시하고 다시 로드
    
    Returns:
        프롬프트 딕셔너리 (system_prompt, user_prompt_template, parameters 등)
    
    Raises:
        FileNotFoundError: 프롬프트 파일이 없는 경우
        yaml.YAMLError: YAML 파싱 실패
    """
    if not reload and name in _cache:
        return _cache[name]
    
    file_path = PROMPTS_DIR / f"{name}.yaml"
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        prompt_data = yaml.safe_load(f)
    
    _cache[name] = prompt_data
    return prompt_data


def render_prompt(name: str, template_key: str = "user_prompt_template", **kwargs) -> str:
    """
    프롬프트 템플릿 렌더링.
    
    Args:
        name: 프롬프트 이름
        template_key: 렌더링할 템플릿 키 (기본: user_prompt_template)
        **kwargs: 템플릿 변수
    
    Returns:
        렌더링된 프롬프트 문자열
    
    Raises:
        KeyError: 템플릿 키가 없는 경우
    """
    prompt = load_prompt(name)
    template = prompt.get(template_key)
    
    if template is None:
        raise KeyError(f"Template key '{template_key}' not found in prompt '{name}'")
    
    # 템플릿 변수 치환
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # 누락된 변수는 빈 문자열로 대체
        import re
        result = template
        for key in re.findall(r'\{(\w+)\}', template):
            if key not in kwargs:
                result = result.replace(f'{{{key}}}', kwargs.get(key, f'[{key}]'))
        return result


def get_system_prompt(name: str) -> str:
    """
    시스템 프롬프트 반환.
    
    Args:
        name: 프롬프트 이름
    
    Returns:
        시스템 프롬프트 문자열
    """
    prompt = load_prompt(name)
    return prompt.get("system_prompt", "")


def get_parameters(name: str) -> Dict[str, Any]:
    """
    프롬프트 파라미터 반환.
    
    Args:
        name: 프롬프트 이름
    
    Returns:
        파라미터 딕셔너리 (temperature, max_tokens 등)
    """
    prompt = load_prompt(name)
    return prompt.get("parameters", {})


def list_prompts() -> list:
    """
    사용 가능한 프롬프트 목록 반환.
    
    Returns:
        프롬프트 이름 리스트
    """
    prompts = []
    for file in PROMPTS_DIR.glob("*.yaml"):
        prompts.append(file.stem)
    return prompts


def clear_cache():
    """프롬프트 캐시 초기화."""
    _cache.clear()
