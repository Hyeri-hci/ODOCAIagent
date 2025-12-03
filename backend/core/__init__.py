"""Core domain layer - LLM/LangGraph 의존성 없음."""
from .models import (
    RepoSnapshot,
    DependencyInfo,
    DependencySnapshot,
    DocsCoreResult,
    ActivityCoreResult,
    DiagnosisCoreResult,
    StructureCoreResult,
    ProjectRules,
    UserGuidelines,
)
from .github_core import fetch_repo_snapshot, verify_repo_access
from .docs_core import analyze_documentation
from .activity_core import analyze_activity
from .structure_core import analyze_structure, analyze_structure_from_snapshot
from .scoring_core import compute_diagnosis
from .dependencies_core import parse_dependencies

__all__ = [
    # Models
    "RepoSnapshot",
    "DependencyInfo",
    "DependencySnapshot",
    "DocsCoreResult",
    "ActivityCoreResult",
    "DiagnosisCoreResult",
    "StructureCoreResult",
    "ProjectRules",
    "UserGuidelines",
    # Functions
    "fetch_repo_snapshot",
    "verify_repo_access",
    "analyze_documentation",
    "analyze_activity",
    "analyze_structure",
    "analyze_structure_from_snapshot",
    "compute_diagnosis",
    "parse_dependencies",
]
