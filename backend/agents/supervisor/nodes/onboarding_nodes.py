from typing import Dict, Any
from backend.agents.supervisor.models import SupervisorState
from backend.llm.kanana_wrapper import KananaWrapper
from backend.common.github_client import fetch_beginner_issues

# Global or instantiated per request? Instantiating per request is safer for now.
# Or use a singleton pattern if needed.


def fetch_issues_node(state: SupervisorState) -> Dict[str, Any]:
    """
    GitHub 이슈 수집 노드.
    경험 레벨에 따라 적절한 라벨의 이슈를 GitHub API로 수집.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 경험 레벨에 따른 라벨 설정
    exp_level = (state.user_preferences or {}).get("experience_level", "beginner")
    
    label_map = {
        "beginner": ["good first issue", "help wanted", "beginner", "easy", "starter", "first-timers-only", "docs"],
        "intermediate": ["help wanted", "enhancement", "bug", "feature", "improvement"],
        "advanced": ["core", "architecture", "performance", "security", "critical", "priority"],
    }
    labels = label_map.get(exp_level, label_map["beginner"])
    
    logger.info(f"Fetching issues for {state.owner}/{state.repo} with experience_level={exp_level}")
    
    try:
        issues = fetch_beginner_issues(
            owner=state.owner,
            repo=state.repo,
            labels=labels,
            max_count=10
        )
        logger.info(f"Fetched {len(issues)} issues for {state.owner}/{state.repo} (level={exp_level})")
        return {"candidate_issues": issues}
    except Exception as e:
        logger.warning(f"Failed to fetch issues: {e}. Using empty list.")
        return {"candidate_issues": []}

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
    import logging
    logger = logging.getLogger(__name__)
    
    # 플랜 생성 실패 시 요약도 스킵
    if state.onboarding_plan is None:
        logger.warning("Onboarding plan is None, skipping summary")
        return {
            "last_answer_kind": "plan",
            "onboarding_summary": "온보딩 플랜 생성에 실패하여 요약을 제공할 수 없습니다."
        }
    
    kanana = KananaWrapper()
    repo_id = f"{state.owner}/{state.repo}"
    
    try:
        summary = kanana.summarize_onboarding_plan(
            repo_id=repo_id,
            plan=state.onboarding_plan
        )
        
        return {
            "last_answer_kind": "plan",
            "onboarding_summary": summary,
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Onboarding summary generation failed: {error_msg}")
        return {
            "last_answer_kind": "plan",
            "onboarding_summary": f"요약 생성 중 오류가 발생했습니다: {error_msg[:100]}",
        }

