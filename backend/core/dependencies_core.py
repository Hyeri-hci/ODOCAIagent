"""의존성 파싱 Core 레이어 - Pure Python implementation."""
from __future__ import annotations

import json
import re
import logging
from typing import List, Optional, Dict

from .models import DependencyInfo, DependencySnapshot, RepoSnapshot
from .github_core import fetch_repo_tree, fetch_file_content

logger = logging.getLogger(__name__)


def parse_dependencies(repo_snapshot: RepoSnapshot) -> DependencySnapshot:
    """저장소의 의존성 파싱 (requirements.txt, package.json)."""
    owner = repo_snapshot.owner
    repo = repo_snapshot.repo
    ref = repo_snapshot.ref

    try:
        file_tree = fetch_repo_tree(owner, repo, ref)
    except Exception as e:
        return DependencySnapshot(
            repo_id=repo_snapshot.repo_id,
            dependencies=[],
            analyzed_files=[],
            parse_errors=[f"Failed to fetch tree: {e}"],
        )

    dependencies: List[DependencyInfo] = []
    analyzed_files: List[str] = []
    errors: List[str] = []

    # 1. requirements.txt (Python)
    req_files = [f for f in file_tree if f.endswith("requirements.txt")]
    for path in req_files:
        try:
            content = fetch_file_content(owner, repo, path, ref)
            if content:
                deps = _parse_requirements_txt(content, path)
                dependencies.extend(deps)
                analyzed_files.append(path)
        except Exception as e:
            errors.append(f"Failed to parse {path}: {e}")

    # 2. package.json (Node.js)
    pkg_files = [f for f in file_tree if f.endswith("package.json")]
    for path in pkg_files:
        try:
            content = fetch_file_content(owner, repo, path, ref)
            if content:
                deps = _parse_package_json(content, path)
                dependencies.extend(deps)
                analyzed_files.append(path)
        except Exception as e:
            errors.append(f"Failed to parse {path}: {e}")

    # 3. pyproject.toml (Python) - 간단 파싱 (poetry/flit 등)
    toml_files = [f for f in file_tree if f.endswith("pyproject.toml")]
    for path in toml_files:
        try:
            content = fetch_file_content(owner, repo, path, ref)
            if content:
                deps = _parse_pyproject_toml(content, path)
                dependencies.extend(deps)
                analyzed_files.append(path)
        except Exception as e:
            errors.append(f"Failed to parse {path}: {e}")

    return DependencySnapshot(
        repo_id=repo_snapshot.repo_id,
        dependencies=dependencies,
        analyzed_files=analyzed_files,
        parse_errors=errors,
    )


def _parse_requirements_txt(content: str, source: str) -> List[DependencyInfo]:
    """requirements.txt 파싱."""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # 간단한 정규식: 패키지명[==version]
        # 예: flask==2.0.1, requests>=2.0, numpy
        match = re.match(r"^([a-zA-Z0-9_\-]+)(.*)", line)
        if match:
            name = match.group(1)
            version_spec = match.group(2).strip()
            deps.append(DependencyInfo(
                name=name,
                version=version_spec if version_spec else None,
                source=source,
                dep_type="runtime",
            ))
    return deps


def _parse_package_json(content: str, source: str) -> List[DependencyInfo]:
    """package.json 파싱."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    deps = []
    
    # dependencies
    for name, ver in data.get("dependencies", {}).items():
        deps.append(DependencyInfo(
            name=name,
            version=ver,
            source=source,
            dep_type="runtime",
        ))
    
    # devDependencies
    for name, ver in data.get("devDependencies", {}).items():
        deps.append(DependencyInfo(
            name=name,
            version=ver,
            source=source,
            dep_type="dev",
        ))

    return deps


def _parse_pyproject_toml(content: str, source: str) -> List[DependencyInfo]:
    """pyproject.toml 파싱 (매우 단순화)."""
    # toml 파서 없이 텍스트 기반으로 [tool.poetry.dependencies] 등 찾기
    deps = []
    lines = content.splitlines()
    current_section = None
    
    for line in lines:
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
        
        if not current_section:
            continue
            
        if "dependencies" in current_section and "=" in line:
            # poetry.dependencies, project.dependencies 등
            parts = line.split("=", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                ver = parts[1].strip().strip('"').strip("'")
                if name != "python":
                    dep_type = "dev" if "dev" in current_section else "runtime"
                    deps.append(DependencyInfo(
                        name=name,
                        version=ver,
                        source=source,
                        dep_type=dep_type,
                    ))
    return deps
