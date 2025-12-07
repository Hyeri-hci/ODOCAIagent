import logging
import time
from typing import Optional

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity, analyze_activity_optimized
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
    
    timings = {}
    total_start = time.time()
    
    # 1. GitHub 데이터 수집
    try:
        fetch_start = time.time()
        snapshot = fetch_repo_snapshot(owner, repo, ref)
        timings["fetch_snapshot"] = round(time.time() - fetch_start, 3)
    except Exception as e:
        logger.error(f"Failed to fetch repo snapshot: {e}")
        raise RuntimeError(f"저장소 조회 실패: {e}")

    # 2. Core 분석
    try:
        # 의존성 파싱
        deps_start = time.time()
        deps = parse_dependencies(snapshot)
        timings["parse_dependencies"] = round(time.time() - deps_start, 3)
        
        # 문서 분석
        docs_start = time.time()
        docs_result = analyze_docs(snapshot)
        timings["analyze_docs"] = round(time.time() - docs_start, 3)
        
        # 활동성 분석 (최적화 버전 사용 - 단일 GraphQL 호출)
        activity_start = time.time()
        activity_result = analyze_activity_optimized(snapshot)
        timings["analyze_activity"] = round(time.time() - activity_start, 3)
        
        # 구조 분석
        structure_start = time.time()
        structure_result = analyze_structure(snapshot)
        timings["analyze_structure"] = round(time.time() - structure_start, 3)
        
        # 3. 점수 계산
        scoring_start = time.time()
        diagnosis = compute_scores(docs_result, activity_result, deps)
        timings["compute_scores"] = round(time.time() - scoring_start, 3)
        
    except Exception as e:
        logger.error(f"Diagnosis core failed: {e}")
        raise RuntimeError(f"진단 실행 실패: {e}")
    
    timings["total_analysis"] = round(time.time() - total_start, 3)
    logger.info(f"Diagnosis timings for {owner}/{repo}: {timings}")

    # 4. 사용자용 요약 생성 (snapshot에서 README 내용 가져옴)
    summary_text = _generate_summary(diagnosis, docs_result, snapshot, input_data.use_llm_summary)

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
        stars=snapshot.stars,
        forks=snapshot.forks,
        summary_for_user=summary_text,
        raw_metrics=diagnosis.to_dict()
    )

def _generate_summary(diagnosis, docs_result, snapshot, use_llm_summary: bool) -> str:
    """진단 결과 요약 생성 (Fallback + LLM)"""
    
    # 활동성 상세 메트릭 가져오기
    activity_result = diagnosis.activity_result if hasattr(diagnosis, 'activity_result') else None
    days_since_last_commit = activity_result.days_since_last_commit if activity_result else None
    issue_close_rate = activity_result.issue_close_rate if activity_result else 0.0
    median_pr_merge_days = activity_result.median_pr_merge_days if activity_result else None
    open_issues_count = activity_result.open_issues_count if activity_result else 0
    
    # 구체적 수치가 포함된 fallback 요약 생성
    commit_status = ""
    if days_since_last_commit is not None:
        if days_since_last_commit <= 7:
            commit_status = f"최근 활동: {days_since_last_commit}일 전 커밋 (활성)"
        elif days_since_last_commit <= 30:
            commit_status = f"최근 활동: {days_since_last_commit}일 전 커밋 (주의)"
        else:
            commit_status = f"최근 활동: {days_since_last_commit}일 전 커밋 (비활성)"
    
    pr_status = ""
    if median_pr_merge_days is not None:
        if median_pr_merge_days <= 7:
            pr_status = f"PR 병합 속도: {median_pr_merge_days:.1f}일 (양호)"
        elif median_pr_merge_days <= 14:
            pr_status = f"PR 병합 속도: {median_pr_merge_days:.1f}일 (느림)"
        else:
            pr_status = f"PR 병합 속도: {median_pr_merge_days:.1f}일 (매우 느림)"

    issue_status = f"이슈 해결률: {issue_close_rate * 100:.1f}% (미해결: {open_issues_count}개)"

    # 점수 해석
    health_interpretation = ""
    if diagnosis.health_score >= 80:
        health_interpretation = "상위 10% 수준 - 매우 건강한 프로젝트"
    elif diagnosis.health_score >= 60:
        health_interpretation = "평균 수준 (OSS 평균: 65점)"
    elif diagnosis.health_score >= 40:
        health_interpretation = "평균 이하 - 개선이 필요함"
    else:
        health_interpretation = "심각한 상태 - 즉각적인 조치 필요"
    
    # 상세 메트릭 목록 구성
    detail_metrics = []
    if commit_status:
        detail_metrics.append(f"- {commit_status}")
    if pr_status:
        detail_metrics.append(f"- {pr_status}")
    detail_metrics.append(f"- {issue_status}")
    detail_section = "\n".join(detail_metrics)
    
    fallback_summary = (
        f"### {diagnosis.repo_id} 진단 결과\n\n"
        f"#### 종합 점수\n"
        f"- **건강 점수**: {diagnosis.health_score}점 ({diagnosis.health_level}) - {health_interpretation}\n"
        f"- **문서 품질**: {diagnosis.documentation_quality}점\n"
        f"- **활동성**: {diagnosis.activity_maintainability}점\n"
        f"- **온보딩**: {diagnosis.onboarding_score}점 ({diagnosis.onboarding_level})\n\n"
        f"#### 상세 메트릭\n"
        f"{detail_section}\n\n"
        f"#### 주요 이슈\n"
        f"- 문서: {', '.join(diagnosis.docs_issues) or '발견된 이슈 없음'}\n"
        f"- 활동성: {', '.join(diagnosis.activity_issues) or '발견된 이슈 없음'}"
    )

    if not use_llm_summary:
        return fallback_summary

    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME

        client = fetch_llm_client()
        
        system_prompt = (
            "당신은 전문 소프트웨어 엔지니어링 컨설턴트입니다. "
            "제공된 저장소 진단 데이터와 README 내용을 분석하고 한글로 간결하고 전문적인 요약을 제공하세요. "
            "반드시 다음 형식으로 작성하세요:\n\n"
            "## 프로젝트 소개\n"
            "이 프로젝트가 무엇인지, 어떤 역할/용도인지 2-3문장으로 설명.\n\n"
            "## 진단 요약\n"
            "전체적인 건강도 평가와 주요 강점/약점.\n\n"
            "## 개선 권장사항\n"
            "개선이 필요한 부분과 구체적인 조치 제안."
        )
        
        # README 내용 가져오기 (snapshot에서 - 처음 800자)
        readme_content = ""
        if snapshot and hasattr(snapshot, 'readme_content') and snapshot.readme_content:
            readme_content = snapshot.readme_content[:800]
        
        docs_detail = ""
        if docs_result:
            missing = ", ".join(docs_result.missing_sections) if hasattr(docs_result, 'missing_sections') else ""
            if missing:
                docs_detail = f"누락된 문서 섹션: {missing}\n"
        
        user_prompt = (
            f"저장소: {diagnosis.repo_id}\n\n"
            f"=== README 내용 ===\n{readme_content or '(README 없음)'}\n\n"
            f"=== 진단 결과 ===\n"
            f"건강 점수: {diagnosis.health_score}점 ({diagnosis.health_level})\n"
            f"문서 품질: {diagnosis.documentation_quality}점\n"
            f"활동성 점수: {diagnosis.activity_maintainability}점\n"
            f"온보딩 점수: {diagnosis.onboarding_score}점 ({diagnosis.onboarding_level})\n"
            f"문서 이슈: {', '.join(diagnosis.docs_issues) or '없음'}\n"
            f"활동성 이슈: {', '.join(diagnosis.activity_issues) or '없음'}\n"
            f"{docs_detail}\n"
            "위 정보를 바탕으로 프로젝트 소개, 진단 요약, 개선 권장사항을 한글로 작성해주세요."
        )

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.2,
        )
        
        response = client.chat(request, timeout=30)
        return response.content

    except Exception as e:
        logger.debug(f"LLM summary full traceback: {e}", exc_info=True)
        logger.warning(f"LLM summary failed (using fallback): {e}")
        return fallback_summary
