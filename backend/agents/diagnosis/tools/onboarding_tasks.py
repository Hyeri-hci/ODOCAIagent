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
TaskIntent = Literal["contribute", "study", "evaluate"]  # 기여 / 학습 / 평가


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
    # 구조적 추천 근거 (LLM 프롬프트용 태그/플래그)
    reason_tags: List[str] = field(default_factory=list)  # ["good_first_issue", "help_wanted", "docs_issue"]
    meta_flags: List[str] = field(default_factory=list)   # ["missing_contributing", "inactive_project"]
    # Fallback용 기본 이유 문장 (LLM 실패 시 사용)
    fallback_reason: Optional[str] = None
    # 고도화 필드 (v1.1)
    intent: TaskIntent = "contribute"  # "contribute" | "study" | "evaluate"
    task_score: float = 0.0  # 우선순위 점수 (0-100, recency/comment/라벨 반영)
    recency_days: Optional[int] = None  # 마지막 업데이트로부터 경과 일수
    comment_count: int = 0  # 댓글 수
    
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

# 온보딩에 적합한 라벨 (우선순위 순)
PRIORITY_LABELS = [
    "good first issue",
    "good-first-issue", 
    "beginner",
    "beginner-friendly",
    "first-timers-only",
    "help wanted",
    "help-wanted",
    "documentation",
    "docs",
    "hacktoberfest",
]


def fetch_open_issues_for_tasks(
    owner: str,
    repo: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    GraphQL로 기여 가능한 Open 이슈 목록 조회.
    
    - 최신 업데이트 순으로 정렬
    - 필요한 필드만 가져와서 응답 크기 최적화
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
            createdAt
            updatedAt
            labels(first: 10) {
              nodes { name }
            }
            comments { totalCount }
            assignees(first: 1) {
              totalCount
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
            logger.warning("Repository not found: %s/%s", owner, repo)
            return []
        
        issues = repo_data.get("issues", {}).get("nodes", []) or []
        
        # 우선순위 라벨이 있는 이슈를 앞으로 정렬
        def priority_score(issue: Dict[str, Any]) -> int:
            label_nodes = issue.get("labels", {}).get("nodes", []) or []
            labels_lower = {node.get("name", "").lower() for node in label_nodes}
            
            for i, priority_label in enumerate(PRIORITY_LABELS):
                if priority_label.lower() in labels_lower:
                    return i  # 낮을수록 우선순위 높음
            return len(PRIORITY_LABELS)  # 우선순위 라벨 없음
        
        issues_sorted = sorted(issues, key=priority_score)
        return issues_sorted
    
    except Exception as e:
        logger.warning("GraphQL fetch failed, falling back to REST: %s", e)
        # GraphQL 실패 시 REST로 폴백
        return fetch_open_issues_for_tasks_rest(owner, repo, limit)


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
    is_healthy: bool = True,
    is_active: bool = True,
) -> List[TaskSuggestion]:
    """
    GitHub 이슈에서 TaskSuggestion 생성.
    
    Args:
        issues: GitHub 이슈 목록
        repo_url: 저장소 URL
        is_healthy: 프로젝트 건강 여부 (intent 결정에 사용)
        is_active: 프로젝트 활성 여부 (intent 결정에 사용)
    """
    from datetime import datetime, timezone
    
    tasks: List[TaskSuggestion] = []
    now = datetime.now(timezone.utc)
    
    for issue in issues:
        # GraphQL 형식
        if "labels" in issue and isinstance(issue.get("labels"), dict):
            label_nodes = issue.get("labels", {}).get("nodes", [])
            labels = [node.get("name", "") for node in label_nodes]
            comment_count = issue.get("comments", {}).get("totalCount", 0)
            url = issue.get("url", "")
            updated_at_str = issue.get("updatedAt", "")
        # REST API 형식
        else:
            labels = [label.get("name", "") for label in issue.get("labels", [])]
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
        
        # 난이도/레벨 결정
        difficulty = determine_difficulty_from_labels(labels)
        level = determine_level(difficulty, labels, comment_count)
        kind = determine_kind_from_labels(labels)
        
        # 구조적 태그 생성 (LLM 프롬프트용)
        reason_tags = generate_reason_tags(labels, difficulty)
        fallback = generate_fallback_reason(difficulty, reason_tags)
        
        # task_score 계산
        task_score = compute_task_score(
            difficulty=difficulty,
            labels=labels,
            comment_count=comment_count,
            recency_days=recency_days,
        )
        
        # intent 결정 (비건강/비활성 프로젝트는 study 중심)
        intent = determine_intent(
            difficulty=difficulty,
            is_healthy=is_healthy,
            is_active=is_active,
        )
        
        task = TaskSuggestion(
            kind=kind,
            difficulty=difficulty,
            level=level,
            id=f"issue#{number}",
            title=title,
            url=url,
            labels=labels,
            reason_tags=reason_tags,
            meta_flags=[],
            fallback_reason=fallback,
            intent=intent,
            task_score=task_score,
            recency_days=recency_days,
            comment_count=comment_count,
        )
        tasks.append(task)
    
    return tasks


# ============================================================
# Task 스코어링 (우선순위 결정)
# ============================================================

def compute_task_score(
    difficulty: Difficulty,
    labels: List[str],
    comment_count: int = 0,
    recency_days: Optional[int] = None,
) -> float:
    """
    Task 우선순위 점수 계산 (0-100).
    
    구성요소:
    - 라벨 점수 (0-40): good-first-issue, help-wanted 등
    - 최신성 점수 (0-30): 최근 업데이트일수록 높음
    - 복잡도 점수 (0-30): 댓글 수 기반 (적정 수준이 좋음)
    """
    score = 0.0
    labels_lower = {label.lower() for label in labels}
    
    # 1. 라벨 점수 (0-40)
    if labels_lower & {"good first issue", "good-first-issue"}:
        score += 40
    elif labels_lower & {"help wanted", "help-wanted"}:
        score += 30
    elif labels_lower & {"documentation", "docs"}:
        score += 25
    elif labels_lower & {"tests", "testing"}:
        score += 20
    elif labels_lower & {"hacktoberfest"}:
        score += 35
    elif labels_lower & {"bug"}:
        score += 15
    else:
        score += 10  # 기본
    
    # 2. 최신성 점수 (0-30)
    if recency_days is not None:
        if recency_days <= 7:
            score += 30
        elif recency_days <= 30:
            score += 25
        elif recency_days <= 90:
            score += 15
        elif recency_days <= 180:
            score += 5
        # 180일 이상은 0점
    
    # 3. 복잡도 점수 (0-30) - 댓글 수 기반
    # 0-2개: 30점 (논의 적음 = 초보자 친화)
    # 3-5개: 25점 (적정 수준)
    # 6-10개: 15점
    # 11+: 5점 (복잡한 이슈)
    if comment_count <= 2:
        score += 30
    elif comment_count <= 5:
        score += 25
    elif comment_count <= 10:
        score += 15
    else:
        score += 5
    
    return min(score, 100.0)


def determine_intent(
    difficulty: Difficulty,
    is_healthy: bool = True,
    is_active: bool = True,
) -> TaskIntent:
    """
    Task의 intent 결정.
    
    건강하고 활성인 프로젝트:
    - 모든 난이도 → contribute
    
    비활성 프로젝트 (no_recent_commits 등):
    - beginner → study (학습용)
    - intermediate/advanced → evaluate (평가/분석용)
    
    비건강 프로젝트 (health_level != good):
    - beginner → study
    - intermediate → evaluate
    - advanced → contribute (경험자만 기여 권장)
    """
    if is_healthy and is_active:
        return "contribute"
    
    # 비활성 프로젝트 (더 엄격하게 study/evaluate)
    if not is_active:
        if difficulty == "beginner":
            return "study"
        else:
            return "evaluate"  # intermediate, advanced 모두 evaluate
    
    # 비건강하지만 활성인 프로젝트
    if difficulty == "beginner":
        return "study"
    elif difficulty == "intermediate":
        return "evaluate"
    else:
        return "contribute"  # advanced만 기여 권장


# ============================================================
# 구조적 태그 생성 (LLM 프롬프트용)
# ============================================================

def generate_reason_tags(labels: List[str], difficulty: Difficulty) -> List[str]:
    """라벨에서 추천 이유 태그 생성 (LLM 프롬프트용)."""
    tags: List[str] = []
    labels_lower = {label.lower() for label in labels}
    
    if labels_lower & {"good first issue", "good-first-issue"}:
        tags.append("good_first_issue")
    
    if labels_lower & {"help wanted", "help-wanted"}:
        tags.append("help_wanted")
    
    if labels_lower & {"documentation", "docs"}:
        tags.append("docs_issue")
    
    if labels_lower & {"tests", "testing"}:
        tags.append("test_issue")
    
    if labels_lower & {"hacktoberfest"}:
        tags.append("hacktoberfest")
    
    if labels_lower & {"bug"}:
        tags.append("bug_fix")
    
    if labels_lower & {"security"}:
        tags.append("security_issue")
    
    if labels_lower & {"enhancement", "feature"}:
        tags.append("feature_request")
    
    if labels_lower & {"refactor", "refactoring"}:
        tags.append("refactoring")
    
    # 기본 난이도 태그 (다른 태그가 없을 때)
    if not tags:
        tags.append(f"difficulty_{difficulty}")
    
    return tags


def generate_fallback_reason(difficulty: Difficulty, reason_tags: List[str]) -> str:
    """태그 기반 기본 추천 이유 문장 생성 (LLM 실패 시 Fallback)."""
    parts: List[str] = []
    
    if "good_first_issue" in reason_tags:
        parts.append("메인테이너가 초보자용으로 표시한 이슈")
    if "help_wanted" in reason_tags:
        parts.append("기여자를 적극적으로 찾는 이슈")
    if "docs_issue" in reason_tags:
        parts.append("코드 이해 없이도 기여 가능")
    if "test_issue" in reason_tags:
        parts.append("코드베이스 학습에 도움")
    if "hacktoberfest" in reason_tags:
        parts.append("Hacktoberfest 참여 가능")
    if "bug_fix" in reason_tags:
        parts.append("버그 수정 이슈")
    if "security_issue" in reason_tags:
        parts.append("보안 관련 이슈")
    
    if parts:
        return ", ".join(parts)
    
    # 기본 난이도별 문장
    if difficulty == "beginner":
        return "초보자도 도전 가능한 난이도"
    elif difficulty == "intermediate":
        return "중급 수준의 기여 이슈"
    else:
        return "경험자에게 적합한 도전적인 이슈"


# ============================================================
# 메타 Task 생성 (진단 결과 기반)
# ============================================================

# 건강한 프로젝트용 메타 Task (이슈가 없어도 기여할 수 있는 Task)
HEALTHY_PROJECT_META_TASKS: List[TaskSuggestion] = [
    TaskSuggestion(
        kind="meta",
        difficulty="beginner",
        level=2,
        id="meta:write_tutorial",
        title="사용자를 위한 튜토리얼 작성",
        url=None,
        labels=["documentation", "meta"],
        reason_tags=["community_contribution", "docs_improvement"],
        meta_flags=["healthy_project"],
        fallback_reason="건강한 프로젝트에 튜토리얼 문서로 기여할 수 있습니다",
        intent="contribute",
        task_score=60.0,
    ),
    TaskSuggestion(
        kind="meta",
        difficulty="beginner",
        level=2,
        id="meta:improve_examples",
        title="코드 예제 보강",
        url=None,
        labels=["documentation", "meta"],
        reason_tags=["community_contribution", "beginner_friendly"],
        meta_flags=["healthy_project"],
        fallback_reason="예제 코드 추가/개선으로 다른 사용자에게 도움을 줄 수 있습니다",
        intent="contribute",
        task_score=55.0,
    ),
    TaskSuggestion(
        kind="meta",
        difficulty="intermediate",
        level=3,
        id="meta:triage_issues",
        title="이슈 정리 및 라벨링 도움",
        url=None,
        labels=["meta", "community"],
        reason_tags=["community_contribution", "organization"],
        meta_flags=["healthy_project"],
        fallback_reason="이슈 분류, 중복 확인 등 커뮤니티 기여가 가능합니다",
        intent="contribute",
        task_score=50.0,
    ),
]

# 비건강/아카이브 프로젝트용 학습 메타 Task
STUDY_META_TASKS: List[TaskSuggestion] = [
    TaskSuggestion(
        kind="meta",
        difficulty="beginner",
        level=2,
        id="meta:analyze_architecture",
        title="프로젝트 아키텍처 분석 및 학습",
        url=None,
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "architecture"],
        meta_flags=["study_mode"],
        fallback_reason="코드를 읽고 아키텍처를 분석하여 학습할 수 있습니다",
        intent="study",
        task_score=70.0,
    ),
    TaskSuggestion(
        kind="meta",
        difficulty="beginner",
        level=2,
        id="meta:document_learnings",
        title="학습 내용 개인 블로그/노트 정리",
        url=None,
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "personal_growth"],
        meta_flags=["study_mode"],
        fallback_reason="프로젝트에서 배운 내용을 정리하여 지식을 공고히 할 수 있습니다",
        intent="study",
        task_score=65.0,
    ),
    TaskSuggestion(
        kind="meta",
        difficulty="intermediate",
        level=3,
        id="meta:evaluate_alternatives",
        title="대안 프로젝트 비교/평가",
        url=None,
        labels=["meta", "evaluation"],
        reason_tags=["evaluation", "comparison"],
        meta_flags=["evaluate_mode", "inactive_project"],
        fallback_reason="이 프로젝트가 비활성인 경우, 활발한 대안을 찾아볼 수 있습니다",
        intent="evaluate",
        task_score=60.0,
    ),
    TaskSuggestion(
        kind="meta",
        difficulty="intermediate",
        level=3,
        id="meta:review_codebase",
        title="코드베이스 리뷰 및 패턴 학습",
        url=None,
        labels=["meta", "learning"],
        reason_tags=["learning_opportunity", "code_review"],
        meta_flags=["study_mode"],
        fallback_reason="실제 프로젝트 코드를 읽으며 베스트 프랙티스를 배울 수 있습니다",
        intent="study",
        task_score=55.0,
    ),
]


def create_meta_tasks_from_labels(
    docs_issues: List[str],
    activity_issues: List[str],
    health_level: str,
    repo_url: str,
) -> List[TaskSuggestion]:
    """
    진단 결과(labels)에서 메타 Task 생성.
    
    실제 이슈가 없어도, 개선이 필요한 영역에 대한 가상 Task 제안.
    reason_tags와 meta_flags로 구조적 정보 전달, LLM이 자연어 생성.
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
            reason_tags=["docs_issue", "low_barrier"],
            meta_flags=["missing_contributing"],
            fallback_reason="프로젝트에 CONTRIBUTING.md가 없어 기여 가이드 작성이 필요함",
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
            reason_tags=["docs_issue", "low_barrier", "quick_win"],
            meta_flags=["missing_what"],
            fallback_reason="README에 프로젝트 소개가 부족하여 간단한 문구 추가로 기여 가능",
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
            reason_tags=["docs_issue", "storytelling"],
            meta_flags=["missing_why"],
            fallback_reason="프로젝트의 필요성/동기 설명 추가로 사용자 이해 향상 가능",
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
            reason_tags=["docs_issue", "onboarding_critical"],
            meta_flags=["missing_how"],
            fallback_reason="Quick Start 또는 Installation 가이드가 없어 개발 환경 세팅 문서 필요",
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
            reason_tags=["docs_issue", "quality_improvement"],
            meta_flags=["weak_documentation"],
            fallback_reason="문서화 점수가 낮아 README 및 관련 문서 전반적 개선 필요",
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
            reason_tags=["caution_needed", "communication_required"],
            meta_flags=["inactive_project"],
            fallback_reason="[주의] 프로젝트가 비활성 상태로, 기여 전 메인테이너 연락 권장",
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
            reason_tags=["community_help", "issue_management"],
            meta_flags=["low_issue_closure"],
            fallback_reason="이슈 처리율이 낮아 오래된 이슈 상태 확인 및 정리 도움 필요",
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
            reason_tags=["caution_needed", "strategic_contribution"],
            meta_flags=["unhealthy_project"],
            fallback_reason="[주의] 프로젝트 전반적 건강 상태가 좋지 않아 신중한 평가 필요",
            intent="evaluate",
            task_score=30.0,
        ))
    
    return tasks


def create_minimum_meta_tasks(repo_url: str) -> List[TaskSuggestion]:
    """
    건강한 프로젝트를 위한 최소 메타 Task 생성.
    
    이슈가 없어도 항상 제공할 수 있는 "추천 활동" 목록.
    """
    return [
        TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=1,
            id="meta:write_tutorial",
            title="초보자를 위한 튜토리얼/블로그 포스트 작성",
            url=None,
            labels=["documentation", "meta", "community"],
            reason_tags=["community_contribution", "low_barrier", "external"],
            meta_flags=["minimum_task"],
            fallback_reason="프로젝트 사용법을 블로그나 미디엄에 작성하여 커뮤니티에 기여",
            intent="contribute",
            task_score=70.0,
        ),
        TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=2,
            id="meta:improve_examples",
            title="예제 코드/샘플 프로젝트 보강",
            url=None,
            labels=["documentation", "meta", "examples"],
            reason_tags=["docs_issue", "quick_win", "practical"],
            meta_flags=["minimum_task"],
            fallback_reason="README나 examples/ 폴더에 실용적인 예제 코드 추가",
            intent="contribute",
            task_score=65.0,
        ),
        TaskSuggestion(
            kind="meta",
            difficulty="intermediate",
            level=3,
            id="meta:triage_open_issues",
            title="오픈 이슈 정리/레이블링 도움",
            url=None,
            labels=["meta", "triage", "community"],
            reason_tags=["community_help", "issue_management"],
            meta_flags=["minimum_task"],
            fallback_reason="기존 이슈에 댓글로 상태 확인하거나 레이블 제안",
            intent="contribute",
            task_score=55.0,
        ),
    ]


def create_study_meta_tasks(repo_url: str) -> List[TaskSuggestion]:
    """
    비건강/비활성 프로젝트를 위한 학습용 메타 Task.
    
    적극적인 기여 대신 학습/평가 목적 활동 제안.
    """
    return [
        TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=1,
            id="meta:study_architecture",
            title="프로젝트 아키텍처 분석 및 학습",
            url=None,
            labels=["meta", "study", "learning"],
            reason_tags=["learning_opportunity", "code_reading"],
            meta_flags=["study_task", "inactive_friendly"],
            fallback_reason="코드 구조와 설계 패턴을 분석하여 학습 (기여 없이도 가치 있음)",
            intent="study",
            task_score=60.0,
        ),
        TaskSuggestion(
            kind="meta",
            difficulty="beginner",
            level=2,
            id="meta:document_learnings",
            title="학습 내용 정리 (개인 노트/블로그)",
            url=None,
            labels=["meta", "study", "documentation"],
            reason_tags=["learning_opportunity", "external"],
            meta_flags=["study_task"],
            fallback_reason="프로젝트에서 배운 것을 개인 블로그나 노트에 정리",
            intent="study",
            task_score=55.0,
        ),
        TaskSuggestion(
            kind="meta",
            difficulty="intermediate",
            level=3,
            id="meta:evaluate_alternatives",
            title="유사 프로젝트/대안 비교 분석",
            url=None,
            labels=["meta", "evaluate", "analysis"],
            reason_tags=["evaluation", "comparison"],
            meta_flags=["study_task"],
            fallback_reason="이 프로젝트와 유사한 다른 프로젝트를 비교 분석",
            intent="evaluate",
            task_score=50.0,
        ),
    ]


# ============================================================
# 메인 함수: compute_onboarding_tasks
# ============================================================

def compute_onboarding_tasks(
    owner: str,
    repo: str,
    labels: Dict[str, Any],
    onboarding_plan: Optional[Dict[str, Any]] = None,
    max_issues: int = 30,
    min_tasks: int = 3,
) -> OnboardingTasks:
    """
    진단 결과를 바탕으로 온보딩 Task 목록 생성.
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        labels: create_diagnosis_labels() 결과 (to_dict())
        onboarding_plan: create_onboarding_plan() 결과 (to_dict())
        max_issues: 조회할 최대 이슈 수
        min_tasks: 최소 Task 개수 (건강한 프로젝트라도 이 개수 보장)
    
    Returns:
        OnboardingTasks (난이도별 그룹핑)
    """
    repo_url = f"https://github.com/{owner}/{repo}"
    
    # 프로젝트 상태 판단
    health_level = labels.get("health_level", "warning")
    activity_issues = labels.get("activity_issues", [])
    docs_issues = labels.get("docs_issues", [])
    
    is_healthy = health_level == "good"
    is_active = "no_recent_commits" not in activity_issues and "inactive_project" not in activity_issues
    
    # 1. GitHub 이슈 기반 Task (GraphQL 우선, 실패 시 REST 폴백)
    logger.info("Fetching open issues for onboarding tasks...")
    issues = fetch_open_issues_for_tasks(owner, repo, limit=max_issues)
    issue_tasks = create_tasks_from_issues(
        issues, repo_url,
        is_healthy=is_healthy,
        is_active=is_active,
    )
    logger.info("Created %d tasks from %d issues", len(issue_tasks), len(issues))
    
    # 2. 메타 Task (진단 결과 기반)
    meta_tasks = create_meta_tasks_from_labels(
        docs_issues=docs_issues,
        activity_issues=activity_issues,
        health_level=health_level,
        repo_url=repo_url,
    )
    logger.info("Created %d meta tasks from diagnosis labels", len(meta_tasks))
    
    # 3. 최소 Task 보장 정책
    all_tasks = issue_tasks + meta_tasks
    
    if len(all_tasks) < min_tasks:
        if is_healthy and is_active:
            # 건강한 프로젝트: 최소 메타 Task 추가
            minimum_tasks = create_minimum_meta_tasks(repo_url)
            # 이미 있는 Task ID 제외
            existing_ids = {t.id for t in all_tasks}
            for task in minimum_tasks:
                if task.id not in existing_ids and len(all_tasks) < min_tasks:
                    all_tasks.append(task)
                    logger.info("Added minimum task: %s", task.id)
        else:
            # 비건강/비활성 프로젝트: 학습용 메타 Task 추가
            study_tasks = create_study_meta_tasks(repo_url)
            existing_ids = {t.id for t in all_tasks}
            for task in study_tasks:
                if task.id not in existing_ids and len(all_tasks) < min_tasks:
                    all_tasks.append(task)
                    logger.info("Added study task: %s", task.id)
    
    # 4. task_score 기준 정렬 후 난이도별 그룹핑
    beginner_tasks = sorted(
        [t for t in all_tasks if t.difficulty == "beginner"],
        key=lambda t: (-t.task_score, t.level),  # 점수 높은 순, 그 다음 레벨 낮은 순
    )
    intermediate_tasks = sorted(
        [t for t in all_tasks if t.difficulty == "intermediate"],
        key=lambda t: (-t.task_score, t.level),
    )
    advanced_tasks = sorted(
        [t for t in all_tasks if t.difficulty == "advanced"],
        key=lambda t: (-t.task_score, t.level),
    )
    
    # 5. 메타 정보 계산
    issue_count = len([t for t in all_tasks if t.kind != "meta"])
    meta_count = len([t for t in all_tasks if t.kind == "meta"])
    
    # 6. 결과 생성
    result = OnboardingTasks(
        beginner=beginner_tasks[:10],  # 각 난이도별 최대 10개
        intermediate=intermediate_tasks[:10],
        advanced=advanced_tasks[:5],  # advanced는 5개로 제한
        total_count=len(all_tasks),
        issue_count=issue_count,
        meta_count=meta_count,
    )
    
    return result


# ============================================================
# 사용자 컨텍스트 기반 필터링/개인화
# ============================================================

@dataclass
class UserTaskContext:
    """사용자 Task 필터링 컨텍스트."""
    
    experience_level: str = "beginner"  # beginner/intermediate/advanced
    preferred_kinds: List[str] = field(default_factory=list)  # ["doc", "test", "issue"]
    time_budget_hours: Optional[float] = None  # 예: 2.0 (2시간)
    preferred_intent: Optional[str] = None  # "contribute", "study", "evaluate"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


def filter_tasks_for_user(
    tasks: OnboardingTasks,
    user_level: str = "beginner",
    preferred_kinds: Optional[List[str]] = None,
    time_budget_hours: Optional[float] = None,
    intent_filter: Optional[str] = None,
) -> List[TaskSuggestion]:
    """
    사용자 컨텍스트에 맞는 Task 필터링 및 우선순위 정렬.
    
    filter_tasks_by_context의 간단한 래퍼로, UserTaskContext 없이 사용 가능.
    
    Args:
        tasks: OnboardingTasks
        user_level: 사용자 경험 수준 (beginner/intermediate/advanced)
        preferred_kinds: 선호하는 Task 종류 ["docs", "test", "issue", ...]
        time_budget_hours: 가용 시간 (시간 단위)
        intent_filter: 특정 intent만 필터링 (contribute/study/evaluate)
    
    Returns:
        task_score 순으로 정렬된 TaskSuggestion 리스트
    """
    # 1. 레벨 기반 필터링
    filtered = filter_tasks_by_user_level(tasks, user_level)
    
    # 2. intent 필터링
    if intent_filter:
        filtered = [t for t in filtered if t.intent == intent_filter]
    
    # 3. preferred_kinds 필터 (선호 kind만 남기거나 우선정렬)
    if preferred_kinds:
        # 선호 kind가 있는 Task를 앞으로
        preferred = [t for t in filtered if t.kind in preferred_kinds]
        others = [t for t in filtered if t.kind not in preferred_kinds]
        filtered = preferred + others
    
    # 4. time_budget_hours 기반 제한
    if time_budget_hours is not None:
        limited: List[TaskSuggestion] = []
        total_hours = 0.0
        for task in filtered:
            estimated = _estimate_hours_from_level(task.level)
            if total_hours + estimated <= time_budget_hours:
                limited.append(task)
                total_hours += estimated
            elif not limited:
                # 최소 1개는 포함
                limited.append(task)
                break
        filtered = limited
    
    # 5. task_score 순 정렬 (높은 점수 우선)
    filtered.sort(key=lambda t: t.task_score, reverse=True)
    
    return filtered


def filter_tasks_by_context(
    tasks: OnboardingTasks,
    context: UserTaskContext,
) -> List[TaskSuggestion]:
    """
    사용자 컨텍스트 기반 개인화 필터링.
    
    1. 레벨 기반 필터링
    2. 선호 kind 우선 정렬
    3. time_budget 기반 제한
    4. intent 필터링
    """
    # 1. 레벨 기반 기본 필터링
    filtered = filter_tasks_by_user_level(tasks, context.experience_level)
    
    # 2. intent 필터링 (선호 intent가 있으면)
    if context.preferred_intent:
        # 선호 intent 우선, 그 외는 뒤로
        preferred = [t for t in filtered if t.intent == context.preferred_intent]
        others = [t for t in filtered if t.intent != context.preferred_intent]
        filtered = preferred + others
    
    # 3. 선호 kind 우선 정렬
    if context.preferred_kinds:
        def kind_priority(task: TaskSuggestion) -> int:
            try:
                return context.preferred_kinds.index(task.kind)
            except ValueError:
                return len(context.preferred_kinds)
        
        # 선호 kind 태스크 + 나머지
        preferred_kind_tasks = sorted(
            [t for t in filtered if t.kind in context.preferred_kinds],
            key=kind_priority,
        )
        other_tasks = [t for t in filtered if t.kind not in context.preferred_kinds]
        
        # 다양성 확보: 선호 2개 + 다른 1개 패턴
        result: List[TaskSuggestion] = []
        pref_idx, other_idx = 0, 0
        while len(result) < len(filtered):
            # 선호 2개
            for _ in range(2):
                if pref_idx < len(preferred_kind_tasks):
                    result.append(preferred_kind_tasks[pref_idx])
                    pref_idx += 1
            # 다른 1개
            if other_idx < len(other_tasks):
                result.append(other_tasks[other_idx])
                other_idx += 1
            # 남은 선호 태스크
            if pref_idx >= len(preferred_kind_tasks) and other_idx >= len(other_tasks):
                break
        
        filtered = result
    
    # 4. time_budget 기반 제한 (추정 시간 누적)
    if context.time_budget_hours is not None:
        time_limited: List[TaskSuggestion] = []
        total_hours = 0.0
        
        for task in filtered:
            # 레벨 기반 추정 시간 (시간 단위)
            estimated = _estimate_hours_from_level(task.level)
            if total_hours + estimated <= context.time_budget_hours:
                time_limited.append(task)
                total_hours += estimated
            elif not time_limited:
                # 최소 1개는 포함
                time_limited.append(task)
                break
        
        filtered = time_limited
    
    return filtered


def _estimate_hours_from_level(level: int) -> float:
    """레벨에서 예상 소요 시간 추정 (시간 단위)."""
    hour_map = {
        1: 0.5,   # 30분
        2: 1.5,   # 1-2시간
        3: 2.5,   # 2-3시간
        4: 4.0,   # 반나절
        5: 8.0,   # 1일
        6: 20.0,  # 2-3일
    }
    return hour_map.get(level, 2.0)


def create_personalized_task_set(
    tasks: OnboardingTasks,
    context: UserTaskContext,
) -> Dict[str, Any]:
    """
    개인화된 Task 세트 생성.
    
    Returns:
        {
            "today_tasks": [...],      # 오늘 할 수 있는 Task
            "week_tasks": [...],       # 1주일 플랜
            "challenge_tasks": [...],  # 도전 과제
            "meta": {...}
        }
    """
    filtered = filter_tasks_by_context(tasks, context)
    
    # time_budget 기준으로 분류
    today_tasks: List[TaskSuggestion] = []
    week_tasks: List[TaskSuggestion] = []
    challenge_tasks: List[TaskSuggestion] = []
    
    budget = context.time_budget_hours or 2.0
    
    for task in filtered:
        hours = _estimate_hours_from_level(task.level)
        
        if hours <= budget:
            today_tasks.append(task)
        elif hours <= budget * 5:  # 주간 예산
            week_tasks.append(task)
        else:
            challenge_tasks.append(task)
    
    # 레벨 범위 밖의 Task는 challenge로
    level_threshold = {"beginner": 3, "intermediate": 5, "advanced": 6}
    max_level = level_threshold.get(context.experience_level, 6)
    
    for task in list(today_tasks + week_tasks):
        if task.level > max_level:
            if task in today_tasks:
                today_tasks.remove(task)
            if task in week_tasks:
                week_tasks.remove(task)
            if task not in challenge_tasks:
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
