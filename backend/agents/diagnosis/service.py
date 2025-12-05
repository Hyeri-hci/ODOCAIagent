import logging
from typing import Optional

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity
from backend.core.structure_core import analyze_structure
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_scores
from backend.core.models import RepoSnapshot

from backend.agents.diagnosis.models import DiagnosisInput, DiagnosisOutput

logger = logging.getLogger(__name__)

def run_diagnosis(input_data: DiagnosisInput) -> DiagnosisOutput:
    """
    OSSDoctor 진단의 단일 진입점.
    데이터 수집 -> 분석 -> 점수 계산 -> 요약 -> DTO 반환 과정을 수행합니다.
    """
    owner = input_data.owner
    repo = input_data.repo
    ref = input_data.ref
    
    # 1. GitHub 데이터 수집
    try:
        snapshot = fetch_repo_snapshot(owner, repo, ref)
    except Exception as e:
        logger.error(f"Failed to fetch repo snapshot: {e}")
        raise RuntimeError(f"저장소 조회 실패: {e}")

    # 2. Core 분석
    try:
        # 의존성 파싱
        deps = parse_dependencies(snapshot)
        
        # 문서 분석
        docs_result = analyze_docs(snapshot)
        
        # 활동성 분석
        activity_result = analyze_activity(snapshot)
        
        # 구조 분석
        structure_result = analyze_structure(snapshot)
        
        # 3. 점수 계산
        diagnosis = compute_scores(docs_result, activity_result, deps)
        
    except Exception as e:
        logger.error(f"Diagnosis core failed: {e}")
        raise RuntimeError(f"진단 실행 실패: {e}")

    # 4. 사용자용 요약 생성
    summary_text = _generate_summary(diagnosis, docs_result, input_data.use_llm_summary)

    # 5. DTO 반환
    return DiagnosisOutput(
        repo_id=diagnosis.repo_id,
        health_score=float(diagnosis.health_score),
        health_level=diagnosis.health_level,
        onboarding_score=float(diagnosis.onboarding_score),
        onboarding_level=diagnosis.onboarding_level,
        docs=docs_result.to_dict() if hasattr(docs_result, "to_dict") else docs_result.__dict__,
        activity=activity_result.to_dict() if hasattr(activity_result, "to_dict") else activity_result.__dict__,
        structure=structure_result.to_dict(),
        dependency_complexity_score=diagnosis.dependency_complexity_score,
        dependency_flags=list(diagnosis.dependency_flags),
        summary_for_user=summary_text,
        raw_metrics=diagnosis.to_dict()
    )

def _generate_summary(diagnosis, docs_result, use_llm_summary: bool) -> str:
    """진단 결과 요약 생성 (Fallback + LLM)"""
    
    fallback_summary = (
        f"### {diagnosis.repo_id} 진단 결과\n\n"
        f"- **건강 점수**: {diagnosis.health_score}점 ({diagnosis.health_level})\n"
        f"- **문서 품질**: {diagnosis.documentation_quality}점\n"
        f"- **활동성**: {diagnosis.activity_maintainability}점\n"
        f"- **온보딩**: {diagnosis.onboarding_score}점 ({diagnosis.onboarding_level})\n\n"
        f"**주요 이슈**:\n"
        f"- 문서: {', '.join(diagnosis.docs_issues) or '없음'}\n"
        f"- 활동성: {', '.join(diagnosis.activity_issues) or '없음'}"
    )

    if not use_llm_summary:
        return fallback_summary

    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME

        client = fetch_llm_client()
        
        system_prompt = (
            "You are an expert software engineering consultant. "
            "Analyze the provided repository diagnosis data and provide a concise, professional summary in Korean. "
            "Highlight key strengths, critical issues, and actionable recommendations. "
            "Use markdown formatting with the following sections:\n"
            "1. **Summary**: Overall assessment.\n"
            "2. **Key Issues**: Critical problems found.\n"
            "3. **Recommendations**: Actionable steps to improve."
        )
        
        docs_detail = ""
        if docs_result:
            missing = ", ".join(docs_result.missing_sections) or "None"
            marketing = f"{docs_result.marketing_ratio:.2f}"
            docs_detail = (
                f"Missing Sections: {missing}\n"
                f"Marketing Ratio: {marketing}\n"
            )
        
        user_prompt = (
            f"Repository: {diagnosis.repo_id}\n"
            f"Health Score: {diagnosis.health_score} ({diagnosis.health_level})\n"
            f"Docs Quality: {diagnosis.documentation_quality}\n"
            f"Activity Score: {diagnosis.activity_maintainability}\n"
            f"Onboarding Score: {diagnosis.onboarding_score} ({diagnosis.onboarding_level})\n"
            f"Docs Issues: {', '.join(diagnosis.docs_issues)}\n"
            f"Activity Issues: {', '.join(diagnosis.activity_issues)}\n"
            f"Dependency Complexity: {diagnosis.dependency_complexity_score} (Flags: {', '.join(diagnosis.dependency_flags) or 'None'})\n"
            f"{docs_detail}\n"
            "Please summarize this diagnosis."
        )

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.2,
        )
        
        response = client.chat(request, timeout=10)
        return response.content

    except Exception as e:
        logger.debug(f"LLM summary full traceback: {e}", exc_info=True)
        logger.warning(f"LLM summary failed (using fallback): {e}")
        return fallback_summary
