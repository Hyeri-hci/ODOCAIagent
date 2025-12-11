import logging
import warnings
from backend.agents.diagnosis.models import DiagnosisInput
from backend.agents.diagnosis.service import run_diagnosis
from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)

warnings.warn(
    "diagnosis_nodes.py deprecated - use Supervisor V2",
    DeprecationWarning,
    stacklevel=2
)


def run_diagnosis_node(state: SupervisorState) -> dict:
    """
    Supervisor 그래프에서 진단을 실행하는 노드.
    SupervisorState -> DiagnosisInput -> run_diagnosis -> SupervisorState 업데이트
    
    * Idempotency: 이미 diagnosis_result가 있다면 재실행하지 않고 기존 결과를 반환합니다.
    * 분석 깊이: state.analysis_depth를 사용하여 분석 범위를 동적으로 조절합니다.
    """
    if state.diagnosis_result:
        # 이미 진단 결과가 있으면 재사용 (Smart Agent Behavior)
        logger.info(f"Reusing existing diagnosis result for {state.owner}/{state.repo}")
        return {}

    if not state.owner or not state.repo:
        return {"error": "owner/repo is required for diagnosis"}

    try:
        # 분석 깊이 결정 (state에서 가져오기, 기본값은 standard)
        analysis_depth = state.analysis_depth or "standard"
        
        logger.info(
            f"Running diagnosis for {state.owner}/{state.repo} "
            f"with analysis_depth={analysis_depth}"
        )
        
        input_data = DiagnosisInput(
            owner=state.owner, 
            repo=state.repo,
            use_llm_summary=state.user_context.get("use_llm_summary", True),
            analysis_depth=analysis_depth,
        )
        
        output = run_diagnosis(input_data)
        
        # 결과 업데이트 (Pydantic 모델의 필드에 맞춰 dict 반환)
        # LangGraph는 이 dict를 기존 state에 merge함
        result_dict = output.to_dict()
        
        # 분석 깊이 정보를 결과에 추가
        result_dict["analysis_depth_used"] = analysis_depth
        
        # API 호환성을 위해 중첩된 점수를 최상위로 추출
        docs_data = result_dict.get("docs", {})
        activity_data = result_dict.get("activity", {})
        result_dict["documentation_quality"] = docs_data.get("total_score", 0)
        result_dict["activity_maintainability"] = activity_data.get("total_score", 0)
        
        # 활동성 메트릭 추출
        result_dict["days_since_last_commit"] = activity_data.get("days_since_last_commit")
        result_dict["total_commits_30d"] = activity_data.get("total_commits_30d", 0)
        result_dict["unique_contributors"] = activity_data.get("unique_contributors", 0)
        result_dict["issue_close_rate"] = activity_data.get("issue_close_rate", 0)
        result_dict["median_pr_merge_days"] = activity_data.get("median_pr_merge_days")
        result_dict["open_issues_count"] = activity_data.get("open_issues_count", 0)
        
        logger.info(
            f"Diagnosis completed for {state.owner}/{state.repo}: "
            f"health_score={output.health_score}, depth={analysis_depth}"
        )
        
        return {
            "diagnosis_result": result_dict,
            "last_answer_kind": "report",
        }
        
    except Exception as e:
        logger.error(f"Diagnosis failed for {state.owner}/{state.repo}: {e}")
        return {"error": f"Diagnosis failed: {str(e)}"}

