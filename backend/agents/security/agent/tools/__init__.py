"""
Security Analysis Agent Tools
"""
from .github_tools import (
    fetch_repository_tree,
    fetch_file_content,
    find_dependency_files,
    check_is_lockfile,
    validate_repository_access
)

from .dependency_tools import (
    analyze_dependencies,
    extract_dependencies_from_file,
    filter_by_source,
    filter_by_type,
    find_outdated_deps,
    count_by_language,
    summarize_analysis
)

from .assessment_tools import (
    calculate_security_score,
    suggest_improvements,
    check_license_compliance,
    assess_risk_level
)

from .report_tools import (
    generate_executive_summary,
    generate_dependency_report,
    generate_recommendations_report,
    generate_full_report,
    export_report
)


# GitHub 툴
GITHUB_TOOLS = [
    fetch_repository_tree,
    fetch_file_content,
    find_dependency_files,
    check_is_lockfile,
    validate_repository_access
]

# 의존성 분석 툴
DEPENDENCY_TOOLS = [
    analyze_dependencies,
    extract_dependencies_from_file,
    filter_by_source,
    filter_by_type,
    find_outdated_deps,
    count_by_language,
    summarize_analysis
]

# 보안 평가 툴
ASSESSMENT_TOOLS = [
    calculate_security_score,
    suggest_improvements,
    check_license_compliance,
    assess_risk_level
]

# 레포트 생성 툴
REPORT_TOOLS = [
    generate_executive_summary,
    generate_dependency_report,
    generate_recommendations_report,
    generate_full_report,
    export_report
]

# 모든 툴 (CPE/NVD 제외)
ALL_TOOLS = GITHUB_TOOLS + DEPENDENCY_TOOLS + ASSESSMENT_TOOLS + REPORT_TOOLS

__all__ = [
    # GitHub Tools
    'fetch_repository_tree',
    'fetch_file_content',
    'find_dependency_files',
    'check_is_lockfile',
    'validate_repository_access',
    # Dependency Tools
    'analyze_dependencies',
    'extract_dependencies_from_file',
    'filter_by_source',
    'filter_by_type',
    'find_outdated_deps',
    'count_by_language',
    'summarize_analysis',
    # Assessment Tools
    'calculate_security_score',
    'suggest_improvements',
    'check_license_compliance',
    'assess_risk_level',
    # Report Tools
    'generate_executive_summary',
    'generate_dependency_report',
    'generate_recommendations_report',
    'generate_full_report',
    'export_report',
    # Tool Lists
    'GITHUB_TOOLS',
    'DEPENDENCY_TOOLS',
    'ASSESSMENT_TOOLS',
    'REPORT_TOOLS',
    'ALL_TOOLS'
]
