"""
Supervisor 메타인지 레이어

결과 통합, 충돌 감지, 추가 검색 필요 여부 판단.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.shared.metacognition import (
    AgentResult,
    AggregatedResult,
    QualityLevel,
    Source,
)
from backend.common.config import LLM_MODEL_NAME

logger = logging.getLogger(__name__)


class SupervisorMetacognition:
    """
    Supervisor 메타인지 레이어
    
    여러 에이전트 결과를 통합하고, 충돌/누락 탐지, 추가 검색 필요 여부 판단.
    """
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
    
    async def aggregate_results(
        self,
        results: List[AgentResult],
        user_request: str,
    ) -> AggregatedResult:
        """
        여러 에이전트 결과를 통합
        
        Args:
            results: 각 에이전트의 결과 목록
            user_request: 원래 사용자 요청 (누락 탐지용)
        """
        logger.info(f"[METACOGNITION] Aggregating {len(results)} agent results")
        
        aggregated = AggregatedResult(results=results)
        
        # 1. 전체 품질 평가
        aggregated.overall_quality, aggregated.overall_confidence = self._evaluate_overall_quality(results)
        
        # 2. 충돌 탐지
        aggregated.conflicts = self._detect_conflicts(results)
        
        # 3. 누락 탐지
        aggregated.missing_info = self._detect_missing_info(results, user_request)
        
        # 4. 추가 검색 필요 여부
        aggregated.needs_more_search, aggregated.suggested_actions = self._determine_followup(results)
        
        # 5. 모든 소스 통합
        aggregated.all_sources = self._collect_all_sources(results)
        
        # 6. 요약 생성
        aggregated.summary = self._generate_summary(results)
        
        # 디버깅 로그
        aggregated.log_aggregation()
        
        return aggregated
    
    def _evaluate_overall_quality(self, results: List[AgentResult]) -> tuple[QualityLevel, float]:
        """전체 품질 평가"""
        if not results:
            return QualityLevel.FAILED, 0.0
        
        # 성공한 결과만 고려
        successful = [r for r in results if r.success]
        if not successful:
            return QualityLevel.FAILED, 0.0
        
        # 평균 신뢰도
        avg_confidence = sum(r.confidence for r in successful) / len(successful)
        
        # 최저 품질 기준
        quality_values = {
            QualityLevel.HIGH: 3,
            QualityLevel.MEDIUM: 2,
            QualityLevel.LOW: 1,
            QualityLevel.FAILED: 0,
        }
        
        min_quality_value = min(quality_values[r.quality_level] for r in successful)
        
        if min_quality_value >= 3:
            overall = QualityLevel.HIGH
        elif min_quality_value >= 2:
            overall = QualityLevel.MEDIUM
        elif min_quality_value >= 1:
            overall = QualityLevel.LOW
        else:
            overall = QualityLevel.FAILED
        
        logger.info(f"[METACOGNITION] Overall quality: {overall.value}, confidence: {avg_confidence:.2f}")
        
        return overall, avg_confidence
    
    def _detect_conflicts(self, results: List[AgentResult]) -> List[str]:
        """결과 간 충돌 탐지"""
        conflicts = []
        
        # 예: 진단 점수와 보안 점수가 크게 다른 경우
        diagnosis_result = next((r for r in results if r.agent_name == "diagnosis"), None)
        security_result = next((r for r in results if r.agent_name == "security"), None)
        
        if diagnosis_result and security_result:
            health_score = diagnosis_result.data.get("health_score", 0)
            security_score = security_result.data.get("security_score", 0)
            
            if health_score and security_score:
                # 30점 이상 차이나면 충돌로 판단
                if abs(health_score - security_score) > 30:
                    conflicts.append(
                        f"건강도 점수({health_score})와 보안 점수({security_score}) 차이가 큼"
                    )
                    logger.warning(f"[METACOGNITION] Conflict detected: health={health_score}, security={security_score}")
        
        return conflicts
    
    def _detect_missing_info(self, results: List[AgentResult], user_request: str) -> List[str]:
        """사용자 요청 대비 누락된 정보 탐지"""
        missing = []
        
        # 요청 키워드 분석
        request_lower = user_request.lower()
        
        # 진단 요청했지만 결과 없음
        if any(kw in request_lower for kw in ["분석", "진단", "건강도", "점수"]):
            diagnosis_result = next((r for r in results if r.agent_name == "diagnosis"), None)
            if not diagnosis_result or not diagnosis_result.success:
                missing.append("진단 결과 누락")
        
        # 보안 요청했지만 결과 없음
        if any(kw in request_lower for kw in ["보안", "취약점", "security"]):
            security_result = next((r for r in results if r.agent_name == "security"), None)
            if not security_result or not security_result.success:
                missing.append("보안 분석 결과 누락")
        
        # 온보딩 요청했지만 결과 없음
        if any(kw in request_lower for kw in ["온보딩", "가이드", "시작"]):
            onboarding_result = next((r for r in results if r.agent_name == "onboarding"), None)
            if not onboarding_result or not onboarding_result.success:
                missing.append("온보딩 플랜 누락")
        
        # 코드 구조 요청했지만 결과 없음
        if any(kw in request_lower for kw in ["구조", "폴더", "트리"]):
            contributor_result = next((r for r in results if r.agent_name == "contributor"), None)
            if contributor_result:
                features = contributor_result.data.get("features", {})
                if not features.get("structure_visualization"):
                    missing.append("코드 구조 시각화 누락")
        
        if missing:
            logger.warning(f"[METACOGNITION] Missing info: {missing}")
        
        return missing
    
    def _determine_followup(self, results: List[AgentResult]) -> tuple[bool, List[str]]:
        """추가 검색 필요 여부 판단"""
        actions = []
        
        for result in results:
            if result.needs_followup:
                actions.extend(result.followup_actions)
            
            # 품질이 낮으면 추가 조사 제안
            if result.quality_level in [QualityLevel.LOW, QualityLevel.FAILED]:
                actions.append(f"{result.agent_name} 결과 보완 필요")
            
            # 갭이 있으면 추가 조사 제안
            if result.gaps:
                for gap in result.gaps[:2]:  # 최대 2개
                    actions.append(f"{gap} 추가 조사")
        
        needs_followup = len(actions) > 0
        
        if needs_followup:
            logger.info(f"[METACOGNITION] Followup needed: {actions}")
        
        return needs_followup, actions
    
    def _collect_all_sources(self, results: List[AgentResult]) -> List[Source]:
        """모든 소스 통합 (중복 제거)"""
        all_sources = []
        seen_urls = set()
        
        for result in results:
            for source in result.sources:
                if source.url not in seen_urls:
                    all_sources.append(source)
                    seen_urls.add(source.url)
        
        # 관련성 순으로 정렬
        all_sources.sort(key=lambda s: s.relevance, reverse=True)
        
        logger.info(f"[METACOGNITION] Collected {len(all_sources)} unique sources")
        
        return all_sources
    
    def _generate_summary(self, results: List[AgentResult]) -> str:
        """결과 요약 생성"""
        summaries = []
        
        for result in results:
            if not result.success:
                summaries.append(f"- {result.agent_name}: 실패")
                continue
            
            # 에이전트별 요약
            if result.agent_name == "diagnosis":
                score = result.data.get("health_score", "N/A")
                summaries.append(f"- 진단: 건강도 {score}점")
            elif result.agent_name == "security":
                score = result.data.get("security_score", "N/A")
                summaries.append(f"- 보안: {score}점")
            elif result.agent_name == "onboarding":
                plan_count = len(result.data.get("plan", []))
                summaries.append(f"- 온보딩: {plan_count}주차 플랜")
            elif result.agent_name == "contributor":
                features = list(result.data.get("features", {}).keys())
                summaries.append(f"- 기여자: {', '.join(features)}")
        
        return "\n".join(summaries) if summaries else "결과 없음"


def format_response_with_sources(
    answer: str,
    sources: List[Source],
    max_sources: int = 5,
) -> str:
    """
    응답에 근거 링크 추가
    
    Args:
        answer: 원본 응답
        sources: 근거 소스 목록
        max_sources: 최대 표시할 소스 수
    """
    if not sources:
        return answer
    
    # 소스 링크 섹션 추가
    source_section = "\n\n**참고 자료:**\n"
    for i, source in enumerate(sources[:max_sources], 1):
        source_section += f"- {source.to_markdown()}\n"
    
    if len(sources) > max_sources:
        source_section += f"- ... 외 {len(sources) - max_sources}개\n"
    
    return answer + source_section
