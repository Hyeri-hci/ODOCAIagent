"""Diagnosis 결과 LLM 요약."""
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
    """Diagnosis JSON을 LLM으로 요약. is_healthy=False면 경고 문구 추가."""
    try:
        diagnosis_json_str = json.dumps(diagnosis_result, ensure_ascii=False, indent=2)
    except Exception:
        diagnosis_json_str = str(diagnosis_result)

    scores = diagnosis_result.get("scores", {}) or {}
    details = diagnosis_result.get("details", {}) or {}
    docs_block = details.get("docs", {}) or {}
    repo_info = details.get("repo_info", {}) or {}

    # v1 점수 추출
    health_score = scores.get("health_score")
    onboarding_score = scores.get("onboarding_score")
    docs_score = scores.get("documentation_quality")
    activity_score = scores.get("activity_maintainability")
    is_healthy = scores.get("is_healthy", True)

    # v2 점수 추출
    docs_effective = scores.get("docs_effective", docs_score)
    tech_score = scores.get("tech_score", 0)
    marketing_penalty = scores.get("marketing_penalty", 0)
    consilience_score = scores.get("consilience_score", 100)
    gate_level = scores.get("gate_level", "unknown")
    is_sustainable = scores.get("is_sustainable", True)
    is_marketing_heavy = scores.get("is_marketing_heavy", False)
    has_broken_refs = scores.get("has_broken_refs", False)

    # 경고 섹션 구성
    warning_section = ""
    warnings = []
    
    if not is_healthy:
        warnings.append(
            "이 프로젝트는 현재 활발하게 유지보수되지 않거나 "
            "더 이상 적극적으로 사용되지 않는 프로젝트입니다."
        )
    
    if gate_level == "abandoned":
        warnings.append(
            "최근 활동이 거의 없어 사실상 중단된 상태입니다. "
            "대안 프로젝트를 검토하세요."
        )
    elif gate_level == "stale":
        warnings.append(
            "유지보수 활동이 둔화되고 있습니다. "
            "장기 사용 전 커뮤니티 동향을 확인하세요."
        )
    
    if is_marketing_heavy:
        warnings.append(
            "README가 마케팅 목적으로 작성되어 실제 기술 문서가 부족할 수 있습니다."
        )
    
    if has_broken_refs:
        warnings.append(
            "README에 깨진 링크나 존재하지 않는 파일 참조가 있습니다."
        )
    
    if warnings:
        warning_section = "[주의] " + " ".join(warnings) + "\n\n"

    # README 미리보기
    raw_readme = details.get("readme_raw", "")
    project_glimpse = ""
    if isinstance(raw_readme, str) and raw_readme.strip():
        project_glimpse = "\n".join(raw_readme.splitlines()[:80])

    # 지속가능성 설명
    gate_desc = {
        "active": "적극적으로 유지보수 중",
        "maintained": "유지보수됨 (정기 업데이트)",
        "stale": "유지보수 둔화",
        "abandoned": "사실상 중단",
        "unknown": "판단 불가"
    }.get(gate_level, gate_level)

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
            - documentation_quality (형식 기반): {docs_score}
            - docs_effective (유효 문서): {docs_effective}
            - activity_maintainability: {activity_score}
            - is_healthy: {is_healthy}

            [문서 품질 분석 (v2)]
            - tech_score: {tech_score} (기술 신호 점수)
            - marketing_penalty: {marketing_penalty} (마케팅 페널티)
            - consilience_score: {consilience_score} (교차검증 점수)
            - is_marketing_heavy: {is_marketing_heavy}
            - has_broken_refs: {has_broken_refs}

            [프로젝트 지속가능성]
            - gate_level: {gate_level} ({gate_desc})
            - is_sustainable: {is_sustainable}

            [README 상단 일부]
            {project_glimpse}

            위 정보를 참고해 다음 구조로 한국어 설명을 작성해라:

            1. 프로젝트 소개
            2. 문서 품질과 온보딩 난이도
               - docs_effective가 documentation_quality보다 낮다면, 
                 마케팅성 문서나 깨진 참조가 있는지 언급
            3. 활동성 및 유지보수성 (gate_level 기반)
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

            [Core Scores]
            - health_score: {health_score}
            - onboarding_score: {onboarding_score}
            - docs_effective: {docs_effective} (actual usable documentation)
            - activity: {activity_score}
            - gate_level: {gate_level} ({gate_desc})

            [Documentation Analysis v2]
            - tech_score: {tech_score}
            - marketing_penalty: {marketing_penalty}
            - is_marketing_heavy: {is_marketing_heavy}
            - has_broken_refs: {has_broken_refs}

            Diagnosis JSON:
            {diagnosis_json_str}

            Write a summary with:
            1. Project overview
            2. Documentation quality & onboarding difficulty
               - If docs_effective < documentation_quality, mention marketing/broken refs
            3. Activity & sustainability (based on gate_level)
            4. Key issues / risks
            5. Suggested next steps for a new contributor
        """).strip()

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    client = fetch_llm_client()
    request = ChatRequest(messages=messages, max_tokens=4000, temperature=0.2)
    response = client.chat(request)

    if warning_section:
        return warning_section + response.content.strip()
    return response.content.strip()


