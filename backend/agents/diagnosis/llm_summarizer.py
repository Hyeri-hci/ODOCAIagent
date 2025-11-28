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
    """Diagnosis Agent 전체 결과 요약"""

    try:
        diagnosis_json_str = json.dumps(
            diagnosis_result,
            ensure_ascii=False,
            indent=2,
        )
    except Exception:
        diagnosis_json_str = str(diagnosis_result)

    scores = diagnosis_result.get("scores", {}) or {}
    details = diagnosis_result.get("details", {}) or {}
    docs_block = details.get("docs", {}) or {}
    repo_info = details.get("repo_info", {}) or {}

    overall_score = scores.get("overall_score")
    docs_score = scores.get("documentation_quality")
    activity_score = scores.get("activity_maintainability")
    readme_dsa = docs_block.get("readme_category_score")

    # README 원문 일부를 project_glimpse로 사용
    raw_readme = details.get("readme_raw", "")
    if isinstance(raw_readme, str) and raw_readme.strip():
        readme_lines = raw_readme.splitlines()
        project_glimpse = "\n".join(readme_lines[:80])
    else:
        project_glimpse = ""

    if language == "ko":
        system_prompt = (
            "너는 오픈소스 프로젝트 진단 결과를 바탕으로 "
            "초보 개발자에게 프로젝트 상태를 설명하는 전문가이다. "
            "항상 먼저 '이 프로젝트가 어떤 프로젝트인지'를 설명하고, "
            "그 다음에 문서 품질과 활동성, 개선점, 온보딩 경로를 순서대로 요약해라. "
            "입력 JSON 안의 숫자 점수는 임의로 바꾸거나 새로 만들지 말고 그대로 사용해라."
        )

        user_prompt = textwrap.dedent(
            f"""
            사용자 수준: {user_level}

            아래 정보들을 바탕으로 프로젝트를 설명해라.

            [리포지토리 요약 정보]
            - name: {repo_info.get("full_name")}
            - description: {repo_info.get("description")}

            [주요 점수 요약] (없으면 None)
            - overall_score: {overall_score}
            - documentation_quality: {docs_score}
            - activity_maintainability: {activity_score}
            - readme_category_score(DSA): {readme_dsa}

            [README 원문 일부]
            이 텍스트는 '이 프로젝트가 무엇을 하는지'를 파악하는 데 사용해라.
            구조 자체를 설명하기보다는, 프로젝트의 목적과 주요 기능을 이해하는 데 집중해라.

            {project_glimpse}

            이제 아래 JSON 전체를 참고해서, 다음 순서로 한국어로 답변해라.

            1. 프로젝트 소개
               - 이 프로젝트가 무엇을 하는지, 어떤 문제를 해결하는지, 어떤 주요 기능이 있는지
                 여러 문장으로 자연스럽게 설명해라.

            2. 문서 품질과 온보딩 관점
               - README와 관련 문서 구조, DSA 점수를 기반으로 "
                 "문서 품질과 온보딩 난이도를 설명해라.

            3. 활동성과 유지보수성
               - 커밋, 이슈, PR 관련 지표를 기반으로 프로젝트가 얼마나 활발하게 유지보수되는지 설명해라.

            4. 개선이 필요한 점
               - 가장 중요한 개선 포인트를 여러 개 bullet 형태로 제시하되,
                 각 bullet은 한두 문장으로 이유와 방향을 함께 설명해라.

            5. 초보 기여자를 위한 온보딩 제안
               - 초보 개발자가 이 프로젝트에 기여를 시작할 때 어떤 순서로 문서와 이슈를 보면 좋은지
                 간단한 단계형 가이드로 제안해라.

            진단 결과 JSON:
            {diagnosis_json_str}
            """
        ).strip()
    else:
        system_prompt = (
            "You explain open source diagnosis results to help new contributors. "
            "Start by explaining what the project is about, then discuss documentation, "
            "activity, improvements, and onboarding."
        )
        user_prompt = f"Diagnosis JSON:\n{diagnosis_json_str}"

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(
        messages=messages,
        max_tokens=1200,
        temperature=0.2,
    )
    response = client.chat(request)
    return response.content
