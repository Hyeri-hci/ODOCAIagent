"""에이전트 실행 헬퍼 함수들."""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, cast

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


def run_diagnosis_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """진단 에이전트 실행."""
    from backend.agents.diagnosis.service import run_diagnosis
    from backend.agents.diagnosis.models import DiagnosisInput, AnalysisDepth
    
    depth_map = {"FAST": "standard", "FULL": "deep", "AUTO": "standard"}
    analysis_depth_str = depth_map.get(mode, "standard")
    analysis_depth = cast(AnalysisDepth, analysis_depth_str)
    
    input_data = DiagnosisInput(
        owner=state.owner,
        repo=state.repo,
        ref="main",
        analysis_depth=analysis_depth,
        use_llm_summary=True
    )
    
    result = asyncio.run(run_diagnosis(input_data))
    
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return result.dict()


def run_security_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """보안 에이전트 실행."""
    from backend.common.config import (
        SECURITY_LLM_BASE_URL,
        SECURITY_LLM_API_KEY,
        SECURITY_LLM_MODEL,
        SECURITY_LLM_TEMPERATURE,
    )

    if not all([SECURITY_LLM_BASE_URL, SECURITY_LLM_API_KEY]):
        logger.error("Security LLM settings not configured")
        return {"error": "Security LLM settings not configured"}

    try:
        from backend.agents.security.agent.security_agent_v2 import SecurityAgentV2

        execution_mode = "fast" if mode == "FAST" else "intelligent"
        agent = SecurityAgentV2(
            llm_base_url=SECURITY_LLM_BASE_URL or "",
            llm_api_key=SECURITY_LLM_API_KEY or "",
            llm_model=SECURITY_LLM_MODEL,
            llm_temperature=SECURITY_LLM_TEMPERATURE,
            execution_mode=execution_mode,
        )

        user_request = f"{state.owner}/{state.repo} 프로젝트의 보안 취약점을 분석해줘"

        async def _run_async():
            return await agent.analyze(user_request=user_request)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            result = asyncio.run(_run_async())
        else:
            fut = asyncio.run_coroutine_threadsafe(_run_async(), loop)
            result = fut.result(timeout=300)

        logger.info(f"Security Agent result keys: {list(result.keys()) if result else 'None'}")
        
        if result:
            results = result.get("results", {})
            logger.info(f"Security Agent result.results keys: {list(results.keys()) if results else 'None'}")
            if results:
                logger.info(f"Security Agent result.results.security_score: {results.get('security_score')}")
                logger.info(f"Security Agent result.results.security_grade: {results.get('security_grade')}")
                vulns = results.get("vulnerabilities", {})
                logger.info(f"Security Agent result.results.vulnerabilities: total={vulns.get('total')}, critical={vulns.get('critical')}")
            else:
                logger.warning(f"Security Agent result has no 'results' key. Full result: {list(result.keys())}")
        
        if result and result.get("error"):
            logger.warning(f"Security Agent returned error: {result.get('error')}")
        
        return result

    except Exception as e:
        logger.error(f"Security Agent V2 failed: {e}")
        return {"error": str(e)}


def run_recommend_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """추천 에이전트 실행 (스텁)."""
    logger.info(f"Recommend agent ({mode}) - stub")
    return {"suggestions": [], "priority_list": []}


def run_onboarding_agent(state: SupervisorState, mode: str) -> Dict[str, Any]:
    """온보딩 에이전트 실행."""
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


def extract_diagnosis_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """진단 결과 요약 추출."""
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


def extract_security_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """보안 분석 결과 요약 추출."""
    results = result.get("results", {})
    vulnerabilities = results.get("vulnerabilities", {})
    
    if not results or not vulnerabilities:
        partial = result.get("partial_results", {})
        if partial:
            vulnerabilities = partial.get("vulnerabilities", [])
            if isinstance(vulnerabilities, list):
                vuln_list = vulnerabilities
                vulnerabilities = {
                    "total": len(vuln_list),
                    "critical": sum(1 for v in vuln_list if v.get("severity") == "CRITICAL"),
                    "high": sum(1 for v in vuln_list if v.get("severity") == "HIGH"),
                    "medium": sum(1 for v in vuln_list if v.get("severity") == "MEDIUM"),
                    "low": sum(1 for v in vuln_list if v.get("severity") == "LOW"),
                }
    
    if not results:
        final_result = result.get("final_result", {})
        results = final_result.get("results", {})
        if not vulnerabilities:
            vulnerabilities = results.get("vulnerabilities", {})
    
    vuln_count = (
        vulnerabilities.get("total") or
        result.get("vulnerability_count") or
        result.get("total_vulnerabilities") or
        0
    )
    security_score = (
        results.get("security_score") or 
        result.get("security_score") or
        result.get("partial_results", {}).get("security_score")
    )
    security_grade = (
        results.get("security_grade") or 
        result.get("security_grade") or
        result.get("partial_results", {}).get("security_grade")
    )
    risk_level = (
        results.get("risk_level") or 
        result.get("risk_level") or
        result.get("partial_results", {}).get("risk_level") or
        "unknown"
    )
    critical = vulnerabilities.get("critical") or result.get("critical_count", 0)
    high = vulnerabilities.get("high") or result.get("high_count", 0)
    medium = vulnerabilities.get("medium") or result.get("medium_count", 0)
    low = vulnerabilities.get("low") or result.get("low_count", 0)
    vuln_details = vulnerabilities.get("details", [])
    if not vuln_details:
        vuln_details = result.get("partial_results", {}).get("vulnerabilities", [])
    
    logger.info(f"Extracted security summary: score={security_score}, grade={security_grade}, vuln_count={vuln_count}, critical={critical}, high={high}")
    
    return {
        "risk_level": risk_level,
        "vuln_count": vuln_count,
        "security_score": security_score,
        "grade": security_grade,
        "critical_count": critical,
        "high_count": high,
        "medium_count": medium,
        "low_count": low,
        "vulnerability_details": vuln_details,
        "summary": result.get("report") or "보안 분석 완료",
        "flags": ["security_present"],
    }


def extract_recommend_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """추천 결과 요약 추출."""
    return {
        "suggestions": result.get("suggestions", []),
        "priority_list": result.get("priority_list", []),
        "summary": "추천 완료",
    }


def generate_security_report(
    state: SupervisorState,
    diagnosis_data: Dict[str, Any],
    security_data: Dict[str, Any]
) -> str:
    """보안 분석 결과 마크다운 보고서 생성."""
    lines = [f"# {state.owner}/{state.repo} 보안 분석 보고서\n"]
    
    if diagnosis_data:
        lines.append("## 저장소 진단 요약")
        lines.append(f"- **Health Score**: {diagnosis_data.get('health_score', 'N/A')}")
        lines.append(f"- **Onboarding Score**: {diagnosis_data.get('onboarding_score', 'N/A')}")
        if diagnosis_data.get("summary"):
            lines.append(f"\n{diagnosis_data['summary']}")
        lines.append("")
    
    lines.append("## 보안 분석 결과")
    
    risk_level = security_data.get("risk_level", "unknown")
    vuln_count = security_data.get("vuln_count", 0)
    security_score = security_data.get("security_score")
    grade = security_data.get("grade")
    
    if security_score is not None:
        lines.append(f"- **Security Score**: {security_score}/100")
    if grade:
        lines.append(f"- **Security Grade**: {grade}")
    lines.append(f"- **Risk Level**: {risk_level}")
    lines.append(f"- **총 발견된 취약점**: {vuln_count}개")
    
    critical = security_data.get("critical_count", 0)
    high = security_data.get("high_count", 0)
    medium = security_data.get("medium_count", 0)
    low = security_data.get("low_count", 0)
    
    if any([critical, high, medium, low]):
        lines.append("")
        lines.append("### 취약점 상세")
        lines.append(f"- **Critical**: {critical}개")
        lines.append(f"- **High**: {high}개")
        lines.append(f"- **Medium**: {medium}개")
        lines.append(f"- **Low**: {low}개")
    
    lines.append("")
    
    summary = security_data.get("summary", "")
    if summary:
        lines.append("## 분석 요약")
        lines.append(summary)
        lines.append("")
    
    lines.append("---")
    lines.append("*상세 분석 결과는 오른쪽 Report 영역에서 확인하세요.*")
    
    return "\n".join(lines)
