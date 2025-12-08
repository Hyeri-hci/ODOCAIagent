import logging
import time
from typing import Optional

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_docs
from backend.core.activity_core import analyze_activity, analyze_activity_optimized
from backend.core.structure_core import analyze_structure
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_scores
from backend.core.models import RepoSnapshot, DependenciesSnapshot

from backend.agents.diagnosis.models import DiagnosisInput, DiagnosisOutput

logger = logging.getLogger(__name__)

# 분석 깊이별 설정
DEPTH_CONFIG = {
    "deep": {
        "use_llm_summary": True,
        "analyze_structure": True,
        "parse_dependencies": True,
        "activity_history_days": 180,  # 더 긴 기간 분석
        "description": "심층 분석 - 모든 메트릭 상세 분석"
    },
    "standard": {
        "use_llm_summary": True,
        "analyze_structure": True,
        "parse_dependencies": True,
        "activity_history_days": 90,
        "description": "표준 분석 - 일반 메트릭 분석"
    },
    "quick": {
        "use_llm_summary": False,  # quick 모드에서는 LLM 요약 스킵
        "analyze_structure": True,
        "parse_dependencies": False,  # 의존성 분석 스킵
        "activity_history_days": 30,  # 짧은 기간만 분석
        "description": "빠른 분석 - 핵심 메트릭만 분석"
    }
}


def run_diagnosis(input_data: DiagnosisInput) -> DiagnosisOutput:
    """
    OSSDoctor 진단의 단일 진입점.
    데이터 수집 -> 분석 -> 점수 계산 -> 요약 -> DTO 반환 과정을 수행합니다.
    
    분석 깊이(analysis_depth)에 따라 분석 범위가 달라집니다:
    - deep: 모든 분석 수행, 긴 기간 데이터 수집
    - standard: 일반 분석 (기본값)
    - quick: LLM 요약 및 의존성 분석 스킵, 짧은 기간 데이터만 수집
    """
    owner = input_data.owner
    repo = input_data.repo
    ref = input_data.ref
    depth = input_data.analysis_depth
    
    # 분석 깊이 설정 가져오기
    depth_config = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["standard"])
    logger.info(f"Running diagnosis with depth={depth}: {depth_config['description']}")
    
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
        # 의존성 파싱 (quick 모드에서는 스킵)
        deps = None
        if depth_config["parse_dependencies"]:
            deps_start = time.time()
            deps = parse_dependencies(snapshot)
            timings["parse_dependencies"] = round(time.time() - deps_start, 3)
        else:
            logger.info(f"Skipping dependency parsing for {depth} mode")
            deps = DependenciesSnapshot(
                repo_id=snapshot.repo_id,
                dependencies=[],
                analyzed_files=["skipped:quick_mode"],
                parse_errors=[],
            )
        
        # 문서 분석
        docs_start = time.time()
        docs_result = analyze_docs(snapshot)
        timings["analyze_docs"] = round(time.time() - docs_start, 3)
        
        # 활동성 분석 (최적화 버전 사용 - 단일 GraphQL 호출)
        activity_start = time.time()
        activity_result = analyze_activity_optimized(snapshot)
        timings["analyze_activity"] = round(time.time() - activity_start, 3)
        
        # 구조 분석
        structure_result = None
        if depth_config["analyze_structure"]:
            structure_start = time.time()
            structure_result = analyze_structure(snapshot)
            timings["analyze_structure"] = round(time.time() - structure_start, 3)
        
        # 3. 점수 계산 (구조 점수 포함)
        scoring_start = time.time()
        diagnosis = compute_scores(docs_result, activity_result, deps, structure_result)
        timings["compute_scores"] = round(time.time() - scoring_start, 3)
        
    except Exception as e:
        logger.error(f"Diagnosis core failed: {e}")
        raise RuntimeError(f"진단 실행 실패: {e}")
    
    timings["total_analysis"] = round(time.time() - total_start, 3)
    timings["analysis_depth"] = depth
    logger.info(f"Diagnosis timings for {owner}/{repo} (depth={depth}): {timings}")

    # 4. 사용자용 요약 생성
    # quick 모드이거나 사용자가 명시적으로 LLM 요약을 비활성화한 경우 fallback 사용
    use_llm = input_data.use_llm_summary and depth_config["use_llm_summary"]
    summary_text = _generate_summary(diagnosis, docs_result, structure_result, snapshot, use_llm)

    # 5. DTO 반환
    return DiagnosisOutput(
        repo_id=diagnosis.repo_id,
        health_score=float(diagnosis.health_score),
        health_level=diagnosis.health_level,
        onboarding_score=float(diagnosis.onboarding_score),
        onboarding_level=diagnosis.onboarding_level,
        docs=docs_result.to_dict() if hasattr(docs_result, "to_dict") else docs_result.__dict__,
        activity=activity_result.to_dict() if hasattr(activity_result, "to_dict") else activity_result.__dict__,
        structure=structure_result.to_dict() if structure_result else {},
        dependency_complexity_score=diagnosis.dependency_complexity_score,
        dependency_flags=list(diagnosis.dependency_flags),
        stars=snapshot.stars,
        forks=snapshot.forks,
        summary_for_user=summary_text,
        raw_metrics=diagnosis.to_dict()
    )


def _generate_summary(diagnosis, docs_result, structure_result, snapshot, use_llm_summary: bool) -> str:
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

    # 구조 정보 요약
    structure_summary = ""
    if structure_result:
        structure_items = []
        if structure_result.has_tests:
            structure_items.append("테스트")
        if structure_result.has_ci:
            structure_items.append("CI/CD")
        if structure_result.has_docs_folder:
            structure_items.append("문서 폴더")
        if structure_result.has_build_config:
            structure_items.append("빌드 설정")
        
        if structure_items:
            structure_summary = f"프로젝트 구조: {', '.join(structure_items)} 존재 ({structure_result.structure_score}점)"
        else:
            structure_summary = "프로젝트 구조: 테스트/CI/문서 폴더 없음 (0점)"

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
    if structure_summary:
        detail_metrics.append(f"- {structure_summary}")
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
            "당신은 ODOC(Open-source Doctor) AI 분석 전문가입니다. "
            "ODOC은 문서품질(README/CONTRIBUTING/LICENSE/docs폴더), "
            "활동성(커밋/이슈/PR), 구조(테스트/CI/빌드설정)를 기반으로 "
            "건강점수(문서25%+활동성65%+구조10%)와 온보딩점수(문서55%+활동성35%+구조10%)를 산출합니다. "
            "등급기준: 80점이상=Excellent, 60-79=Good, 40-59=Fair, 40미만=Poor. "
            "제공된 진단 데이터를 분석하고 한글로 간결하고 전문적인 요약을 제공하세요. "
            "반드시 다음 형식으로 작성하세요:\n\n"
            "## 프로젝트 소개\n"
            "이 프로젝트가 무엇인지, 어떤 역할/용도인지 2-3문장으로 설명.\n\n"
            "## 진단 요약\n"
            "ODOC 평가 기준에 따른 전체적인 건강도 평가와 주요 강점/약점. "
            "프로젝트 구조(테스트, CI, 문서 폴더 등) 관점에서의 성숙도도 언급.\n\n"
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
        
        # 구조 정보 생성
        structure_detail = ""
        if structure_result:
            struct_items = []
            struct_items.append(f"테스트: {'있음' if structure_result.has_tests else '없음'}")
            struct_items.append(f"CI/CD: {'있음' if structure_result.has_ci else '없음'}")
            struct_items.append(f"문서 폴더: {'있음' if structure_result.has_docs_folder else '없음'}")
            struct_items.append(f"빌드 설정: {'있음' if structure_result.has_build_config else '없음'}")
            structure_detail = f"프로젝트 구조: {', '.join(struct_items)} (구조 점수: {structure_result.structure_score}점)\n"
        
        user_prompt = (
            f"저장소: {diagnosis.repo_id}\n\n"
            f"=== README 내용 ===\n{readme_content or '(README 없음)'}\n\n"
            f"=== 진단 결과 ===\n"
            f"건강 점수: {diagnosis.health_score}점 ({diagnosis.health_level})\n"
            f"문서 품질: {diagnosis.documentation_quality}점\n"
            f"활동성 점수: {diagnosis.activity_maintainability}점\n"
            f"온보딩 점수: {diagnosis.onboarding_score}점 ({diagnosis.onboarding_level})\n"
            f"{structure_detail}"
            f"문서 이슈: {', '.join(diagnosis.docs_issues) or '없음'}\n"
            f"활동성 이슈: {', '.join(diagnosis.activity_issues) or '없음'}\n"
            f"{docs_detail}\n"
            "위 정보를 바탕으로 프로젝트 소개, 진단 요약, 개선 권장사항을 한글로 작성해주세요. "
            "진단 요약에서는 프로젝트 구조(테스트/CI 유무 등)가 기여 용이성에 미치는 영향도 언급해주세요."
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
