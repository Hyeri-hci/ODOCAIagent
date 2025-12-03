"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .readme.readme_lang_normalizer import (
    detect_readme_language,
    translate_section_to_english_for_rules,
)

__all__ = [
    "detect_readme_language",
    "translate_section_to_english_for_rules",
]
