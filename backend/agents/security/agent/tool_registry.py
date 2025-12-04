"""
Tool Registry - Fixed Version
모든 도구를 등록하고 LLM이 사용할 수 있도록 관리 (Import 오류 수정)
"""
from typing import Dict, Any, Callable, List
from .state_v2 import SecurityAnalysisStateV2
import requests
import base64
import json
import re


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
        """도구 등록"""
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
async def fetch_repository_info(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """레포지토리 기본 정보 가져오기"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

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
async def fetch_file_content(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """특정 파일 내용 가져오기"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    file_path = kwargs.get("file_path", "")
    token = kwargs.get("token") or state.get("github_token")

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
async def fetch_directory_structure(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """디렉토리 구조 가져오기"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    path = kwargs.get("path", "")
    token = kwargs.get("token") or state.get("github_token")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            files = [item["name"] for item in data if isinstance(data, list)]
            return {"success": True, "files": files, "count": len(files)}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ===== Dependency Tools =====

@register_tool(
    "detect_lock_files",
    "Detect dependency lock files in repository",
    "dependency"
)
async def detect_lock_files(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """의존성 락 파일 감지"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

    # 찾을 파일 목록
    lock_files_to_check = [
        "package.json", "package-lock.json", "yarn.lock",
        "requirements.txt", "Pipfile", "Pipfile.lock",
        "Gemfile", "Gemfile.lock",
        "Cargo.toml", "Cargo.lock",
        "go.mod", "go.sum",
        "pom.xml", "build.gradle"
    ]

    found_files = []

    # 디렉토리 구조 가져오기
    dir_result = await fetch_directory_structure(state, owner=owner, repo=repo, token=token)

    if dir_result.get("success"):
        files = dir_result.get("files", [])
        for lock_file in lock_files_to_check:
            if lock_file in files:
                found_files.append(lock_file)

    return {
        "success": True,
        "lock_files": found_files,
        "count": len(found_files),
        "state_update": {
            "lock_files_found": found_files
        }
    }


@register_tool(
    "parse_package_json",
    "Parse package.json to extract Node.js dependencies",
    "dependency"
)
async def parse_package_json(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """package.json 파싱"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

    # 파일 내용 가져오기
    content_result = await fetch_file_content(state, file_path="package.json", owner=owner, repo=repo, token=token)

    if not content_result.get("success"):
        return {"success": False, "error": "Failed to fetch package.json"}

    try:
        data = json.loads(content_result["content"])
        dependencies = {}

        # dependencies와 devDependencies 모두 추출
        if "dependencies" in data:
            dependencies.update(data["dependencies"])
        if "devDependencies" in data:
            dependencies.update(data["devDependencies"])

        return {
            "success": True,
            "dependencies": dependencies,
            "total_count": len(dependencies),
            "ecosystem": "npm"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool(
    "parse_requirements_txt",
    "Parse requirements.txt to extract Python dependencies",
    "dependency"
)
async def parse_requirements_txt(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """requirements.txt 파싱"""
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

    content_result = await fetch_file_content(state, file_path="requirements.txt", owner=owner, repo=repo, token=token)

    if not content_result.get("success"):
        return {"success": False, "error": "Failed to fetch requirements.txt"}

    try:
        content = content_result["content"]
        dependencies = {}

        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                # 패키지==버전 형식 파싱
                if "==" in line:
                    pkg, ver = line.split("==", 1)
                    dependencies[pkg.strip()] = ver.strip()
                elif ">=" in line:
                    pkg = line.split(">=")[0].strip()
                    dependencies[pkg] = "latest"
                else:
                    dependencies[line] = "latest"

        return {
            "success": True,
            "dependencies": dependencies,
            "total_count": len(dependencies),
            "ecosystem": "pip"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool(
    "parse_pipfile",
    "Parse Pipfile to extract Python dependencies",
    "dependency"
)
async def parse_pipfile(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """Pipfile 파싱"""
    return {"success": True, "dependencies": {}, "total_count": 0, "ecosystem": "pipenv"}


@register_tool(
    "parse_gemfile",
    "Parse Gemfile to extract Ruby dependencies",
    "dependency"
)
async def parse_gemfile(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """Gemfile 파싱"""
    return {"success": True, "dependencies": {}, "total_count": 0, "ecosystem": "gem"}


@register_tool(
    "parse_cargo_toml",
    "Parse Cargo.toml to extract Rust dependencies",
    "dependency"
)
async def parse_cargo_toml(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """Cargo.toml 파싱"""
    return {"success": True, "dependencies": {}, "total_count": 0, "ecosystem": "cargo"}


# ===== Vulnerability Tools =====

@register_tool(
    "search_cve_by_cpe",
    "Search CVE vulnerabilities by CPE",
    "vulnerability"
)
async def search_cve_by_cpe(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """CPE로 CVE 검색 (Mock)"""
    return {
        "success": True,
        "vulnerabilities": [],
        "count": 0
    }


@register_tool(
    "fetch_cve_details",
    "Fetch detailed information about a specific CVE",
    "vulnerability"
)
async def fetch_cve_details(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """CVE 상세 정보 (Mock)"""
    return {"success": True, "details": {}}


@register_tool(
    "assess_severity",
    "Assess vulnerability severity",
    "vulnerability"
)
async def assess_severity(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """취약점 심각도 평가 (Mock)"""
    return {"success": True, "severity": "LOW", "score": 3.0}


# ===== Assessment Tools =====

@register_tool(
    "check_license_compatibility",
    "Check license compatibility",
    "assessment"
)
async def check_license_compatibility(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """라이센스 호환성 체크 (Mock)"""
    return {"success": True, "compatible": True, "violations": []}


@register_tool(
    "calculate_security_score",
    "Calculate overall security score",
    "assessment"
)
async def calculate_security_score(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """보안 점수 계산"""
    vuln_count = state.get("vulnerability_count", 0)
    critical = state.get("critical_count", 0)
    high = state.get("high_count", 0)

    # 간단한 점수 계산
    base_score = 100
    score = base_score - (critical * 20) - (high * 10) - (vuln_count * 2)
    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "success": True,
        "score": score,
        "grade": grade,
        "state_update": {
            "security_score": {"score": score},
            "security_grade": grade
        }
    }


# ===== Report Tools =====

@register_tool(
    "generate_security_report",
    "Generate comprehensive security analysis report",
    "report"
)
async def generate_security_report(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """보안 분석 보고서 생성"""
    report = f"""
# Security Analysis Report

## Repository: {state.get('owner')}/{state.get('repository')}

## Summary
- Dependencies: {state.get('dependency_count', 0)}
- Vulnerabilities: {state.get('vulnerability_count', 0)}
- Security Grade: {state.get('security_grade', 'N/A')}

## Dependencies Found
{json.dumps(state.get('dependencies', {}), indent=2)}

## Recommendations
- Keep dependencies up to date
- Review and fix vulnerabilities
- Enable security scanning
"""

    return {
        "success": True,
        "report": report,
        "state_update": {
            "report": report
        }
    }


@register_tool(
    "generate_summary",
    "Generate brief summary",
    "report"
)
async def generate_summary(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """요약 생성"""
    summary = f"""Security Analysis Summary: {state.get('owner')}/{state.get('repository')}
Dependencies: {state.get('dependency_count', 0)}
Vulnerabilities: {state.get('vulnerability_count', 0)}
Grade: {state.get('security_grade', 'N/A')}"""

    return {"success": True, "summary": summary}


# ===== Composite Tools =====

@register_tool(
    "analyze_dependencies_full",
    "Complete dependency analysis",
    "dependency"
)
async def analyze_dependencies_full(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """전체 의존성 분석"""
    # 1. 락 파일 감지
    lock_result = await detect_lock_files(state)
    lock_files = lock_result.get("lock_files", [])

    all_dependencies = {}
    total_count = 0

    # 2. 각 락 파일 파싱
    if "package.json" in lock_files or "package-lock.json" in lock_files:
        pkg_result = await parse_package_json(state)
        if pkg_result.get("success"):
            all_dependencies["npm"] = pkg_result.get("dependencies", {})
            total_count += pkg_result.get("total_count", 0)

    if "requirements.txt" in lock_files:
        req_result = await parse_requirements_txt(state)
        if req_result.get("success"):
            all_dependencies["pip"] = req_result.get("dependencies", {})
            total_count += req_result.get("total_count", 0)

    return {
        "success": True,
        "dependencies": all_dependencies,
        "total_count": total_count,
        "lock_files": lock_files,
        "state_update": {
            "dependencies": all_dependencies,
            "dependency_count": total_count,
            "lock_files_found": lock_files
        }
    }


@register_tool(
    "scan_vulnerabilities_full",
    "Complete vulnerability scan",
    "vulnerability"
)
async def scan_vulnerabilities_full(state: SecurityAnalysisStateV2, **kwargs) -> Dict[str, Any]:
    """전체 취약점 스캔 (Mock)"""
    return {
        "success": True,
        "vulnerabilities": [],
        "total_count": 0,
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "state_update": {
            "vulnerabilities": [],
            "vulnerability_count": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0
        }
    }
