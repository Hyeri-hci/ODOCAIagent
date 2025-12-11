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

[중요 지침]
- 사용자 질문에 위 기준을 바탕으로 정확하게 답변하세요.
- 반드시 현재 분석 중인 저장소에 대해서만 답변하세요.
- 다른 저장소(예: Flask, React, Django 등)를 예시로 사용하지 마세요.
- 현재 저장소의 실제 분석 결과를 기반으로 답변하세요.
"""


def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
    """채팅 응답 생성."""
    from backend.llm.factory import fetch_llm_client
    from backend.llm.base import ChatRequest, ChatMessage
    from backend.common.config import LLM_MODEL_NAME
    from backend.common.cache_manager import analysis_cache
    import re

    intent = state.detected_intent
    message = state.chat_message or ""
    context = state.chat_context or {}
    
    # diagnosis 우선순위: 1) state.diagnosis_result → 2) chat_context.analysisResult
    diagnosis = state.diagnosis_result or {}
    if not diagnosis and context.get("analysisResult"):
        # 프론트엔드에서 전달한 analysisResult 사용 (캐시 미스 시 폴백)
        diagnosis = context.get("analysisResult")
        logger.info("Using analysisResult from chat_context as diagnosis fallback")
    
    candidate_issues = list(state.candidate_issues)

    # repo_url에서 owner/repo 파싱 (chat_context에서 우선 사용)
    def parse_github_url(url: str):
        """GitHub URL에서 owner, repo 추출."""
        if not url:
            return None, None
        match = re.match(r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    # chat_context의 repo_url을 우선 사용
    context_repo_url = context.get("repo_url") or context.get("repoUrl")
    logger.info(f"Chat context repo_url={context_repo_url}, state.owner={state.owner}, state.repo={state.repo}")
    
    # 메시지에서 다른 저장소 이름 언급 감지
    def extract_repo_from_message(msg: str):
        """메시지에서 저장소 이름 추출 (e.g., 'OSSDoctor에서 기여하는 법')"""
        import re as re_module
        patterns = [
            r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:에서|에|의|을|를)",  # owner/repo 형식
            r"([A-Za-z][A-Za-z0-9_.-]{2,})(?:에서|에|의|을|를|는|로)",  # repo 이름만 (최소 3글자, 알파벳으로 시작)
        ]
        for pattern in patterns:
            match = re_module.search(pattern, msg)
            if match:
                repo_name = match.group(1)
                logger.info(f"Extracted repo name from message: {repo_name}")
                return repo_name
        return None
    
    mentioned_repo = extract_repo_from_message(message) if message else None
    
    if context_repo_url:
        chat_owner, chat_repo = parse_github_url(context_repo_url)
        logger.info(f"Parsed from context: {chat_owner}/{chat_repo}")
    else:
        chat_owner, chat_repo = state.owner, state.repo
        logger.info(f"Using state fallback: {chat_owner}/{chat_repo}")

    # 메시지에서 언급된 저장소와 현재 컨텍스트 저장소가 다른 경우, 캐시에서 해당 저장소 찾기
    if mentioned_repo and chat_repo and mentioned_repo.lower() != chat_repo.lower():
        # mentioned_repo가 owner/repo 형식인지 확인
        if "/" in mentioned_repo:
            m_owner, m_repo = mentioned_repo.split("/", 1)
        else:
            m_owner, m_repo = None, mentioned_repo
        
        # 캐시에서 해당 저장소 찾기 (전체 캐시 검색)
        cached_for_mentioned = None
        if m_owner:
            cached_for_mentioned = analysis_cache.get_analysis(m_owner, m_repo, "main")
        else:
            # owner가 없으면 repo 이름으로 검색 (간단한 휴리스틱: 전체 캐시에서 repo 이름 매칭)
            all_cached = analysis_cache._analyses if hasattr(analysis_cache, '_analyses') else {}
            for key, cached_data in all_cached.items():
                if m_repo.lower() in key.lower():
                    cached_for_mentioned = cached_data.get('data')
                    parts = key.split('/')
                    if len(parts) >= 2:
                        m_owner = parts[0]
                        m_repo = parts[1].split('@')[0]  # Remove @branch
                    break
        
        if cached_for_mentioned:
            logger.info(f"Found mentioned repo in cache: {m_owner}/{m_repo}, switching context")
            chat_owner, chat_repo = m_owner, m_repo
            diagnosis = cached_for_mentioned
            candidate_issues = cached_for_mentioned.get("recommended_issues", []) or []

    # 캐시에서 진단 결과 로드 (chat_context 기반 owner/repo 사용)
    if not diagnosis and chat_owner and chat_owner != "unknown":
        cached = analysis_cache.get_analysis(chat_owner, chat_repo, "main")
        if cached:
            diagnosis = cached
            logger.info(f"Chat loaded cached diagnosis for {chat_owner}/{chat_repo}")
            candidate_issues = cached.get("recommended_issues", []) or []

    logger.info(f"Chat response: intent={intent}, message={message[:50] if message else ''}, has_diagnosis={bool(diagnosis)}, repo={chat_owner}/{chat_repo}")

    try:
        client = fetch_llm_client()

        if intent == "explain" and (context or diagnosis):
            system_prompt = _build_explain_prompt(context, diagnosis)
        elif intent == "onboard" and (context or diagnosis):
            system_prompt = _build_onboard_prompt(context, diagnosis, candidate_issues)
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
        chat_response = _generate_fallback(intent, message, context, diagnosis, candidate_issues)

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

