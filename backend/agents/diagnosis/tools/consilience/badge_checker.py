"""배지 검증기: GitHub Actions 배지와 실제 워크플로 대조."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any

from backend.common.github_client import fetch_workflows
from backend.agents.diagnosis.config import get_consilience_config


@dataclass
class BadgeCheckResult:
    """배지 검증 결과."""
    valid: int = 0
    broken: int = 0
    unchecked: int = 0
    total: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# GitHub Actions 배지 패턴
ACTIONS_BADGE_PATTERN = re.compile(
    r"github\.com/([^/]+)/([^/]+)/(?:actions/)?workflows/([^/]+\.ya?ml)/badge\.svg"
)

# 일반 배지 패턴 (shields.io 등)
SHIELDS_PATTERN = re.compile(
    r"img\.shields\.io/github/(?:actions|workflow)/status/([^/]+)/([^/]+)"
)


def _extract_workflow_info(badge_url: str) -> Dict[str, Any]:
    """배지 URL에서 워크플로 정보 추출."""
    # GitHub Actions 직접 배지
    match = ACTIONS_BADGE_PATTERN.search(badge_url)
    if match:
        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "workflow": match.group(3),
        }
    
    # shields.io 배지
    match = SHIELDS_PATTERN.search(badge_url)
    if match:
        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "workflow": None,  # 워크플로 이름 없음
        }
    
    return {}


def check_badge_refs(
    owner: str,
    repo: str,
    badge_urls: List[str],
) -> BadgeCheckResult:
    """배지 URL이 실제 워크플로와 연결되는지 검증."""
    if not badge_urls:
        return BadgeCheckResult()
    
    result = BadgeCheckResult(total=len(badge_urls))
    
    # 워크플로 목록 가져오기 (함수 기반)
    workflows = fetch_workflows(owner, repo)
    workflow_files = {w.get("path", "").split("/")[-1] for w in workflows}
    
    for url in badge_urls:
        info = _extract_workflow_info(url)
        
        if not info:
            # GitHub Actions 배지가 아님 → unchecked
            result.unchecked += 1
            result.details.append({
                "url": url,
                "status": "unchecked",
                "reason": "not_actions_badge"
            })
            continue
        
        # 소유자/리포 확인
        if info.get("owner") != owner or info.get("repo") != repo:
            # 다른 리포의 배지 → 확인 불가
            result.unchecked += 1
            result.details.append({
                "url": url,
                "status": "unchecked",
                "reason": "different_repo"
            })
            continue
        
        workflow_file = info.get("workflow")
        
        if not workflow_file:
            # 워크플로 파일을 특정할 수 없음
            if workflows:
                # 워크플로가 하나라도 있으면 valid로 간주
                result.valid += 1
                result.details.append({
                    "url": url,
                    "status": "valid",
                    "reason": "has_workflows"
                })
            else:
                result.broken += 1
                result.details.append({
                    "url": url,
                    "status": "broken",
                    "reason": "no_workflows"
                })
            continue
        
        # 워크플로 파일 존재 확인
        if workflow_file in workflow_files:
            result.valid += 1
            result.details.append({
                "url": url,
                "status": "valid",
                "workflow": workflow_file
            })
        else:
            result.broken += 1
            result.details.append({
                "url": url,
                "status": "broken",
                "workflow": workflow_file,
                "reason": "workflow_not_found"
            })
    
    return result
