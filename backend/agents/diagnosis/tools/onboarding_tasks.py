"""
Onboarding Tasks Generator

진단 결과 기반 난이도/레벨별 기여 Task 제안.
- GitHub 이슈 기반 (good-first-issue 등)
- 진단 결과 기반 메타 Task
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional
import logging

logger = logging.getLogger(__name__)

Difficulty = Literal["beginner", "intermediate", "advanced"]
TaskKind = Literal["issue", "doc", "test", "refactor", "meta"]
TaskIntent = Literal["contribute", "study", "evaluate"]


@dataclass
class TaskSuggestion:
    """기여 Task 제안."""
    kind: TaskKind
    difficulty: Difficulty
    level: int  # 1-6 (게임식 레벨)
    id: str  # "issue#123", "meta:improve_contributing"
    title: str
    url: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    reason_tags: List[str] = field(default_factory=list)
    meta_flags: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    intent: TaskIntent = "contribute"
    task_score: float = 0.0  # 0-100
    recency_days: Optional[int] = None
    comment_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OnboardingTasks:
    """난이도별 그룹핑된 Task 목록."""
    beginner: List[TaskSuggestion] = field(default_factory=list)
    intermediate: List[TaskSuggestion] = field(default_factory=list)
    advanced: List[TaskSuggestion] = field(default_factory=list)
    total_count: int = 0
    issue_count: int = 0
    meta_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beginner": [t.to_dict() for t in self.beginner],
            "intermediate": [t.to_dict() for t in self.intermediate],
            "advanced": [t.to_dict() for t in self.advanced],
            "meta": {
                "total_count": self.total_count,
                "issue_count": self.issue_count,
                "meta_count": self.meta_count,
            },
        }


# 라벨 분류
BEGINNER_LABELS = {
    "good first issue", "good-first-issue", "beginner", "beginner-friendly",
    "first-timers-only", "first-time-contributor", "easy", "starter",
    "newbie", "hacktoberfest",
}
INTERMEDIATE_LABELS = {
    "help wanted", "help-wanted", "documentation", "docs", "tests",
    "testing", "enhancement", "feature", "improvement",
}
ADVANCED_LABELS = {
    "bug", "critical", "security", "performance", "refactor",
    "breaking-change", "architecture", "core",
}
PRIORITY_LABELS = [
    "good first issue", "good-first-issue", "beginner", "beginner-friendly",
    "first-timers-only", "help wanted", "help-wanted", "documentation",
    "docs", "hacktoberfest",
]

# 미리 정의된 메타 Task (레거시 호환용)
HEALTHY_PROJECT_META_TASKS: List[TaskSuggestion] = [
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:write_tutorial", title="사용자를 위한 튜토리얼 작성",
        labels=["documentation", "meta"],
        reason_tags=["community_contribution", "docs_improvement"],
        meta_flags=["healthy_project"],
        fallback_reason="건강한 프로젝트에 튜토리얼 문서로 기여할 수 있습니다",
        intent="contribute", task_score=60.0,
    ),
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:improve_examples", title="코드 예제 보강",
        labels=["documentation", "meta"],
        reason_tags=["community_contribution", "beginner_friendly"],
        meta_flags=["healthy_project"],
        fallback_reason="예제 코드 추가/개선으로 다른 사용자에게 도움을 줄 수 있습니다",
        intent="contribute", task_score=55.0,
    ),
    TaskSuggestion(
        kind="meta", difficulty="intermediate", level=3,
        id="meta:triage_issues", title="이슈 정리 및 라벨링 도움",
        labels=["meta", "community"],
        reason_tags=["community_contribution", "organization"],
        meta_flags=["healthy_project"],
        fallback_reason="이슈 분류, 중복 확인 등 커뮤니티 기여가 가능합니다",
        intent="contribute", task_score=50.0,
    ),
]

STUDY_META_TASKS: List[TaskSuggestion] = [
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:analyze_architecture", title="프로젝트 아키텍처 분석 및 학습",
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "architecture"],
        meta_flags=["study_mode"],
        fallback_reason="코드를 읽고 아키텍처를 분석하여 학습할 수 있습니다",
        intent="study", task_score=70.0,
    ),
    TaskSuggestion(
        kind="meta", difficulty="beginner", level=2,
        id="meta:document_learnings", title="학습 내용 개인 블로그/노트 정리",
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "personal_growth"],
        meta_flags=["study_mode"],
        fallback_reason="프로젝트에서 배운 내용을 정리하여 지식을 공고히 할 수 있습니다",
        intent="study", task_score=65.0,
    ),
]


def determine_difficulty_from_labels(labels: List[str]) -> Difficulty:
    """라벨 목록에서 난이도 결정."""
    labels_lower = {label.lower() for label in labels}
    if labels_lower & BEGINNER_LABELS:
        return "beginner"
    if labels_lower & ADVANCED_LABELS:
        return "advanced"
    return "intermediate"


def determine_level(difficulty: Difficulty, labels: List[str], comment_count: int = 0) -> int:
    """난이도/메타데이터 기반 레벨 결정 (1-6)."""
    labels_lower = {label.lower() for label in labels}

    if difficulty == "beginner":
        if labels_lower & {"good first issue", "good-first-issue", "first-timers-only"}:
            return 1
        return 2
    elif difficulty == "intermediate":
        if labels_lower & {"documentation", "docs", "tests", "testing"}:
            return 3
        return 4
    else:
        return 6 if comment_count > 10 else 5


def determine_kind_from_labels(labels: List[str]) -> TaskKind:
    """라벨에서 Task 종류 결정."""
    labels_lower = {label.lower() for label in labels}
    if labels_lower & {"documentation", "docs"}:
        return "doc"
    if labels_lower & {"tests", "testing", "test"}:
        return "test"
    if labels_lower & {"refactor", "refactoring", "cleanup"}:
        return "refactor"
    return "issue"


def fetch_open_issues_for_tasks(owner: str, repo: str, limit: int = 50) -> List[Dict[str, Any]]:
    """GraphQL로 Open 이슈 목록 조회."""
    from backend.common.github_client import _github_graphql

    query = """
    query($owner: String!, $name: String!, $limit: Int!) {
      repository(owner: $owner, name: $name) {
        issues(first: $limit, states: [OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
            title
            url
            createdAt
            updatedAt
            labels(first: 10) { nodes { name } }
            comments { totalCount }
            assignees(first: 1) { totalCount }
          }
        }
      }
    }
    """

    try:
        data = _github_graphql(query, {"owner": owner, "name": repo, "limit": limit})
        repo_data = data.get("repository")
        if not repo_data:
            logger.warning("Repository not found: %s/%s", owner, repo)
            return []

        issues = repo_data.get("issues", {}).get("nodes", []) or []

        def priority_score(issue: Dict[str, Any]) -> int:
            label_nodes = issue.get("labels", {}).get("nodes", []) or []
            labels_lower = {node.get("name", "").lower() for node in label_nodes}
            for i, pl in enumerate(PRIORITY_LABELS):
                if pl.lower() in labels_lower:
                    return i
            return len(PRIORITY_LABELS)

        return sorted(issues, key=priority_score)

    except Exception as e:
        logger.warning("GraphQL fetch failed: %s", e)
        return _fetch_issues_rest(owner, repo, limit)


def _fetch_issues_rest(owner: str, repo: str, limit: int = 50) -> List[Dict[str, Any]]:
    """REST API로 Open 이슈 조회 (폴백)."""
    import requests
    from backend.common.github_client import _build_headers, GITHUB_API_BASE

    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
        params = {"state": "open", "per_page": limit, "sort": "updated", "direction": "desc"}
        resp = requests.get(url, headers=_build_headers(), params=params, timeout=15)
        if resp.status_code != 200:
            return []
        return [issue for issue in resp.json() if "pull_request" not in issue]
    except Exception as e:
        logger.warning("REST API failed: %s", e)
        return []


def compute_task_score(
    difficulty: Difficulty,
    labels: List[str],
    comment_count: int = 0,
    recency_days: Optional[int] = None,
) -> float:
    """
    Task 우선순위 점수 (0-100).
    
    구성: 라벨(40) + 최신성(30) + 복잡도(30)
    가중치 설정: backend/agents/diagnosis/config/settings.py
    """
    from backend.agents.diagnosis.config import DIAGNOSIS_CONFIG
    w = DIAGNOSIS_CONFIG.task_score

    score = 0.0
    labels_lower = {label.lower() for label in labels}

    # 라벨 점수 (최대 40점)
    if labels_lower & {"good first issue", "good-first-issue"}:
        score += w.label_good_first_issue
    elif labels_lower & {"hacktoberfest"}:
        score += w.label_hacktoberfest
    elif labels_lower & {"help wanted", "help-wanted"}:
        score += w.label_help_wanted
    elif labels_lower & {"documentation", "docs"}:
        score += w.label_documentation
    elif labels_lower & {"tests", "testing"}:
        score += w.label_tests
    elif labels_lower & {"bug"}:
        score += w.label_bug
    else:
        score += w.label_default

    # 최신성 점수 (최대 30점)
    if recency_days is not None:
        if recency_days <= 7:
            score += w.recency_7d
        elif recency_days <= 30:
            score += w.recency_30d
        elif recency_days <= 90:
            score += w.recency_90d
        elif recency_days <= 180:
            score += w.recency_180d

    # 복잡도 점수 (댓글 적을수록 초보자 친화, 최대 30점)
    if comment_count <= 2:
        score += w.complexity_low
    elif comment_count <= 5:
        score += w.complexity_medium
    elif comment_count <= 10:
        score += w.complexity_high
    else:
        score += w.complexity_very_high

    return min(score, 100.0)


def determine_intent(difficulty: Difficulty, is_healthy: bool, is_active: bool) -> TaskIntent:
    """Task intent 결정."""
    if is_healthy and is_active:
        return "contribute"
    if not is_active:
        return "study" if difficulty == "beginner" else "evaluate"
    if difficulty == "beginner":
        return "study"
    elif difficulty == "intermediate":
        return "evaluate"
    return "contribute"


def generate_reason_tags(labels: List[str], difficulty: Difficulty) -> List[str]:
    """라벨에서 추천 이유 태그 생성."""
    tags: List[str] = []
    labels_lower = {label.lower() for label in labels}

    tag_map = {
        "good_first_issue": {"good first issue", "good-first-issue"},
        "help_wanted": {"help wanted", "help-wanted"},
        "docs_issue": {"documentation", "docs"},
        "test_issue": {"tests", "testing"},
        "hacktoberfest": {"hacktoberfest"},
        "bug_fix": {"bug"},
        "security_issue": {"security"},
        "feature_request": {"enhancement", "feature"},
        "refactoring": {"refactor", "refactoring"},
    }

    for tag, label_set in tag_map.items():
        if labels_lower & label_set:
            tags.append(tag)

    return tags or [f"difficulty_{difficulty}"]


def generate_fallback_reason(difficulty: Difficulty, reason_tags: List[str]) -> str:
    """태그 기반 기본 추천 이유 문장."""
    parts = []
    tag_reasons = {
        "good_first_issue": "메인테이너가 초보자용으로 표시한 이슈",
        "help_wanted": "기여자를 적극적으로 찾는 이슈",
        "docs_issue": "코드 이해 없이도 기여 가능",
        "test_issue": "코드베이스 학습에 도움",
        "hacktoberfest": "Hacktoberfest 참여 가능",
        "bug_fix": "버그 수정 이슈",
        "security_issue": "보안 관련 이슈",
    }

    for tag, reason in tag_reasons.items():
        if tag in reason_tags:
            parts.append(reason)

    if parts:
        return ", ".join(parts)

    difficulty_reasons = {
        "beginner": "초보자도 도전 가능한 난이도",
        "intermediate": "중급 수준의 기여 이슈",
        "advanced": "경험자에게 적합한 도전적인 이슈",
    }
    return difficulty_reasons.get(difficulty, "")


def create_tasks_from_issues(
    issues: List[Dict[str, Any]],
    repo_url: str,
    is_healthy: bool = True,
    is_active: bool = True,
) -> List[TaskSuggestion]:
    """GitHub 이슈에서 TaskSuggestion 생성."""
    from datetime import datetime, timezone

    tasks: List[TaskSuggestion] = []
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
        ))

    return tasks


def create_meta_tasks_from_labels(
    docs_issues: List[str],
    activity_issues: List[str],
    health_level: str,
    repo_url: str,
) -> List[TaskSuggestion]:
    """진단 결과(labels)에서 메타 Task 생성."""
    tasks: List[TaskSuggestion] = []

    # 문서 관련 (issue_key: (task_id, title, diff, lvl, reason, reason_tags))
    doc_meta = {
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

    for issue_key, (task_id, title, diff, lvl, reason, tags) in doc_meta.items():
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

    # 활동성 관련
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


def create_minimum_meta_tasks(repo_url: str) -> List[TaskSuggestion]:
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


def create_study_meta_tasks(repo_url: str) -> List[TaskSuggestion]:
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


def compute_onboarding_tasks(
    owner: str,
    repo: str,
    labels: Dict[str, Any],
    onboarding_plan: Optional[Dict[str, Any]] = None,
    max_issues: int = 30,
    min_tasks: int = 3,
) -> OnboardingTasks:
    """진단 결과를 바탕으로 온보딩 Task 목록 생성."""
    repo_url = f"https://github.com/{owner}/{repo}"

    health_level = labels.get("health_level", "warning")
    activity_issues = labels.get("activity_issues", [])
    docs_issues = labels.get("docs_issues", [])

    is_healthy = health_level == "good"
    is_active = "no_recent_commits" not in activity_issues and "inactive_project" not in activity_issues

    # 1. GitHub 이슈 기반 Task
    logger.info("Fetching open issues for onboarding tasks...")
    issues = fetch_open_issues_for_tasks(owner, repo, limit=max_issues)
    issue_tasks = create_tasks_from_issues(issues, repo_url, is_healthy, is_active)
    logger.info("Created %d tasks from %d issues", len(issue_tasks), len(issues))

    # 2. 메타 Task (진단 결과 기반)
    meta_tasks = create_meta_tasks_from_labels(docs_issues, activity_issues, health_level, repo_url)
    logger.info("Created %d meta tasks from diagnosis labels", len(meta_tasks))

    # 3. 최소 Task 보장
    all_tasks = issue_tasks + meta_tasks

    if len(all_tasks) < min_tasks:
        existing_ids = {t.id for t in all_tasks}
        extra_tasks = (
            create_minimum_meta_tasks(repo_url) if (is_healthy and is_active)
            else create_study_meta_tasks(repo_url)
        )
        for task in extra_tasks:
            if task.id not in existing_ids and len(all_tasks) < min_tasks:
                all_tasks.append(task)
                logger.info("Added extra task: %s", task.id)

    # 4. task_score 기준 정렬 후 난이도별 그룹핑
    def sort_key(t: TaskSuggestion):
        return (-t.task_score, t.level)

    beginner_tasks = sorted([t for t in all_tasks if t.difficulty == "beginner"], key=sort_key)
    intermediate_tasks = sorted([t for t in all_tasks if t.difficulty == "intermediate"], key=sort_key)
    advanced_tasks = sorted([t for t in all_tasks if t.difficulty == "advanced"], key=sort_key)

    issue_count = len([t for t in all_tasks if t.kind != "meta"])
    meta_count = len([t for t in all_tasks if t.kind == "meta"])

    return OnboardingTasks(
        beginner=beginner_tasks[:10],
        intermediate=intermediate_tasks[:10],
        advanced=advanced_tasks[:5],
        total_count=len(all_tasks),
        issue_count=issue_count,
        meta_count=meta_count,
    )


# 사용자 컨텍스트 기반 필터링

@dataclass
class UserTaskContext:
    """사용자 Task 필터링 컨텍스트."""
    experience_level: str = "beginner"
    preferred_kinds: List[str] = field(default_factory=list)
    time_budget_hours: Optional[float] = None
    preferred_intent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def filter_tasks_by_user_level(tasks: OnboardingTasks, user_level: str = "beginner") -> List[TaskSuggestion]:
    """사용자 레벨에 맞는 Task 필터링."""
    if user_level == "beginner":
        return tasks.beginner + tasks.intermediate[:3]
    elif user_level == "intermediate":
        return tasks.beginner[:3] + tasks.intermediate + tasks.advanced[:2]
    return tasks.beginner[:2] + tasks.intermediate + tasks.advanced


def _estimate_hours_from_level(level: int) -> float:
    """레벨에서 예상 소요 시간 추정 (시간 단위)."""
    return {1: 0.5, 2: 1.5, 3: 2.5, 4: 4.0, 5: 8.0, 6: 20.0}.get(level, 2.0)


def filter_tasks_for_user(
    tasks: OnboardingTasks,
    user_level: str = "beginner",
    preferred_kinds: Optional[List[str]] = None,
    time_budget_hours: Optional[float] = None,
    intent_filter: Optional[str] = None,
) -> List[TaskSuggestion]:
    """사용자 컨텍스트에 맞는 Task 필터링 및 우선순위 정렬."""
    filtered = filter_tasks_by_user_level(tasks, user_level)

    if intent_filter:
        filtered = [t for t in filtered if t.intent == intent_filter]

    if preferred_kinds:
        preferred = [t for t in filtered if t.kind in preferred_kinds]
        others = [t for t in filtered if t.kind not in preferred_kinds]
        filtered = preferred + others

    if time_budget_hours is not None:
        limited: List[TaskSuggestion] = []
        total_hours = 0.0
        for task in filtered:
            estimated = _estimate_hours_from_level(task.level)
            if total_hours + estimated <= time_budget_hours:
                limited.append(task)
                total_hours += estimated
            elif not limited:
                limited.append(task)
                break
        filtered = limited

    filtered.sort(key=lambda t: t.task_score, reverse=True)
    return filtered


def filter_tasks_by_context(tasks: OnboardingTasks, context: UserTaskContext) -> List[TaskSuggestion]:
    """사용자 컨텍스트 기반 개인화 필터링."""
    filtered = filter_tasks_by_user_level(tasks, context.experience_level)

    if context.preferred_intent:
        preferred = [t for t in filtered if t.intent == context.preferred_intent]
        others = [t for t in filtered if t.intent != context.preferred_intent]
        filtered = preferred + others

    if context.preferred_kinds:
        def kind_priority(task: TaskSuggestion) -> int:
            try:
                return context.preferred_kinds.index(task.kind)
            except ValueError:
                return len(context.preferred_kinds)

        preferred_kind_tasks = sorted(
            [t for t in filtered if t.kind in context.preferred_kinds],
            key=kind_priority,
        )
        other_tasks = [t for t in filtered if t.kind not in context.preferred_kinds]

        result: List[TaskSuggestion] = []
        pref_idx, other_idx = 0, 0
        while len(result) < len(filtered):
            for _ in range(2):
                if pref_idx < len(preferred_kind_tasks):
                    result.append(preferred_kind_tasks[pref_idx])
                    pref_idx += 1
            if other_idx < len(other_tasks):
                result.append(other_tasks[other_idx])
                other_idx += 1
            if pref_idx >= len(preferred_kind_tasks) and other_idx >= len(other_tasks):
                break
        filtered = result

    if context.time_budget_hours is not None:
        time_limited: List[TaskSuggestion] = []
        total_hours = 0.0
        for task in filtered:
            estimated = _estimate_hours_from_level(task.level)
            if total_hours + estimated <= context.time_budget_hours:
                time_limited.append(task)
                total_hours += estimated
            elif not time_limited:
                time_limited.append(task)
                break
        filtered = time_limited

    return filtered


def create_personalized_task_set(tasks: OnboardingTasks, context: UserTaskContext) -> Dict[str, Any]:
    """개인화된 Task 세트 생성."""
    filtered = filter_tasks_by_context(tasks, context)

    today_tasks: List[TaskSuggestion] = []
    week_tasks: List[TaskSuggestion] = []
    challenge_tasks: List[TaskSuggestion] = []

    budget = context.time_budget_hours or 2.0
    level_threshold = {"beginner": 3, "intermediate": 5, "advanced": 6}
    max_level = level_threshold.get(context.experience_level, 6)

    for task in filtered:
        hours = _estimate_hours_from_level(task.level)
        if task.level > max_level:
            challenge_tasks.append(task)
        elif hours <= budget:
            today_tasks.append(task)
        elif hours <= budget * 5:
            week_tasks.append(task)
        else:
            challenge_tasks.append(task)

    return {
        "today_tasks": [t.to_dict() for t in today_tasks[:5]],
        "week_tasks": [t.to_dict() for t in week_tasks[:10]],
        "challenge_tasks": [t.to_dict() for t in challenge_tasks[:3]],
        "meta": {
            "experience_level": context.experience_level,
            "time_budget_hours": budget,
            "preferred_kinds": context.preferred_kinds,
            "total_filtered": len(filtered),
        },
    }


# 레거시 호환: REST 폴백 함수 별칭
fetch_open_issues_for_tasks_rest = _fetch_issues_rest
