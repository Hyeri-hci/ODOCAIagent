"""
Onboarding Plan Generator v1.0

초보자를 위한 온보딩 계획을 생성하는 모듈.
- v0: 규칙 기반 생성
- v1: LLM 기반 풍부한 생성

Related: docs/DIAGNOSIS_SCHEMA_v1.md
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class OnboardingPlan:
    """초보자 온보딩 계획"""
    
    recommended_for_beginner: bool
    difficulty: str  # "easy" | "normal" | "hard"
    first_steps: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    estimated_setup_time: Optional[str] = None  # e.g., "30분", "1시간"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# v0: 규칙 기반 생성
# ============================================================

def _compute_difficulty(onboarding_score: int) -> str:
    """onboarding_score 기반 난이도 판정."""
    if onboarding_score >= 75:
        return "easy"
    elif onboarding_score >= 55:
        return "normal"
    else:
        return "hard"


def _compute_recommended(onboarding_score: int, is_healthy: bool) -> bool:
    """초보자 추천 여부 판정."""
    # onboarding_score >= 70 AND is_healthy
    return onboarding_score >= 70 and is_healthy


def _generate_first_steps_rule_based(
    difficulty: str,
    docs_issues: List[str],
    readme_categories: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """규칙 기반 first_steps 생성."""
    steps: List[str] = []
    
    # 1. README 읽기 (항상)
    if "missing_what" not in docs_issues:
        steps.append("README의 프로젝트 소개를 읽고 어떤 프로젝트인지 파악한다.")
    else:
        steps.append("프로젝트 GitHub 페이지에서 Description과 Topics를 확인한다.")
    
    # 2. 설치/실행 (HOW 존재 여부에 따라)
    if "missing_how" not in docs_issues:
        steps.append("README의 Quick Start 또는 Installation 섹션을 따라 개발 환경을 세팅한다.")
    else:
        steps.append("package.json 또는 requirements.txt를 확인해 의존성을 설치한다.")
    
    # 3. 기여 가이드 (CONTRIBUTING 존재 여부에 따라)
    if "missing_contributing" not in docs_issues:
        steps.append("CONTRIBUTING.md를 읽고 코딩 규칙과 PR 절차를 숙지한다.")
    else:
        steps.append("기존 PR들을 살펴보고 프로젝트의 코딩 스타일을 파악한다.")
    
    # 4. 이슈 찾기 (난이도에 따라)
    if difficulty == "easy":
        steps.append("'good-first-issue' 또는 'beginner-friendly' 라벨이 붙은 이슈를 선택한다.")
    elif difficulty == "normal":
        steps.append("최근 이슈 목록에서 본인이 해결할 수 있을 것 같은 이슈를 찾는다.")
    else:
        steps.append("이슈를 직접 해결하기보다 먼저 코드베이스를 충분히 탐색한다.")
    
    # 5. 커뮤니케이션
    steps.append("이슈에 댓글을 달아 작업 의사를 밝히고 메인테이너의 피드백을 기다린다.")
    
    return steps


def _generate_risks_rule_based(
    is_healthy: bool,
    docs_issues: List[str],
    activity_issues: List[str],
) -> List[str]:
    """규칙 기반 risks 생성."""
    risks: List[str] = []
    
    # is_healthy=False 경고
    if not is_healthy:
        risks.append("이 프로젝트는 현재 활발하게 유지보수되지 않습니다. 기여가 반영되지 않을 수 있습니다.")
    
    # 활동성 문제
    if "inactive_project" in activity_issues:
        risks.append("프로젝트가 비활성 상태입니다. 응답을 받지 못할 가능성이 높습니다.")
    elif "no_recent_commits" in activity_issues:
        risks.append("최근 커밋이 없어 메인테이너의 응답이 느릴 수 있습니다.")
    
    if "low_issue_closure" in activity_issues:
        risks.append("이슈 해결 속도가 느려 답변을 오래 기다려야 할 수 있습니다.")
    
    if "slow_pr_merge" in activity_issues:
        risks.append("PR 머지가 느린 편이므로 리뷰에 시간이 걸릴 수 있습니다.")
    
    # 문서 문제
    if "weak_documentation" in docs_issues:
        risks.append("문서가 부족해 코드를 직접 읽으며 파악해야 할 수 있습니다.")
    
    if "missing_contributing" in docs_issues and "missing_how" in docs_issues:
        risks.append("기여 가이드와 설치 방법이 없어 시작하기 어려울 수 있습니다.")
    
    return risks


def _estimate_setup_time(difficulty: str, docs_issues: List[str]) -> str:
    """예상 세팅 시간 추정."""
    if difficulty == "easy" and len(docs_issues) == 0:
        return "30분 이내"
    elif difficulty == "easy":
        return "30분 ~ 1시간"
    elif difficulty == "normal":
        return "1 ~ 2시간"
    else:
        return "2시간 이상"


def create_onboarding_plan_v0(
    onboarding_score: int,
    is_healthy: bool,
    docs_issues: List[str],
    activity_issues: List[str],
    readme_categories: Optional[Dict[str, Any]] = None,
) -> OnboardingPlan:
    """
    v0: 규칙 기반 온보딩 계획 생성.
    
    Args:
        onboarding_score: HealthScore.onboarding_score (0-100)
        is_healthy: HealthScore.is_healthy
        docs_issues: labels.docs_issues
        activity_issues: labels.activity_issues
        readme_categories: details.docs.readme_categories (optional)
    
    Returns:
        OnboardingPlan with rule-based content
    """
    difficulty = _compute_difficulty(onboarding_score)
    recommended = _compute_recommended(onboarding_score, is_healthy)
    
    first_steps = _generate_first_steps_rule_based(
        difficulty=difficulty,
        docs_issues=docs_issues,
        readme_categories=readme_categories,
    )
    
    risks = _generate_risks_rule_based(
        is_healthy=is_healthy,
        docs_issues=docs_issues,
        activity_issues=activity_issues,
    )
    
    setup_time = _estimate_setup_time(difficulty, docs_issues)
    
    return OnboardingPlan(
        recommended_for_beginner=recommended,
        difficulty=difficulty,
        first_steps=first_steps,
        risks=risks,
        estimated_setup_time=setup_time,
    )


# ============================================================
# v1: LLM 기반 생성
# ============================================================

def create_onboarding_plan_v1(
    scores: Dict[str, Any],
    labels: Dict[str, Any],
    docs_summary: str,
    repo_info: Dict[str, Any],
) -> OnboardingPlan:
    """
    v1: LLM 기반 온보딩 계획 생성.
    
    규칙 기반 뼈대 + LLM으로 first_steps/risks를 풍부하게 생성.
    """
    from backend.llm.base import ChatMessage, ChatRequest
    from backend.llm.factory import fetch_llm_client
    
    # 규칙 기반 기본값 먼저 계산
    onboarding_score = scores.get("onboarding_score", 50)
    is_healthy = scores.get("is_healthy", True)
    docs_issues = labels.get("docs_issues", [])
    activity_issues = labels.get("activity_issues", [])
    
    difficulty = _compute_difficulty(onboarding_score)
    recommended = _compute_recommended(onboarding_score, is_healthy)
    setup_time = _estimate_setup_time(difficulty, docs_issues)
    
    # LLM 프롬프트
    system_prompt = """너는 오픈소스 프로젝트 온보딩 전문가이다.
주어진 프로젝트 정보를 바탕으로 초보 기여자를 위한 온보딩 계획을 JSON으로 생성해라.

반드시 아래 JSON 형식으로만 응답해라 (다른 텍스트 없이):
{
  "first_steps": ["단계1", "단계2", "단계3", "단계4", "단계5"],
  "risks": ["위험요소1", "위험요소2"]
}

first_steps:
- 5개 이내의 구체적인 단계
- 초보자가 바로 따라할 수 있는 명확한 액션
- 프로젝트 특성에 맞게 커스터마이즈

risks:
- 0~3개의 주의사항
- 초보자가 알아야 할 잠재적 어려움
- 위험이 없으면 빈 배열 []"""

    context = {
        "repo_name": repo_info.get("full_name", "unknown"),
        "description": repo_info.get("description", ""),
        "language": repo_info.get("language", ""),
        "stars": repo_info.get("stars", 0),
        "scores": {
            "health_score": scores.get("health_score"),
            "onboarding_score": onboarding_score,
            "is_healthy": is_healthy,
        },
        "labels": labels,
        "docs_summary": docs_summary[:500] if docs_summary else "",
    }
    
    user_prompt = f"""프로젝트 정보:
{json.dumps(context, ensure_ascii=False, indent=2)}

이 프로젝트에 처음 기여하려는 초보 개발자를 위한 온보딩 계획을 생성해라."""

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]
    
    try:
        client = fetch_llm_client()
        request = ChatRequest(messages=messages, max_tokens=800, temperature=0.3)
        response = client.chat(request)
        
        raw = response.content.strip()
        
        # JSON 파싱
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        data = json.loads(raw)
        first_steps = data.get("first_steps", [])
        risks = data.get("risks", [])
        
        # 유효성 검사
        if not isinstance(first_steps, list):
            first_steps = []
        if not isinstance(risks, list):
            risks = []
        
        return OnboardingPlan(
            recommended_for_beginner=recommended,
            difficulty=difficulty,
            first_steps=first_steps[:5],  # 최대 5개
            risks=risks[:3],  # 최대 3개
            estimated_setup_time=setup_time,
        )
        
    except Exception as exc:
        logger.warning("LLM onboarding plan generation failed: %s", exc)
        # Fallback to v0
        return create_onboarding_plan_v0(
            onboarding_score=onboarding_score,
            is_healthy=is_healthy,
            docs_issues=docs_issues,
            activity_issues=activity_issues,
        )


def create_onboarding_plan(
    scores: Dict[str, Any],
    labels: Dict[str, Any],
    docs_summary: str = "",
    repo_info: Optional[Dict[str, Any]] = None,
    use_llm: bool = False,
) -> OnboardingPlan:
    """
    온보딩 계획 생성 (통합 인터페이스).
    
    Args:
        scores: HealthScore dict (scores block)
        labels: DiagnosisLabels dict (labels block)
        docs_summary: README 요약 텍스트
        repo_info: 레포지토리 정보 dict
        use_llm: True면 v1(LLM), False면 v0(규칙 기반)
    
    Returns:
        OnboardingPlan
    """
    if use_llm and repo_info:
        return create_onboarding_plan_v1(
            scores=scores,
            labels=labels,
            docs_summary=docs_summary,
            repo_info=repo_info,
        )
    else:
        return create_onboarding_plan_v0(
            onboarding_score=scores.get("onboarding_score", 50),
            is_healthy=scores.get("is_healthy", True),
            docs_issues=labels.get("docs_issues", []),
            activity_issues=labels.get("activity_issues", []),
        )
