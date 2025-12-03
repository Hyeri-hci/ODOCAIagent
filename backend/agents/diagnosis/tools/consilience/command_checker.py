"""명령 검증기: 설치/실행 명령이 참조하는 파일 존재 확인."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Set

from backend.common.github_client import fetch_repo_contents


@dataclass
class CommandCheckResult:
    """명령 검증 결과."""
    valid: int = 0
    broken: int = 0
    unchecked: int = 0
    total: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 엔트리포인트 추출 패턴
ENTRYPOINT_PATTERNS = [
    # Python
    (r"python\s+(?:-m\s+)?(\w+(?:\.\w+)*)", "python"),
    (r"pip\s+install\s+(?:-e\s+)?['\"]?\.?/?([^\s'\"]+)", "pip"),
    
    # Node.js
    (r"node\s+([^\s]+\.js)", "node"),
    (r"npm\s+(?:run\s+)?(\w+)", "npm"),
    (r"yarn\s+(?:run\s+)?(\w+)", "yarn"),
    
    # Docker
    (r"docker\s+(?:build|run)\s+.*?(?:-f\s+)?([^\s]+[Dd]ockerfile[^\s]*)?", "docker"),
    
    # Make
    (r"make\s+(\w+)", "make"),
    
    # Shell scripts
    (r"(?:bash|sh|\./)([^\s]+\.sh)", "shell"),
]


def _extract_entrypoints(commands: Dict[str, int]) -> Set[str]:
    """명령에서 엔트리포인트 추출."""
    entrypoints = set()
    
    # 명령 블록 키에서 직접 추출
    for cmd_type, count in commands.items():
        if count > 0:
            # pip install → setup.py, pyproject.toml 확인
            if "pip" in cmd_type:
                entrypoints.add("setup.py")
                entrypoints.add("pyproject.toml")
            
            # npm/yarn → package.json 확인
            if any(x in cmd_type for x in ["npm", "yarn", "pnpm"]):
                entrypoints.add("package.json")
            
            # docker → Dockerfile 확인
            if "docker" in cmd_type:
                entrypoints.add("Dockerfile")
                entrypoints.add("docker-compose.yml")
                entrypoints.add("compose.yml")
            
            # make → Makefile 확인
            if "make" in cmd_type:
                entrypoints.add("Makefile")
                entrypoints.add("makefile")
            
            # pytest → tests/ 확인
            if "pytest" in cmd_type:
                entrypoints.add("tests/")
                entrypoints.add("test/")
    
    return entrypoints


def check_command_refs(
    owner: str,
    repo: str,
    command_blocks: Dict[str, int],
) -> CommandCheckResult:
    """명령이 참조하는 엔트리포인트/파일 존재 확인."""
    if not command_blocks:
        return CommandCheckResult()
    
    # 엔트리포인트 추출
    entrypoints = _extract_entrypoints(command_blocks)
    
    if not entrypoints:
        return CommandCheckResult()
    
    result = CommandCheckResult(total=len(entrypoints))
    
    # 리포 루트 파일 목록 가져오기 (함수 기반)
    contents = fetch_repo_contents(owner, repo, "")
    
    if not contents:
        # 가져올 수 없으면 unchecked
        return CommandCheckResult(
            unchecked=len(entrypoints),
            total=len(entrypoints),
            details=[{"file": f, "status": "unchecked"} for f in entrypoints]
        )
    
    # 파일/디렉토리 이름 집합
    existing = set()
    for item in contents:
        name = item.get("name", "")
        existing.add(name)
        if item.get("type") == "dir":
            existing.add(name + "/")
    
    for entry in entrypoints:
        # 정확히 매칭
        if entry in existing or entry.rstrip("/") in existing:
            result.valid += 1
            result.details.append({"file": entry, "status": "valid"})
        else:
            result.broken += 1
            result.details.append({"file": entry, "status": "broken"})
    
    return result
