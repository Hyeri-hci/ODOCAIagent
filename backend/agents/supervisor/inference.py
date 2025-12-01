"""
Active Inference - 누락 옵션 추론기.

사용자 입력에서 누락된 정보(owner/repo, 기간, 브랜치 등)를 추론.
신뢰도가 낮으면 disambiguation으로 전환.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.shared.contracts import InferenceHints
from backend.common.events import (
    EventType,
    emit_event,
    persist_artifact,
)

logger = logging.getLogger(__name__)

# 잘 알려진 저장소 매핑 (약어 → owner/repo)
KNOWN_REPOS: Dict[str, str] = {
    "react": "facebook/react",
    "vue": "vuejs/vue",
    "angular": "angular/angular",
    "next": "vercel/next.js",
    "nextjs": "vercel/next.js",
    "svelte": "sveltejs/svelte",
    "django": "django/django",
    "flask": "pallets/flask",
    "fastapi": "tiangolo/fastapi",
    "express": "expressjs/express",
    "nest": "nestjs/nest",
    "nestjs": "nestjs/nest",
    "tensorflow": "tensorflow/tensorflow",
    "pytorch": "pytorch/pytorch",
    "keras": "keras-team/keras",
    "pandas": "pandas-dev/pandas",
    "numpy": "numpy/numpy",
    "scikit-learn": "scikit-learn/scikit-learn",
    "sklearn": "scikit-learn/scikit-learn",
    "langchain": "langchain-ai/langchain",
    "langgraph": "langchain-ai/langgraph",
    "vscode": "microsoft/vscode",
    "typescript": "microsoft/TypeScript",
    "rust": "rust-lang/rust",
    "go": "golang/go",
    "kubernetes": "kubernetes/kubernetes",
    "k8s": "kubernetes/kubernetes",
    "docker": "moby/moby",
}

# GitHub URL 패턴 (greedy 매칭 후 후처리)
GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)",
    re.IGNORECASE
)

# owner/repo 패턴 (URL 없이)
OWNER_REPO_PATTERN = re.compile(
    r"(?:^|\s)([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)",
)


def extract_repo_from_text(text: str) -> Optional[Tuple[str, str, float]]:
    """
    텍스트에서 저장소 정보 추출.
    
    Returns:
        Tuple[owner, repo, confidence] or None
    """
    # 1. GitHub URL 패턴 매칭 (가장 높은 신뢰도)
    url_match = GITHUB_URL_PATTERN.search(text)
    if url_match:
        owner, repo = url_match.groups()
        # .git 접미사 제거
        if repo.endswith(".git"):
            repo = repo[:-4]
        return (owner, repo, 0.99)
    
    # 2. owner/repo 패턴 매칭
    owner_repo_match = OWNER_REPO_PATTERN.search(text)
    if owner_repo_match:
        owner, repo = owner_repo_match.groups()
        return (owner, repo, 0.9)
    
    # 3. 잘 알려진 저장소 약어 매칭
    text_lower = text.lower()
    for keyword, full_name in KNOWN_REPOS.items():
        # 단어 경계 확인
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, text_lower):
            owner, repo = full_name.split("/")
            return (owner, repo, 0.8)
    
    return None


def infer_user_level(text: str) -> Tuple[str, float]:
    """
    사용자 수준 추론.
    
    Returns:
        Tuple[level, confidence]
    """
    text_lower = text.lower()
    
    # 초보자 키워드
    beginner_keywords = [
        "초보", "입문", "처음", "시작", "newbie", "beginner", "junior",
        "쉬운", "간단한", "첫", "first", "easy", "simple", "기초",
    ]
    
    # 고급자 키워드
    advanced_keywords = [
        "고급", "심화", "전문", "advanced", "senior", "expert",
        "복잡한", "어려운", "challenging", "hard", "difficult",
        "아키텍처", "설계", "architecture", "core", "internal",
    ]
    
    beginner_count = sum(1 for kw in beginner_keywords if kw in text_lower)
    advanced_count = sum(1 for kw in advanced_keywords if kw in text_lower)
    
    if beginner_count > advanced_count:
        confidence = min(0.9, 0.5 + beginner_count * 0.15)
        return ("beginner", confidence)
    elif advanced_count > beginner_count:
        confidence = min(0.9, 0.5 + advanced_count * 0.15)
        return ("advanced", confidence)
    else:
        return ("intermediate", 0.5)


def infer_goal(text: str) -> Tuple[Optional[str], float]:
    """
    사용자 목표 추론.
    
    Returns:
        Tuple[goal, confidence]
    """
    text_lower = text.lower()
    
    goal_patterns = [
        (r"기여.*하고\s*싶|contribute|contribution|pr.*보내", "contribute", 0.85),
        (r"학습|배우|공부|learn|study", "learn", 0.8),
        (r"분석|analyze|진단|평가|evaluate", "analyze", 0.8),
        (r"비교|compare|versus|vs", "compare", 0.85),
        (r"온보딩|onboarding|시작|start", "onboarding", 0.8),
    ]
    
    for pattern, goal, confidence in goal_patterns:
        if re.search(pattern, text_lower):
            return (goal, confidence)
    
    return (None, 0.0)


def infer_missing(
    user_text: str,
    current_state: Dict[str, Any],
) -> InferenceHints:
    """
    사용자 입력에서 누락된 정보 추론.
    
    Args:
        user_text: 사용자 쿼리
        current_state: 현재 상태 (이전 repo, context 등)
    
    Returns:
        InferenceHints: 추론된 정보
    """
    hints = InferenceHints()
    inferred_fields: List[str] = []
    confidences: List[float] = []
    
    # 1. 저장소 추론
    current_repo = current_state.get("repo")
    if not current_repo or not current_repo.get("owner"):
        repo_info = extract_repo_from_text(user_text)
        if repo_info:
            owner, repo, conf = repo_info
            hints.owner = owner
            hints.name = repo
            hints.repo_guess = f"{owner}/{repo}"
            inferred_fields.append("repo")
            confidences.append(conf)
        else:
            # 이전 저장소가 있으면 재사용 (follow-up 패턴)
            last_repo = current_state.get("last_repo")
            if last_repo and last_repo.get("owner"):
                hints.owner = last_repo.get("owner")
                hints.name = last_repo.get("name")
                hints.repo_guess = f"{hints.owner}/{hints.name}"
                inferred_fields.append("repo_from_history")
                confidences.append(0.7)
    
    # 2. 사용자 수준 추론
    user_context = current_state.get("user_context") or {}
    if not user_context.get("level"):
        level, level_conf = infer_user_level(user_text)
        if level_conf > 0.5:
            inferred_fields.append("level")
            confidences.append(level_conf)
    
    # 3. 목표 추론
    if not user_context.get("goal"):
        goal, goal_conf = infer_goal(user_text)
        if goal:
            inferred_fields.append("goal")
            confidences.append(goal_conf)
    
    # 4. 기본값 설정
    hints.branch = "main"
    hints.window_days = 90
    
    # 종합 신뢰도
    hints.inferred_fields = inferred_fields
    if confidences:
        hints.confidence = sum(confidences) / len(confidences)
    else:
        hints.confidence = 0.0
    
    # 이벤트 발행 및 Artifact 저장
    if inferred_fields:
        artifact_id = persist_artifact(
            kind="inference_hints",
            content=hints.model_dump(),
        )
        
        emit_event(
            EventType.ARTIFACT_CREATED,
            outputs={
                "artifact_id": artifact_id,
                "inferred_fields": inferred_fields,
                "confidence": hints.confidence,
            },
            artifacts_out=[artifact_id],
        )
    
    return hints


def needs_disambiguation(hints: InferenceHints, threshold: float = 0.6) -> bool:
    """disambiguation이 필요한지 판단."""
    # 저장소 추론 실패
    if not hints.repo_guess and not hints.owner:
        return True
    
    # 전체 신뢰도가 낮음
    if hints.confidence < threshold:
        return True
    
    return False


def build_disambiguation_message(hints: InferenceHints) -> str:
    """disambiguation 메시지 생성."""
    parts = []
    
    if not hints.repo_guess:
        parts.append("어떤 저장소를 분석할까요? GitHub URL이나 owner/repo 형식으로 알려주세요.")
    elif hints.confidence < 0.7:
        parts.append(f"'{hints.repo_guess}' 저장소를 분석할까요? 맞다면 '네'라고 답해주세요.")
    
    if not parts:
        parts.append("추가 정보가 필요합니다. 어떤 저장소를 어떻게 분석할지 자세히 알려주세요.")
    
    return " ".join(parts)
