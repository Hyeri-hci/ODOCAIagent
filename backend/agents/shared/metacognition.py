"""
메타인지 공통 모듈

에이전트 결과의 품질 체크, 근거 수집, 누락 탐지를 위한 공통 인프라.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """결과 품질 레벨"""
    HIGH = "high"       # 완전한 결과, 근거 충분
    MEDIUM = "medium"   # 부분적 결과, 일부 누락
    LOW = "low"         # 불완전한 결과, 검증 필요
    FAILED = "failed"   # 실패


@dataclass
class Source:
    """근거 출처 정보"""
    url: str                    # GitHub URL 등
    title: str                  # 표시용 제목
    type: str = "file"          # file, issue, pr, readme, etc.
    relevance: float = 1.0      # 관련성 점수 (0.0 ~ 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "type": self.type,
            "relevance": self.relevance,
        }
    
    def to_markdown(self) -> str:
        """마크다운 링크 형식으로 변환"""
        return f"[{self.title}]({self.url})"


@dataclass
class AgentResult:
    """
    에이전트 결과 + 메타인지 정보
    
    모든 에이전트가 이 형식으로 결과 반환.
    """
    # 기본 정보
    agent_name: str
    success: bool
    
    # 실제 결과 데이터
    data: Dict[str, Any] = field(default_factory=dict)
    
    # 메타인지 정보
    quality_level: QualityLevel = QualityLevel.MEDIUM
    confidence: float = 0.5         # 결과 신뢰도 (0.0 ~ 1.0)
    sources: List[Source] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)           # 누락된 정보
    warnings: List[str] = field(default_factory=list)       # 경고 사항
    
    # 추가 검색 필요 여부
    needs_followup: bool = False
    followup_actions: List[str] = field(default_factory=list)
    
    # 디버깅용 reasoning
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "success": self.success,
            "data": self.data,
            "quality_level": self.quality_level.value,
            "confidence": self.confidence,
            "sources": [s.to_dict() for s in self.sources],
            "gaps": self.gaps,
            "warnings": self.warnings,
            "needs_followup": self.needs_followup,
            "followup_actions": self.followup_actions,
            "reasoning": self.reasoning,
        }
    
    def log_metacognition(self) -> None:
        """메타인지 정보를 로그에 출력 (디버깅용)"""
        logger.info(f"[METACOGNITION] Agent: {self.agent_name}")
        logger.info(f"  - Success: {self.success}")
        logger.info(f"  - Quality: {self.quality_level.value} (confidence: {self.confidence:.2f})")
        
        if self.sources:
            logger.info(f"  - Sources ({len(self.sources)}):")
            for src in self.sources[:3]:  # 최대 3개만 출력
                logger.info(f"    * [{src.type}] {src.title}")
        
        if self.gaps:
            logger.info(f"  - Gaps: {', '.join(self.gaps)}")
        
        if self.warnings:
            logger.info(f"  - Warnings: {', '.join(self.warnings)}")
        
        if self.needs_followup:
            logger.info(f"  - Needs followup: {', '.join(self.followup_actions)}")
        
        if self.reasoning:
            logger.info(f"  - Reasoning: {self.reasoning[:200]}...")


@dataclass
class AggregatedResult:
    """
    Supervisor가 여러 에이전트 결과를 통합한 결과
    """
    # 통합된 결과들
    results: List[AgentResult] = field(default_factory=list)
    
    # 전체 품질 평가
    overall_quality: QualityLevel = QualityLevel.MEDIUM
    overall_confidence: float = 0.5
    
    # 충돌/누락 탐지
    conflicts: List[str] = field(default_factory=list)      # 상반된 결과
    missing_info: List[str] = field(default_factory=list)   # 요청했지만 결과 없음
    
    # 추가 작업 필요 여부
    needs_more_search: bool = False
    suggested_actions: List[str] = field(default_factory=list)
    
    # 최종 응답 생성용
    summary: str = ""
    all_sources: List[Source] = field(default_factory=list)
    
    def log_aggregation(self) -> None:
        """통합 결과를 로그에 출력 (디버깅용)"""
        logger.info("[METACOGNITION] === Aggregated Result ===")
        logger.info(f"  - Total agents: {len(self.results)}")
        logger.info(f"  - Overall quality: {self.overall_quality.value} (confidence: {self.overall_confidence:.2f})")
        
        if self.conflicts:
            logger.warning(f"  - CONFLICTS detected: {', '.join(self.conflicts)}")
        
        if self.missing_info:
            logger.warning(f"  - MISSING info: {', '.join(self.missing_info)}")
        
        if self.needs_more_search:
            logger.info(f"  - Needs more search: {', '.join(self.suggested_actions)}")
        
        logger.info(f"  - Total sources: {len(self.all_sources)}")


class QualityChecker:
    """
    결과 품질 체크 유틸리티
    
    각 에이전트에서 self.quality_checker.evaluate(result)로 사용.
    """
    
    @staticmethod
    def evaluate_diagnosis(data: Dict[str, Any]) -> tuple[QualityLevel, float, List[str]]:
        """진단 결과 품질 평가"""
        gaps = []
        score = 0.0
        
        # 필수 필드 체크
        if data.get("health_score") is not None:
            score += 0.3
        else:
            gaps.append("health_score 누락")
        
        if data.get("documentation_quality") is not None:
            score += 0.2
        else:
            gaps.append("documentation_quality 누락")
        
        if data.get("activity_maintainability") is not None:
            score += 0.2
        else:
            gaps.append("activity_maintainability 누락")
        
        # 상세 분석 체크
        if data.get("docs_issues") or data.get("activity_issues"):
            score += 0.2
        else:
            gaps.append("상세 이슈 분석 부족")
        
        # 요약 체크
        if data.get("summary_for_user"):
            score += 0.1
        else:
            gaps.append("사용자 요약 없음")
        
        # 레벨 결정
        if score >= 0.8:
            level = QualityLevel.HIGH
        elif score >= 0.5:
            level = QualityLevel.MEDIUM
        elif score > 0:
            level = QualityLevel.LOW
        else:
            level = QualityLevel.FAILED
        
        return level, score, gaps
    
    @staticmethod
    def evaluate_contributor(data: Dict[str, Any]) -> tuple[QualityLevel, float, List[str]]:
        """기여자 가이드 결과 품질 평가"""
        gaps = []
        score = 0.0
        
        features = data.get("features", {})
        
        if features.get("first_contribution_guide"):
            score += 0.3
        else:
            gaps.append("첫 기여 가이드 없음")
        
        if features.get("contribution_checklist"):
            score += 0.2
        else:
            gaps.append("기여 체크리스트 없음")
        
        if features.get("structure_visualization"):
            score += 0.3
        
        if features.get("community_analysis"):
            score += 0.2
        
        # 레벨 결정
        if score >= 0.7:
            level = QualityLevel.HIGH
        elif score >= 0.4:
            level = QualityLevel.MEDIUM
        elif score > 0:
            level = QualityLevel.LOW
        else:
            level = QualityLevel.FAILED
        
        return level, score, gaps
    
    @staticmethod
    def evaluate_onboarding(data: Dict[str, Any]) -> tuple[QualityLevel, float, List[str]]:
        """온보딩 결과 품질 평가"""
        gaps = []
        score = 0.0
        
        if data.get("plan") and len(data.get("plan", [])) > 0:
            score += 0.5
            # 플랜 주차 수에 따라 추가 점수
            weeks = len(data.get("plan", []))
            if weeks >= 4:
                score += 0.2
            elif weeks >= 2:
                score += 0.1
        else:
            gaps.append("온보딩 플랜 없음")
        
        if data.get("summary"):
            score += 0.2
        else:
            gaps.append("플랜 요약 없음")
        
        if data.get("agent_analysis"):
            score += 0.1
        
        # 레벨 결정
        if score >= 0.7:
            level = QualityLevel.HIGH
        elif score >= 0.4:
            level = QualityLevel.MEDIUM
        elif score > 0:
            level = QualityLevel.LOW
        else:
            level = QualityLevel.FAILED
        
        return level, score, gaps


def create_github_source(owner: str, repo: str, path: str, title: str = None) -> Source:
    """GitHub 파일 URL로 Source 생성"""
    url = f"https://github.com/{owner}/{repo}/blob/main/{path}"
    return Source(
        url=url,
        title=title or path,
        type="file",
    )


def create_github_issue_source(owner: str, repo: str, issue_number: int, title: str) -> Source:
    """GitHub 이슈 URL로 Source 생성"""
    url = f"https://github.com/{owner}/{repo}/issues/{issue_number}"
    return Source(
        url=url,
        title=f"#{issue_number}: {title}",
        type="issue",
    )


def create_github_repo_source(owner: str, repo: str) -> Source:
    """GitHub 저장소 URL로 Source 생성"""
    return Source(
        url=f"https://github.com/{owner}/{repo}",
        title=f"{owner}/{repo}",
        type="repository",
    )
