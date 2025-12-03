"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
from .readme.readme_categories import (
    ReadmeCategory,
    CategoryInfo,
    SectionClassification,
    classify_readme_sections,
)

__all__ = [
    "ReadmeCategory",
    "CategoryInfo",
    "SectionClassification",
    "classify_readme_sections",
]
