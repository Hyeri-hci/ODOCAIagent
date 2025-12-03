"""경로 검증기: README 경로 참조와 리포 트리 대조."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, FrozenSet

from backend.common.github_client import fetch_repo_tree


@dataclass
class PathCheckResult:
    """경로 검증 결과."""
    valid: int = 0
    broken: int = 0
    total: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _build_path_set(tree_data: Dict[str, Any]) -> FrozenSet[str]:
    """트리 데이터에서 경로 집합 생성."""
    if not tree_data or "tree" not in tree_data:
        return frozenset()
    
    paths = set()
    for item in tree_data.get("tree", []):
        path = item.get("path", "")
        if path:
            paths.add(path)
            # 디렉토리 경로도 추가 (슬래시 포함)
            if item.get("type") == "tree":
                paths.add(path + "/")
    
    return frozenset(paths)


def _normalize_path(path: str) -> str:
    """경로 정규화."""
    # 앞뒤 공백, 백틱, 따옴표 제거
    path = path.strip().strip("`'\"")
    # ./ 제거
    if path.startswith("./"):
        path = path[2:]
    return path


def check_path_refs(
    owner: str,
    repo: str,
    path_refs: List[str],
    sha: str = "HEAD",
) -> PathCheckResult:
    """README의 경로 참조가 리포에 존재하는지 검증."""
    if not path_refs:
        return PathCheckResult()
    
    result = PathCheckResult(total=len(path_refs))
    
    # 리포 트리 가져오기 (github_client 함수 사용)
    tree_data = fetch_repo_tree(owner, repo, sha)
    path_set = _build_path_set(tree_data)
    
    if not path_set:
        # 트리를 가져올 수 없으면 모두 unchecked로 처리
        return PathCheckResult(
            valid=0,
            broken=0,
            total=len(path_refs),
            details=[{"path": p, "status": "unchecked"} for p in path_refs]
        )
    
    for path in path_refs:
        normalized = _normalize_path(path)
        
        # 직접 매칭
        if normalized in path_set:
            result.valid += 1
            result.details.append({"path": path, "status": "valid"})
            continue
        
        # 접두사 매칭 (디렉토리)
        prefix_match = any(
            t.startswith(normalized.rstrip("/")) 
            for t in path_set
        )
        
        if prefix_match:
            result.valid += 1
            result.details.append({"path": path, "status": "valid"})
        else:
            result.broken += 1
            result.details.append({"path": path, "status": "broken"})
    
    return result
