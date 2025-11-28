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
    Diagnosis Agent 전체 JSON 결과를 LLM으로 요약한다.
    - diagnosis_result 전체를 그대로 JSON 문자열로 넘겨 숫자 값은
      LLM이 임의로 수정하지 않도록 한다.
    - language == "ko" 인 경우 한국어 설명, 그 외에는 영어 설명을 생성한다.
    """
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
    readme_dsa = docs_block.get("readme_dsa", {})

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
            "입력 JSON 안의 숫자 점수(overall_score 등)는 임의로 바꾸거나 새로 만들지 말고, "
            "설명할 때 그대로 사용해라."
        )

        user_prompt = textwrap.dedent(
            f"""
            [사용자 수준]
            - {user_level}

            [리포지토리 기본 정보]
            - name: {repo_info.get("full_name")}
            - description: {repo_info.get("description")}

            [주요 점수 요약]
            - overall_score: {overall_score}
            - documentation_quality: {docs_score}
            - activity_maintainability: {activity_score}

            [README DSA 요약 정보]
            - keys: {list(readme_dsa.keys()) if isinstance(readme_dsa, dict) else readme_dsa}

            [README 상단 일부]
            {project_glimpse}

            위 정보를 참고하되, 최종적으로는 아래 Diagnosis JSON 전체를 기반으로
            다음 구조로 한국어 설명을 작성해라.

            1. 프로젝트 소개
               - 무엇을 하는 프로젝트인지, 어떤 문제를 해결하는지, 주요 기능은 무엇인지

            2. 문서 품질과 온보딩 난이도
               - README/문서 구조와 점수를 기반으로 초보 기여자가 이해하기 쉬운지 설명

            3. 활동성 및 유지보수성
               - 최근 커밋, 이슈, PR 흐름을 점수와 함께 요약

            4. 개선이 필요한 부분
               - 문서, 활동성, 보안 등에서 보완하면 좋을 점을 제안

            5. 초보 기여자를 위한 온보딩 경로
               - 어떤 파일/문서를 먼저 보면 좋을지,
                 어떤 종류의 이슈나 작업부터 시작하면 좋을지 제안

            [Diagnosis JSON 원본]
            {diagnosis_json_str}
            """
        ).strip()
    else:
        system_prompt = (
            "You explain open source diagnosis results to help new contributors. "
            "Start by explaining what the project is about, then discuss documentation, "
            "activity, suggested improvements, and recommended onboarding paths. "
            "Do not change or invent numeric scores; use them as given in the JSON."
        )
        user_prompt = textwrap.dedent(
            f"""
            User level: {user_level}

            Below is the full diagnosis JSON. Write a concise but detailed English summary
            following this structure:

            1. Project overview
            2. Documentation quality & onboarding difficulty
            3. Activity & maintainability
            4. Key issues / risks
            5. Suggested next steps for a new contributor

            Diagnosis JSON:
            {diagnosis_json_str}
            """
        ).strip()

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
    return response.content.strip()


def summarize_readme_category_for_embedding(
    category: str,
    text: str,
) -> str:
    """LLM을 사용해 README 카테고리별 요약문 생성 (임베딩 용도)"""
    text = text or ""
    if not text.strip():
        return ""

    system_prompt = (
        "You summarize sections of GitHub READMEs. "
        "The input text may contain any language. "
        "Your task is to produce a short English paragraph (3-6 sentences) "
        "that captures the core purpose and intent of the section, "
        "suitable for semantic embedding. "
        "Do not include Markdown syntax, code, or bullet lists; "
        "write plain English sentences only."
    )

    user_prompt = textwrap.dedent(
        f"""
        Category: {category}

        Section text:
        {text}

        Write only the English summary paragraph.
        """
    ).strip()

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(
        messages=messages,
        max_tokens=512,
        temperature=0.2,
    )
    response = client.chat(request)
    return response.content.strip()
