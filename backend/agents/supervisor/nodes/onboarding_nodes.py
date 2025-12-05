from typing import Dict, Any
from backend.agents.supervisor.models import SupervisorState
from backend.llm.kanana_wrapper import KananaWrapper

# Global or instantiated per request? Instantiating per request is safer for now.
# Or use a singleton pattern if needed.


def fetch_issues_node(state: SupervisorState) -> Dict[str, Any]:
    """
    GitHub 이슈 수집 노드 (Placeholder).
    실제 구현 시: GitHub API로 'good first issue', 'help wanted' 라벨이 붙은 이슈 수집.
    """
    # Mock Data
    issues = [
        {"number": 101, "title": "Fix typo in README", "labels": ["good first issue"]},
        {"number": 102, "title": "Add unit tests for utils", "labels": ["help wanted", "good first issue"]},
    ]
    return {"candidate_issues": issues}

def plan_onboarding_node(state: SupervisorState) -> Dict[str, Any]:
    """
    온보딩 플랜 생성 노드.
    Kanana LLM을 사용하여 사용자 컨텍스트와 진단 결과를 바탕으로 주차별 플랜 생성.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    kanana = KananaWrapper()
    
    repo_id = f"{state.owner}/{state.repo}"
    diagnosis_summary = state.diagnosis_result.get("summary_for_user", "") if state.diagnosis_result else ""
    
    try:
        plan = kanana.generate_onboarding_plan(
            repo_id=repo_id,
            diagnosis_summary=diagnosis_summary,
            user_context=state.user_context,
            candidate_issues=state.candidate_issues
        )
        logger.info(f"Onboarding plan generated: {len(plan)} weeks")
        return {"onboarding_plan": plan}
    except ValueError as e:
        # LLM JSON 파싱 실패
        error_msg = str(e)
        logger.error(f"Onboarding plan generation failed: {error_msg}")
        return {
            "onboarding_plan": None,
            "error": f"LLM_JSON_PARSE_ERROR: {error_msg[:100]}"
        }
    except Exception as e:
        # 기타 에러
        error_msg = str(e)
        logger.error(f"Onboarding plan generation failed: {error_msg}")
        return {
            "onboarding_plan": None,
            "error": f"ONBOARDING_PLAN_ERROR: {error_msg[:100]}"
        }

def summarize_onboarding_plan_node(state: SupervisorState) -> Dict[str, Any]:
    """
    온보딩 플랜 요약 노드.
    Kanana LLM을 사용하여 플랜을 자연어로 설명.
    """
    kanana = KananaWrapper()
    repo_id = f"{state.owner}/{state.repo}"
    
    summary = kanana.summarize_onboarding_plan(
        repo_id=repo_id,
        plan=state.onboarding_plan
    )
    
    return {
        "last_answer_kind": "plan",
        "onboarding_summary": summary,
    }
