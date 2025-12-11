"""
Onboarding Agent Graph - 하이브리드 패턴 (LangGraph + 안전한 예외 처리)

향상된 에이전트 흐름:
parse_intent → analyze_diagnosis → assess_risks → fetch_issues → generate_plan → summarize
                                                                        ↓ (에러 시)
                                                                  error_handler

특징:
- 모든 노드에 @safe_node 데코레이터로 예외 처리
- 에러 발생 시 error_handler로 라우팅 (조건부 분기)
- Core scoring 활용 (health_score, onboarding_score, levels)
- 경험 수준별 리스크 평가
- 적응형 플랜 생성
"""
from typing import Dict, Any, Optional, Literal, List, Callable, TypeVar
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging
from functools import wraps

from backend.agents.onboarding.models import OnboardingState, OnboardingOutput
from backend.core.scoring_core import (
    compute_health_score,
    compute_onboarding_score,
    compute_health_level,
    compute_onboarding_level,
    HEALTH_GOOD_THRESHOLD,
    HEALTH_WARNING_THRESHOLD,
    ONBOARDING_EASY_THRESHOLD,
    ONBOARDING_NORMAL_THRESHOLD,
    WEAK_DOCS_THRESHOLD,
    INACTIVE_ACTIVITY_THRESHOLD,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


# === 예외 처리 데코레이터 ===

def safe_node(default_updates: Dict[str, Any] = None):
    """
    노드 함수에 안전한 예외 처리를 추가하는 데코레이터
    
    Args:
        default_updates: 예외 발생 시 반환할 기본 상태 업데이트
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: OnboardingState) -> Dict[str, Any]:
            node_name = func.__name__.replace("_node", "")
            try:
                return await func(state)
            except Exception as e:
                logger.error(f"[Onboarding Agent] {node_name} failed: {e}", exc_info=True)
                
                # 기본 업데이트 값 설정
                updates = default_updates.copy() if default_updates else {}
                updates["error"] = str(e)
                updates["execution_path"] = (state.get("execution_path") or "") + f" → {node_name}(ERROR)"
                
                return updates
        return wrapper
    return decorator

# === 에이전트 결정 로직 ===

def _assess_onboarding_risks(
    onboarding_score: int,
    health_score: int,
    onboarding_level: str,
    health_level: str,
    experience_level: str,
) -> List[Dict[str, Any]]:
    """경험 수준에 따른 온보딩 리스크 평가"""
    risks = []
    
    # 초보자에게만 해당하는 리스크
    if experience_level == "beginner":
        if onboarding_score < ONBOARDING_NORMAL_THRESHOLD:
            risks.append({
                "type": "onboarding_difficulty",
                "severity": "high",
                "message": f"온보딩 점수가 {onboarding_score}점으로 낮습니다. 초보자에게 도전적인 프로젝트입니다.",
                "recommendation": "good-first-issue 라벨이 있는 이슈부터 시작하세요."
            })
        if health_score < HEALTH_WARNING_THRESHOLD:
            risks.append({
                "type": "project_health",
                "severity": "medium",
                "message": f"프로젝트 건강도가 {health_score}점으로 낮습니다. 유지보수가 활발하지 않을 수 있습니다.",
                "recommendation": "최근 커밋/PR 활동을 확인하고 메인테이너 응답 여부를 살펴보세요."
            })
    
    # 중급자에게 해당하는 리스크
    elif experience_level == "intermediate":
        if onboarding_score < WEAK_DOCS_THRESHOLD:
            risks.append({
                "type": "documentation_gap",
                "severity": "medium",
                "message": "문서화가 부족합니다. 코드를 직접 읽어가며 파악해야 할 수 있습니다.",
                "recommendation": "코드 구조 분석부터 시작하고, 테스트 코드를 참고하세요."
            })
    
    # 고급자에게는 더 적은 제약
    elif experience_level == "advanced":
        if health_score < INACTIVE_ACTIVITY_THRESHOLD:
            risks.append({
                "type": "inactive_project",
                "severity": "low",
                "message": "프로젝트 활동이 적습니다. 기여해도 머지되지 않을 수 있습니다.",
                "recommendation": "이슈에서 메인테이너 응답 현황을 먼저 확인하세요."
            })
    
    # 모든 수준 공통 리스크
    if health_level == "bad" and onboarding_level == "hard":
        risks.append({
            "type": "overall_challenge",
            "severity": "high" if experience_level == "beginner" else "medium",
            "message": "전체적으로 기여하기 어려운 프로젝트입니다.",
            "recommendation": "다른 프로젝트를 먼저 경험해보는 것을 권장합니다."
        })
    
    return risks


def _determine_plan_intensity(
    onboarding_level: str,
    health_level: str,
    experience_level: str,
    risk_count: int,
) -> Dict[str, Any]:
    """플랜 강도 및 기간 결정"""
    # 기본 설정
    config = {
        "weeks": 4,
        "issues_per_week": 2,
        "include_advanced_topics": False,
        "focus_areas": [],
    }
    
    # 경험 수준에 따른 기본 조정
    if experience_level == "beginner":
        config["weeks"] = 6
        config["issues_per_week"] = 1
        config["focus_areas"] = ["documentation_reading", "environment_setup", "small_fixes"]
    elif experience_level == "intermediate":
        config["weeks"] = 4
        config["issues_per_week"] = 2
        config["focus_areas"] = ["code_understanding", "feature_contribution", "testing"]
    else:  # advanced
        config["weeks"] = 3
        config["issues_per_week"] = 3
        config["include_advanced_topics"] = True
        config["focus_areas"] = ["architecture", "core_features", "performance"]
    
    # 온보딩 난이도에 따른 조정
    if onboarding_level == "hard":
        config["weeks"] += 2
        config["focus_areas"].insert(0, "deep_documentation_study")
    elif onboarding_level == "easy":
        config["weeks"] = max(2, config["weeks"] - 1)
    
    # 프로젝트 건강도에 따른 조정
    if health_level == "bad":
        config["focus_areas"].append("maintainer_communication")
    
    # 리스크가 많으면 더 긴 플랜
    if risk_count >= 3:
        config["weeks"] += 1
    
    return config


# === 노드 함수들 (안전한 예외 처리 포함) ===

@safe_node(default_updates={"experience_level": "beginner", "user_context": {}})
async def parse_intent_node(state: OnboardingState) -> Dict[str, Any]:
    """온보딩 의도 파싱 - 경험 수준 및 컨텍스트 처리"""
    logger.info(f"[Onboarding Agent] Parsing intent for {state['owner']}/{state['repo']}")
    
    experience_level = state.get("experience_level", "beginner")
    user_context = state.get("user_context", {})
    
    # 사용자 메시지에서 추가 힌트 추출 (있는 경우)
    user_message = state.get("user_message") or ""
    
    # 경험 수준 키워드 감지
    if "고급" in user_message or "advanced" in user_message.lower():
        experience_level = "advanced"
    elif "중급" in user_message or "intermediate" in user_message.lower():
        experience_level = "intermediate"
    elif "초보" in user_message or "beginner" in user_message.lower():
        experience_level = "beginner"
    
    logger.info(f"[Onboarding Agent] Determined experience level: {experience_level}")
    
    return {
        "experience_level": experience_level,
        "user_context": user_context,
        "execution_path": "onboarding_graph:parse_intent"
    }


@safe_node(default_updates={
    "diagnosis_analysis": {
        "doc_score": 50, "activity_score": 50, "structure_score": 0,
        "health_score": 50, "onboarding_score": 50,
        "health_level": "warning", "onboarding_level": "normal"
    }
})
async def analyze_diagnosis_node(state: OnboardingState) -> Dict[str, Any]:
    """Core scoring을 활용한 진단 분석 - 에이전트 핵심 판단 노드"""
    logger.info(f"[Onboarding Agent] Analyzing diagnosis for {state['owner']}/{state['repo']}")
    
    diagnosis_summary = state.get("diagnosis_summary", "")
    
    # 진단 요약에서 점수 추출 시도
    doc_score = 50  # 기본값
    activity_score = 50  # 기본값
    structure_score = 0
    
    # diagnosis_summary가 dict인 경우 (진단 에이전트로부터 온 경우)
    if isinstance(diagnosis_summary, dict):
        doc_score = diagnosis_summary.get("documentation_quality", 50)
        activity_score = diagnosis_summary.get("activity_maintainability", 50)
        structure_score = diagnosis_summary.get("structure_score", 0)
    # diagnosis_summary가 문자열인 경우 파싱 시도
    elif isinstance(diagnosis_summary, str) and diagnosis_summary:
        import re
        # "문서화: 65점" 같은 패턴 파싱
        doc_match = re.search(r'(?:문서화|documentation)[:\s]*(\d+)', diagnosis_summary, re.IGNORECASE)
        if doc_match:
            doc_score = int(doc_match.group(1))
        activity_match = re.search(r'(?:활동성|activity)[:\s]*(\d+)', diagnosis_summary, re.IGNORECASE)
        if activity_match:
            activity_score = int(activity_match.group(1))
    
    # Core scoring 계산
    health_score = compute_health_score(doc_score, activity_score, structure_score)
    onboarding_score = compute_onboarding_score(doc_score, activity_score, structure_score)
    health_level = compute_health_level(health_score)
    onboarding_level = compute_onboarding_level(onboarding_score)
    
    logger.info(f"[Onboarding Agent] Computed scores - Health: {health_score} ({health_level}), Onboarding: {onboarding_score} ({onboarding_level})")
    
    # 분석 결과를 상태에 저장
    analysis = {
        "doc_score": doc_score,
        "activity_score": activity_score,
        "structure_score": structure_score,
        "health_score": health_score,
        "onboarding_score": onboarding_score,
        "health_level": health_level,
        "onboarding_level": onboarding_level,
    }
    
    return {
        "diagnosis_analysis": analysis,
        "execution_path": state.get("execution_path", "") + " → analyze_diagnosis"
    }


@safe_node(default_updates={
    "onboarding_risks": [],
    "plan_config": {"weeks": 4, "issues_per_week": 2, "focus_areas": []},
    "agent_decision": {}
})
async def assess_risks_node(state: OnboardingState) -> Dict[str, Any]:
    """경험 수준별 리스크 평가 및 플랜 설정 결정"""
    logger.info(f"[Onboarding Agent] Assessing risks for {state['owner']}/{state['repo']}")
    
    analysis = state.get("diagnosis_analysis", {})
    experience_level = state.get("experience_level", "beginner")
    
    # 리스크 평가
    risks = _assess_onboarding_risks(
        onboarding_score=analysis.get("onboarding_score", 50),
        health_score=analysis.get("health_score", 50),
        onboarding_level=analysis.get("onboarding_level", "normal"),
        health_level=analysis.get("health_level", "warning"),
        experience_level=experience_level,
    )
    
    # 플랜 강도 결정
    plan_config = _determine_plan_intensity(
        onboarding_level=analysis.get("onboarding_level", "normal"),
        health_level=analysis.get("health_level", "warning"),
        experience_level=experience_level,
        risk_count=len(risks),
    )
    
    logger.info(f"[Onboarding Agent] Identified {len(risks)} risks, plan config: {plan_config['weeks']} weeks")
    
    # 에이전트 결정 로그
    agent_decision = {
        "risks": risks,
        "plan_config": plan_config,
        "reasoning": f"Based on onboarding_level={analysis.get('onboarding_level')}, health_level={analysis.get('health_level')}, experience={experience_level}"
    }
    
    return {
        "onboarding_risks": risks,
        "plan_config": plan_config,
        "agent_decision": agent_decision,
        "execution_path": state.get("execution_path", "") + " → assess_risks"
    }


@safe_node(default_updates={"candidate_issues": []})
async def fetch_issues_node(state: OnboardingState) -> Dict[str, Any]:
    """GitHub에서 경험 수준에 맞는 이슈 수집 - 플랜 설정 반영"""
    logger.info(f"[Onboarding Agent] Fetching issues for {state['owner']}/{state['repo']}")
    
    from backend.agents.onboarding.nodes import fetch_issues
    
    experience_level = state.get("experience_level", "beginner")
    plan_config = state.get("plan_config", {})
    
    # 플랜 설정에 따라 수집할 이슈 수 조정
    max_issues = plan_config.get("weeks", 4) * plan_config.get("issues_per_week", 2)
    max_issues = min(max_issues, 20)  # 최대 20개로 제한
    
    issues = await fetch_issues(
        owner=state["owner"],
        repo=state["repo"],
        experience_level=experience_level,
        max_count=max_issues
    )
    
    logger.info(f"[Onboarding Agent] Fetched {len(issues)} candidate issues (max requested: {max_issues})")
    
    return {
        "candidate_issues": issues,
        "execution_path": state.get("execution_path", "") + " → fetch_issues"
    }


@safe_node(default_updates={"plan": []})
async def generate_plan_node(state: OnboardingState) -> Dict[str, Any]:
    """LLM을 사용하여 주차별 온보딩 플랜 생성 - 에이전트 분석 결과 반영"""
    logger.info(f"[Onboarding Agent] Generating onboarding plan for {state['owner']}/{state['repo']}")
    
    from backend.agents.onboarding.nodes import generate_plan
    
    repo_id = f"{state['owner']}/{state['repo']}"
    diagnosis_summary = state.get("diagnosis_summary", "")
    user_context = state.get("user_context", {})
    candidate_issues = state.get("candidate_issues", [])
    
    # 에이전트 분석 결과를 user_context에 추가
    diagnosis_analysis = state.get("diagnosis_analysis", {})
    onboarding_risks = state.get("onboarding_risks", [])
    plan_config = state.get("plan_config", {})
    
    # 향상된 컨텍스트 구성
    enhanced_context = {
        **user_context,
        "agent_analysis": {
            "health_score": diagnosis_analysis.get("health_score"),
            "onboarding_score": diagnosis_analysis.get("onboarding_score"),
            "health_level": diagnosis_analysis.get("health_level"),
            "onboarding_level": diagnosis_analysis.get("onboarding_level"),
        },
        "risks": [r["message"] for r in onboarding_risks],
        "recommendations": [r["recommendation"] for r in onboarding_risks if r.get("recommendation")],
        "plan_weeks": plan_config.get("weeks", 4),
        "focus_areas": plan_config.get("focus_areas", []),
        "include_advanced_topics": plan_config.get("include_advanced_topics", False),
    }
    
    plan_result = await generate_plan(
        repo_id=repo_id,
        diagnosis_summary=diagnosis_summary,
        user_context=enhanced_context,
        candidate_issues=candidate_issues,
    )
    
    if plan_result.get("error"):
        logger.error(f"[Onboarding Agent] Plan generation failed: {plan_result['error']}")
        return {
            "plan": [],
            "error": plan_result["error"],
            "execution_path": state.get("execution_path", "") + " → generate_plan(ERROR)"
        }
    
    plan = plan_result.get("plan", [])
    logger.info(f"[Onboarding Agent] Generated {len(plan)} week plan")
    
    return {
        "plan": plan,
        "error": None,
        "execution_path": state.get("execution_path", "") + " → generate_plan"
    }


@safe_node(default_updates={"similar_projects": []})
async def fetch_recommendations_node(state: OnboardingState) -> Dict[str, Any]:
    """유사 프로젝트 추천 가져오기 (Recommend 에이전트 호출)"""
    
    # 추천 포함 여부 확인 (기본값: True)
    if not state.get("include_recommendations", True):
        logger.info("[Onboarding Agent] Skipping recommendations (disabled)")
        return {
            "similar_projects": [],
            "execution_path": state.get("execution_path", "") + " → fetch_recommendations(skipped)"
        }
    
    logger.info(f"[Onboarding Agent] Fetching recommendations for {state['owner']}/{state['repo']}")
    
    try:
        from backend.agents.recommend.agent.graph import run_recommend
        
        result = await run_recommend(
            owner=state["owner"],
            repo=state["repo"],
            user_message=state.get("user_message")
        )
        
        # 상위 5개 추천만 가져옴
        recommendations = result.get("recommendations", [])[:5]
        
        logger.info(f"[Onboarding Agent] Fetched {len(recommendations)} recommendations")
        
        return {
            "similar_projects": recommendations,
            "execution_path": state.get("execution_path", "") + " → fetch_recommendations"
        }
    except Exception as e:
        logger.warning(f"[Onboarding Agent] Failed to fetch recommendations: {e}")
        return {
            "similar_projects": [],
            "execution_path": state.get("execution_path", "") + " → fetch_recommendations(error)"
        }


@safe_node(default_updates={"summary": "", "result": {}})
async def summarize_node(state: OnboardingState) -> Dict[str, Any]:
    """LLM을 사용하여 온보딩 플랜을 자연어로 요약 - 리스크 포함"""
    logger.info(f"[Onboarding Agent] Summarizing onboarding plan for {state['owner']}/{state['repo']}")
    
    from backend.agents.onboarding.nodes import summarize_plan
    
    repo_id = f"{state['owner']}/{state['repo']}"
    plan = state.get("plan", [])
    
    # 에러가 있으면 에러 결과 반환
    if state.get("error"):
        return {
            "result": OnboardingOutput(
                repo_id=repo_id,
                experience_level=state.get("experience_level", "beginner"),
                candidate_issues=state.get("candidate_issues", []),
                error=state.get("error")
            ).dict()
        }
    
    # 리스크 정보를 요약에 포함
    onboarding_risks = state.get("onboarding_risks", [])
    diagnosis_analysis = state.get("diagnosis_analysis", {})
    
    # 요약에 추가할 컨텍스트 구성
    summary_context = {
        "health_level": diagnosis_analysis.get("health_level", "unknown"),
        "onboarding_level": diagnosis_analysis.get("onboarding_level", "unknown"),
        "health_score": diagnosis_analysis.get("health_score"),
        "onboarding_score": diagnosis_analysis.get("onboarding_score"),
        "risks": onboarding_risks,
    }
    
    summary = await summarize_plan(
        repo_id=repo_id,
        plan=plan,
        summary_context=summary_context,
    )
    
    logger.info("[Onboarding Agent] Onboarding summary generated")
    
    # 최종 결과 조립 - 에이전트 분석 결과 포함
    result = OnboardingOutput(
        repo_id=repo_id,
        experience_level=state.get("experience_level", "beginner"),
        plan=plan,
        candidate_issues=state.get("candidate_issues", []),
        summary=summary,
    )
    
    # 결과 dict에 에이전트 분석 정보 추가
    result_dict = result.dict()
    result_dict["agent_analysis"] = {
        "diagnosis": diagnosis_analysis,
        "risks": onboarding_risks,
        "plan_config": state.get("plan_config", {}),
        "decision_reasoning": state.get("agent_decision", {}).get("reasoning", ""),
    }
    
    # 유사 프로젝트 추천 결과 추가
    similar_projects = state.get("similar_projects", [])
    if similar_projects:
        result_dict["similar_projects"] = similar_projects
        logger.info(f"[Onboarding Agent] Including {len(similar_projects)} similar projects in result")
    
    return {
        "summary": summary,
        "result": result_dict,
        "execution_path": state.get("execution_path", "") + " → summarize"
    }


# === 에러 핸들러 노드 ===

async def error_handler_node(state: OnboardingState) -> Dict[str, Any]:
    """에러 발생 시 안전한 결과 반환"""
    logger.warning(f"[Onboarding Agent] Error handler triggered: {state.get('error')}")
    
    repo_id = f"{state['owner']}/{state['repo']}"
    error_msg = state.get("error", "Unknown error occurred")
    
    # None 체크를 포함한 안전한 기본값 설정
    candidate_issues = state.get("candidate_issues") or []
    plan = state.get("plan") or []
    
    # 에러 결과 생성
    result = OnboardingOutput(
        repo_id=repo_id,
        experience_level=state.get("experience_level", "beginner"),
        candidate_issues=candidate_issues,
        plan=plan,
        summary=f"온보딩 플랜 생성 중 오류가 발생했습니다: {error_msg}",
        error=error_msg
    )
    
    return {
        "result": result.dict(),
        "execution_path": (state.get("execution_path") or "") + " → error_handler"
    }


# === 조건부 라우팅 (하이브리드 패턴 핵심) ===

def check_error_and_route(state: OnboardingState) -> Literal["continue", "error_handler"]:
    """에러 상태 체크 후 라우팅 - LangGraph 조건부 분기 활용"""
    if state.get("error"):
        return "error_handler"
    return "continue"


# === 그래프 빌드 (하이브리드 패턴) ===

def build_onboarding_graph():
    """
    Onboarding StateGraph 빌드 (하이브리드 패턴)
    
    향상된 흐름 (Recommend 통합):
    parse_intent → analyze_diagnosis → assess_risks → fetch_issues → generate_plan
                                                                         ↓
                                                                 fetch_recommendations
                                                                         ↓
                                                             [check_error_and_route]
                                                                    /          \\
                                                          summarize    error_handler
                                                               ↓              ↓
                                                             END            END
    
    특징:
    - 모든 노드에 @safe_node 데코레이터로 예외 처리
    - fetch_recommendations로 유사 프로젝트도 함께 가져옴
    - generate_plan 후 에러 체크로 조건부 분기 (LangGraph 장점 활용)
    - 각 노드가 독립적인 판단을 수행하는 에이전트 방식
    """
    
    graph = StateGraph(OnboardingState)
    
    # 노드 추가
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("analyze_diagnosis", analyze_diagnosis_node)
    graph.add_node("assess_risks", assess_risks_node)
    graph.add_node("fetch_issues", fetch_issues_node)
    graph.add_node("generate_plan", generate_plan_node)
    graph.add_node("fetch_recommendations", fetch_recommendations_node)  # 추천 노드 추가
    graph.add_node("summarize", summarize_node)
    graph.add_node("error_handler", error_handler_node)
    
    # 기본 순차 흐름
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "analyze_diagnosis")
    graph.add_edge("analyze_diagnosis", "assess_risks")
    graph.add_edge("assess_risks", "fetch_issues")
    graph.add_edge("fetch_issues", "generate_plan")
    graph.add_edge("generate_plan", "fetch_recommendations")  # 플랜 생성 후 추천 가져오기
    
    # fetch_recommendations 후 조건부 분기 (LangGraph 장점)
    graph.add_conditional_edges(
        "fetch_recommendations",
        check_error_and_route,
        {
            "continue": "summarize",
            "error_handler": "error_handler"
        }
    )
    
    # 종료 엣지
    graph.add_edge("summarize", END)
    graph.add_edge("error_handler", END)
    
    return graph.compile(checkpointer=MemorySaver())


# === 싱글톤 그래프 ===
_onboarding_graph = None


def get_onboarding_graph():
    """Onboarding Graph 싱글톤 인스턴스"""
    global _onboarding_graph
    if _onboarding_graph is None:
        _onboarding_graph = build_onboarding_graph()
        logger.info("Onboarding Graph initialized (hybrid pattern with error handling)")
    return _onboarding_graph


# === 편의 함수 ===

async def run_onboarding_graph(
    owner: str,
    repo: str,
    experience_level: str = "beginner",
    diagnosis_summary: str = "",
    user_context: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None,
    ref: str = "main",
    include_recommendations: bool = True
) -> Dict[str, Any]:
    """
    Onboarding Graph 실행
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        experience_level: 사용자 경험 수준 (beginner/intermediate/advanced)
        diagnosis_summary: 진단 요약 (있으면) - dict 또는 문자열
        user_context: 사용자 컨텍스트
        user_message: 사용자 메시지 (의도 파싱용)
        ref: 브랜치/태그
        include_recommendations: 유사 프로젝트 추천 포함 여부 (기본값: True)
    
    Returns:
        OnboardingOutput dict with agent_analysis and optional similar_projects
    """
    graph = get_onboarding_graph()
    
    initial_state: OnboardingState = {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "experience_level": experience_level,
        "diagnosis_summary": diagnosis_summary,
        "user_context": user_context or {},
        "user_message": user_message,
        "candidate_issues": None,
        "plan": None,
        "summary": None,
        # 에이전트 분석 필드 초기화
        "diagnosis_analysis": None,
        "onboarding_risks": None,
        "plan_config": None,
        "agent_decision": None,
        # 추천 관련 필드 초기화
        "similar_projects": None,
        "include_recommendations": include_recommendations,
        # 결과 필드
        "result": None,
        "error": None,
        "execution_path": None
    }
    
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state.get("result", {})
    except Exception as e:
        logger.error(f"[Onboarding Agent] Graph execution failed: {e}", exc_info=True)
        # 최상위 예외 처리 - 안전한 결과 반환
        return OnboardingOutput(
            repo_id=f"{owner}/{repo}",
            experience_level=experience_level,
            error=str(e),
            summary=f"온보딩 그래프 실행 중 오류가 발생했습니다: {e}"
        ).dict()


async def run_onboarding_stream(
    owner: str,
    repo: str,
    experience_level: str = "beginner",
    diagnosis_summary: str = "",
    user_context: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None,
    ref: str = "main",
    include_recommendations: bool = True
):
    """
    Onboarding Graph 스트리밍 실행 - 각 노드 완료 시 진행 상황 전달.
    
    Yields:
        Dict with keys: step, node, progress, message, data
    """
    graph = get_onboarding_graph()
    
    initial_state: OnboardingState = {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "experience_level": experience_level,
        "diagnosis_summary": diagnosis_summary,
        "user_context": user_context or {},
        "user_message": user_message,
        "candidate_issues": None,
        "plan": None,
        "summary": None,
        "diagnosis_analysis": None,
        "onboarding_risks": None,
        "plan_config": None,
        "agent_decision": None,
        "similar_projects": None,
        "include_recommendations": include_recommendations,
        "result": None,
        "error": None,
        "execution_path": None
    }
    
    node_progress = {
        "parse_intent": {"progress": 10, "message": "의도 분석 중"},
        "analyze_diagnosis": {"progress": 25, "message": "진단 결과 분석 중"},
        "assess_risks": {"progress": 40, "message": "위험 평가 중"},
        "fetch_issues": {"progress": 55, "message": "이슈 수집 중"},
        "generate_plan": {"progress": 70, "message": "플랜 생성 중"},
        "fetch_recommendations": {"progress": 85, "message": "추천 프로젝트 검색 중"},
        "summarize": {"progress": 95, "message": "요약 생성 중"},
        "error_handler": {"progress": 100, "message": "에러 처리 중"},
    }
    
    step = 0
    final_result = None
    
    try:
        async for event in graph.astream(initial_state):
            step += 1
            for node_name, node_output in event.items():
                info = node_progress.get(node_name, {"progress": 50, "message": node_name})
                
                yield {
                    "step": step,
                    "node": node_name,
                    "progress": info["progress"],
                    "message": info["message"],
                    "data": node_output
                }
                
                if node_output.get("result"):
                    final_result = node_output.get("result")
        
        yield {
            "step": step + 1,
            "node": "complete",
            "progress": 100,
            "message": "온보딩 플랜 완료",
            "data": {"result": final_result}
        }
    except Exception as e:
        logger.error(f"[Onboarding Stream] Error: {e}")
        yield {
            "step": step + 1,
            "node": "error",
            "progress": 100,
            "message": f"오류 발생: {e}",
            "data": {"error": str(e)}
        }

