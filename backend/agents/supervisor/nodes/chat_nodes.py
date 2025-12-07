"""채팅 응답 노드."""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)

ODOC_SYSTEM_CONTEXT = """
당신은 ODOC(Open-source Doctor) AI 어시스턴트입니다.
ODOC은 오픈소스 프로젝트의 건강 상태를 분석하는 시스템입니다.

[ODOC 평가 기준]

1. 문서 품질 (0-100점)
   - README 존재 및 내용 (40점): 설명, 설치 방법, 사용법, 기여 가이드 포함 여부
   - CONTRIBUTING.md 존재 (20점): 기여 가이드라인 문서
   - LICENSE 존재 (15점): 라이선스 파일
   - docs 폴더 존재 (15점): 별도 문서화 폴더
   - 코드 주석 비율 (10점): 코드 내 주석 비율

2. 활동성/유지보수성 (0-100점)
   - 커밋 활동 (40점): 최근 90일간 커밋 빈도, 마지막 커밋 일자
   - 이슈 관리 (30점): 이슈 종료율, 평균 이슈 처리 시간
   - PR 관리 (30점): PR 병합률, 평균 PR 처리 시간

3. 구조 점수 (0-100점)
   - 테스트 파일 존재: tests/, test_, _test.py 등
   - CI/CD 설정: .github/workflows/, .gitlab-ci.yml 등
   - 문서 폴더: docs/, documentation/ 등
   - 빌드 설정: setup.py, pyproject.toml, package.json 등

[점수 계산 방식]

- 건강 점수 = 문서 25% + 활동성 65% + 구조 10%
- 온보딩 점수 = 문서 55% + 활동성 35% + 구조 10%

[건강 등급]
- 80점 이상: Excellent (우수)
- 60-79점: Good (양호)
- 40-59점: Fair (보통)
- 40점 미만: Poor (미흡)

사용자 질문에 위 기준을 바탕으로 정확하게 답변하세요.
"""


def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
    """채팅 응답 생성."""
    from backend.llm.factory import fetch_llm_client
    from backend.llm.base import ChatRequest, ChatMessage
    from backend.common.config import LLM_MODEL_NAME

    intent = state.detected_intent
    message = state.chat_message or ""
    context = state.chat_context or {}
    diagnosis = state.diagnosis_result or {}

    logger.info(f"Chat response: intent={intent}, message={message[:50]}...")

    try:
        client = fetch_llm_client()

        if intent == "explain" and (context or diagnosis):
            system_prompt = _build_explain_prompt(context, diagnosis)
        elif intent == "onboard" and (context or diagnosis):
            system_prompt = _build_onboard_prompt(context, diagnosis, state.candidate_issues)
        else:
            system_prompt = _build_chat_prompt(context, diagnosis)

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=message),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.7,
        )

        response = client.chat(request, timeout=60)
        chat_response = response.content

    except Exception as e:
        logger.warning(f"LLM chat failed: {e}")
        chat_response = _generate_fallback(intent, message, context, diagnosis, state.candidate_issues)

    return {
        "chat_response": chat_response,
        "step": state.step + 1,
    }


def _build_explain_prompt(context: Dict, diagnosis: Dict) -> str:
    """분석 결과 기반 설명 프롬프트."""
    health = diagnosis.get("health_score", context.get("health_score", "N/A"))
    docs = diagnosis.get("documentation_quality", context.get("documentation_quality", "N/A"))
    activity = diagnosis.get("activity_maintainability", context.get("activity_maintainability", "N/A"))
    onboard = diagnosis.get("onboarding_score", context.get("onboarding_score", "N/A"))
    structure = diagnosis.get("structure_score", context.get("structure_score", 0))

    return f"""{ODOC_SYSTEM_CONTEXT}

[현재 분석 결과]
- 건강 점수: {health}점
- 문서 품질: {docs}점
- 활동성: {activity}점
- 온보딩 점수: {onboard}점
- 구조 점수: {structure}점

위 분석 결과와 ODOC 평가 기준을 바탕으로 사용자 질문에 답변하세요."""


def _build_chat_prompt(context: Dict, diagnosis: Dict) -> str:
    """일반 채팅 프롬프트."""
    if context or diagnosis:
        health = diagnosis.get("health_score", context.get("health_score", ""))
        docs = diagnosis.get("documentation_quality", context.get("documentation_quality", ""))
        activity = diagnosis.get("activity_maintainability", context.get("activity_maintainability", ""))
        onboard = diagnosis.get("onboarding_score", context.get("onboarding_score", ""))
        repo = diagnosis.get("repo_id", context.get("repo_id", ""))
        
        if repo:
            result_info = f"\n[현재 분석 중인 저장소: {repo}]"
            if health:
                result_info += f"\n- 건강 점수: {health}점"
            if docs:
                result_info += f"\n- 문서 품질: {docs}점"
            if activity:
                result_info += f"\n- 활동성: {activity}점"
            if onboard:
                result_info += f"\n- 온보딩 점수: {onboard}점"
            return f"{ODOC_SYSTEM_CONTEXT}{result_info}\n\n사용자 질문에 답변하세요."

    return f"{ODOC_SYSTEM_CONTEXT}\n사용자 질문에 답변하세요."


def _build_onboard_prompt(context: Dict, diagnosis: Dict, candidate_issues: list = None) -> str:
    """온보딩/기여 관련 프롬프트."""
    repo = diagnosis.get("repo_id", context.get("repo_id", "알 수 없는 저장소"))
    onboard_score = diagnosis.get("onboarding_score", context.get("onboarding_score", "N/A"))
    docs = diagnosis.get("documentation_quality", context.get("documentation_quality", "N/A"))
    
    issues_info = ""
    if candidate_issues and len(candidate_issues) > 0:
        issues_info = "\n\n[추천 이슈 목록]\n"
        for i, issue in enumerate(candidate_issues[:5], 1):
            title = issue.get("title", "제목 없음")
            url = issue.get("html_url", issue.get("url", ""))
            labels = ", ".join(issue.get("labels", []))
            issues_info += f"{i}. {title}"
            if labels:
                issues_info += f" (라벨: {labels})"
            if url:
                issues_info += f"\n   링크: {url}"
            issues_info += "\n"
    
    return f"""{ODOC_SYSTEM_CONTEXT}

[현재 저장소: {repo}]
- 온보딩 점수: {onboard_score}점
- 문서 품질: {docs}점
{issues_info}
오픈소스 기여를 처음 시작하는 초보자에게 도움이 되는 정보를 제공하세요.
추천 이슈가 있으면 해당 이슈를 소개하고, 기여 시작 방법을 안내하세요.
CONTRIBUTING.md 파일이나 프로젝트 문서를 먼저 읽도록 권장하세요."""


def _generate_fallback(
    intent: str, 
    message: str, 
    context: Dict, 
    diagnosis: Dict,
    candidate_issues: list = None
) -> str:
    """LLM 실패 시 폴백 응답."""
    msg_lower = message.lower()
    
    if intent == "explain":
        health = diagnosis.get("health_score", context.get("health_score"))
        if health:
            return f"현재 프로젝트의 건강 점수는 {health}점입니다. 구체적인 분석 결과는 리포트를 참고해주세요."
        return "분석 결과가 없습니다. 먼저 저장소를 분석해주세요."
    
    if any(kw in msg_lower for kw in ["기여", "초보자", "시작", "어떻게"]):
        repo = diagnosis.get("repo_id", context.get("repo_id", ""))
        onboard_score = diagnosis.get("onboarding_score", context.get("onboarding_score", 0))
        
        issues_info = ""
        if candidate_issues and len(candidate_issues) > 0:
            issues_info = f"\n\n추천 이슈가 {len(candidate_issues)}개 있습니다. 리포트의 '추천 이슈' 섹션을 확인해주세요."
        
        if repo:
            tips = []
            if onboard_score >= 70:
                tips.append("이 프로젝트는 초보자 친화적입니다.")
            elif onboard_score >= 50:
                tips.append("이 프로젝트는 중간 수준의 진입 장벽이 있습니다.")
            else:
                tips.append("이 프로젝트는 초보자에게 다소 어려울 수 있습니다.")
            
            tips.append("CONTRIBUTING.md 파일을 먼저 읽어보세요.")
            tips.append("'good first issue' 라벨이 붙은 이슈를 찾아보세요.")
            
            return f"{repo}에 기여하고 싶으시군요!\n\n" + "\n".join(f"- {t}" for t in tips) + issues_info
        
        return "오픈소스 기여를 시작하려면 먼저 저장소를 분석해주세요. 분석 결과에서 추천 이슈와 온보딩 점수를 확인할 수 있습니다."
    
    return "요청을 처리하는 중 문제가 발생했습니다. 다시 시도해주세요."


def route_after_chat(state: SupervisorState) -> str:
    """채팅 노드 후 라우팅."""
    return "__end__"

