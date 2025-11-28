from __future__ import annotations

from typing import Any, Dict
import json

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client


def summarize_diagnosis_repository(
    diagnosis_result: Dict[str, Any],
    user_level: str = "beginner",
    language: str = "ko",
) -> str:
    """
    Diagnosis Agent 최종 요약용 LLM 호출 함수.

    - diagnosis_result: run_diagnosis()가 만든 전체 JSON
      (scores / details / docs.readme_categories 포함)
    """

    # JSON을 LLM이 읽기 좋은 형태로 직렬화
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

    overall_score = scores.get("overall_score")
    docs_score = scores.get("documentation_quality")
    activity_score = scores.get("activity_maintainability")
    readme_dsa = docs_block.get("readme_category_score")

    if language == "ko":
        system_prompt = (
            "너는 오픈소스 프로젝트 진단 결과를 바탕으로 "
            "초보 개발자에게 프로젝트 상태를 설명하는 전문가이다. "
            "입력으로 주어지는 JSON 안의 점수와 지표를 바탕으로 "
            "자연스럽게 문단을 구성해 설명하되, "
            "숫자 점수는 임의로 바꾸거나 새로 만들지 말고 반드시 입력에 있는 값만 사용해라. "
            "문장이 중간에 끊기지 않도록 완결된 문장들로 답변해라."
        )

        user_prompt = (
            f"사용자 수준: {user_level}\n\n"
            "다음은 한 GitHub 저장소에 대한 진단 결과 JSON이다.\n"
            "전체 Health Score, 문서 품질, 활동성/유지보수성, "
            "README 8-카테고리 분석 결과가 포함되어 있다.\n\n"
            "먼저 주요 점수 요약은 다음과 같다. 값이 없으면 None이다.\n"
            f"- overall_score: {overall_score}\n"
            f"- documentation_quality: {docs_score}\n"
            f"- activity_maintainability: {activity_score}\n"
            f"- readme_category_score(DSA): {readme_dsa}\n\n"
            "아래 JSON 전체를 참고해서, 다음 형식으로 한국어로 답변해라.\n\n"
            "[프로젝트 상태 개요]\n"
            "전체 Health Score와 주요 지표를 바탕으로 프로젝트의 전반적인 상태를 "
            "여러 문장으로 설명해라. 한두 문장으로 끝내지 말고 자연스럽게 하나의 문단이 되도록 작성해라.\n\n"
            "[문서 품질 및 온보딩 관점]\n"
            "README/문서 구조와 DSA 점수를 기반으로 문서 품질과 온보딩 난이도를 설명해라. "
            "초보 기여자가 README만 보고 이해하고 시작할 수 있는지 평가하라.\n\n"
            "[활동성 및 유지보수성]\n"
            "커밋과 이슈 관련 지표를 바탕으로 프로젝트가 얼마나 활발하게 유지보수되고 있는지 설명해라.\n\n"
            "[개선이 필요한 점]\n"
            "가장 중요한 개선 포인트를 여러 개 bullet 형식으로 정리하되, "
            "각 bullet은 한 줄짜리 짧은 문장이 아니라 한두 문장 정도로 이유와 방향을 함께 설명해라.\n\n"
            "[초보 기여자를 위한 온보딩 제안]\n"
            "초보 개발자가 이 프로젝트에 기여를 시작할 때 어떤 순서로 문서와 이슈를 보면 좋은지 "
            "간단한 단계형 가이드로 제안해라.\n\n"
            "각 섹션은 문장이 중간에 잘리지 않도록 완결된 문장으로 작성하라.\n\n"
            "진단 결과 JSON:\n"
            f"{diagnosis_json_str}"
        )
    else:
        system_prompt = (
            "You explain open-source diagnosis results to help new contributors. "
            "Use only the numeric scores provided in the input. "
            "Write complete sentences and avoid truncation."
        )
        user_prompt = (
            f"User level: {user_level}\n\n"
            f"Diagnosis JSON:\n{diagnosis_json_str}"
        )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(
        messages=messages,
        max_tokens=1200,      # 이전보다 여유 있게 설정
        temperature=0.2,
    )
    response = client.chat(request)

    return response.content
