"""Diagnosis 설정 로더: YAML 설정 파일 로드 및 캐시."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml


CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "diagnosis.config.yaml"


@lru_cache(maxsize=1)
def load_diagnosis_config() -> Dict[str, Any]:
    """diagnosis.config.yaml 로드 (캐시됨)."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


def get_config_hash() -> str:
    """설정 파일의 SHA256 해시 반환 (재현성 보증용)."""
    if not CONFIG_FILE.exists():
        return "config_not_found"
    
    with open(CONFIG_FILE, "rb") as f:
        content = f.read()
    
    return hashlib.sha256(content).hexdigest()[:16]


def reload_config() -> Dict[str, Any]:
    """캐시를 무효화하고 설정 다시 로드."""
    load_diagnosis_config.cache_clear()
    return load_diagnosis_config()


def get_marketing_config() -> Dict[str, Any]:
    """마케팅 편향 설정 반환."""
    config = load_diagnosis_config()
    return config.get("marketing", {})


def get_consilience_config() -> Dict[str, Any]:
    """교차검증 설정 반환."""
    config = load_diagnosis_config()
    return config.get("consilience", {})


def get_freshness_config() -> Dict[str, Any]:
    """문서 최신성 설정 반환."""
    config = load_diagnosis_config()
    return config.get("freshness", {})


def get_docs_config() -> Dict[str, Any]:
    """유효 문서 점수 설정 반환."""
    config = load_diagnosis_config()
    return config.get("docs", {})


def get_gate_config() -> Dict[str, Any]:
    """지속성 게이트 설정 반환."""
    config = load_diagnosis_config()
    return config.get("gate", {})


def get_labels_config() -> Dict[str, Any]:
    """라벨 임계값 설정 반환."""
    config = load_diagnosis_config()
    return config.get("labels", {})


def get_tech_patterns() -> Dict[str, list]:
    """기술 신호 패턴 반환."""
    config = load_diagnosis_config()
    return config.get("tech_patterns", {})


def get_marketing_keywords() -> Dict[str, list]:
    """마케팅 키워드 반환."""
    config = load_diagnosis_config()
    return config.get("marketing_keywords", {})


def get_readme_preference() -> list:
    """README 우선순위 반환."""
    config = load_diagnosis_config()
    return config.get("readme", {}).get("prefer", ["README.md"])
