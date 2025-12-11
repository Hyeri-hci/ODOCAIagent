"""Onboarding Agent - 추천 결과 LLM 요약 생성."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.agents.onboarding.models import UserContext, OnboardingAgentResult, RepoRecommendation

logger = logging.getLogger(__name__)


# 프롬프트 템플릿

RECOMMENDATION_SUMMARY_PROMPT = """당신은 오픈소스 기여 멘토입니다.
사용자의 정보와 추천된 저장소 목록을 바탕으로, 친근하고 실용적인 조언을 제공해주세요.

## 사용자 정보
{user_context_section}

## 추천 저장소 (우선순위 순)
{recommendations_section}

## 작성 지침

1. **추천 요약** (2-3문장)
   - 사용자의 목표와 수준에 맞춰 왜 이 저장소들을 추천하는지 설명

2. **TOP 추천 저장소 상세 설명**
   - 각 추천 저장소에 대해:
     - 왜 이 프로젝트가 사용자에게 적합한지
     - 주의해야 할 점이 있다면 언급

3. **첫 1주일 실행 계획**
   - 가장 추천하는 저장소를 기준으로
   - 구체적이고 실행 가능한 단계별 계획
   - 각 단계에 예상 소요 시간 포함

4. **격려 메시지** (1-2문장)
   - 사용자를 격려하는 마무리

## 작성 규칙
- 한국어로 작성
- 친근하지만 전문적인 톤
- 구체적이고 실행 가능한 조언
- 이모지는 사용하지 않음
- 마크다운 형식으로 작성
"""

USER_CONTEXT_TEMPLATE = """- 경험 수준: {experience_level}
- 선호 기술 스택: {preferred_stack}
- 주당 가용 시간: {available_hours_per_week}시간
- 목표: {goal}"""

REPO_RECOMMENDATION_TEMPLATE = """### {rank}. {repo}
- 매칭 점수: {match_score}/100
- 추천 이유: {reason}
- 난이도: {onboarding_level}
- 건강 상태: {health_level}
- 첫 단계:
{first_steps}
- 주의할 점:
{risks}"""


def format_user_context(user_context: UserContext) -> str:
    """사용자 컨텍스트를 프롬프트용 문자열로 포맷."""
    exp_level_map = {
        "beginner": "초보자 (오픈소스 기여 경험 없음)",
        "intermediate": "중급자 (몇 번의 기여 경험 있음)",
        "advanced": "고급자 (활발한 기여 경험)",
    }
    
    stack_str = ", ".join(user_context.preferred_stack) if user_context.preferred_stack else "특별히 없음"
    
    return USER_CONTEXT_TEMPLATE.format(
        experience_level=exp_level_map.get(user_context.experience_level, user_context.experience_level),
        preferred_stack=stack_str,
        available_hours_per_week=user_context.available_hours_per_week,
        goal=user_context.goal,
    )


def format_recommendation(rank: int, rec: RepoRecommendation) -> str:
    """단일 추천 결과를 프롬프트용 문자열로 포맷."""
    onboarding_plan = rec.onboarding_plan or {}
    
    # 난이도 한글화
    level_map = {
        "easy": "쉬움 (초보자 추천)",
        "normal": "보통",
        "hard": "어려움 (도전 필요)",
    }
    
    health_map = {
        "good": "건강함",
        "warning": "주의 필요",
        "bad": "문제 있음",
    }
    
    # first_steps 포맷
    first_steps = onboarding_plan.get("first_steps", [])
    if first_steps:
        steps_str = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(first_steps[:3]))
    else:
        steps_str = "  (정보 없음)"
    
    # risks 포맷
    risks = onboarding_plan.get("risks", [])
    if risks:
        risks_str = "\n".join(f"  - {risk}" for risk in risks[:3])
    else:
        risks_str = "  (특별한 주의사항 없음)"
    
    return REPO_RECOMMENDATION_TEMPLATE.format(
        rank=rank,
        repo=rec.repo,
        match_score=rec.match_score,
        reason=rec.reason,
        onboarding_level=level_map.get(rec.onboarding_level, rec.onboarding_level),
        health_level=health_map.get(rec.health_level, rec.health_level),
        first_steps=steps_str,
        risks=risks_str,
    )


def build_recommendation_prompt(
    user_context: UserContext,
    recommendations: List[RepoRecommendation],
) -> str:
    """추천 요약을 위한 전체 프롬프트 생성."""
    user_section = format_user_context(user_context)
    
    rec_sections = []
    for i, rec in enumerate(recommendations, 1):
        rec_sections.append(format_recommendation(i, rec))
    
    recommendations_section = "\n\n".join(rec_sections) if rec_sections else "(추천할 저장소가 없습니다)"
    
    return RECOMMENDATION_SUMMARY_PROMPT.format(
        user_context_section=user_section,
        recommendations_section=recommendations_section,
    )


# LLM 호출

def generate_recommendation_summary_llm(
    user_context: UserContext,
    recommendations: List[RepoRecommendation],
) -> str:
    """LLM을 사용하여 추천 요약 생성."""
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        
        prompt = build_recommendation_prompt(user_context, recommendations)
        
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="system",
                    content="당신은 오픈소스 기여 멘토입니다. 사용자에게 친근하고 실용적인 조언을 제공합니다.",
                ),
                ChatMessage(
                    role="user",
                    content=prompt,
                ),
            ],
            temperature=0.7,
            max_tokens=4000,
        )
        response = client.chat(request)
        
        return response.content.strip()
    
    except Exception as e:
        logger.warning(f"LLM 요약 생성 실패, 규칙 기반 폴백: {e}")
        return generate_recommendation_summary_fallback(user_context, recommendations)


def generate_recommendation_summary_fallback(
    user_context: UserContext,
    recommendations: List[RepoRecommendation],
) -> str:
    """LLM 실패 시 규칙 기반 요약 생성."""
    if not recommendations:
        return "추천할 저장소가 없습니다. 다른 후보 저장소를 시도해보세요."
    
    parts: List[str] = []
    
    # 요약 헤더
    parts.append(f"## 추천 결과 ({len(recommendations)}개 저장소)\n")
    
    # 사용자 목표 반영
    parts.append(f"목표: {user_context.goal}")
    parts.append(f"경험 수준: {user_context.experience_level}\n")
    
    # 추천 저장소 목록
    for i, rec in enumerate(recommendations, 1):
        parts.append(f"### {i}. {rec.repo}")
        parts.append(f"- 매칭 점수: {rec.match_score}/100")
        parts.append(f"- 추천 이유: {rec.reason}")
        parts.append(f"- 난이도: {rec.onboarding_level}")
        
        # 첫 단계
        first_steps = rec.onboarding_plan.get("first_steps", [])
        if first_steps:
            parts.append("- 첫 단계:")
            for step in first_steps[:3]:
                parts.append(f"  - {step}")
        parts.append("")
    
    # 첫 1주일 계획 (가장 높은 추천)
    top_rec = recommendations[0]
    parts.append("## 첫 1주일 계획\n")
    parts.append(f"{top_rec.repo} 저장소를 기준으로:\n")
    
    first_steps = top_rec.onboarding_plan.get("first_steps", [])
    for i, step in enumerate(first_steps, 1):
        parts.append(f"{i}. {step}")
    
    return "\n".join(parts)


def generate_recommendation_summary(
    user_context: UserContext,
    recommendations: List[RepoRecommendation],
    use_llm: bool = True,
) -> str:
    """추천 요약 생성. use_llm=False면 규칙 기반."""
    if not recommendations:
        return "추천할 저장소가 없습니다. 다른 후보 저장소를 시도해보세요."
    
    if use_llm:
        return generate_recommendation_summary_llm(user_context, recommendations)
    else:
        return generate_recommendation_summary_fallback(user_context, recommendations)
