"""Task 생성 함수: Issue 기반/Meta 기반 Task 생성."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .models import TaskSuggestion
from .labels import (
    determine_difficulty_from_labels,
    determine_level,
    determine_kind_from_labels,
    get_estimated_hours_from_level,
    extract_skills_from_labels,
)
from .scoring import (
    compute_task_score,
    determine_intent,
    generate_reason_tags,
    generate_fallback_reason,
)

logger = logging.getLogger(__name__)


def create_tasks_from_issues(
    issues: list[dict[str, Any]],
    repo_url: str,
    is_healthy: bool = True,
    is_active: bool = True,
) -> list[TaskSuggestion]:
    """GitHub 이슈에서 TaskSuggestion 생성."""
    tasks: list[TaskSuggestion] = []
    now = datetime.now(timezone.utc)

    for issue in issues:
        # GraphQL vs REST 형식 처리
        if isinstance(issue.get("labels"), dict):
            label_nodes = issue.get("labels", {}).get("nodes", [])
            labels = [node.get("name", "") for node in label_nodes]
            comment_count = issue.get("comments", {}).get("totalCount", 0)
            url = issue.get("url", "")
            updated_at_str = issue.get("updatedAt", "")
        else:
            labels = [l.get("name", "") for l in issue.get("labels", [])]
            comment_count = issue.get("comments", 0)
            url = issue.get("html_url", "")
            updated_at_str = issue.get("updated_at", "")

        number = issue.get("number")
        title = issue.get("title", "")

        # recency 계산
        recency_days = None
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                recency_days = (now - updated_at).days
            except (ValueError, TypeError):
                pass

        difficulty = determine_difficulty_from_labels(labels)
        level = determine_level(difficulty, labels, comment_count)
        kind = determine_kind_from_labels(labels)
        reason_tags = generate_reason_tags(labels, difficulty)
        task_score = compute_task_score(difficulty, labels, comment_count, recency_days)
        intent = determine_intent(difficulty, is_healthy, is_active)
        estimated_hours = get_estimated_hours_from_level(level)
        required_skills = extract_skills_from_labels(labels)

        tasks.append(TaskSuggestion(
            kind=kind,
            difficulty=difficulty,
            level=level,
            id=f"issue#{number}",
            title=title,
            url=url,
            labels=labels,
            reason_tags=reason_tags,
            meta_flags=[],
            fallback_reason=generate_fallback_reason(difficulty, reason_tags),
            intent=intent,
            task_score=task_score,
            recency_days=recency_days,
            comment_count=comment_count,
            estimated_hours=estimated_hours,
            required_skills=required_skills,
        ))

    return tasks


# Meta Task 정의 (문서 관련)
DOC_META_TASKS: dict[str, tuple[str, str, str, int, str, list[str]]] = {
    "missing_contributing": (
        "meta:create_contributing", "CONTRIBUTING.md 초안 작성",
        "beginner", 2, "프로젝트에 CONTRIBUTING.md가 없음",
        ["docs_issue", "low_barrier"],
    ),
    "missing_what": (
        "meta:improve_readme_what", "README에 '프로젝트 소개' 섹션 보강",
        "beginner", 1, "README에 프로젝트 소개가 부족",
        ["docs_issue", "low_barrier", "quick_win"],
    ),
    "missing_why": (
        "meta:improve_readme_why", "README에 '왜 이 프로젝트가 필요한지' 추가",
        "beginner", 2, "프로젝트의 필요성/동기 설명 추가 필요",
        ["docs_issue", "storytelling"],
    ),
    "missing_how": (
        "meta:add_installation_guide", "설치 및 실행 가이드 작성",
        "intermediate", 3, "Quick Start/Installation 가이드 필요",
        ["docs_issue", "onboarding_critical"],
    ),
    "weak_documentation": (
        "meta:improve_documentation", "전반적인 문서 품질 개선",
        "intermediate", 3, "문서화 점수가 낮음",
        ["docs_issue", "quality_improvement"],
    ),
}


def create_meta_tasks_from_labels(
    docs_issues: list[str],
    activity_issues: list[str],
    health_level: str,
    repo_url: str,
) -> list[TaskSuggestion]:
    """진단 결과(labels)에서 메타 Task 생성."""
    tasks: list[TaskSuggestion] = []

    # 문서 관련 메타 Task
    for issue_key, (task_id, title, diff, lvl, reason, tags) in DOC_META_TASKS.items():
        if issue_key in docs_issues:
            tasks.append(TaskSuggestion(
                kind="meta",
                difficulty=diff,
                level=lvl,
                id=task_id,
                title=title,
                labels=["documentation", "meta"],
                reason_tags=tags,
                meta_flags=[issue_key],
                fallback_reason=reason,
            ))

    # 활동성 관련 메타 Task
    if "inactive_project" in activity_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="advanced",
            level=5,
            id="meta:check_maintainer_status",
            title="메인테이너 활동 여부 확인 및 커뮤니케이션",
            labels=["meta", "communication"],
            reason_tags=["caution_needed"],
            meta_flags=["inactive_project"],
            fallback_reason="[주의] 프로젝트가 비활성 상태, 기여 전 메인테이너 연락 권장",
        ))

    if "low_issue_closure" in activity_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="intermediate",
            level=4,
            id="meta:help_triage_issues",
            title="오래된 이슈 정리(triage) 도움",
            labels=["meta", "triage"],
            reason_tags=["community_help"],
            meta_flags=["low_issue_closure"],
            fallback_reason="이슈 처리율이 낮아 오래된 이슈 상태 확인 필요",
        ))

    if health_level == "bad":
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="advanced",
            level=6,
            id="meta:evaluate_project_health",
            title="프로젝트 건강 상태 평가 및 개선 제안",
            labels=["meta", "analysis"],
            reason_tags=["caution_needed"],
            meta_flags=["unhealthy_project"],
            fallback_reason="[주의] 프로젝트 전반적 건강 상태가 좋지 않음",
            intent="evaluate",
            task_score=30.0,
        ))

    return tasks


def create_minimum_meta_tasks(repo_url: str) -> list[TaskSuggestion]:
    """건강한 프로젝트를 위한 최소 메타 Task."""
    return [
        TaskSuggestion(
            kind="meta", difficulty="beginner", level=1,
            id="meta:write_tutorial",
            title="초보자를 위한 튜토리얼/블로그 포스트 작성",
            labels=["documentation", "meta", "community"],
            reason_tags=["community_contribution", "external"],
            meta_flags=["minimum_task"],
            fallback_reason="프로젝트 사용법을 블로그나 미디엄에 작성하여 커뮤니티에 기여",
            intent="contribute",
            task_score=70.0,
        ),
        TaskSuggestion(
            kind="meta", difficulty="beginner", level=2,
            id="meta:improve_examples",
            title="예제 코드/샘플 프로젝트 보강",
            labels=["documentation", "meta", "examples"],
            reason_tags=["docs_issue", "practical"],
            meta_flags=["minimum_task"],
            fallback_reason="README나 examples/ 폴더에 실용적인 예제 코드 추가",
            intent="contribute",
            task_score=65.0,
        ),
        TaskSuggestion(
            kind="meta", difficulty="intermediate", level=3,
            id="meta:triage_open_issues",
            title="오픈 이슈 정리/레이블링 도움",
            labels=["meta", "triage", "community"],
            reason_tags=["community_help"],
            meta_flags=["minimum_task"],
            fallback_reason="기존 이슈에 댓글로 상태 확인하거나 레이블 제안",
            intent="contribute",
            task_score=55.0,
        ),
    ]


def create_study_meta_tasks(repo_url: str) -> list[TaskSuggestion]:
    """비건강/비활성 프로젝트를 위한 학습용 메타 Task."""
    return [
        TaskSuggestion(
            kind="meta", difficulty="beginner", level=1,
            id="meta:study_architecture",
            title="프로젝트 아키텍처 분석 및 학습",
            labels=["meta", "study", "learning"],
            reason_tags=["learning_opportunity"],
            meta_flags=["study_task"],
            fallback_reason="코드 구조와 설계 패턴을 분석하여 학습",
            intent="study",
            task_score=60.0,
        ),
        TaskSuggestion(
            kind="meta", difficulty="beginner", level=2,
            id="meta:document_learnings",
            title="학습 내용 정리 (개인 노트/블로그)",
            labels=["meta", "study", "documentation"],
            reason_tags=["learning_opportunity", "external"],
            meta_flags=["study_task"],
            fallback_reason="프로젝트에서 배운 것을 개인 블로그나 노트에 정리",
            intent="study",
            task_score=55.0,
        ),
        TaskSuggestion(
            kind="meta", difficulty="intermediate", level=3,
            id="meta:evaluate_alternatives",
            title="유사 프로젝트/대안 비교 분석",
            labels=["meta", "evaluate", "analysis"],
            reason_tags=["evaluation"],
            meta_flags=["study_task"],
            fallback_reason="이 프로젝트와 유사한 다른 프로젝트를 비교 분석",
            intent="evaluate",
            task_score=50.0,
        ),
    ]
