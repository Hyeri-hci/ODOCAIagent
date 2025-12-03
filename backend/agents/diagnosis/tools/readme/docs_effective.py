"""문서 유효 점수 계산: tech_signals + marketing_penalty + consilience 교차검증."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from backend.agents.diagnosis.config import (
    get_marketing_config,
    get_consilience_config,
    get_docs_config,
)
from .tech_signals import TechSignals, extract_tech_signals
from .marketing_signals import MarketingSignals, extract_marketing_signals
from backend.agents.diagnosis.tools.consilience import (
    check_path_refs,
    check_badge_refs,
    check_command_refs,
    PathCheckResult,
    BadgeCheckResult,
    CommandCheckResult,
)


@dataclass
class DocsEffectiveResult:
    """문서 유효 점수 결과."""
    # 원본 점수
    docs_quality_raw: int  # 기존 방식 (형식 기반)
    
    # 신호별 점수 (0-100)
    tech_score: int        # 기술 신호 점수
    marketing_penalty: int # 마케팅 페널티 (0-30)
    consilience_score: int # 교차검증 점수 (0-100)
    
    # 최종 유효 점수
    docs_effective: int    # 최종 문서 품질 (0-100)
    
    # 상세 분석
    tech_signals: Optional[Dict[str, Any]] = None
    marketing_signals: Optional[Dict[str, Any]] = None
    consilience_details: Optional[Dict[str, Any]] = None
    
    # 플래그
    is_marketing_heavy: bool = False  # marketing_density > threshold
    has_broken_refs: bool = False     # 교차검증 실패 항목 존재
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _compute_tech_score(signals: TechSignals) -> int:
    """기술 신호 → 점수 (0-100)."""
    config = get_docs_config()
    weights = config.get("tech_score_weights", {
        "code_blocks": 25,
        "commands": 20,
        "path_refs": 15,
        "platforms": 15,
        "density": 25,
    })
    
    score = 0.0
    
    # 코드 블록 점수 (0-25)
    code_count = sum(signals.code_blocks.values())
    if code_count >= 5:
        score += weights["code_blocks"]
    elif code_count >= 3:
        score += weights["code_blocks"] * 0.8
    elif code_count >= 1:
        score += weights["code_blocks"] * 0.5
    
    # 명령 블록 점수 (0-20)
    cmd_total = signals.command_block_count
    if cmd_total >= 3:
        score += weights["commands"]
    elif cmd_total >= 1:
        score += weights["commands"] * 0.6
    
    # 경로 참조 점수 (0-15)
    path_count = len(signals.path_refs)
    if path_count >= 5:
        score += weights["path_refs"]
    elif path_count >= 2:
        score += weights["path_refs"] * 0.7
    elif path_count >= 1:
        score += weights["path_refs"] * 0.4
    
    # 플랫폼 플래그 점수 (0-15)
    platform_count = sum([
        signals.platform_flags.get("has_docker", False),
        signals.platform_flags.get("has_ci", False),
        signals.platform_flags.get("has_npm", False) or signals.platform_flags.get("has_package_json", False),
        signals.platform_flags.get("has_pip", False) or signals.platform_flags.get("has_pyproject", False),
    ])
    score += weights["platforms"] * min(platform_count / 2, 1.0)
    
    # 밀도 점수 (0-25) - tech_density는 per 1k tokens
    density = signals.tech_density / 1000 if signals.tech_density > 1 else signals.tech_density
    if density >= 0.15:
        score += weights["density"]
    elif density >= 0.08:
        score += weights["density"] * 0.7
    elif density >= 0.03:
        score += weights["density"] * 0.4
    
    return min(100, round(score))


def _compute_marketing_penalty(signals: MarketingSignals) -> int:
    """마케팅 신호 → 페널티 (0-30)."""
    config = get_marketing_config()
    max_penalty = config.get("max_penalty", 30)
    
    penalty = 0.0
    
    # 마케팅 밀도 페널티 (per 1k tokens 기준)
    density_threshold = config.get("density_threshold", 0.08)
    density = signals.marketing_density / 1000 if signals.marketing_density > 1 else signals.marketing_density
    if density > density_threshold:
        excess = density - density_threshold
        penalty += min(excess * 100, 10)  # 최대 10점
    
    # 비연결 불릿 페널티
    bullet_threshold = config.get("unlinked_bullet_threshold", 5)
    if signals.unlinked_feature_bullets > bullet_threshold:
        excess = signals.unlinked_feature_bullets - bullet_threshold
        penalty += min(excess * 1.5, 8)  # 최대 8점
    
    # 배지 과다 페널티
    badge_threshold = config.get("badge_threshold", 8)
    badge_count = sum(signals.badge_counts.values())
    if badge_count > badge_threshold:
        excess = badge_count - badge_threshold
        penalty += min(excess * 1.0, 6)  # 최대 6점
    
    # 템플릿 유사도 페널티
    template_threshold = config.get("template_similarity_threshold", 0.6)
    if signals.template_similarity > template_threshold:
        penalty += 6  # 고정 6점
    
    return min(max_penalty, round(penalty))


def _compute_consilience_score(
    owner: str,
    repo: str,
    tech_signals: TechSignals,
    marketing_signals: MarketingSignals,
) -> tuple[int, Dict[str, Any], bool]:
    """교차검증 점수 계산 (0-100)."""
    config = get_consilience_config()
    
    details: Dict[str, Any] = {
        "path": None,
        "badge": None,
        "command": None,
    }
    has_broken = False
    
    total_valid = 0
    total_checked = 0
    
    # 경로 검증
    if tech_signals.path_refs:
        path_result = check_path_refs(owner, repo, tech_signals.path_refs)
        details["path"] = path_result.to_dict()
        total_valid += path_result.valid
        total_checked += path_result.total - (path_result.total - path_result.valid - path_result.broken)
        if path_result.broken > 0:
            has_broken = True
    
    # 배지 검증
    if marketing_signals.badge_urls:
        badge_result = check_badge_refs(owner, repo, marketing_signals.badge_urls)
        details["badge"] = badge_result.to_dict()
        total_valid += badge_result.valid
        total_checked += badge_result.total - badge_result.unchecked
        if badge_result.broken > 0:
            has_broken = True
    
    # 명령 검증
    if tech_signals.command_blocks:
        cmd_result = check_command_refs(owner, repo, tech_signals.command_blocks)
        details["command"] = cmd_result.to_dict()
        total_valid += cmd_result.valid
        total_checked += cmd_result.total - cmd_result.unchecked
        if cmd_result.broken > 0:
            has_broken = True
    
    # 점수 계산
    if total_checked == 0:
        score = 100  # 검증 대상 없음 → 만점
    else:
        score = round((total_valid / total_checked) * 100)
    
    return score, details, has_broken


def compute_docs_effective(
    owner: str,
    repo: str,
    readme_content: str,
    docs_quality_raw: int,
    skip_consilience: bool = False,
) -> DocsEffectiveResult:
    """문서 유효 점수 계산."""
    # 신호 추출
    tech_signals = extract_tech_signals(readme_content)
    marketing_signals = extract_marketing_signals(readme_content)
    
    # 점수 계산
    tech_score = _compute_tech_score(tech_signals)
    marketing_penalty = _compute_marketing_penalty(marketing_signals)
    
    # 교차검증 (선택적)
    if skip_consilience:
        consilience_score = 100
        consilience_details = None
        has_broken = False
    else:
        consilience_score, consilience_details, has_broken = _compute_consilience_score(
            owner, repo, tech_signals, marketing_signals
        )
    
    # 수식 안정화: consilience 하한 적용 (점수 붕괴 방지)
    docs_config = get_docs_config()
    consilience_floor = docs_config.get("consilience_floor", 60)
    consilience_score = max(consilience_score, consilience_floor)
    
    # 마케팅 과다 플래그
    config = get_marketing_config()
    is_marketing_heavy = marketing_signals.marketing_density > config.get("density_threshold", 0.08)
    
    # 최종 점수 계산
    # docs_effective = (raw×0.3 + tech×0.4 + consilience×0.3) - penalty
    # consilience 하한으로 점수 붕괴 방지, penalty 상한으로 과도한 감점 방지
    weights = docs_config.get("effective_weights", {
        "raw": 0.3,
        "tech": 0.4,
        "consilience": 0.3,
    })
    penalty_cap = docs_config.get("marketing_penalty_cap", 30)
    marketing_penalty = min(marketing_penalty, penalty_cap)
    
    base_score = (
        docs_quality_raw * weights["raw"] +
        tech_score * weights["tech"] +
        consilience_score * weights["consilience"]
    )
    
    docs_effective = max(0, min(100, round(base_score - marketing_penalty)))
    
    return DocsEffectiveResult(
        docs_quality_raw=docs_quality_raw,
        tech_score=tech_score,
        marketing_penalty=marketing_penalty,
        consilience_score=consilience_score,
        docs_effective=docs_effective,
        tech_signals=tech_signals.to_dict(),
        marketing_signals=marketing_signals.to_dict(),
        consilience_details=consilience_details,
        is_marketing_heavy=is_marketing_heavy,
        has_broken_refs=has_broken,
    )
