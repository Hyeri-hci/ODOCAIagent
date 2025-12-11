"""
품질 평가 리포트 생성기.

정성적/정량적 지표를 종합하여 전체 품질 점수와 상세 리포트를 생성합니다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class QualityGrade(Enum):
    """품질 등급."""
    EXCELLENT = "A"  # 90-100
    GOOD = "B"       # 80-89
    FAIR = "C"       # 70-79
    POOR = "D"       # 60-69
    CRITICAL = "F"   # 0-59


@dataclass
class MetricScore:
    """개별 지표 점수."""
    name: str
    category: str  # "quantitative" or "qualitative"
    value: float
    max_value: float = 100.0
    weight: float = 1.0
    description: str = ""
    
    @property
    def normalized_score(self) -> float:
        """0-100 정규화 점수."""
        return min(100, (self.value / self.max_value) * 100) if self.max_value > 0 else 0
    
    @property
    def weighted_score(self) -> float:
        """가중치 적용 점수."""
        return self.normalized_score * self.weight


@dataclass
class QualityReport:
    """
    종합 품질 평가 리포트.
    
    정성적/정량적 지표를 종합하여 전체 품질을 평가합니다.
    """
    agent_name: str
    repo: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 정량적 지표 (Quantitative)
    quantitative_metrics: List[MetricScore] = field(default_factory=list)
    
    # 정성적 지표 (Qualitative)  
    qualitative_metrics: List[MetricScore] = field(default_factory=list)
    
    # 가중치
    quantitative_weight: float = 0.4  # 40%
    qualitative_weight: float = 0.6   # 60%
    
    @property
    def quantitative_score(self) -> float:
        """정량적 지표 종합 점수."""
        if not self.quantitative_metrics:
            return 0
        total_weight = sum(m.weight for m in self.quantitative_metrics)
        if total_weight == 0:
            return 0
        return sum(m.weighted_score for m in self.quantitative_metrics) / total_weight
    
    @property
    def qualitative_score(self) -> float:
        """정성적 지표 종합 점수."""
        if not self.qualitative_metrics:
            return 0
        total_weight = sum(m.weight for m in self.qualitative_metrics)
        if total_weight == 0:
            return 0
        return sum(m.weighted_score for m in self.qualitative_metrics) / total_weight
    
    @property
    def total_score(self) -> float:
        """전체 종합 점수."""
        return (
            self.quantitative_score * self.quantitative_weight +
            self.qualitative_score * self.qualitative_weight
        )
    
    @property
    def grade(self) -> QualityGrade:
        """품질 등급."""
        score = self.total_score
        if score >= 90:
            return QualityGrade.EXCELLENT
        elif score >= 80:
            return QualityGrade.GOOD
        elif score >= 70:
            return QualityGrade.FAIR
        elif score >= 60:
            return QualityGrade.POOR
        else:
            return QualityGrade.CRITICAL
    
    def add_quantitative(self, name: str, value: float, max_value: float = 100.0, 
                         weight: float = 1.0, description: str = ""):
        """정량적 지표 추가."""
        self.quantitative_metrics.append(MetricScore(
            name=name,
            category="quantitative",
            value=value,
            max_value=max_value,
            weight=weight,
            description=description,
        ))
    
    def add_qualitative(self, name: str, value: float, max_value: float = 100.0,
                        weight: float = 1.0, description: str = ""):
        """정성적 지표 추가."""
        self.qualitative_metrics.append(MetricScore(
            name=name,
            category="qualitative",
            value=value,
            max_value=max_value,
            weight=weight,
            description=description,
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "agent": self.agent_name,
            "repo": self.repo,
            "timestamp": self.timestamp,
            "scores": {
                "quantitative": round(self.quantitative_score, 2),
                "qualitative": round(self.qualitative_score, 2),
                "total": round(self.total_score, 2),
                "grade": self.grade.value,
            },
            "weights": {
                "quantitative": self.quantitative_weight,
                "qualitative": self.qualitative_weight,
            },
            "metrics": {
                "quantitative": [
                    {
                        "name": m.name,
                        "value": m.value,
                        "max": m.max_value,
                        "normalized": round(m.normalized_score, 2),
                        "weight": m.weight,
                        "description": m.description,
                    }
                    for m in self.quantitative_metrics
                ],
                "qualitative": [
                    {
                        "name": m.name,
                        "value": m.value,
                        "max": m.max_value,
                        "normalized": round(m.normalized_score, 2),
                        "weight": m.weight,
                        "description": m.description,
                    }
                    for m in self.qualitative_metrics
                ],
            },
        }
    
    def generate_report(self) -> str:
        """발표용 마크다운 리포트 생성."""
        lines = [
            f"# {self.agent_name.upper()} 품질 평가 리포트",
            "",
            f"**레포지토리**: {self.repo}",
            f"**평가 시간**: {self.timestamp}",
            "",
            "---",
            "",
            "## 종합 점수",
            "",
            f"| 구분 | 점수 | 가중치 |",
            f"|------|------|--------|",
            f"| 정량적 지표 | {self.quantitative_score:.1f} | {self.quantitative_weight*100:.0f}% |",
            f"| 정성적 지표 | {self.qualitative_score:.1f} | {self.qualitative_weight*100:.0f}% |",
            f"| **종합** | **{self.total_score:.1f}** | **등급: {self.grade.value}** |",
            "",
            "---",
            "",
            "## 정량적 지표 (Quantitative)",
            "",
            "| 지표 | 값 | 정규화 점수 | 가중치 |",
            "|------|-----|------------|--------|",
        ]
        
        for m in self.quantitative_metrics:
            lines.append(
                f"| {m.name} | {m.value:.2f} / {m.max_value:.0f} | {m.normalized_score:.1f} | {m.weight} |"
            )
        
        lines.extend([
            "",
            "---",
            "",
            "## 정성적 지표 (Qualitative)",
            "",
            "| 지표 | 값 | 정규화 점수 | 가중치 |",
            "|------|-----|------------|--------|",
        ])
        
        for m in self.qualitative_metrics:
            lines.append(
                f"| {m.name} | {m.value:.2f} / {m.max_value:.0f} | {m.normalized_score:.1f} | {m.weight} |"
            )
        
        lines.extend([
            "",
            "---",
            "",
            "## 등급 기준",
            "",
            "| 등급 | 점수 범위 |",
            "|------|----------|",
            "| A (Excellent) | 90-100 |",
            "| B (Good) | 80-89 |",
            "| C (Fair) | 70-79 |",
            "| D (Poor) | 60-69 |",
            "| F (Critical) | 0-59 |",
        ])
        
        return "\n".join(lines)
    
    def save_report(self, filepath: str):
        """리포트 저장 (Markdown)."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.generate_report())
    
    def save_json(self, filepath: str):
        """JSON 저장."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def create_diagnosis_quality_report(
    repo: str,
    # 정량적 지표
    total_time_ms: float,
    node_count: int,
    # 정성적 지표
    tool_success_rate: float,
    health_score: float,
    cache_hit_rate: float = 0.0,
    error_count: int = 0,
) -> QualityReport:
    """
    Diagnosis Agent 품질 리포트 생성.
    
    Args:
        repo: 레포지토리 (owner/repo)
        total_time_ms: 전체 실행 시간
        node_count: 실행된 노드 수
        tool_success_rate: Tool 성공률 (0-100)
        health_score: 건강 점수 (0-100)
        cache_hit_rate: 캐시 히트율 (0-100)
        error_count: 에러 발생 수
        
    Returns:
        QualityReport: 품질 리포트
    """
    report = QualityReport(agent_name="diagnosis", repo=repo)
    
    # 정량적 지표
    # 시간: 10초 이하가 최고 (10000ms = 100점, 그 이상은 점수 감소)
    time_score = max(0, 100 - (total_time_ms / 1000))
    report.add_quantitative("실행 시간", time_score, 100, 0.3, f"{total_time_ms:.0f}ms")
    
    # 노드 수: 완전성 지표
    node_score = min(100, node_count * 20)  # 5개 노드 = 100점
    report.add_quantitative("노드 완성도", node_score, 100, 0.3, f"{node_count}개 노드 실행")
    
    # 캐시 효율
    report.add_quantitative("캐시 효율", cache_hit_rate, 100, 0.4, f"캐시 히트율 {cache_hit_rate:.1f}%")
    
    # 정성적 지표
    report.add_qualitative("Tool 성공률", tool_success_rate, 100, 0.4, "도구 호출 성공률")
    report.add_qualitative("결과 품질", health_score, 100, 0.4, "레포 건강 점수")
    
    # 에러: 0개가 최고
    error_score = max(0, 100 - (error_count * 20))
    report.add_qualitative("안정성", error_score, 100, 0.2, f"에러 {error_count}개")
    
    return report


def create_supervisor_quality_report(
    repo: str,
    # 정량적 지표
    total_time_ms: float,
    plan_completeness: float,
    # 정성적 지표
    intent_accuracy: float,
    subagent_success_rate: float,
    error_recovery_rate: float = 100.0,
) -> QualityReport:
    """
    Supervisor Agent 품질 리포트 생성.
    """
    report = QualityReport(agent_name="supervisor", repo=repo)
    
    # 정량적 지표
    time_score = max(0, 100 - (total_time_ms / 1000))
    report.add_quantitative("실행 시간", time_score, 100, 0.4, f"{total_time_ms:.0f}ms")
    report.add_quantitative("플랜 완성도", plan_completeness, 100, 0.6, "실행된 플랜 비율")
    
    # 정성적 지표
    report.add_qualitative("의도 분석", intent_accuracy, 100, 0.3, "의도 파악 정확도")
    report.add_qualitative("오케스트레이션", subagent_success_rate, 100, 0.4, "서브에이전트 성공률")
    report.add_qualitative("에러 복구", error_recovery_rate, 100, 0.3, "에러 복구 성공률")
    
    return report


# CLI용 데모
if __name__ == "__main__":
    # 예시 리포트 생성
    report = create_diagnosis_quality_report(
        repo="Hyeri-hci/ODOCAIagent",
        total_time_ms=6500,
        node_count=5,
        tool_success_rate=100,
        health_score=58,
        cache_hit_rate=25,
        error_count=0,
    )
    
    print(report.generate_report())
    print("\n=== JSON ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
