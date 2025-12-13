"""
Diagnosis Agent - Reinterpret Path
캐시된 진단 결과를 다양한 관점으로 재해석
"""
from typing import Dict, Any, Optional, Literal
from backend.llm.factory import fetch_llm_client
from backend.llm.base import ChatRequest, ChatMessage
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


# 관점별 프롬프트 템플릿
PERSPECTIVE_PROMPTS = {
    "beginner": """
초보자 관점에서 설명하세요:
- 기술 용어를 쉽게 풀어쓰기
- "왜 중요한지" 설명 추가
- 시작하는 방법 강조
- 예시와 비유 사용
""",
    
    "tech_lead": """
기술 리드 관점에서 설명하세요:
- 아키텍처 품질 평가
- 기술 부채 지적
- 확장성/유지보수성 중심
- 리팩토링 우선순위 제시
""",
    
    "security_officer": """
보안 담당자 관점에서 설명하세요:
- 보안 취약점 위험도
- 규정 준수 여부
- 보안 개선 권장사항
- 즉시 조치 필요 항목
""",
    
    "manager": """
관리자 관점에서 설명하세요:
- 비즈니스 영향 분석
- 리소스 필요성
- ROI 및 우선순위
- 팀 생산성에 미치는 영향
""",
    
    "contributor": """
기여자 관점에서 설명하세요:
- 기여하기 좋은 영역
- Good First Issue 추천
- 기여 가이드라인
- 커뮤니티 활성도
""",
    
    "maintainer": """
오픈소스 메인테이너 관점에서 설명하세요:
- 유지보수 부담
- 이슈/PR 관리 전략
- 커뮤니티 건강도
- 지속가능성 평가
"""
}


async def execute_reinterpret_path(
    cached_result: Dict[str, Any],
    perspective: Literal["beginner", "tech_lead", "security_officer", "manager", "contributor", "maintainer"],
    detail_level: Literal["brief", "standard", "detailed"],
    user_question: Optional[str] = None,
    llm = None
) -> Dict[str, Any]:
    import time
    start_time = time.time()
    
    logger.info(f"Reinterpret path: perspective={perspective}, detail_level={detail_level}")
    
    if llm is None:
        llm = fetch_llm_client()
    
    # 진단 결과 요약
    summary_data = _summarize_diagnosis(cached_result)
    
    # 프롬프트 로드
    prompt_data = load_prompt("diagnosis_prompts")
    reinterpret_prompts = prompt_data.get("reinterpret", {})
    perspective_instruction = reinterpret_prompts.get(perspective, "일반적인 관점에서 설명하세요.")
    
    # LLM 요청 준비
    system_prompt = (
        "당신은 오픈소스 프로젝트 분석 전문가입니다. "
        "주어진 분석 데이터를 바탕으로 사용자의 질문에 답하거나 분석 결과를 설명해야 합니다.\n"
        f"{perspective_instruction}\n"
        f"분석 대상: {summary_data['repository']}\n"
        "설명은 한국어로 작성하고, 마크다운 형식을 사용하여 가독성을 높이세요."
    )
    
    # 상세도별 지시사항
    detail_instructions = {
        "brief": "3-5문장으로 핵심만 간결하게 요약하세요.",
        "standard": "1-2단락으로 주요 내용을 설명하세요.",
        "detailed": "여러 단락으로 상세하게 설명하고, 구체적인 예시와 권장사항을 포함하세요."
    }
    detail_instruction = detail_instructions.get(detail_level, detail_instructions["standard"])
    
    # 프롬프트 구성
    prompt = f"""다음은 GitHub 저장소의 진단 결과입니다:

=== 진단 결과 요약 ===
{json.dumps(summary_data, indent=2, ensure_ascii=False)}

=== 사용자 요청 ===
{user_question or "진단 결과를 다른 관점으로 설명해주세요"}

=== 지시사항 ===
{perspective_instruction}

{detail_instruction}

=== 응답 형식 ===
마크다운 형식으로 작성하세요:
- 제목 (## 레벨)
- 주요 발견사항 (bullet points)
- 권장사항 (구체적으로)
- 결론
"""

    try:
        # 비동기 LLM 호출
        loop = asyncio.get_event_loop()
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=1500
        )
        response = await loop.run_in_executor(None, llm.chat, request)
        reinterpreted_answer = response.content
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Reinterpret completed in {execution_time_ms}ms")
        
        return {
            "type": "reinterpret",
            "perspective": perspective,
            "detail_level": detail_level,
            "original_result": summary_data,
            "reinterpreted_answer": reinterpreted_answer,
            "execution_time_ms": execution_time_ms
        }
        
    except Exception as e:
        logger.error(f"Reinterpret failed: {e}", exc_info=True)
        return {
            "type": "reinterpret",
            "perspective": perspective,
            "detail_level": detail_level,
            "error": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


def _summarize_diagnosis(diagnosis_result: Dict[str, Any]) -> Dict[str, Any]:
    summary = {
        "repository": f"{diagnosis_result.get('owner', 'unknown')}/{diagnosis_result.get('repo', 'unknown')}",
        "analyzed_at": diagnosis_result.get("analyzed_at", "unknown"),
    }
    
    # 점수들
    scores = {}
    if "health_score" in diagnosis_result:
        scores["health_score"] = diagnosis_result["health_score"]
    if "onboarding_score" in diagnosis_result:
        scores["onboarding_score"] = diagnosis_result["onboarding_score"]
    if "docs_score" in diagnosis_result:
        scores["docs_score"] = diagnosis_result["docs_score"]
    if "activity_score" in diagnosis_result:
        scores["activity_score"] = diagnosis_result["activity_score"]
    if "structure_score" in diagnosis_result:
        scores["structure_score"] = diagnosis_result["structure_score"]
    
    summary["scores"] = scores
    
    # 주요 발견사항
    if "key_findings" in diagnosis_result:
        summary["key_findings"] = diagnosis_result["key_findings"][:5]  # 최대 5개
    
    # 경고
    if "warnings" in diagnosis_result:
        summary["warnings"] = diagnosis_result["warnings"][:5]
    
    # 권장사항
    if "recommendations" in diagnosis_result:
        summary["recommendations"] = diagnosis_result["recommendations"][:5]
    
    # 문서화 요약
    if "documentation" in diagnosis_result:
        doc = diagnosis_result["documentation"]
        summary["documentation"] = {
            "has_readme": doc.get("has_readme"),
            "readme_score": doc.get("readme_score"),
            "has_contributing": doc.get("has_contributing"),
            "has_license": doc.get("has_license")
        }
    
    # 활동 요약
    if "activity" in diagnosis_result:
        act = diagnosis_result["activity"]
        summary["activity"] = {
            "commit_frequency": act.get("commit_frequency"),
            "active_contributors": act.get("active_contributors"),
            "last_commit_date": act.get("last_commit_date")
        }
    
    return summary


async def generate_perspective_suggestions(
    diagnosis_result: Dict[str, Any]
) -> list:
    suggestions = []
    
    # 온보딩 점수가 낮으면 contributor 관점 추천
    if diagnosis_result.get("onboarding_score", 100) < 60:
        suggestions.append("contributor")
    
    # 건강도가 낮으면 manager 관점 추천
    if diagnosis_result.get("health_score", 100) < 70:
        suggestions.append("manager")
    
    # 문서화가 부족하면 beginner 관점 추천
    if diagnosis_result.get("docs_score", 100) < 70:
        suggestions.append("beginner")
    
    # 항상 tech_lead 추천 (기본)
    if "tech_lead" not in suggestions:
        suggestions.append("tech_lead")
    
    return suggestions[:3]  # 최대 3개
