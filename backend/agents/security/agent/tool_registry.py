"""
Tool Registry - Fixed Version
모든 도구를 등록하고 LLM이 사용할 수 있도록 관리 (Import 오류 수정)
"""
from typing import Dict, Any, Callable, List
from .state import SecurityAnalysisState
from ..vulnerability.nvd_client import NvdClient
import requests
import base64
import json
import re

# Import from dependencies_core.py
from ....core.dependencies_core import parse_dependencies as core_parse_dependencies
from ....core.models import RepoSnapshot

# NVD Client 전역 인스턴스
_nvd_client = None

def get_nvd_client() -> NvdClient:
    """NVD 클라이언트 싱글톤 인스턴스"""
    global _nvd_client
    if _nvd_client is None:
        _nvd_client = NvdClient()
    return _nvd_client


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
async def fetch_repository_info(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def fetch_file_content(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def fetch_directory_structure(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def detect_lock_files(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def parse_package_json(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def parse_requirements_txt(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def parse_pipfile(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """Pipfile 파싱"""
    return {"success": True, "dependencies": {}, "total_count": 0, "ecosystem": "pipenv"}


@register_tool(
    "parse_gemfile",
    "Parse Gemfile to extract Ruby dependencies",
    "dependency"
)
async def parse_gemfile(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """Gemfile 파싱"""
    return {"success": True, "dependencies": {}, "total_count": 0, "ecosystem": "gem"}


@register_tool(
    "parse_cargo_toml",
    "Parse Cargo.toml to extract Rust dependencies",
    "dependency"
)
async def parse_cargo_toml(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """Cargo.toml 파싱"""
    return {"success": True, "dependencies": {}, "total_count": 0, "ecosystem": "cargo"}


@register_tool(
    "parse_dependencies",
    "Parse all dependency files in repository (requirements.txt, package.json, pyproject.toml)",
    "dependency"
)
async def parse_dependencies(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    의존성 파일 파싱 (dependencies_core.py 사용)

    RepoSnapshot을 생성하고 core_parse_dependencies를 호출하여
    레포지토리의 모든 의존성 파일을 파싱합니다.
    """
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")

    print(f"[parse_dependencies] Parsing dependencies for {owner}/{repo}")

    try:
        # RepoSnapshot 생성 (최소한의 정보만)
        repo_snapshot = RepoSnapshot(
            owner=owner,
            repo=repo,
            ref="main",  # 기본 브랜치
            full_name=f"{owner}/{repo}",
            description=None,
            stars=0,
            forks=0,
            open_issues=0,
            primary_language=None,
            created_at=None,
            pushed_at=None,
            is_archived=False,
            is_fork=False,
            readme_content=None,
            has_readme=False,
            license_spdx=None
        )

        # core_parse_dependencies 호출
        dependency_snapshot = core_parse_dependencies(repo_snapshot)

        # 결과를 tool_registry 형식으로 변환 (중복 제거)
        dependencies = {}
        unique_deps = {}  # {(ecosystem, name): version} 형식으로 중복 제거

        for dep in dependency_snapshot.dependencies:
            ecosystem = "npm" if "package.json" in dep.source else "pip"

            # 중복 제거: 같은 패키지가 여러 파일에 있을 경우 한 번만 카운트
            key = (ecosystem, dep.name)
            if key not in unique_deps:
                unique_deps[key] = dep.version or "latest"

        # unique_deps를 dependencies 형식으로 변환
        for (ecosystem, name), version in unique_deps.items():
            if ecosystem not in dependencies:
                dependencies[ecosystem] = {}
            dependencies[ecosystem][name] = version

        # 실제 고유 의존성 개수 계산
        actual_count = len(unique_deps)

        return {
            "success": True,
            "dependencies": dependencies,
            "total_count": actual_count,  # 중복 제거된 개수
            "analyzed_files": dependency_snapshot.analyzed_files,
            "parse_errors": dependency_snapshot.parse_errors,
            "state_update": {
                "dependencies": dependencies,
                "dependency_count": actual_count,  # 중복 제거된 개수
                "analyzed_files": dependency_snapshot.analyzed_files
            }
        }

    except Exception as e:
        error_msg = f"Failed to parse dependencies: {str(e)}"
        print(f"[parse_dependencies] Error: {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "dependencies": {},
            "total_count": 0
        }


# ===== Vulnerability Tools =====

@register_tool(
    "search_cve_by_cpe",
    "Search CVE vulnerabilities by product and version",
    "vulnerability"
)
async def search_cve_by_cpe(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    Product/Version으로 CVE 검색

    Args:
        product: 제품명 (예: lodash, react, node.js)
        version: 버전 (예: 4.17.0, 선택적)
        vendor: 벤더 (선택적)
    """
    product = kwargs.get("product")
    version = kwargs.get("version", "*")
    vendor = kwargs.get("vendor", "*")

    if not product:
        return {
            "success": False,
            "error": "Product name is required",
            "vulnerabilities": [],
            "count": 0
        }

    print(f"[search_cve_by_cpe] Searching vulnerabilities for {product}@{version}")

    # NVD Client 사용
    client = get_nvd_client()
    result = client.get_product_vulnerabilities(
        product=product,
        version=version,
        vendor=vendor
    )

    return {
        "success": result.get("success", False),
        "vulnerabilities": result.get("vulnerabilities", []),
        "count": result.get("total_count", 0),
        "cpe_uri": result.get("cpe_uri"),
        "error": result.get("error")
    }


@register_tool(
    "fetch_cve_details",
    "Fetch detailed information about a specific CVE",
    "vulnerability"
)
async def fetch_cve_details(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    CVE ID로 상세 정보 조회

    Args:
        cve_id: CVE ID (예: CVE-2021-44228)
    """
    cve_id = kwargs.get("cve_id")

    if not cve_id:
        return {
            "success": False,
            "error": "CVE ID is required"
        }

    print(f"[fetch_cve_details] Fetching details for {cve_id}")

    client = get_nvd_client()
    result = client.get_vulnerability_by_cve_id(cve_id)

    return result


@register_tool(
    "assess_severity",
    "Assess vulnerability severity",
    "vulnerability"
)
async def assess_severity(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """취약점 심각도 평가 (Mock)"""
    return {"success": True, "severity": "LOW", "score": 3.0}


@register_tool(
    "search_vulnerabilities",
    "Search vulnerabilities for all dependencies in state",
    "vulnerability"
)
async def search_vulnerabilities(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    전체 의존성에 대한 취약점 검색 (nvd_client.py 사용)

    state에서 dependencies를 가져와서 NVD API로 취약점 조회
    """
    print("[search_vulnerabilities] Starting vulnerability search...")

    # State에서 의존성 가져오기
    dependencies = state.get("dependencies", {})

    if not dependencies:
        print("[search_vulnerabilities] No dependencies found in state")
        return {
            "success": True,
            "vulnerabilities": [],
            "total_count": 0,
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
            "summary": "No dependencies to scan",
            "state_update": {
                "vulnerabilities": [],
                "vulnerability_count": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0
            }
        }

    # 의존성 데이터를 analyze_dependency_vulnerabilities 형식으로 변환
    # dependencies = {"npm": {"react": "^18.0.0", ...}, "pip": {...}}
    # -> {"npm": [{"name": "react", "version": "18.0.0"}, ...], ...}
    formatted_deps = {}
    for ecosystem, packages in dependencies.items():
        formatted_deps[ecosystem] = []
        if isinstance(packages, dict):
            for name, version in packages.items():
                # 버전 문자열에서 ^, ~, >= 등 제거
                clean_version = version.replace("^", "").replace("~", "").replace(">=", "").strip()
                formatted_deps[ecosystem].append({
                    "name": name,
                    "version": clean_version if clean_version else "*"
                })

    # NVD Client로 취약점 분석 (DB 기반 필터링 활성화)
    client = get_nvd_client()
    result = client.analyze_dependency_vulnerabilities(
        dependencies=formatted_deps,
        skip_unmapped=True  # DB에 없는 패키지는 스킵
    )

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Unknown error"),
            "vulnerabilities": [],
            "total_count": 0
        }

    # 결과 파싱
    vulnerabilities = result.get("vulnerabilities", [])
    severity_counts = result.get("severity_counts", {})
    total_count = result.get("total_count", 0)
    packages_scanned = result.get("packages_scanned", 0)
    packages_skipped = result.get("packages_skipped", 0)

    print(f"[search_vulnerabilities] Found {total_count} vulnerabilities")
    print(f"[search_vulnerabilities] Scanned: {packages_scanned}, Skipped: {packages_skipped}")
    print(f"[search_vulnerabilities] Severity: {severity_counts}")

    # State 업데이트 데이터 (보안점수 계산을 위해 먼저 state 업데이트)
    state_update = {
        "vulnerabilities": vulnerabilities,
        "vulnerability_count": total_count,
        "critical_count": severity_counts.get("CRITICAL", 0),
        "high_count": severity_counts.get("HIGH", 0),
        "medium_count": severity_counts.get("MEDIUM", 0),
        "low_count": severity_counts.get("LOW", 0),
        "unknown_count": severity_counts.get("UNKNOWN", 0),
        "packages_scanned": packages_scanned,
        "packages_skipped": packages_skipped
    }

    # State를 업데이트하여 보안점수 계산에 사용
    updated_state = {**state, **state_update}

    # 보안 점수 자동 계산
    print("[search_vulnerabilities] Calculating security score...")
    score_result = await calculate_security_score(updated_state)

    if score_result.get("success"):
        security_score = score_result.get("score")
        security_grade = score_result.get("grade")
        risk_level = score_result.get("risk_level")
        deductions = score_result.get("deductions", {})

        # State 업데이트에 보안점수 추가
        state_update.update({
            "security_score": security_score,
            "security_grade": security_grade,
            "risk_level": risk_level
        })

        return {
            "success": True,
            "vulnerabilities": vulnerabilities,
            "total_count": total_count,
            "severity_counts": severity_counts,
            "packages_scanned": packages_scanned,
            "packages_skipped": packages_skipped,
            "summary": result.get("summary", ""),
            "security_score": security_score,
            "security_grade": security_grade,
            "risk_level": risk_level,
            "deductions": deductions,
            "state_update": state_update
        }
    else:
        # 보안점수 계산 실패 시에도 취약점 정보는 반환
        return {
            "success": True,
            "vulnerabilities": vulnerabilities,
            "total_count": total_count,
            "severity_counts": severity_counts,
            "packages_scanned": packages_scanned,
            "packages_skipped": packages_skipped,
            "summary": result.get("summary", ""),
            "state_update": state_update
        }


# ===== Assessment Tools =====

@register_tool(
    "check_license_compatibility",
    "Check license compatibility",
    "assessment"
)
async def check_license_compatibility(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """라이센스 호환성 체크 (Mock)"""
    return {"success": True, "compatible": True, "violations": []}


@register_tool(
    "calculate_security_score",
    "Calculate overall security score based on vulnerability severity",
    "assessment"
)
async def calculate_security_score(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    보안 점수 계산

    점수 계산 방식 (100점 만점):
    - CRITICAL: -4점
    - HIGH: -3점
    - MEDIUM: -2점
    - LOW: -1점
    - 최종 점수: 0 ~ 100 범위로 제한
    """
    critical = state.get("critical_count", 0)
    high = state.get("high_count", 0)
    medium = state.get("medium_count", 0)
    low = state.get("low_count", 0)

    # 점수 계산
    base_score = 100
    score = base_score - (critical * 4) - (high * 3) - (medium * 2) - (low * 1)

    # 0 ~ 100 범위로 제한
    score = max(0, min(100, score))

    # 등급 산정
    if score >= 90:
        grade = "A"
        risk_level = "Low"
    elif score >= 75:
        grade = "B"
        risk_level = "Low"
    elif score >= 60:
        grade = "C"
        risk_level = "Medium"
    elif score >= 40:
        grade = "D"
        risk_level = "High"
    else:
        grade = "F"
        risk_level = "Critical"

    # 점수 계산 상세 정보
    deductions = {
        "critical": critical * 4,
        "high": high * 3,
        "medium": medium * 2,
        "low": low * 1,
        "total": base_score - score
    }

    print(f"[Security Score] Calculated: {score}/100 (Grade: {grade})")
    print(f"[Security Score] Deductions: CRITICAL(-{deductions['critical']}), HIGH(-{deductions['high']}), MEDIUM(-{deductions['medium']}), LOW(-{deductions['low']})")

    return {
        "success": True,
        "score": score,
        "grade": grade,
        "risk_level": risk_level,
        "deductions": deductions,
        "vulnerability_summary": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "total": critical + high + medium + low
        },
        "state_update": {
            "security_score": score,
            "security_grade": grade,
            "risk_level": risk_level
        }
    }


# ===== Report Tools =====

@register_tool(
    "generate_security_report",
    "Generate comprehensive security analysis report",
    "report"
)
async def generate_security_report(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
async def generate_summary(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """요약 생성"""
    summary = f"""Security Analysis Summary: {state.get('owner')}/{state.get('repository')}
Dependencies: {state.get('dependency_count', 0)}
Vulnerabilities: {state.get('vulnerability_count', 0)}
Grade: {state.get('security_grade', 'N/A')}"""

    return {"success": True, "summary": summary}


# ===== File-Specific Tools =====

@register_tool(
    "parse_file_dependencies",
    "Parse dependencies from a specific file (package.json, requirements.txt, etc.)",
    "dependency"
)
async def parse_file_dependencies(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    특정 파일의 의존성만 파싱 (CPE/NVD 조회 하지 않음)

    Args:
        file_path: 파일 경로 (예: "package.json", "requirements.txt")
    """
    file_path = kwargs.get("file_path") or state.get("target_files", [None])[0]

    if not file_path:
        return {
            "success": False,
            "error": "File path is required"
        }

    print(f"[parse_file_dependencies] Parsing {file_path}")

    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    token = kwargs.get("token") or state.get("github_token")

    # 파일 타입에 따라 적절한 파서 호출
    if "package.json" in file_path.lower():
        result = await parse_package_json(state, owner=owner, repo=repo, token=token)
    elif "requirements.txt" in file_path.lower():
        result = await parse_requirements_txt(state, owner=owner, repo=repo, token=token)
    elif "pipfile" in file_path.lower():
        result = await parse_pipfile(state, owner=owner, repo=repo, token=token)
    elif "gemfile" in file_path.lower():
        result = await parse_gemfile(state, owner=owner, repo=repo, token=token)
    elif "cargo.toml" in file_path.lower():
        result = await parse_cargo_toml(state, owner=owner, repo=repo, token=token)
    else:
        return {
            "success": False,
            "error": f"Unsupported file type: {file_path}"
        }

    if result.get("success"):
        # State 업데이트 (취약점 조회는 하지 않음)
        dependencies = result.get("dependencies", {})
        ecosystem = result.get("ecosystem", "unknown")

        return {
            "success": True,
            "dependencies": {ecosystem: dependencies},
            "total_count": result.get("total_count", 0),
            "file_path": file_path,
            "ecosystem": ecosystem,
            "state_update": {
                "dependencies": {ecosystem: dependencies},
                "dependency_count": result.get("total_count", 0),
                "analyzed_files": [file_path]
            }
        }
    else:
        return result


@register_tool(
    "search_file_vulnerabilities",
    "Search vulnerabilities for dependencies in a specific file",
    "vulnerability"
)
async def search_file_vulnerabilities(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    특정 파일의 의존성에 대한 취약점 조회

    1. 파일의 의존성 파싱
    2. CPE DB 조회
    3. 취약점이 있는 의존성만 NVD API 요청
    """
    file_path = kwargs.get("file_path") or state.get("target_files", [None])[0]

    if not file_path:
        return {
            "success": False,
            "error": "File path is required"
        }

    print(f"[search_file_vulnerabilities] Analyzing vulnerabilities for {file_path}")

    # 1. 파일의 의존성 먼저 파싱
    deps_result = await parse_file_dependencies(state, file_path=file_path, **kwargs)

    if not deps_result.get("success"):
        return deps_result

    # 2. 파싱된 의존성을 state에 업데이트
    temp_state = {**state, **deps_result.get("state_update", {})}

    # 3. 취약점 조회
    vuln_result = await search_vulnerabilities(temp_state, **kwargs)

    if vuln_result.get("success"):
        # 파일 정보 추가
        vuln_result["file_path"] = file_path
        vuln_result["analyzed_files"] = [file_path]

    return vuln_result


# ===== Composite Tools =====

@register_tool(
    "analyze_dependencies_full",
    "Complete dependency analysis (without vulnerability scanning)",
    "dependency"
)
async def analyze_dependencies_full(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
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
    "Complete vulnerability scan for all dependencies",
    "vulnerability"
)
async def scan_vulnerabilities_full(state: SecurityAnalysisState, **kwargs) -> Dict[str, Any]:
    """
    전체 의존성에 대한 취약점 스캔

    state에서 dependencies를 가져와서 NVD API로 취약점 조회

    Returns:
        {
            "success": bool,
            "vulnerabilities": List[Dict],
            "total_count": int,
            "severity_counts": Dict,
            "summary": str,
            "state_update": Dict
        }
    """
    print("[scan_vulnerabilities_full] Starting full vulnerability scan...")

    # State에서 의존성 가져오기
    dependencies = state.get("dependencies", {})

    if not dependencies:
        print("[scan_vulnerabilities_full] No dependencies found in state")
        return {
            "success": True,
            "vulnerabilities": [],
            "total_count": 0,
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0},
            "summary": "No dependencies to scan",
            "state_update": {
                "vulnerabilities": [],
                "vulnerability_count": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0
            }
        }

    # 의존성 데이터를 analyze_dependency_vulnerabilities 형식으로 변환
    # dependencies = {"npm": {"react": "^18.0.0", ...}, "pip": {...}}
    # -> {"npm": [{"name": "react", "version": "18.0.0"}, ...], ...}
    formatted_deps = {}
    for ecosystem, packages in dependencies.items():
        formatted_deps[ecosystem] = []
        if isinstance(packages, dict):
            for name, version in packages.items():
                # 버전 문자열에서 ^, ~, >= 등 제거
                clean_version = version.replace("^", "").replace("~", "").replace(">=", "").strip()
                formatted_deps[ecosystem].append({
                    "name": name,
                    "version": clean_version if clean_version else "*"
                })

    # NVD Client로 취약점 분석 (DB 기반 필터링 활성화)
    client = get_nvd_client()
    result = client.analyze_dependency_vulnerabilities(
        dependencies=formatted_deps,
        skip_unmapped=True  # DB에 없는 패키지는 스킵
    )

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Unknown error"),
            "vulnerabilities": [],
            "total_count": 0
        }

    # 결과 파싱
    vulnerabilities = result.get("vulnerabilities", [])
    severity_counts = result.get("severity_counts", {})
    total_count = result.get("total_count", 0)
    packages_scanned = result.get("packages_scanned", 0)
    packages_skipped = result.get("packages_skipped", 0)

    print(f"[scan_vulnerabilities_full] Found {total_count} vulnerabilities")
    print(f"[scan_vulnerabilities_full] Scanned: {packages_scanned}, Skipped: {packages_skipped}")
    print(f"[scan_vulnerabilities_full] Severity: {severity_counts}")

    # State 업데이트 데이터 (보안점수 계산을 위해 먼저 state 업데이트)
    state_update = {
        "vulnerabilities": vulnerabilities,
        "vulnerability_count": total_count,
        "critical_count": severity_counts.get("CRITICAL", 0),
        "high_count": severity_counts.get("HIGH", 0),
        "medium_count": severity_counts.get("MEDIUM", 0),
        "low_count": severity_counts.get("LOW", 0),
        "unknown_count": severity_counts.get("UNKNOWN", 0),
        "packages_scanned": packages_scanned,
        "packages_skipped": packages_skipped
    }

    # State를 업데이트하여 보안점수 계산에 사용
    updated_state = {**state, **state_update}

    # 보안 점수 자동 계산
    print("[scan_vulnerabilities_full] Calculating security score...")
    score_result = await calculate_security_score(updated_state)

    if score_result.get("success"):
        security_score = score_result.get("score")
        security_grade = score_result.get("grade")
        risk_level = score_result.get("risk_level")
        deductions = score_result.get("deductions", {})

        # State 업데이트에 보안점수 추가
        state_update.update({
            "security_score": security_score,
            "security_grade": security_grade,
            "risk_level": risk_level
        })

        return {
            "success": True,
            "vulnerabilities": vulnerabilities,
            "total_count": total_count,
            "severity_counts": severity_counts,
            "packages_scanned": packages_scanned,
            "packages_skipped": packages_skipped,
            "summary": result.get("summary", ""),
            "security_score": security_score,
            "security_grade": security_grade,
            "risk_level": risk_level,
            "deductions": deductions,
            "state_update": state_update
        }
    else:
        # 보안점수 계산 실패 시에도 취약점 정보는 반환
        return {
            "success": True,
            "vulnerabilities": vulnerabilities,
            "total_count": total_count,
            "severity_counts": severity_counts,
            "packages_scanned": packages_scanned,
            "packages_skipped": packages_skipped,
            "summary": result.get("summary", ""),
            "state_update": state_update
        }
