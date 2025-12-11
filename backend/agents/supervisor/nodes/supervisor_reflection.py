"""Supervisor 반성 및 최종 응답 노드."""
from __future__ import annotations
import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from backend.agents.supervisor.models import SupervisorState
from backend.common.config import LLM_MODEL_NAME, LLM_API_BASE, LLM_API_KEY
from backend.agents.supervisor.prompts import REFLECTION_PROMPT, FINALIZE_REPORT_PROMPT
from backend.agents.supervisor.nodes.agent_runners import generate_security_report

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    """ChatOpenAI 인스턴스 반환."""
    return ChatOpenAI(
        model=LLM_MODEL_NAME,
        api_key=LLM_API_KEY,  # type: ignore
        base_url=LLM_API_BASE,
        temperature=0.1
    )


def _invoke_chain(prompt: ChatPromptTemplate, params: Dict[str, Any]) -> str:
    """LangChain 체인 동기 호출."""
    try:
        llm = _get_llm()
        chain = prompt | llm
        response = chain.invoke(params)
        content = str(response.content).strip() if response.content else ""
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return content
    except Exception as e:
        logger.error(f"Chain invoke failed: {e}")
        raise


async def _ainvoke_chain(prompt: ChatPromptTemplate, params: Dict[str, Any]) -> str:
    """LangChain 체인 비동기 호출."""
    try:
        llm = _get_llm()
        chain = prompt | llm
        response = await chain.ainvoke(params)
        content = str(response.content).strip() if response.content else ""
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return content
    except Exception as e:
        logger.error(f"Async chain invoke failed: {e}")
        raise


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
    
    response = None
    try:
        response = _invoke_chain(REFLECTION_PROMPT, {
            "task_plan": json.dumps(state.task_plan, ensure_ascii=False),
            "task_results": json.dumps(state.task_results, ensure_ascii=False),
            "user_preferences": json.dumps(state.user_preferences, ensure_ascii=False),
        })
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
        logger.error(f"Reflection failed: {e}, raw_response={response!r}")
        return {
            "reflection_summary": f"자기 점검 실패: {e}",
            "next_node_override": "finalize_supervisor_answer",
            "step": state.step + 1,
        }


async def reflect_supervisor_async(state: SupervisorState) -> Dict[str, Any]:
    """계획 반성 및 재조정 (비동기)."""
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
    
    response = None
    try:
        response = await _ainvoke_chain(REFLECTION_PROMPT, {
            "task_plan": json.dumps(state.task_plan, ensure_ascii=False),
            "task_results": json.dumps(state.task_results, ensure_ascii=False),
            "user_preferences": json.dumps(state.user_preferences, ensure_ascii=False),
        })
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
        logger.error(f"Reflection failed (async): {e}, raw_response={response!r}")
        return {
            "reflection_summary": f"자기 점검 실패: {e}",
            "next_node_override": "finalize_supervisor_answer",
            "step": state.step + 1,
        }


def finalize_supervisor_answer(state: SupervisorState) -> Dict[str, Any]:
    """최종 응답 생성."""
    task_results = state.task_results or {}
    reflection = state.reflection_summary or ""
    
    diagnosis_data = task_results.get("diagnosis", {})
    onboarding_data = task_results.get("onboarding", {})
    
    if state.global_intent == "onboard" and onboarding_data:
        report_lines = []
        
        if diagnosis_data:
            health = diagnosis_data.get("health_score", "N/A")
            onboard_score = diagnosis_data.get("onboarding_score", "N/A")
            report_lines.append(f"## 저장소 진단 결과")
            report_lines.append(f"- **Health Score**: {health}")
            report_lines.append(f"- **Onboarding Score**: {onboard_score}")
            if diagnosis_data.get("summary"):
                report_lines.append(f"\n{diagnosis_data['summary']}")
            report_lines.append("")
        
        report_lines.append("## 온보딩 가이드")
        
        onboarding_plan = onboarding_data.get("onboarding_plan", [])
        if onboarding_plan:
            weeks_count = len(onboarding_plan)
            final_answer = f"{state.owner}/{state.repo} 저장소에 대한 **{weeks_count}주 온보딩 가이드**가 생성되었습니다!\n\n오른쪽 Report 영역에서 상세 플랜을 확인하세요."
        else:
            final_answer = "온보딩 가이드 생성 중 문제가 발생했습니다."
        
        logger.info("Final answer generated (onboard intent, simple message)")
        
        return {
            "chat_response": final_answer,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    
    security_data = task_results.get("security", {})
    if state.global_intent == "security" and security_data:
        report = generate_security_report(state, diagnosis_data, security_data)
        logger.info("Final answer generated (security intent, direct markdown)")
        
        return {
            "chat_response": report,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    
    try:
        final_answer = _invoke_chain(FINALIZE_REPORT_PROMPT, {
            "task_results": json.dumps(task_results, indent=2, ensure_ascii=False),
            "reflection_summary": reflection,
        })
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
            fallback += (
                "**진단 요약**\n"
                f"- Health Score: {diagnosis_data.get('health_score', 'N/A')}\n"
                f"- Onboarding Score: {diagnosis_data.get('onboarding_score', 'N/A')}\n\n"
            )

        security_data = task_results.get("security")
        if security_data:
            fallback += "**보안 요약**\n"
            fallback += f"- Risk Level: {security_data.get('risk_level', 'N/A')}\n"
            fallback += f"- Vulnerabilities: {security_data.get('vuln_count', 'N/A')}개\n"
            score = security_data.get("security_score")
            grade = security_data.get("grade")
            if score is not None or grade is not None:
                fallback += f"- Security Score: {score} (Grade: {grade})\n"
            fallback += "\n"

        return {
            "chat_response": fallback,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "error": str(e),
            "step": state.step + 1,
        }


async def finalize_supervisor_answer_async(state: SupervisorState) -> Dict[str, Any]:
    """최종 응답 생성 (비동기)."""
    task_results = state.task_results or {}
    reflection = state.reflection_summary or ""
    
    diagnosis_data = task_results.get("diagnosis", {})
    onboarding_data = task_results.get("onboarding", {})
    
    if state.global_intent == "onboard" and onboarding_data:
        report_lines = []
        
        if diagnosis_data:
            health = diagnosis_data.get("health_score", "N/A")
            onboard_score = diagnosis_data.get("onboarding_score", "N/A")
            report_lines.append(f"## 저장소 진단 결과")
            report_lines.append(f"- **Health Score**: {health}")
            report_lines.append(f"- **Onboarding Score**: {onboard_score}")
            if diagnosis_data.get("summary"):
                report_lines.append(f"\n{diagnosis_data['summary']}")
            report_lines.append("")
        
        report_lines.append("## 온보딩 가이드")
        
        onboarding_plan = onboarding_data.get("onboarding_plan", [])
        if onboarding_plan:
            weeks_count = len(onboarding_plan)
            final_answer = f"{state.owner}/{state.repo} 저장소에 대한 **{weeks_count}주 온보딩 가이드**가 생성되었습니다!\n\n오른쪽 Report 영역에서 상세 플랜을 확인하세요."
        else:
            final_answer = "온보딩 가이드 생성 중 문제가 발생했습니다."
        
        logger.info("Final answer generated (async, onboard intent)")
        
        return {
            "chat_response": final_answer,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    
    security_data = task_results.get("security", {})
    if state.global_intent == "security" and security_data:
        report = generate_security_report(state, diagnosis_data, security_data)
        logger.info("Final answer generated (async, security intent)")
        
        return {
            "chat_response": report,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    
    try:
        final_answer = await _ainvoke_chain(FINALIZE_REPORT_PROMPT, {
            "task_results": json.dumps(task_results, indent=2, ensure_ascii=False),
            "reflection_summary": reflection,
        })
        logger.info("Final answer generated via LLM (async)")
        
        return {
            "chat_response": final_answer,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "step": state.step + 1,
        }
    except Exception as e:
        logger.error(f"Final answer failed (async): {e}")
        fallback = "분석 완료.\n\n"

        if diagnosis_data:
            fallback += (
                "**진단 요약**\n"
                f"- Health Score: {diagnosis_data.get('health_score', 'N/A')}\n"
                f"- Onboarding Score: {diagnosis_data.get('onboarding_score', 'N/A')}\n\n"
            )

        security_data = task_results.get("security")
        if security_data:
            fallback += "**보안 요약**\n"
            fallback += f"- Risk Level: {security_data.get('risk_level', 'N/A')}\n"
            fallback += f"- Vulnerabilities: {security_data.get('vuln_count', 'N/A')}개\n"
            score = security_data.get("security_score")
            grade = security_data.get("grade")
            if score is not None or grade is not None:
                fallback += f"- Security Score: {score} (Grade: {grade})\n"
            fallback += "\n"

        return {
            "chat_response": fallback,
            "last_answer_kind": "report",
            "diagnosis_result": diagnosis_data,
            "error": str(e),
            "step": state.step + 1,
        }
