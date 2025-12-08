"""
Security analysis tools for AI agents
각 함수는 독립적으로 호출 가능한 툴로 설계되어 있습니다.
"""
from .dependency_analyzer import (
    analyze_repository_dependencies,
    get_dependencies_by_source,
    get_dependencies_by_type,
    get_outdated_dependencies,
    count_dependencies_by_language,
    summarize_dependency_analysis,
    find_dependency_files,
)

from .vulnerability_checker import (
    check_vulnerabilities,
    get_security_score,
    check_license_compliance,
    suggest_security_improvements,
)

__all__ = [
    # Dependency analysis tools
    'analyze_repository_dependencies',
    'get_dependencies_by_source',
    'get_dependencies_by_type',
    'get_outdated_dependencies',
    'count_dependencies_by_language',
    'summarize_dependency_analysis',
    'find_dependency_files',

    # Vulnerability and security tools
    'check_vulnerabilities',
    'get_security_score',
    'check_license_compliance',
    'suggest_security_improvements',
]
