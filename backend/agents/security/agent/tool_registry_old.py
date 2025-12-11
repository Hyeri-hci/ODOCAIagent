"""
Tool Registry
모든 도구를 등록하고 LLM이 사용할 수 있도록 관리
"""
from typing import Dict, Any, Callable, List
from .state import SecurityAnalysisState


class ToolRegistry:
    """도구 등록 및 관리"""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_descriptions: Dict[str, str] = {}
        self.tool_categories: Dict[str, List[str]] = {
            "github": [],
            "dependency": [],
            "vulnerability": [],
            "assessment": [],
            "report": []
        }

    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        category: str = "general"
    ):
        """
        도구 등록

        Args:
            name: 도구 이름
            func: 실행 함수
            description: 도구 설명
            category: 카테고리
        """
        self.tools[name] = func
        self.tool_descriptions[name] = description

        if category in self.tool_categories:
            self.tool_categories[category].append(name)

        print(f"[ToolRegistry] Registered '{name}' in category '{category}'")

    def get_tool(self, name: str) -> Callable:
        """도구 가져오기"""
        return self.tools.get(name)

    def get_all_tools(self) -> Dict[str, Callable]:
        """모든 도구 가져오기"""
        return self.tools

    def get_tool_list_for_llm(self) -> str:
        """LLM용 도구 목록 텍스트"""
        lines = []
        for category, tool_names in self.tool_categories.items():
            if tool_names:
                lines.append(f"\n{category.upper()} Tools:")
                for name in tool_names:
                    desc = self.tool_descriptions.get(name, "No description")
                    lines.append(f"  - {name}: {desc}")

        return "\n".join(lines)

    def get_tools_by_category(self, category: str) -> Dict[str, Callable]:
        """카테고리별 도구 가져오기"""
        tool_names = self.tool_categories.get(category, [])
        return {name: self.tools[name] for name in tool_names if name in self.tools}


# 전역 레지스트리 인스턴스
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """전역 레지스트리 가져오기"""
    return _global_registry


def register_tool(name: str, description: str, category: str = "general"):
    """데코레이터: 도구 등록"""
    def decorator(func: Callable):
        _global_registry.register(name, func, description, category)
        return func
    return decorator


# ===== GitHub Tools =====

@register_tool(
    "fetch_repository_info",
    "Fetch basic repository information (stars, forks, language, etc.)",
    "github"
)
async def fetch_repository_info(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """레포지토리 기본 정보 가져오기"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

    # GitHub API 호출 (간단한 구현)
    import requests

    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "name": data.get("name"),
                "language": data.get("language"),
                "stars": data.get("stargazers_count"),
                "forks": data.get("forks_count"),
                "description": data.get("description")
            }
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool(
    "fetch_file_content",
    "Fetch content of a specific file from repository",
    "github"
)
async def fetch_file_content(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """특정 파일 내용 가져오기"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    file_path = kwargs.get("file_path", "")
    token = kwargs.get("token") or state.get("github_token")

    import requests
    import base64

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
            return {"success": True, "content": content, "path": file_path}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool(
    "fetch_directory_structure",
    "Fetch directory structure of repository",
    "github"
)
async def fetch_directory_structure(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """디렉토리 구조 가져오기"""
    from ..tools.github_tools import fetch_directory_structure as original
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    path = kwargs.get("path", "")
    token = kwargs.get("token") or state.get("github_token")

    result = original(owner, repo, path, token)
    return result


# ===== Dependency Tools =====

@register_tool(
    "detect_lock_files",
    "Detect dependency lock files in repository (package-lock.json, requirements.txt, etc.)",
    "dependency"
)
async def detect_lock_files(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """의존성 락 파일 감지"""
    from ..tools.dependency_tools import detect_lock_files as original
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

    result = original(owner, repo, token)

    # 상태 업데이트 정보 반환
    return {
        "lock_files": result.get("lock_files", []),
        "state_update": {
            "lock_files_found": result.get("lock_files", [])
        }
    }


@register_tool(
    "parse_package_json",
    "Parse package.json to extract Node.js dependencies",
    "dependency"
)
async def parse_package_json(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """package.json 파싱"""
    from ..tools.dependency_tools import parse_package_json as original
    content = kwargs.get("content", "")

    if not content:
        # 상태에서 가져오기
        file_result = await fetch_file_content(state, file_path="package.json")
        content = file_result.get("content", "")

    result = original(content)
    return result


@register_tool(
    "parse_requirements_txt",
    "Parse requirements.txt to extract Python dependencies",
    "dependency"
)
async def parse_requirements_txt(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """requirements.txt 파싱"""
    from ..tools.dependency_tools import parse_requirements_txt as original
    content = kwargs.get("content", "")

    if not content:
        file_result = await fetch_file_content(state, file_path="requirements.txt")
        content = file_result.get("content", "")

    result = original(content)
    return result


@register_tool(
    "parse_pipfile",
    "Parse Pipfile/Pipfile.lock to extract Python dependencies",
    "dependency"
)
async def parse_pipfile(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """Pipfile 파싱"""
    from ..tools.dependency_tools import parse_pipfile as original
    content = kwargs.get("content", "")

    if not content:
        file_result = await fetch_file_content(state, file_path="Pipfile")
        content = file_result.get("content", "")

    result = original(content)
    return result


@register_tool(
    "parse_gemfile",
    "Parse Gemfile/Gemfile.lock to extract Ruby dependencies",
    "dependency"
)
async def parse_gemfile(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """Gemfile 파싱"""
    from ..tools.dependency_tools import parse_gemfile as original
    content = kwargs.get("content", "")

    if not content:
        file_result = await fetch_file_content(state, file_path="Gemfile")
        content = file_result.get("content", "")

    result = original(content)
    return result


@register_tool(
    "parse_cargo_toml",
    "Parse Cargo.toml to extract Rust dependencies",
    "dependency"
)
async def parse_cargo_toml(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """Cargo.toml 파싱"""
    from ..tools.dependency_tools import parse_cargo_toml as original
    content = kwargs.get("content", "")

    if not content:
        file_result = await fetch_file_content(state, file_path="Cargo.toml")
        content = file_result.get("content", "")

    result = original(content)
    return result


# ===== Vulnerability Tools =====

@register_tool(
    "search_cve_by_cpe",
    "Search CVE vulnerabilities by CPE (Common Platform Enumeration)",
    "vulnerability"
)
async def search_cve_by_cpe(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """CPE로 CVE 검색"""
    from ..tools.vulnerability_tools import search_cve_by_cpe as original
    cpe = kwargs.get("cpe", "")

    result = original(cpe)
    return result


@register_tool(
    "fetch_cve_details",
    "Fetch detailed information about a specific CVE",
    "vulnerability"
)
async def fetch_cve_details(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """CVE 상세 정보 가져오기"""
    from ..tools.vulnerability_tools import fetch_cve_details as original
    cve_id = kwargs.get("cve_id", "")

    result = original(cve_id)
    return result


@register_tool(
    "assess_severity",
    "Assess vulnerability severity and calculate risk score",
    "vulnerability"
)
async def assess_severity(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """취약점 심각도 평가"""
    from ..tools.vulnerability_tools import assess_severity as original
    cvss_score = kwargs.get("cvss_score", 0.0)
    exploitability = kwargs.get("exploitability", "unknown")

    result = original(cvss_score, exploitability)
    return result


# ===== Assessment Tools =====

@register_tool(
    "check_license_compatibility",
    "Check license compatibility and detect violations",
    "assessment"
)
async def check_license_compatibility(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """라이센스 호환성 체크"""
    from ..tools.assessment_tools import check_license_compatibility as original
    licenses = kwargs.get("licenses", [])
    project_license = kwargs.get("project_license", "MIT")

    result = original(licenses, project_license)
    return result


@register_tool(
    "calculate_security_score",
    "Calculate overall security score based on vulnerabilities and dependencies",
    "assessment"
)
async def calculate_security_score(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """보안 점수 계산"""
    from ..tools.assessment_tools import calculate_security_score as original

    # 상태에서 정보 가져오기
    vulnerability_count = state.get("vulnerability_count", 0)
    critical_count = state.get("critical_count", 0)
    high_count = state.get("high_count", 0)
    medium_count = state.get("medium_count", 0)
    low_count = state.get("low_count", 0)
    dependency_count = state.get("dependency_count", 0)

    result = original(
        vulnerability_count=vulnerability_count,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        dependency_count=dependency_count
    )

    return result


# ===== Report Tools =====

@register_tool(
    "generate_security_report",
    "Generate comprehensive security analysis report",
    "report"
)
async def generate_security_report(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """보안 분석 보고서 생성"""
    from ..tools.report_tools import generate_security_report as original

    # 상태에서 모든 정보 수집
    report_data = {
        "repository": f"{state.get('owner')}/{state.get('repository')}",
        "dependencies": state.get("dependencies", {}),
        "dependency_count": state.get("dependency_count", 0),
        "vulnerabilities": state.get("vulnerabilities", []),
        "vulnerability_count": state.get("vulnerability_count", 0),
        "critical_count": state.get("critical_count", 0),
        "high_count": state.get("high_count", 0),
        "medium_count": state.get("medium_count", 0),
        "low_count": state.get("low_count", 0),
        "security_score": state.get("security_score", {}),
        "security_grade": state.get("security_grade", ""),
        "license_info": state.get("license_info", {}),
        "recommendations": state.get("recommendations", [])
    }

    result = original(report_data)
    return result


@register_tool(
    "generate_summary",
    "Generate brief summary of security analysis",
    "report"
)
async def generate_summary(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """요약 생성"""
    summary = f"""Security Analysis Summary for {state.get('owner')}/{state.get('repository')}

Dependencies: {state.get('dependency_count', 0)}
Vulnerabilities: {state.get('vulnerability_count', 0)}
  - Critical: {state.get('critical_count', 0)}
  - High: {state.get('high_count', 0)}
  - Medium: {state.get('medium_count', 0)}
  - Low: {state.get('low_count', 0)}

Security Grade: {state.get('security_grade', 'N/A')}
Risk Level: {state.get('risk_level', 'N/A')}
"""

    return {"summary": summary}


# ===== Composite Tools (여러 도구 조합) =====

@register_tool(
    "analyze_dependencies_full",
    "Complete dependency analysis: detect lock files and parse all dependencies",
    "dependency"
)
async def analyze_dependencies_full(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """전체 의존성 분석"""
    results = {
        "lock_files": [],
        "dependencies": {},
        "total_count": 0
    }

    # 1. 락 파일 감지
    lock_result = await detect_lock_files(state)
    results["lock_files"] = lock_result.get("lock_files", [])

    # 2. 각 락 파일 파싱
    all_dependencies = {}

    for lock_file in results["lock_files"]:
        if "package.json" in lock_file or "package-lock.json" in lock_file:
            dep_result = await parse_package_json(state)
            all_dependencies["npm"] = dep_result.get("dependencies", {})

        elif "requirements.txt" in lock_file:
            dep_result = await parse_requirements_txt(state)
            all_dependencies["pip"] = dep_result.get("dependencies", {})

        elif "Pipfile" in lock_file:
            dep_result = await parse_pipfile(state)
            all_dependencies["pipenv"] = dep_result.get("dependencies", {})

        elif "Gemfile" in lock_file:
            dep_result = await parse_gemfile(state)
            all_dependencies["gem"] = dep_result.get("dependencies", {})

        elif "Cargo.toml" in lock_file:
            dep_result = await parse_cargo_toml(state)
            all_dependencies["cargo"] = dep_result.get("dependencies", {})

    results["dependencies"] = all_dependencies

    # 전체 개수
    total = sum(len(deps) for deps in all_dependencies.values())
    results["total_count"] = total

    return {
        **results,
        "state_update": {
            "dependencies": all_dependencies,
            "dependency_count": total,
            "lock_files_found": results["lock_files"]
        }
    }


@register_tool(
    "scan_vulnerabilities_full",
    "Complete vulnerability scan: search CVEs for all dependencies",
    "vulnerability"
)
async def scan_vulnerabilities_full(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """전체 취약점 스캔"""
    dependencies = state.get("dependencies", {})
    all_vulnerabilities = []

    # 각 의존성에 대해 CVE 검색
    for ecosystem, deps in dependencies.items():
        for package_name, version in deps.items():
            # CPE 생성 (간단한 버전)
            cpe = f"cpe:2.3:a:*:{package_name}:{version}:*:*:*:*:*:*:*"

            # CVE 검색
            cve_result = await search_cve_by_cpe(state, cpe=cpe)
            vulnerabilities = cve_result.get("vulnerabilities", [])

            for vuln in vulnerabilities:
                vuln["package"] = package_name
                vuln["version"] = version
                vuln["ecosystem"] = ecosystem
                all_vulnerabilities.append(vuln)

    # 심각도별 카운트
    severity_counts = {
        "critical": len([v for v in all_vulnerabilities if v.get("severity") == "CRITICAL"]),
        "high": len([v for v in all_vulnerabilities if v.get("severity") == "HIGH"]),
        "medium": len([v for v in all_vulnerabilities if v.get("severity") == "MEDIUM"]),
        "low": len([v for v in all_vulnerabilities if v.get("severity") == "LOW"])
    }

    return {
        "vulnerabilities": all_vulnerabilities,
        "total_count": len(all_vulnerabilities),
        "severity_counts": severity_counts,
        "state_update": {
            "vulnerabilities": all_vulnerabilities,
            "vulnerability_count": len(all_vulnerabilities),
            "critical_count": severity_counts["critical"],
            "high_count": severity_counts["high"],
            "medium_count": severity_counts["medium"],
            "low_count": severity_counts["low"]
        }
    }
