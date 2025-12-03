"""Sustainability Gate: 프로젝트 지속가능성 판단."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

from backend.agents.diagnosis.config import get_gate_config, get_freshness_config


@dataclass
class GateCheckResult:
    """게이트 체크 결과."""
    name: str
    passed: bool
    value: Any
    threshold: Any
    message: str


@dataclass
class SustainabilityGateResult:
    """지속가능성 게이트 결과."""
    # 최종 판단
    is_sustainable: bool      # 모든 필수 게이트 통과
    gate_level: str           # "active" | "maintained" | "stale" | "abandoned"
    
    # 개별 게이트 결과
    checks: List[GateCheckResult]
    
    # 점수 (0-100)
    sustainability_score: int
    
    # 경고/권고 메시지
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["checks"] = [asdict(c) for c in self.checks]
        return result


def _days_since(dt: Optional[datetime]) -> int:
    """날짜로부터 경과 일수 계산."""
    if dt is None:
        return 999
    
    now = datetime.now(timezone.utc)
    
    # naive datetime 처리
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    delta = now - dt
    return delta.days


def _parse_datetime(value: Any) -> Optional[datetime]:
    """문자열/datetime/date를 datetime으로 변환."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # date 타입 처리 (CHAOSS metrics에서 date 객체로 반환됨)
    from datetime import date
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(value, str):
        # ISO 8601 형식 파싱
        try:
            # Z 접미사 처리
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def check_sustainability_gate(
    activity_data: Dict[str, Any],
    repo_info: Optional[Dict[str, Any]] = None,
) -> SustainabilityGateResult:
    """지속가능성 게이트 체크."""
    config = get_gate_config()
    freshness = get_freshness_config()
    
    checks: List[GateCheckResult] = []
    warnings: List[str] = []
    
    # 커밋 데이터 추출
    commit_data = activity_data.get("commit", {})
    last_commit_date = _parse_datetime(commit_data.get("last_commit_date"))
    days_since_commit = _days_since(last_commit_date)
    total_commits = commit_data.get("total_commits", 0)
    unique_authors = commit_data.get("unique_authors", 0)
    
    # 이슈 데이터 추출
    issue_data = activity_data.get("issue", {})
    open_issues = issue_data.get("open_issues", 0)
    closed_in_window = issue_data.get("closed_in_window", 0)
    
    # PR 데이터 추출
    pr_data = activity_data.get("pr", {})
    merged_in_window = pr_data.get("merged_in_window", 0)
    
    # Gate 1: 최근 커밋 (필수)
    commit_threshold = config.get("commit_recency_days", 180)
    commit_passed = days_since_commit <= commit_threshold
    checks.append(GateCheckResult(
        name="recent_commit",
        passed=commit_passed,
        value=days_since_commit,
        threshold=commit_threshold,
        message=f"마지막 커밋: {days_since_commit}일 전" if last_commit_date else "커밋 정보 없음"
    ))
    if not commit_passed:
        warnings.append(f"마지막 커밋이 {days_since_commit}일 전입니다 (기준: {commit_threshold}일)")
    
    # Gate 2: 최소 커밋 수 (권장)
    min_commits = config.get("min_commits", 10)
    commits_passed = total_commits >= min_commits
    checks.append(GateCheckResult(
        name="min_commits",
        passed=commits_passed,
        value=total_commits,
        threshold=min_commits,
        message=f"총 커밋: {total_commits}개"
    ))
    if not commits_passed:
        warnings.append(f"커밋 수가 {total_commits}개로 부족합니다 (권장: {min_commits}개 이상)")
    
    # Gate 3: 기여자 다양성 (권장)
    min_authors = config.get("min_authors", 1)
    authors_passed = unique_authors >= min_authors
    checks.append(GateCheckResult(
        name="contributor_diversity",
        passed=authors_passed,
        value=unique_authors,
        threshold=min_authors,
        message=f"고유 기여자: {unique_authors}명"
    ))
    
    # Gate 4: 이슈 응답성 (선택)
    if open_issues > 0 or closed_in_window > 0:
        issue_activity = closed_in_window > 0
        checks.append(GateCheckResult(
            name="issue_responsiveness",
            passed=issue_activity,
            value=closed_in_window,
            threshold=1,
            message=f"최근 종료된 이슈: {closed_in_window}개"
        ))
        if not issue_activity and open_issues > 5:
            warnings.append(f"열린 이슈 {open_issues}개가 있지만 최근 종료된 이슈가 없습니다")
    
    # Gate 5: PR 활동 (선택)
    if merged_in_window > 0:
        checks.append(GateCheckResult(
            name="pr_activity",
            passed=True,
            value=merged_in_window,
            threshold=1,
            message=f"최근 병합된 PR: {merged_in_window}개"
        ))
    
    # Gate 6: Bus Factor 경고 (CHAOSS Risk Metrics)
    # 출처: CHAOSS - healthy >= 3명, risky = 1명
    bus_factor_warning = config.get("bus_factor_warning", 2)
    if unique_authors < bus_factor_warning:
        checks.append(GateCheckResult(
            name="bus_factor",
            passed=False,
            value=unique_authors,
            threshold=bus_factor_warning,
            message=f"기여자 {unique_authors}명 - Bus Factor 위험"
        ))
        warnings.append(f"핵심 기여자가 {unique_authors}명뿐입니다 (권장: {bus_factor_warning}명 이상)")
    else:
        checks.append(GateCheckResult(
            name="bus_factor",
            passed=True,
            value=unique_authors,
            threshold=bus_factor_warning,
            message=f"기여자 {unique_authors}명 - Bus Factor 양호"
        ))
    
    # 게이트 레벨 결정
    gate_level = _determine_gate_level(
        days_since_commit=days_since_commit,
        total_commits=total_commits,
        unique_authors=unique_authors,
        config=config,
    )
    
    # 필수 게이트 통과 여부
    # 출처: CHAOSS - 최근 커밋 + 최소 기여자 수
    required_gates = ["recent_commit", "min_commits"]
    is_sustainable = all(
        c.passed for c in checks if c.name in required_gates
    )
    
    # 지속가능성 점수 계산
    sustainability_score = _compute_sustainability_score(
        checks=checks,
        gate_level=gate_level,
        config=config,
    )
    
    return SustainabilityGateResult(
        is_sustainable=is_sustainable,
        gate_level=gate_level,
        checks=checks,
        sustainability_score=sustainability_score,
        warnings=warnings,
    )


def _determine_gate_level(
    days_since_commit: int,
    total_commits: int,
    unique_authors: int,
    config: Dict[str, Any],
) -> str:
    """게이트 레벨 결정.
    
    출처:
    - GitHub Octoverse 2023: 30일 = "최근 활동"
    - 분기별 릴리스 주기: 90일
    - GitHub Archive Program: 365일 = "1년 내 활동"
    """
    active_days = config.get("active_threshold_days", 30)
    maintained_days = config.get("maintained_threshold_days", 90)
    stale_days = config.get("stale_threshold_days", 365)  # 변경: 180 → 365
    min_authors = config.get("min_authors", 2)  # 변경: 1 → 2 (Archive 기준)
    
    # active: 30일 내 커밋 + 2명 이상 기여자
    if days_since_commit <= active_days and unique_authors >= min_authors:
        return "active"
    # maintained: 90일 내 커밋
    elif days_since_commit <= maintained_days:
        return "maintained"
    # stale: 365일 내 커밋
    elif days_since_commit <= stale_days:
        return "stale"
    else:
        return "abandoned"


def _compute_sustainability_score(
    checks: List[GateCheckResult],
    gate_level: str,
    config: Dict[str, Any],
) -> int:
    """지속가능성 점수 계산 (0-100).
    
    가중치 근거:
    - 게이트 레벨 70%: 핵심 판단 기준
    - 체크 통과율 30%: 세부 지표 보정
    """
    # 기본 점수 (게이트 레벨 기반)
    level_scores = {
        "active": 90,
        "maintained": 70,
        "stale": 40,
        "abandoned": 10,
    }
    base_score = level_scores.get(gate_level, 50)
    
    # 체크 통과율 보정 (30%)
    if checks:
        passed_count = sum(1 for c in checks if c.passed)
        pass_ratio = passed_count / len(checks)
        base_score = base_score * 0.7 + (pass_ratio * 100) * 0.3
    
    return min(100, max(0, round(base_score)))
