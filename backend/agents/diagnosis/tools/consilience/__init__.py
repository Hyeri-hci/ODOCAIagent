"""Consilience (교차검증) 모듈: README 주장과 리포 실체 대조."""
from .path_checker import check_path_refs, PathCheckResult
from .badge_checker import check_badge_refs, BadgeCheckResult
from .link_checker import check_link_refs, LinkCheckResult
from .command_checker import check_command_refs, CommandCheckResult

__all__ = [
    "check_path_refs",
    "PathCheckResult",
    "check_badge_refs", 
    "BadgeCheckResult",
    "check_link_refs",
    "LinkCheckResult",
    "check_command_refs",
    "CommandCheckResult",
]
