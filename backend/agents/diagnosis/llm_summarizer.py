"""
Diagnosis Result Summarizer

전체 진단 결과를 LLM으로 요약하는 모듈.
README 관련 요약은 tools/readme_summarizer.py 참조.
"""
from __future__ import annotations

from typing import Any, Dict
import json
import textwrap

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client


def summarize_diagnosis_repository(
    diagnosis_result: Dict[str, Any],
    user_level: str = "beginner",
    language: str = "ko",
) -> str:
    """
    Diagnosis Agent 전체 JSON 결과를 LLM으로 요약.
    is_healthy=False인 경우 경고 문구를 앞에 추가.
    """
    try:
        diagnosis_json_str = json.dumps(diagnosis_result, ensure_ascii=False, indent=2)
    except Exception:
        diagnosis_json_str = str(diagnosis_result)

    scores = diagnosis_result.get("scores", {}) or {}
    details = diagnosis_result.get("details", {}) or {}
    docs_block = details.get("docs", {}) or {}
    repo_info = details.get("repo_info", {}) or {}

    # 점수 추출
    health_score = scores.get("health_score")
    onboarding_score = scores.get("onboarding_score")
    docs_score = scores.get("documentation_quality")
    activity_score = scores.get("activity_maintainability")
    is_healthy = scores.get("is_healthy", True)

    # is_healthy=False 경고 문구
    warning_section = ""
    if not is_healthy:
        warning_section = (
            "[주의] 이 프로젝트는 현재 활발하게 유지보수되지 않거나 "
            "더 이상 적극적으로 사용되지 않는 프로젝트입니다. "
            "신규 프로젝트에 도입하기 전에 대안을 검토하는 것을 권장합니다.\n\n"
        )

    # README 미리보기
    raw_readme = details.get("readme_raw", "")
    project_glimpse = ""
    if isinstance(raw_readme, str) and raw_readme.strip():
        project_glimpse = "\n".join(raw_readme.splitlines()[:80])

    if language == "ko":
        system_prompt = (
            "너는 오픈소스 프로젝트 진단 결과를 바탕으로 "
            "초보 개발자에게 프로젝트 상태를 설명하는 전문가이다. "
            "항상 먼저 '이 프로젝트가 어떤 프로젝트인지'를 설명하고, "
            "그 다음에 문서 품질과 활동성, 개선점, 온보딩 경로를 순서대로 요약해라. "
            "입력 JSON 안의 숫자 점수는 임의로 바꾸거나 새로 만들지 말고, 그대로 사용해라."
        )

        user_prompt = textwrap.dedent(f"""
            [사용자 수준] {user_level}

            [리포지토리 기본 정보]
            - name: {repo_info.get("full_name")}
            - description: {repo_info.get("description")}

            [주요 점수]
            - health_score: {health_score}
            - onboarding_score: {onboarding_score}
            - documentation_quality: {docs_score}
            - activity_maintainability: {activity_score}
            - is_healthy: {is_healthy}

            [README 상단 일부]
            {project_glimpse}

            위 정보를 참고해 다음 구조로 한국어 설명을 작성해라:

            1. 프로젝트 소개
            2. 문서 품질과 온보딩 난이도
            3. 활동성 및 유지보수성
            4. 개선이 필요한 부분
            5. 초보 기여자를 위한 온보딩 경로

            [Diagnosis JSON 원본]
            {diagnosis_json_str}
        """).strip()
    else:
        system_prompt = (
            "You explain open source diagnosis results to help new contributors. "
            "Do not change or invent numeric scores; use them as given in the JSON."
        )
        user_prompt = textwrap.dedent(f"""
            User level: {user_level}

            Diagnosis JSON:
            {diagnosis_json_str}

            Write a summary with:
            1. Project overview
            2. Documentation quality & onboarding difficulty
            3. Activity & maintainability
            4. Key issues / risks
            5. Suggested next steps for a new contributor
        """).strip()

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(messages=messages, max_tokens=2000, temperature=0.2)
    response = client.chat(request)

    if not is_healthy:
        return warning_section + response.content.strip()
    return response.content.strip()

