from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.agents.supervisor.models import SupervisorState

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """성찰 결과."""
    is_consistent: bool
    issues: List[str]
    suggestions: List[str]
    confidence: float  # 0.0 ~ 1.0
    reasoning: str


REFLECTION_SYSTEM_PROMPT = """당신은 ODOC(Open-source Doctor) AI의 품질 검증 전문가입니다.

주어진 오픈소스 프로젝트 진단 결과를 검토하고 논리적 일관성을 평가하세요.

[ODOC 평가 기준]
- 건강 점수 = 문서 25% + 활동성 65% + 구조 10%
- 온보딩 점수 = 문서 55% + 활동성 35% + 구조 10%
- 80점 이상: Excellent, 60-79: Good, 40-59: Fair, 40 미만: Poor

[검토 항목]
1. 점수 일관성: 개별 점수와 종합 점수가 계산 공식과 일치하는가?
2. 레벨 일관성: 점수와 레벨(good/fair/warning/bad)이 맞는가?
3. 논리적 모순: 상충되는 결과가 있는가?
   - 예: 문서 점수 높은데 docs_issues가 많음
   - 예: 활동성 높은데 health_score가 낮음 (가중치 65%인데)
4. 이상치 탐지: 비정상적인 값이 있는가?

반드시 다음 JSON 형식으로만 응답하세요:
{
    "is_consistent": true/false,
    "issues": ["발견된 문제 1", "발견된 문제 2"],
    "suggestions": ["개선 제안 1", "개선 제안 2"],
    "confidence": 0.0-1.0,
    "reasoning": "판단 근거 설명"
}
"""


def build_reflection_prompt(diagnosis: Dict[str, Any]) -> str:
    """성찰 프롬프트 생성."""
    health_score = diagnosis.get("health_score", 0)
    onboarding_score = diagnosis.get("onboarding_score", 0)
    docs_score = diagnosis.get("documentation_quality", 0)
    activity_score = diagnosis.get("activity_maintainability", 0)
    structure_score = diagnosis.get("structure", {}).get("structure_score", 0)
    
    health_level = diagnosis.get("health_level", "unknown")
    onboarding_level = diagnosis.get("onboarding_level", "unknown")
    
    docs_issues = diagnosis.get("docs_issues", [])
    activity_issues = diagnosis.get("activity_issues", [])
    
    # 예상 점수 계산 (공식 기반)
    expected_health = docs_score * 0.25 + activity_score * 0.65 + structure_score * 0.10
    expected_onboarding = docs_score * 0.55 + activity_score * 0.35 + structure_score * 0.10
    
    prompt = f"""다음 진단 결과를 검토해주세요:

[진단 결과]
- 저장소: {diagnosis.get('repo_id', 'unknown')}
- 건강 점수: {health_score}점 ({health_level})
- 온보딩 점수: {onboarding_score}점 ({onboarding_level})
- 문서 품질: {docs_score}점
- 활동성: {activity_score}점
- 구조 점수: {structure_score}점

[이슈 목록]
- 문서 이슈: {', '.join(docs_issues) if docs_issues else '없음'}
- 활동성 이슈: {', '.join(activity_issues) if activity_issues else '없음'}

[참고: 예상 점수 (공식 기반)]
- 예상 건강 점수: {expected_health:.1f}점 (실제: {health_score}점, 차이: {abs(health_score - expected_health):.1f})
- 예상 온보딩 점수: {expected_onboarding:.1f}점 (실제: {onboarding_score}점, 차이: {abs(onboarding_score - expected_onboarding):.1f})

위 결과의 논리적 일관성을 평가하고 JSON 형식으로 응답해주세요."""
    
    return prompt


def parse_reflection_response(response: str) -> ReflectionResult:
    """LLM 응답 파싱."""
    try:
        # JSON 블록 추출
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()
        
        data = json.loads(response)
        
        return ReflectionResult(
            is_consistent=data.get("is_consistent", True),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            confidence=float(data.get("confidence", 0.8)),
            reasoning=data.get("reasoning", ""),
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse reflection response: {e}")
        # 파싱 실패 시 기본값 반환
        return ReflectionResult(
            is_consistent=True,
            issues=[],
            suggestions=[],
            confidence=0.5,
            reasoning="LLM 응답 파싱 실패",
        )


def rule_based_reflection(diagnosis: Dict[str, Any]) -> ReflectionResult:
    """규칙 기반 일관성 검사 (LLM fallback)."""
    issues = []
    suggestions = []
    
    health_score = diagnosis.get("health_score", 0)
    onboarding_score = diagnosis.get("onboarding_score", 0)
    docs_score = diagnosis.get("documentation_quality", 0)
    activity_score = diagnosis.get("activity_maintainability", 0)
    structure_score = diagnosis.get("structure", {}).get("structure_score", 0)
    
    health_level = diagnosis.get("health_level", "unknown")
    onboarding_level = diagnosis.get("onboarding_level", "unknown")
    
    # 1. 점수-레벨 일관성 검사
    expected_level = ""
    if health_score >= 80:
        expected_level = "good"
    elif health_score >= 60:
        expected_level = "fair"
    elif health_score >= 40:
        expected_level = "warning"
    else:
        expected_level = "bad"
    
    if expected_level and health_level != expected_level and health_level != "unknown":
        issues.append(f"건강 점수({health_score})와 레벨({health_level})이 일치하지 않습니다. 예상 레벨: {expected_level}")
    
    # 2. 공식 기반 점수 검증
    expected_health = docs_score * 0.25 + activity_score * 0.65 + structure_score * 0.10
    if abs(health_score - expected_health) > 5:
        issues.append(f"건강 점수({health_score})가 공식 계산값({expected_health:.1f})과 차이가 있습니다.")
    
    expected_onboarding = docs_score * 0.55 + activity_score * 0.35 + structure_score * 0.10
    if abs(onboarding_score - expected_onboarding) > 5:
        issues.append(f"온보딩 점수({onboarding_score})가 공식 계산값({expected_onboarding:.1f})과 차이가 있습니다.")
    
    # 3. 이슈와 점수 일관성
    docs_issues = diagnosis.get("docs_issues", [])
    if docs_score >= 80 and len(docs_issues) >= 3:
        issues.append(f"문서 점수({docs_score})가 높지만 문서 이슈가 {len(docs_issues)}개 있습니다.")
        suggestions.append("문서 이슈 목록을 점수에 더 반영하는 것을 고려하세요.")
    
    activity_issues = diagnosis.get("activity_issues", [])
    if activity_score >= 80 and len(activity_issues) >= 2:
        issues.append(f"활동성 점수({activity_score})가 높지만 활동성 이슈가 {len(activity_issues)}개 있습니다.")
    
    # 4. 점수 범위 검증
    for score_name, score in [
        ("health_score", health_score),
        ("onboarding_score", onboarding_score),
        ("docs_score", docs_score),
        ("activity_score", activity_score),
    ]:
        if score < 0 or score > 100:
            issues.append(f"{score_name}({score})가 유효 범위(0-100)를 벗어났습니다.")
    
    # 5. 활동성-건강 점수 관계
    if activity_score >= 70 and health_score < 40:
        issues.append(f"활동성({activity_score})이 높은데 건강 점수({health_score})가 매우 낮습니다. 가중치 65%를 고려하면 이상합니다.")
        suggestions.append("활동성 점수 산정 로직을 확인하세요.")
    
    is_consistent = len(issues) == 0
    confidence = 1.0 if is_consistent else max(0.3, 1.0 - len(issues) * 0.15)
    
    reasoning = "규칙 기반 검사 완료. "
    if is_consistent:
        reasoning += "모든 일관성 검사를 통과했습니다."
    else:
        reasoning += f"{len(issues)}개의 불일치가 발견되었습니다."
    
    return ReflectionResult(
        is_consistent=is_consistent,
        issues=issues,
        suggestions=suggestions,
        confidence=confidence,
        reasoning=reasoning,
    )


def self_reflection_node(state: SupervisorState) -> Dict[str, Any]:
    """
    LLM 기반 자기 성찰 노드.
    
    진단 결과의 논리적 일관성을 검증하고 모순이나 이상치를 탐지합니다.
    LLM 호출 실패 시 규칙 기반 검사로 fallback합니다.
    """
    diagnosis = state.diagnosis_result
    
    if not diagnosis:
        logger.warning("No diagnosis result to reflect on")
        return {
            "next_node_override": "__end__",
            "step": state.step + 1,
        }
    
    # LLM 기반 성찰 시도
    reflection: Optional[ReflectionResult] = None
    
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        from backend.common.config import LLM_MODEL_NAME
        
        client = fetch_llm_client()
        user_prompt = build_reflection_prompt(diagnosis)
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=REFLECTION_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            model=LLM_MODEL_NAME,
            temperature=0.1,  # 낮은 temperature로 일관된 분석
        )
        
        response = client.chat(request, timeout=30)
        reflection = parse_reflection_response(response.content)
        logger.info(f"LLM reflection completed: is_consistent={reflection.is_consistent}, issues={len(reflection.issues)}")
        
    except Exception as e:
        logger.warning(f"LLM reflection failed, using rule-based: {e}")
        reflection = None
    
    # LLM 실패 시 규칙 기반 검사
    if reflection is None or reflection.confidence < 0.5:
        rule_reflection = rule_based_reflection(diagnosis)
        if reflection is None:
            reflection = rule_reflection
        else:
            # LLM 결과와 규칙 기반 결과 병합
            reflection.issues.extend(rule_reflection.issues)
            reflection.suggestions.extend(rule_reflection.suggestions)
            if not reflection.is_consistent or not rule_reflection.is_consistent:
                reflection.is_consistent = False
    
    # 결과 처리
    warnings = list(state.warnings)
    quality_issues = list(state.quality_issues)
    
    result: Dict[str, Any] = {
        "step": state.step + 1,
    }
    
    if reflection.issues:
        quality_issues.extend(reflection.issues)
        result["quality_issues"] = quality_issues
    
    # 심각한 불일치가 있고 재실행 횟수가 남았으면 재분석
    if not reflection.is_consistent and len(reflection.issues) >= 2:
        if state.rerun_count < state.max_rerun:
            logger.info(f"Significant inconsistencies found, scheduling rerun")
            warnings.append("진단 결과에 불일치가 발견되어 재분석을 수행합니다.")
            result["rerun_count"] = state.rerun_count + 1
            result["next_node_override"] = "run_diagnosis_node"
            result["diagnosis_result"] = None  # 기존 결과 클리어
        else:
            logger.warning("Max rerun reached despite inconsistencies")
            warnings.extend(reflection.suggestions)
            result["next_node_override"] = "__end__"
    else:
        # 경미한 이슈는 경고로만 표시
        if reflection.suggestions:
            warnings.extend(reflection.suggestions[:2])  # 최대 2개 제안만
        result["next_node_override"] = "__end__"
    
    result["warnings"] = warnings
    
    # 성찰 결과를 diagnosis_result에 추가
    if diagnosis:
        diagnosis_updated = dict(diagnosis)
        diagnosis_updated["reflection"] = {
            "is_consistent": reflection.is_consistent,
            "issues": reflection.issues,
            "suggestions": reflection.suggestions,
            "confidence": reflection.confidence,
        }
        result["diagnosis_result"] = diagnosis_updated
    
    logger.info(f"Self-reflection complete: is_consistent={reflection.is_consistent}, "
                f"issues={len(reflection.issues)}, next={result.get('next_node_override')}")
    
    return result


def route_to_reflection(state: SupervisorState) -> str:
    """품질 검사 후 성찰 노드로 라우팅할지 결정."""
    # 분석 깊이가 deep이거나 특정 플래그가 있으면 성찰 수행
    if state.analysis_depth == "deep":
        return "self_reflection_node"
    if state.user_context.get("enable_reflection"):
        return "self_reflection_node"
    
    # 기본은 성찰 스킵
    return route_after_reflection(state)


def route_after_reflection(state: SupervisorState) -> str:
    """성찰 노드 후 라우팅."""
    # quality_check_node의 기존 라우팅 로직 재사용
    if state.next_node_override:
        return state.next_node_override
    
    if state.detected_intent == "onboard" and state.task_type == "build_onboarding_plan":
        return "fetch_issues_node"
    
    if state.detected_intent == "compare":
        return "compare_results_node"
    
    return "__end__"
