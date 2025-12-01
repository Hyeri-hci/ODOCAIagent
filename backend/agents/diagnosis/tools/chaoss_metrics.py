"""호환성 모듈: 기존 import 경로 유지를 위한 re-export."""
# 모든 public + private 함수/클래스 re-export
from .scoring.chaoss_metrics import (
    CommitActivityMetrics,
    IssueActivityMetrics,
    PullRequestActivityMetrics,
    compute_commit_activity,
    compute_issue_activity,
    compute_pr_activity,
    _parse_iso8601,
    _parse_commit_date,
    _extract_author_id,
)
# 테스트 mock용 - 원본 모듈에서 import하는 외부 함수도 re-export
from backend.common.github_client import (
    fetch_recent_commits,
    fetch_recent_issues,
    fetch_recent_pull_requests,
    fetch_activity_summary,
)
