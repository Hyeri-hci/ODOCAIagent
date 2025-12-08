"""메타 에이전트 노드."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, cast

from backend.agents.supervisor.models import SupervisorState, TaskType
from backend.agents.shared.agent_mode import AgentMode, AgentModeLiteral
from backend.llm.factory import fetch_llm_client
from backend.llm.base import ChatRequest, ChatMessage
from backend.common.config import LLM_MODEL_NAME
from backend.agents.supervisor.nodes.routing_nodes import INTENT_TO_TASK_TYPE, INTENT_KEYWORDS

logger = logging.getLogger(__name__)


def _predict(prompt: str, timeout: int = 15) -> str:
    """LLM 예측 헬퍼. 타임아웃 시 빠르게 실패."""
    try:
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            model=LLM_MODEL_NAME,
            temperature=0.1,
        )
        response = client.chat(request, timeout=timeout)
        content = response.content.strip()
        
        # JSON 포맷팅 제거
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return content
    except Exception as e:
        logger.error(f"LLM predict failed: {e}")
        raise


def _map_intent_to_task_type(intent: str, fallback: TaskType) -> TaskType:
    """LLM이 반환한 intent를 TaskType으로 정규화."""
    mapped = INTENT_TO_TASK_TYPE.get(intent)
    if mapped in ("diagnose_repo", "build_onboarding_plan", "general_inquiry"):
        return cast(TaskType, mapped)
    return fallback


def _detect_onboard_intent(message: str) -> bool:
    """온보딩 의도 여부 감지."""
    if not message:
        return False
    msg_lower = message.lower()
    for keyword in INTENT_KEYWORDS.get("onboard", []):
        if keyword.lower() in msg_lower:
            return True
    return False


def _extract_github_repo(message: str) -> tuple[str, str] | None:
    """메시지에서 GitHub 저장소 정보 추출. (owner, repo) 반환."""
    import re
    if not message:
        return None
    
    # 패턴 1: 전체 URL (https://github.com/owner/repo)
    url_match = re.search(r'github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)', message, re.IGNORECASE)
    if url_match:
        owner, repo = url_match.group(1), url_match.group(2)
        # .git 제거
        if repo.endswith('.git'):
            repo = repo[:-4]
        return owner, repo
    
    # 패턴 2: owner/repo 형식 (문장 내에서 감지)
    # "Hyeri-hci/OSSDoctor에는" → Hyeri-hci/OSSDoctor
    short_match = re.search(r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)', message)
    if short_match:
        owner, repo = short_match.group(1), short_match.group(2)
        # 일반적인 단어 제외 (e.g., "a/b", "and/or")
        if len(owner) > 2 and len(repo) > 2:
            return owner, repo
    
    return None

def parse_supervisor_intent(state: SupervisorState) -> Dict[str, Any]:
    """사용자 메시지에서 상위 의도 추출."""
    user_msg = state.user_message or state.chat_message or ""
    
    # 0. 메시지에서 새 저장소 URL 추출 (기존 저장소와 다른 경우 업데이트)
    new_repo = _extract_github_repo(user_msg)
    new_owner, new_repo_name = None, None
    if new_repo:
        extracted_owner, extracted_repo = new_repo
        # 현재 저장소와 다른 경우에만 업데이트
        if (extracted_owner.lower() != (state.owner or "").lower() or 
            extracted_repo.lower() != (state.repo or "").lower()):
            new_owner, new_repo_name = extracted_owner, extracted_repo
            logger.info(f"New repository detected in message: {new_owner}/{new_repo_name}")
    
    # 1. 키워드 기반 onboard 의도 우선 감지 (LLM 호출 전)
    if _detect_onboard_intent(user_msg):
        logger.info(f"Onboard intent detected via keyword matching: '{user_msg[:50]}...'")
        result = {
            "global_intent": "onboard",
            "detected_intent": "onboard",
            "task_type": "build_onboarding_plan",
            "user_preferences": {"focus": ["beginner-friendly", "good first issue"], "ignore": []},
            "priority": "thoroughness",
            "step": state.step + 1,
        }
        # 새 저장소가 감지된 경우 업데이트
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
    
    # 2. LLM 기반 의도 분류 (키워드로 판별되지 않은 경우)
    prompt = f"""당신은 GitHub 저장소 분석 시스템의 의도 분석 전문가입니다.

사용자 메시지: "{user_msg}"
요청 유형 (시스템): "{state.task_type}" (diagnose_repo인 경우 진단 필수)
저장소: {state.owner}/{state.repo}

다음 JSON 형식으로 추출:
{{
  "task_type": "chat|diagnose|onboard|security|recommend|compare|full_audit",
  "user_preferences": {{"focus": [], "ignore": []}},
  "priority": "speed|thoroughness",
  "initial_mode_hint": "FAST|FULL|null"
}}

의도 분류 규칙 (우선순위 순서):
1. **onboard** (온보딩/기여 가이드): 다음 키워드 포함 시
   - "초보", "beginner", "기여", "contribute", "이슈", "issue", "PR", "참여"
   - "good first issue", "기여하기 좋은", "시작하기 좋은", "입문"
   - 예: "초보자가 기여하기 좋은 이슈 찾아줘" → onboard
   
2. **diagnose** (저장소 진단): 다음 키워드 포함 시
   - "진단", "분석", "건강", "health", "score", "점수"
   - 요청 유형이 "diagnose_repo"인 경우
   
3. **compare** (비교 분석): "비교", "compare", "vs" 포함 시

4. **security** (보안 분석): "보안", "security", "취약점" 포함 시

5. **recommend** (일반 추천): 위 카테고리에 해당하지 않는 추천 요청
   - 주의: "이슈 추천", "기여 추천"은 onboard로 분류

6. **chat** (일반 대화): 위 어느 것에도 해당하지 않음

추가 규칙:
- "간단히/빨리" → speed/FAST
- "자세히/깊게" → thoroughness/FULL
"""
    
    try:
        response = _predict(prompt)
        parsed = json.loads(response)
        
        logger.info(f"Parsed intent: {parsed}")
        global_intent = parsed.get("task_type", "chat")
        mapped_task_type = _map_intent_to_task_type(global_intent, state.task_type)
        
        result = {
            "global_intent": global_intent,
            "detected_intent": global_intent,
            "task_type": mapped_task_type,
            "user_preferences": parsed.get("user_preferences", {"focus": [], "ignore": []}),
            "priority": parsed.get("priority", "thoroughness"),
            "step": state.step + 1,
        }
        # 새 저장소가 감지된 경우 업데이트
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        fallback_intent = "chat"
        result = {
            "global_intent": fallback_intent,
            "detected_intent": fallback_intent,
            "task_type": state.task_type,
            "user_preferences": {"focus": [], "ignore": []},
            "priority": "thoroughness",
            "step": state.step + 1,
        }
        # 새 저장소가 감지된 경우 업데이트
        if new_owner and new_repo_name:
            result["owner"] = new_owner
            result["repo"] = new_repo_name
        return result


def create_supervisor_plan(state: SupervisorState) -> Dict[str, Any]:
    """에이전트 실행 계획 수립."""
    global_intent = state.global_intent or "chat"
    user_prefs = state.user_preferences or {"focus": [], "ignore": []}
    priority = state.priority or "thoroughness"
    
    default_mode = "FULL" if priority == "thoroughness" else "FAST"
    plan = []
    
    if global_intent == "chat":
        plan.append({
            "step": 1, "agent": "chat", "mode": "AUTO",
            "condition": "always", "description": "일반 채팅"
        })
    elif global_intent == "diagnose":
        plan.append({
            "step": 1, "agent": "diagnosis", "mode": default_mode,
            "condition": "always", "description": "저장소 진단"
        })
            # [Future] 조건부 보안 분석 예시 (현재 실행하지 않음)
            # if "security" not in user_prefs.get("ignore", []):
            #     plan.append({
            #         "step": 2, "agent": "security", "mode": "FAST",
            #         "condition": "if diagnosis.health_score < 50",
            #         "description": "조건부 보안 분석"
            #     })
        # [Future] 추천 예시 (현재 실행하지 않음)
        # plan.append({
        #     "step": 3, "agent": "recommend", "mode": "AUTO",
        #     "condition": "always", "description": "개선 추천"
        # })
    elif global_intent == "security":
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": "FAST", "condition": "always"},
        # [Future]
            # {"step": 2, "agent": "security", "mode": "FULL", "condition": "always"},
            # {"step": 3, "agent": "recommend", "mode": "AUTO", "condition": "always"},
        ])
    elif global_intent == "full_audit":
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": "FULL", "condition": "always"},
        # [Future]
            # {"step": 2, "agent": "security", "mode": "FULL", "condition": "always"},
            # {"step": 3, "agent": "recommend", "mode": "FULL", "condition": "always"},
        ])
    elif global_intent == "compare":
        plan.append({
            "step": 1, "agent": "diagnosis", "mode": "FAST",
            "condition": "always", "description": "비교 분석"
        })
    elif global_intent == "recommend":
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": default_mode, "condition": "always"},
        # [Future]
            # {"step": 2, "agent": "recommend", "mode": "FULL", "condition": "always"},
        ])
    elif global_intent == "onboard":
        plan.extend([
            {"step": 1, "agent": "diagnosis", "mode": "FAST", "condition": "always", "description": "저장소 구조 파악"},
            {"step": 2, "agent": "onboarding", "mode": "AUTO", "condition": "always", "description": "기여 가이드 및 추천"},
        ])

    
    
    logger.info(f"Created plan: {len(plan)} steps")
    return {
        "task_plan": plan,
        "plan_history": [plan],
        "step": state.step + 1,
    }


def execute_supervisor_plan(state: SupervisorState) -> Dict[str, Any]:
    """task_plan 순차 실행."""
    task_plan = state.task_plan or []
    task_results = dict(state.task_results) if state.task_results else {}
    
    for step_config in task_plan:
        agent_name = step_config.get("agent")
        mode = step_config.get("mode", "AUTO")
        condition = step_config.get("condition", "always")
        
        if not _evaluate_condition(condition, task_results):
            logger.info(f"Skip {agent_name}: {condition}")
            continue
        
        logger.info(f"Execute {agent_name} ({mode})")
        
        if agent_name == "chat":
            continue
        elif agent_name == "diagnosis":
            result = _run_diagnosis_agent(state, mode)
            task_results["diagnosis"] = _extract_diagnosis_summary(result)
        elif agent_name == "security":
            result = _run_security_agent(state, mode)
            task_results["security"] = _extract_security_summary(result)
        elif agent_name == "recommend":
            result = _run_recommend_agent(state, mode)
            task_results["recommend"] = _extract_recommend_summary(result)
        elif agent_name == "onboarding":
            result = _run_onboarding_agent(state, mode)
            task_results["onboarding"] = result
    
    logger.info(f"Plan executed: {list(task_results.keys())}")
    return {
        "task_results": task_results,
        "step": state.step + 1,
    }


def _evaluate_condition(condition: str, results: Dict[str, Any]) -> bool:
    """조건 평가."""
    if condition == "always":
        return True
    
    if condition.startswith("if "):
        cond_expr = condition[3:].strip()
        try:
            if "diagnosis.health_score" in cond_expr:
                health_score = results.get("diagnosis", {}).get("health_score")
                if health_score is None:
                    return False
                
                if "<" in cond_expr:
                    threshold = int(cond_expr.split("<")[1].strip())
                    return health_score < threshold
                elif ">" in cond_expr:
                    threshold = int(cond_expr.split(">")[1].strip())
                    return health_score > threshold
        except Exception as e:
            logger.warning(f"Condition eval failed: {e}")
            return False
    
    return False


def _run_diagnosis_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """Diagnosis 실행."""
    from backend.agents.diagnosis.service import run_diagnosis
    from backend.agents.diagnosis.models import DiagnosisInput
    
    depth_map = {"FAST": "quick", "FULL": "deep", "AUTO": "standard"}
    analysis_depth = depth_map.get(mode, "standard")
    
    input_data = DiagnosisInput(
        owner=state.owner,
        repo=state.repo,
        ref="main",
        analysis_depth=analysis_depth,
        use_llm_summary=True
    )
    
    result = run_diagnosis(input_data)
    
    # 이미 dict인 경우 그대로 반환, 아니면 to_dict() 또는 dict() 호출
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return result.dict()


def _run_security_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """Security 실행 (스텁)."""
    from backend.agents.security.service import analyze_repository
    
    try:
        return analyze_repository(owner=state.owner, repo=state.repo)
    except Exception as e:
        logger.error(f"Security failed: {e}")
        return {"error": str(e)}


def _run_recommend_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """Recommend 실행 (스텁)."""
    logger.info(f"Recommend agent ({mode}) - stub")
    return {"suggestions": [], "priority_list": []}


def _extract_diagnosis_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnosis 요약 추출."""
    health_score = result.get("health_score", 0)
    onboarding_score = result.get("onboarding_score", 0)
    
    flags = []
    if health_score < 30:
        flags.append("health_critical")
    elif health_score < 50:
        flags.append("health_low")
    if onboarding_score < 30:
        flags.append("onboarding_critical")
    
    return {
        "health_score": health_score,
        "onboarding_score": onboarding_score,
        "summary": result.get("summary_for_user", ""),
        "flags": flags,
    }


def _extract_security_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Security 요약 추출."""
    return {
        "risk_level": "low",
        "vuln_count": result.get("total_dependencies", 0),
        "summary": "보안 분석 완료",
        "flags": ["security_present"],
    }


def _extract_recommend_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Recommend 요약 추출."""
    return {
        "suggestions": result.get("suggestions", []),
        "priority_list": result.get("priority_list", []),
        "summary": "추천 완료",
    }


def reflect_supervisor(state: SupervisorState) -> Dict[str, Any]:
    """계획 반성 및 재조정."""
    skip_replan_intents = {
        "diagnose",
        "recommend",
        "onboard",
        "compare",
        "security",
        "full_audit",
    }
    if (
        not state.user_context.get("enable_replan")
        and state.global_intent in skip_replan_intents
    ):
        return {
            "reflection_summary": f"{state.global_intent} intent: skip replan",
            "next_node_override": "finalize_supervisor_answer",
            "step": state.step + 1,
        }

    if state.replan_count >= state.max_replan:
        logger.info("Max replan reached")
        return {
            "reflection_summary": "재계획 제한 도달",
            "next_node_override": "finalize_supervisor_answer",
            "step": state.step + 1,
        }
    
    prompt = f"""Supervisor 자기 점검.

실행 계획: {state.task_plan}
실행 결과: {state.task_results}
사용자 선호: {state.user_preferences}

질문:
1. focus가 충분히 커버되었는가?
2. ignore를 존중했는가?
3. 결과 기반으로 추가 실행 필요한가?

JSON 응답:
{{
  "should_replan": true/false,
  "plan_adjustments": [{{"action": "append", "step": {{...}}}}],
  "reflection_summary": "..."
}}
"""
    
    try:
        response = _predict(prompt)
        reflection = json.loads(response)
        
        should_replan = reflection.get("should_replan", False)
        plan_adjustments = reflection.get("plan_adjustments", [])
        reflection_summary = reflection.get("reflection_summary", "")
        
        if should_replan and plan_adjustments:
            new_plan = list(state.task_plan)
            for adj in plan_adjustments:
                if adj.get("action") == "append":
                    new_step = adj.get("step")
                    if new_step:
                        new_step["step"] = len(new_plan) + 1
                        new_plan.append(new_step)
            
            return {
                "task_plan": new_plan,
                "replan_count": state.replan_count + 1,
                "reflection_summary": reflection_summary,
                "next_node_override": "execute_supervisor_plan",
                "step": state.step + 1,
            }
        else:
            return {
                "reflection_summary": reflection_summary,
                "next_node_override": "finalize_supervisor_answer",
                "step": state.step + 1,
            }
    except Exception as e:
        logger.error(f"Reflection failed: {e}")
        return {
            "reflection_summary": f"자기 점검 실패: {e}",
            "next_node_override": "finalize_supervisor_answer",
            "step": state.step + 1,
        }


def finalize_supervisor_answer(state: SupervisorState) -> Dict[str, Any]:
    task_results = state.task_results or {}
    reflection = state.reflection_summary or ""
    
    # diagnosis 결과를 diagnosis_result로 변환 (http_router.py 호환)
    diagnosis_data = task_results.get("diagnosis", {})
    onboarding_data = task_results.get("onboarding", {})
    
    # onboard intent: 이미 LLM으로 플랜이 생성됨 → 직접 마크다운 생성
    if state.global_intent == "onboard" and onboarding_data:
        report_lines = []
        
        # 진단 결과
        if diagnosis_data:
            health = diagnosis_data.get("health_score", "N/A")
            onboard_score = diagnosis_data.get("onboarding_score", "N/A")
            report_lines.append(f"## 저장소 진단 결과")
            report_lines.append(f"- **Health Score**: {health}")
            report_lines.append(f"- **Onboarding Score**: {onboard_score}")
            if diagnosis_data.get("summary"):
                report_lines.append(f"\n{diagnosis_data['summary']}")
            report_lines.append("")
        
        # 온보딩 결과
        report_lines.append("## 온보딩 가이드")
        
        # 온보딩 플랜
        onboarding_plan = onboarding_data.get("onboarding_plan", [])
        if onboarding_plan:
            for week in onboarding_plan:
                week_num = week.get("week", "?")
                report_lines.append(f"\n### {week_num}주차")
                
                goals = week.get("goals", [])
                if goals:
                    report_lines.append("**목표:**")
                    for goal in goals:
                        report_lines.append(f"- {goal}")
                
                tasks = week.get("tasks", [])
                if tasks:
                    report_lines.append("**할 일:**")
                    for task in tasks:
                        report_lines.append(f"- {task}")
        
        # 추천 이슈
        candidate_issues = onboarding_data.get("candidate_issues", [])
        if candidate_issues:
            report_lines.append("\n### 추천 이슈 (Good First Issue)")
            for issue in candidate_issues[:5]:
                num = issue.get("number", "?")
                title = issue.get("title", "제목 없음")
                url = issue.get("url", "")
                labels = issue.get("labels", [])
                label_str = ", ".join(labels[:2]) if labels else ""
                if url:
                    report_lines.append(f"- [#{num}]({url}): {title} ({label_str})")
                else:
                    report_lines.append(f"- #{num}: {title} ({label_str})")
        
        # 온보딩 요약
        if onboarding_data.get("onboarding_summary"):
            report_lines.append(f"\n### 요약\n{onboarding_data['onboarding_summary']}")
        
        final_answer = "\n".join(report_lines) if report_lines else "온보딩 가이드가 생성되었습니다."
        
        logger.info("Final answer generated (onboard intent, no extra LLM call)")
        
        return {
            "chat_response": final_answer,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    
    # 그 외 intent: LLM으로 보고서 생성
    prompt = f"""GitHub 저장소 분석 보고서 작성.

분석 결과:
{json.dumps(task_results, indent=2, ensure_ascii=False)}

자기 점검:
{reflection}

사용자에게 다음 포함하여 보고:
1. 진단 요약
2. 보안 분석 (있는 경우)
3. 추천 사항
4. 플랜 설명

한국어 마크다운으로 작성.
"""
    
    try:
        final_answer = _predict(prompt)
        logger.info("Final answer generated via LLM")
        
        return {
            "chat_response": final_answer,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    except Exception as e:
        logger.error(f"Final answer failed: {e}")
        
        fallback = "분석 완료.\n\n"
        if diagnosis_data:
            fallback += f"**진단**\n- Health: {diagnosis_data.get('health_score', 'N/A')}\n\n"
        if "security" in task_results:
            fallback += f"**보안**\n- Risk: {task_results['security'].get('risk_level', 'N/A')}\n\n"
        
        return {
            "chat_response": fallback,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "error": str(e),
            "step": state.step + 1,
        }

def _run_onboarding_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """온보딩(Onboarding) 에이전트 실행 헬퍼."""
    from backend.agents.supervisor.nodes.onboarding_nodes import (
        fetch_issues_node, 
        plan_onboarding_node
    )
    
    logger.info(f"Running Onboarding Agent ({mode})")
    
    try:
        temp_state = state.model_copy()
        
        issues_update = fetch_issues_node(temp_state)

        if isinstance(issues_update, dict):
            for k, v in issues_update.items():
                if hasattr(temp_state, k):
                    setattr(temp_state, k, v)
        
        plan_update = plan_onboarding_node(temp_state)
        
        return {
            "onboarding_plan": plan_update.get("onboarding_plan"),
            "onboarding_summary": plan_update.get("onboarding_summary"),
            "candidate_issues": getattr(temp_state, "candidate_issues", []),
            "summary": "온보딩 플랜 생성 완료"
        }
    except Exception as e:
        logger.error(f"Onboarding execution failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": str(e)}
