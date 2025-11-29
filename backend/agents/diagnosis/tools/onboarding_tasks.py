"""
Onboarding Tasks Generator v1.0

진단 결과를 바탕으로 난이도/레벨별 기여 Task를 제안하는 Tool.

데이터 소스:
1. GitHub 이슈 기반 (good-first-issue, help-wanted 등)
2. 진단 결과 기반 메타 Task (docs_issues에서 파생)

Related: docs/DIAGNOSIS_SCHEMA_v1.md
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 타입 정의
# ============================================================

Difficulty = Literal["beginner", "intermediate", "advanced"]
TaskKind = Literal["issue", "doc", "test", "refactor", "meta"]


# ============================================================
# 데이터 모델
# ============================================================

@dataclass
class TaskSuggestion:
    """기여 Task 제안"""
    
    kind: TaskKind  # "issue" | "doc" | "test" | "refactor" | "meta"
    difficulty: Difficulty  # "beginner" | "intermediate" | "advanced"
    level: int  # 1, 2, 3... (게임식 레벨)
    id: str  # "issue#123", "meta:improve_contributing"
    title: str
    url: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)  # 왜 추천했는지 (근거 문장)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OnboardingTasks:
    """난이도별 그룹핑된 Task 목록"""
    
    beginner: List[TaskSuggestion] = field(default_factory=list)
    intermediate: List[TaskSuggestion] = field(default_factory=list)
    advanced: List[TaskSuggestion] = field(default_factory=list)
    
    # 메타 정보
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


# ============================================================
# 라벨 기반 난이도 결정
# ============================================================

# Beginner 라벨 (가장 우선순위 높음)
BEGINNER_LABELS = {
    "good first issue",
    "good-first-issue",
    "beginner",
    "beginner-friendly",
    "first-timers-only",
    "first-time-contributor",
    "easy",
    "starter",
    "newbie",
    "hacktoberfest",
}

# Intermediate 라벨
INTERMEDIATE_LABELS = {
    "help wanted",
    "help-wanted",
    "documentation",
    "docs",
    "tests",
    "testing",
    "enhancement",
    "feature",
    "improvement",
}

# Advanced 라벨
ADVANCED_LABELS = {
    "bug",
    "critical",
    "security",
    "performance",
    "refactor",
    "breaking-change",
    "architecture",
    "core",
}


def determine_difficulty_from_labels(labels: List[str]) -> Difficulty:
    """라벨 목록에서 난이도 결정."""
    labels_lower = {label.lower() for label in labels}
    
    # Beginner 라벨 우선
    if labels_lower & BEGINNER_LABELS:
        return "beginner"
    
    # Advanced 라벨
    if labels_lower & ADVANCED_LABELS:
        return "advanced"
    
    # Intermediate 라벨 또는 기본값
    if labels_lower & INTERMEDIATE_LABELS:
        return "intermediate"
    
    return "intermediate"  # 기본값


def determine_level(difficulty: Difficulty, labels: List[str], comment_count: int = 0) -> int:
    """난이도 + 메타데이터 기반 레벨 결정."""
    labels_lower = {label.lower() for label in labels}
    
    if difficulty == "beginner":
        # good-first-issue → level 1, 그 외 beginner → level 2
        if labels_lower & {"good first issue", "good-first-issue", "first-timers-only"}:
            return 1
        return 2
    
    elif difficulty == "intermediate":
        # docs/test → level 3, 그 외 → level 4
        if labels_lower & {"documentation", "docs", "tests", "testing"}:
            return 3
        return 4
    
    else:  # advanced
        # 댓글 많은 복잡한 이슈 → level 6, 그 외 → level 5
        if comment_count > 10:
            return 6
        return 5


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


# ============================================================
# GitHub 이슈 기반 Task 생성
# ============================================================

def fetch_open_issues_for_tasks(
    owner: str,
    repo: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    기여 가능한 Open 이슈 목록 조회.
    
    good-first-issue, help-wanted 등 라벨 우선으로 가져옴.
    """
    from backend.common.github_client import _github_graphql
    
    query = """
    query($owner: String!, $name: String!, $limit: Int!) {
      repository(owner: $owner, name: $name) {
        issues(
          first: $limit
          states: [OPEN]
          orderBy: { field: UPDATED_AT, direction: DESC }
        ) {
          nodes {
            number
            title
            url
            state
            createdAt
            updatedAt
            labels(first: 10) {
              nodes { name }
            }
            comments { totalCount }
            author { login }
            assignees(first: 3) {
              nodes { login }
            }
          }
        }
      }
    }
    """
    
    try:
        data = _github_graphql(query, {"owner": owner, "name": repo, "limit": limit})
        repo_data = data.get("repository")
        if not repo_data:
            return []
        
        issues = repo_data.get("issues", {}).get("nodes", [])
        return issues
    
    except Exception as e:
        logger.warning("Failed to fetch issues for tasks: %s", e)
        return []


def fetch_open_issues_for_tasks_rest(
    owner: str,
    repo: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    REST API로 Open 이슈 조회 (GraphQL 대안).
    """
    import requests
    from backend.common.github_client import _build_headers, GITHUB_API_BASE
    
    try:
        # good-first-issue 라벨 이슈 우선
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
        params = {
            "state": "open",
            "per_page": limit,
            "sort": "updated",
            "direction": "desc",
        }
        
        resp = requests.get(url, headers=_build_headers(), params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning("REST API failed: %s", resp.status_code)
            return []
        
        issues = resp.json()
        # PR 제외 (PR도 issues API에 포함됨)
        return [issue for issue in issues if "pull_request" not in issue]
    
    except Exception as e:
        logger.warning("Failed to fetch issues via REST: %s", e)
        return []


def create_tasks_from_issues(
    issues: List[Dict[str, Any]],
    repo_url: str,
) -> List[TaskSuggestion]:
    """GitHub 이슈에서 TaskSuggestion 생성."""
    tasks: List[TaskSuggestion] = []
    
    for issue in issues:
        # GraphQL 형식
        if "labels" in issue and isinstance(issue.get("labels"), dict):
            label_nodes = issue.get("labels", {}).get("nodes", [])
            labels = [node.get("name", "") for node in label_nodes]
            comment_count = issue.get("comments", {}).get("totalCount", 0)
            url = issue.get("url", "")
        # REST API 형식
        else:
            labels = [label.get("name", "") for label in issue.get("labels", [])]
            comment_count = issue.get("comments", 0)
            url = issue.get("html_url", "")
        
        number = issue.get("number")
        title = issue.get("title", "")
        
        # 난이도/레벨 결정
        difficulty = determine_difficulty_from_labels(labels)
        level = determine_level(difficulty, labels, comment_count)
        kind = determine_kind_from_labels(labels)
        
        # 추천 이유 생성
        reasons = generate_issue_reasons(labels, difficulty)
        
        task = TaskSuggestion(
            kind=kind,
            difficulty=difficulty,
            level=level,
            id=f"issue#{number}",
            title=title,
            url=url,
            labels=labels,
            reasons=reasons,
        )
        tasks.append(task)
    
    return tasks


def generate_issue_reasons(labels: List[str], difficulty: Difficulty) -> List[str]:
    """이슈에 대한 추천 이유 생성."""
    reasons: List[str] = []
    labels_lower = {label.lower() for label in labels}
    
    if labels_lower & {"good first issue", "good-first-issue"}:
        reasons.append("good-first-issue 라벨: 메인테이너가 초보자용으로 표시한 이슈")
    
    if labels_lower & {"help wanted", "help-wanted"}:
        reasons.append("help-wanted 라벨: 기여자를 적극적으로 찾는 이슈")
    
    if labels_lower & {"documentation", "docs"}:
        reasons.append("문서 관련 이슈: 코드 이해 없이도 기여 가능")
    
    if labels_lower & {"tests", "testing"}:
        reasons.append("테스트 관련 이슈: 코드베이스 학습에 도움")
    
    if labels_lower & {"hacktoberfest"}:
        reasons.append("Hacktoberfest 참여 가능 이슈")
    
    if not reasons:
        if difficulty == "beginner":
            reasons.append("초보자도 도전 가능한 난이도")
        elif difficulty == "intermediate":
            reasons.append("중급 수준의 기여 이슈")
        else:
            reasons.append("경험자에게 적합한 도전적인 이슈")
    
    return reasons


# ============================================================
# 메타 Task 생성 (진단 결과 기반)
# ============================================================

def create_meta_tasks_from_labels(
    docs_issues: List[str],
    activity_issues: List[str],
    health_level: str,
    repo_url: str,
) -> List[TaskSuggestion]:
    """
    진단 결과(labels)에서 메타 Task 생성.
    
    실제 이슈가 없어도, 개선이 필요한 영역에 대한 가상 Task 제안.
    """
    tasks: List[TaskSuggestion] = []
    
    # 1. 문서 관련 메타 Task
    if "missing_contributing" in docs_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=2,
            id="meta:create_contributing",
            title="CONTRIBUTING.md 초안 작성",
            url=None,
            labels=["documentation", "meta"],
            reasons=[
                "프로젝트에 CONTRIBUTING.md가 없음",
                "기여 가이드 문서를 만들면 다른 기여자에게 도움",
                "문서 작성은 코드 이해 없이도 가능",
            ],
        ))
    
    if "missing_what" in docs_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=1,
            id="meta:improve_readme_what",
            title="README에 '프로젝트 소개' 섹션 보강",
            url=None,
            labels=["documentation", "meta"],
            reasons=[
                "README에 프로젝트가 무엇인지 설명이 부족",
                "간단한 소개 문구 추가로 큰 기여 가능",
            ],
        ))
    
    if "missing_why" in docs_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=2,
            id="meta:improve_readme_why",
            title="README에 '왜 이 프로젝트가 필요한지' 섹션 추가",
            url=None,
            labels=["documentation", "meta"],
            reasons=[
                "프로젝트의 필요성/동기 설명이 부족",
                "사용 사례나 문제 해결 시나리오 추가 권장",
            ],
        ))
    
    if "missing_how" in docs_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="intermediate",
            level=3,
            id="meta:add_installation_guide",
            title="설치 및 실행 가이드 작성",
            url=None,
            labels=["documentation", "meta"],
            reasons=[
                "Quick Start 또는 Installation 가이드가 없음",
                "개발 환경 세팅 경험이 있으면 작성 가능",
            ],
        ))
    
    if "weak_documentation" in docs_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="intermediate",
            level=3,
            id="meta:improve_documentation",
            title="전반적인 문서 품질 개선",
            url=None,
            labels=["documentation", "meta"],
            reasons=[
                "문서화 점수가 낮음 (50점 미만)",
                "README나 관련 문서의 전반적인 개선 필요",
            ],
        ))
    
    # 2. 활동성 관련 메타 Task
    if "inactive_project" in activity_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="advanced",
            level=5,
            id="meta:check_maintainer_status",
            title="메인테이너 활동 여부 확인 및 커뮤니케이션",
            url=None,
            labels=["meta", "communication"],
            reasons=[
                "[주의] 프로젝트가 비활성 상태로 보임",
                "기여 전에 메인테이너에게 연락하여 상태 확인 권장",
                "이슈나 Discussion에 질문 글 작성 고려",
            ],
        ))
    
    if "low_issue_closure" in activity_issues:
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="intermediate",
            level=4,
            id="meta:help_triage_issues",
            title="오래된 이슈 정리(triage) 도움",
            url=None,
            labels=["meta", "triage"],
            reasons=[
                "이슈 처리율이 낮음",
                "오래된 이슈에 댓글로 상태 확인 요청",
                "재현 가능 여부 테스트 후 리포트",
            ],
        ))
    
    # 3. 건강 상태 기반 추가 Task
    if health_level == "bad":
        tasks.append(TaskSuggestion(
            kind="meta",
            difficulty="advanced",
            level=6,
            id="meta:evaluate_project_health",
            title="프로젝트 건강 상태 평가 및 개선 제안",
            url=None,
            labels=["meta", "analysis"],
            reasons=[
                "[주의] 프로젝트 전반적인 건강 상태가 좋지 않음",
                "기여하기 전에 프로젝트 상태를 신중히 평가 권장",
                "개선 방향을 Discussion에 제안하는 것도 좋은 기여",
            ],
        ))
    
    return tasks


# ============================================================
# 메인 함수: compute_onboarding_tasks
# ============================================================

def compute_onboarding_tasks(
    owner: str,
    repo: str,
    labels: Dict[str, Any],
    onboarding_plan: Optional[Dict[str, Any]] = None,
    max_issues: int = 30,
) -> OnboardingTasks:
    """
    진단 결과를 바탕으로 온보딩 Task 목록 생성.
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        labels: create_diagnosis_labels() 결과 (to_dict())
        onboarding_plan: create_onboarding_plan() 결과 (to_dict())
        max_issues: 조회할 최대 이슈 수
    
    Returns:
        OnboardingTasks (난이도별 그룹핑)
    """
    repo_url = f"https://github.com/{owner}/{repo}"
    
    # 1. GitHub 이슈 기반 Task
    logger.info("Fetching open issues for onboarding tasks...")
    issues = fetch_open_issues_for_tasks_rest(owner, repo, limit=max_issues)
    issue_tasks = create_tasks_from_issues(issues, repo_url)
    logger.info("Created %d tasks from %d issues", len(issue_tasks), len(issues))
    
    # 2. 메타 Task (진단 결과 기반)
    docs_issues = labels.get("docs_issues", [])
    activity_issues = labels.get("activity_issues", [])
    health_level = labels.get("health_level", "warning")
    
    meta_tasks = create_meta_tasks_from_labels(
        docs_issues=docs_issues,
        activity_issues=activity_issues,
        health_level=health_level,
        repo_url=repo_url,
    )
    logger.info("Created %d meta tasks from diagnosis labels", len(meta_tasks))
    
    # 3. 모든 Task 병합
    all_tasks = issue_tasks + meta_tasks
    
    # 4. 난이도별 그룹핑
    beginner_tasks = sorted(
        [t for t in all_tasks if t.difficulty == "beginner"],
        key=lambda t: t.level,
    )
    intermediate_tasks = sorted(
        [t for t in all_tasks if t.difficulty == "intermediate"],
        key=lambda t: t.level,
    )
    advanced_tasks = sorted(
        [t for t in all_tasks if t.difficulty == "advanced"],
        key=lambda t: t.level,
    )
    
    # 5. 결과 생성
    result = OnboardingTasks(
        beginner=beginner_tasks[:10],  # 각 난이도별 최대 10개
        intermediate=intermediate_tasks[:10],
        advanced=advanced_tasks[:5],  # advanced는 5개로 제한
        total_count=len(all_tasks),
        issue_count=len(issue_tasks),
        meta_count=len(meta_tasks),
    )
    
    return result


# ============================================================
# 진단 결과 기반 필터링 (optional)
# ============================================================

def filter_tasks_by_user_level(
    tasks: OnboardingTasks,
    user_level: str = "beginner",
) -> List[TaskSuggestion]:
    """
    사용자 레벨에 맞는 Task만 필터링.
    
    beginner: beginner 전체 + intermediate 일부
    intermediate: beginner 일부 + intermediate 전체 + advanced 일부
    advanced: 모든 난이도
    """
    if user_level == "beginner":
        return tasks.beginner + tasks.intermediate[:3]
    elif user_level == "intermediate":
        return tasks.beginner[:3] + tasks.intermediate + tasks.advanced[:2]
    else:  # advanced
        return tasks.beginner[:2] + tasks.intermediate + tasks.advanced
