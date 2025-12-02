"""Intent-specific thresholds, calibration, and LLM parameters (Step 8 & 9)."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Intent 비용 가중치 (API 호출/토큰 비용 기준)
class IntentCost(str, Enum):
    """Relative cost of each intent type."""
    LIGHTWEIGHT = "lightweight"  # smalltalk, help: 템플릿 응답, LLM 호출 없음
    LOW = "low"                  # overview, general_qa: 단순 LLM 호출
    MEDIUM = "medium"            # followup: 이전 결과 참조 + LLM
    HIGH = "high"                # analyze, compare: GitHub API + 복잡한 처리 + LLM


# 의도별 임계 테이블 (비용에 맞춘 전환 기준)
@dataclass
class IntentThreshold:
    """Threshold configuration for an intent."""
    base_threshold: float           # 기본 임계값
    disambiguation_threshold: float # 이 미만이면 disambiguation
    cost: IntentCost               # 비용 수준
    requires_repo: bool = False    # 저장소 필요 여부
    max_tokens: int = 512          # 출력 토큰 상한
    
    def should_disambiguate(self, confidence: float) -> bool:
        """confidence가 disambiguation_threshold 미만이면 True."""
        return confidence < self.disambiguation_threshold
    
    def should_proceed(self, confidence: float) -> bool:
        """confidence가 base_threshold 이상이면 True."""
        return confidence >= self.base_threshold


# 의도별 임계 테이블 정의
INTENT_THRESHOLDS: Dict[str, IntentThreshold] = {
    # 경량 경로: 낮은 임계, LLM 호출 없음
    "smalltalk": IntentThreshold(
        base_threshold=0.3,
        disambiguation_threshold=0.15,
        cost=IntentCost.LIGHTWEIGHT,
        max_tokens=200,
    ),
    "help": IntentThreshold(
        base_threshold=0.4,
        disambiguation_threshold=0.2,
        cost=IntentCost.LIGHTWEIGHT,
        max_tokens=300,
    ),
    
    # 저비용: 단순 LLM 호출
    "overview": IntentThreshold(
        base_threshold=0.4,
        disambiguation_threshold=0.25,
        cost=IntentCost.LOW,
        requires_repo=True,
        max_tokens=400,
    ),
    "general_qa": IntentThreshold(
        base_threshold=0.5,
        disambiguation_threshold=0.3,
        cost=IntentCost.LOW,
        max_tokens=300,
    ),
    
    # 중비용: 이전 결과 + LLM
    "followup": IntentThreshold(
        base_threshold=0.5,
        disambiguation_threshold=0.3,
        cost=IntentCost.MEDIUM,
        max_tokens=512,
    ),
    "recommendation": IntentThreshold(
        base_threshold=0.5,
        disambiguation_threshold=0.3,
        cost=IntentCost.MEDIUM,
        requires_repo=True,
        max_tokens=600,
    ),
    
    # 고비용: GitHub API + 복잡한 처리
    "analyze": IntentThreshold(
        base_threshold=0.6,
        disambiguation_threshold=0.4,
        cost=IntentCost.HIGH,
        requires_repo=True,
        max_tokens=1024,
    ),
    "compare": IntentThreshold(
        base_threshold=0.6,
        disambiguation_threshold=0.4,
        cost=IntentCost.HIGH,
        requires_repo=True,
        max_tokens=1200,
    ),
}

DEFAULT_THRESHOLD = IntentThreshold(
    base_threshold=0.5,
    disambiguation_threshold=0.3,
    cost=IntentCost.MEDIUM,
)


def get_intent_threshold(intent: str) -> IntentThreshold:
    """Returns threshold config for intent."""
    return INTENT_THRESHOLDS.get(intent, DEFAULT_THRESHOLD)


# Calibration 모듈

@dataclass
class CalibrationRecord:
    """Weekly calibration record."""
    intent: str
    week_start: datetime
    total_queries: int = 0
    disambiguation_count: int = 0    # Disambiguation 발생 횟수
    wrong_proceed_count: int = 0     # Wrong-Proceed 발생 횟수 (사용자 피드백 기반)
    entropy_sum: float = 0.0         # 엔트로피 누적
    margin_sum: float = 0.0          # 마진 누적 (1등 - 2등 확률 차이)
    threshold_adjustment: float = 0.0


class CalibrationStore:
    """In-memory calibration store with weekly adjustment."""
    
    MAX_ADJUSTMENT = 0.02  # 주 1회 ±0.02 보정
    TARGET_DISAMBIGUATION_RATE = (0.10, 0.25)  # 10-25% 목표
    TARGET_WRONG_PROCEED_RATE = 0.01           # < 1% 목표
    
    def __init__(self):
        self._records: Dict[Tuple[str, str], CalibrationRecord] = {}
        self._adjustments: Dict[str, float] = {}  # intent → 누적 조정값
    
    def get_week_key(self, dt: datetime) -> str:
        """Returns week key (YYYY-WNN format)."""
        return dt.strftime("%Y-W%W")
    
    def record_query(
        self,
        intent: str,
        confidence: float,
        prob_distribution: Optional[Dict[str, float]] = None,
        was_disambiguation: bool = False,
        was_wrong_proceed: bool = False,
    ) -> None:
        """Records a query for calibration."""
        now = datetime.now()
        week_key = self.get_week_key(now)
        key = (intent, week_key)
        
        if key not in self._records:
            self._records[key] = CalibrationRecord(
                intent=intent,
                week_start=now - timedelta(days=now.weekday()),
            )
        
        record = self._records[key]
        record.total_queries += 1
        
        if was_disambiguation:
            record.disambiguation_count += 1
        if was_wrong_proceed:
            record.wrong_proceed_count += 1
        
        # 엔트로피/마진 계산
        if prob_distribution:
            entropy = self._compute_entropy(prob_distribution)
            margin = self._compute_margin(prob_distribution)
            record.entropy_sum += entropy
            record.margin_sum += margin
    
    def _compute_entropy(self, probs: Dict[str, float]) -> float:
        """Computes entropy of probability distribution."""
        entropy = 0.0
        for p in probs.values():
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    
    def _compute_margin(self, probs: Dict[str, float]) -> float:
        """Computes margin (top1 - top2 probability)."""
        sorted_probs = sorted(probs.values(), reverse=True)
        if len(sorted_probs) < 2:
            return 1.0
        return sorted_probs[0] - sorted_probs[1]
    
    def compute_weekly_adjustment(self, intent: str) -> float:
        """Computes weekly threshold adjustment for intent."""
        now = datetime.now()
        week_key = self.get_week_key(now)
        key = (intent, week_key)
        
        if key not in self._records:
            return 0.0
        
        record = self._records[key]
        if record.total_queries < 10:
            return 0.0  # 데이터 부족
        
        disambiguation_rate = record.disambiguation_count / record.total_queries
        wrong_proceed_rate = record.wrong_proceed_count / record.total_queries
        
        adjustment = 0.0
        
        # Disambiguation 비율 조정
        if disambiguation_rate < self.TARGET_DISAMBIGUATION_RATE[0]:
            # 너무 낮음 → 임계값 올림 (더 많이 disambiguation)
            adjustment += self.MAX_ADJUSTMENT
        elif disambiguation_rate > self.TARGET_DISAMBIGUATION_RATE[1]:
            # 너무 높음 → 임계값 내림 (덜 disambiguation)
            adjustment -= self.MAX_ADJUSTMENT
        
        # Wrong-Proceed 비율 조정 (우선순위 높음)
        if wrong_proceed_rate > self.TARGET_WRONG_PROCEED_RATE:
            # Wrong-Proceed 너무 많음 → 임계값 올림
            adjustment += self.MAX_ADJUSTMENT
        
        # 범위 제한
        adjustment = max(-self.MAX_ADJUSTMENT, min(self.MAX_ADJUSTMENT, adjustment))
        record.threshold_adjustment = adjustment
        
        return adjustment
    
    def get_adjusted_threshold(self, intent: str) -> float:
        """Returns calibrated threshold for intent."""
        base = get_intent_threshold(intent).base_threshold
        adjustment = self._adjustments.get(intent, 0.0)
        
        # 범위: 0.2 ~ 0.8
        return max(0.2, min(0.8, base + adjustment))
    
    def apply_weekly_adjustments(self) -> Dict[str, float]:
        """Applies weekly adjustments to all intents. Call weekly."""
        adjustments = {}
        for intent in INTENT_THRESHOLDS.keys():
            adj = self.compute_weekly_adjustment(intent)
            if adj != 0.0:
                current = self._adjustments.get(intent, 0.0)
                # 누적 조정값 제한: ±0.1
                new_adj = max(-0.1, min(0.1, current + adj))
                self._adjustments[intent] = new_adj
                adjustments[intent] = new_adj
        
        return adjustments
    
    def get_metrics(self, intent: str) -> Optional[Dict[str, float]]:
        """Returns current metrics for intent."""
        now = datetime.now()
        week_key = self.get_week_key(now)
        key = (intent, week_key)
        
        if key not in self._records:
            return None
        
        record = self._records[key]
        if record.total_queries == 0:
            return None
        
        return {
            "total_queries": record.total_queries,
            "disambiguation_rate": record.disambiguation_count / record.total_queries,
            "wrong_proceed_rate": record.wrong_proceed_count / record.total_queries,
            "avg_entropy": record.entropy_sum / record.total_queries,
            "avg_margin": record.margin_sum / record.total_queries,
            "threshold_adjustment": record.threshold_adjustment,
        }


# Global calibration store
calibration_store = CalibrationStore()


# Disambiguation Logic

class DisambiguationResult:
    """Result of disambiguation check."""
    
    def __init__(
        self,
        should_disambiguate: bool,
        reason: str,
        suggested_intents: List[str],
        confidence: float,
    ):
        self.should_disambiguate = should_disambiguate
        self.reason = reason
        self.suggested_intents = suggested_intents
        self.confidence = confidence


def check_disambiguation(
    intent: str,
    confidence: float,
    prob_distribution: Optional[Dict[str, float]] = None,
    has_repo: bool = False,
) -> DisambiguationResult:
    """
    Checks if disambiguation is needed.
    
    Returns DisambiguationResult with:
    - should_disambiguate: True if user clarification needed
    - reason: Why disambiguation is triggered
    - suggested_intents: Top alternative intents to suggest
    - confidence: Original confidence score
    """
    threshold = get_intent_threshold(intent)
    calibrated_threshold = calibration_store.get_adjusted_threshold(intent)
    
    # 1. 저장소 필요한데 없으면 disambiguation
    if threshold.requires_repo and not has_repo:
        return DisambiguationResult(
            should_disambiguate=True,
            reason="저장소 정보가 필요합니다.",
            suggested_intents=[intent],
            confidence=confidence,
        )
    
    # 2. Confidence가 disambiguation 임계 미만
    if confidence < threshold.disambiguation_threshold:
        alternatives = _get_alternative_intents(prob_distribution, intent)
        return DisambiguationResult(
            should_disambiguate=True,
            reason="의도를 명확히 이해하지 못했습니다.",
            suggested_intents=alternatives,
            confidence=confidence,
        )
    
    # 3. Confidence가 base 임계 미만 (calibrated)
    if confidence < calibrated_threshold:
        # 엔트로피/마진 보조 체크
        if prob_distribution:
            entropy = calibration_store._compute_entropy(prob_distribution)
            margin = calibration_store._compute_margin(prob_distribution)
            
            # 높은 엔트로피 + 낮은 마진 → disambiguation
            if entropy > 1.5 and margin < 0.2:
                alternatives = _get_alternative_intents(prob_distribution, intent)
                return DisambiguationResult(
                    should_disambiguate=True,
                    reason="여러 의도가 혼재되어 있습니다.",
                    suggested_intents=alternatives,
                    confidence=confidence,
                )
    
    # 4. 통과
    return DisambiguationResult(
        should_disambiguate=False,
        reason="",
        suggested_intents=[],
        confidence=confidence,
    )


def _get_alternative_intents(
    prob_distribution: Optional[Dict[str, float]],
    primary_intent: str,
) -> List[str]:
    """Returns top 2 alternative intents."""
    if not prob_distribution:
        return ["analyze", "general_qa"]
    
    sorted_intents = sorted(
        prob_distribution.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    
    alternatives = []
    for intent, prob in sorted_intents[:3]:
        if intent != primary_intent:
            alternatives.append(intent)
        if len(alternatives) >= 2:
            break
    
    return alternatives or ["analyze", "general_qa"]


def build_disambiguation_message(result: DisambiguationResult) -> str:
    """Builds user-facing disambiguation message."""
    if not result.should_disambiguate:
        return ""
    
    lines = [result.reason, "", "**다음 중 하나를 선택해 주세요:**"]
    
    intent_descriptions = {
        "analyze": "저장소 건강도 분석하기",
        "compare": "두 저장소 비교하기",
        "overview": "저장소 개요 보기",
        "followup": "이전 분석 결과 더 알아보기",
        "general_qa": "일반 질문하기",
        "help": "사용법 알아보기",
        "recommendation": "기여할 저장소 추천받기",
    }
    
    for i, intent in enumerate(result.suggested_intents, 1):
        desc = intent_descriptions.get(intent, intent)
        lines.append(f"{i}. {desc}")
    
    return "\n".join(lines)


# Temperature Scaling

def temperature_scale(
    logits: Dict[str, float],
    temperature: float = 1.5,
) -> Dict[str, float]:
    """
    Applies temperature scaling to logits.
    
    Higher temperature → softer probabilities (more conservative)
    Lower temperature → sharper probabilities (more confident)
    """
    if temperature <= 0:
        temperature = 1.0
    
    # Apply temperature
    scaled = {k: v / temperature for k, v in logits.items()}
    
    # Softmax
    max_val = max(scaled.values())
    exp_vals = {k: math.exp(v - max_val) for k, v in scaled.items()}
    total = sum(exp_vals.values())
    
    return {k: v / total for k, v in exp_vals.items()}
