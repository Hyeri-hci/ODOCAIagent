"""
Reasoning Builder - explain 모드를 위한 점수 근거 데이터 생성.

Diagnosis 결과에서 각 metric별 reasoning_data를 추출하여
summarize_node가 LLM에게 "왜 이 점수가 나왔는지" 설명할 수 있게 합니다.
"""
from __future__ import annotations

from typing import Any

from .health_formulas import (
    HEALTH_SCORE_FORMULA,
    ONBOARDING_SCORE_FORMULA,
    ACTIVITY_SCORE_FORMULA,
    FORMULA_WEIGHTS,
)


def build_health_reasoning(scores: dict, details: dict) -> dict:
    """health_score 근거 데이터 생성"""
    doc = scores.get("documentation_quality", 0)
    activity = scores.get("activity_maintainability", 0)
    health = scores.get("health_score", 0)
    
    doc_contribution = round(0.3 * doc, 1)
    activity_contribution = round(0.7 * activity, 1)
    
    return {
        "score": health,
        "formula": HEALTH_SCORE_FORMULA,
        "components": {
            "documentation_quality": {
                "score": doc,
                "weight": 0.3,
                "contribution": doc_contribution,
            },
            "activity_maintainability": {
                "score": activity,
                "weight": 0.7,
                "contribution": activity_contribution,
            },
        },
        "is_healthy": scores.get("is_healthy", False),
    }


def build_docs_reasoning(scores: dict, details: dict) -> dict:
    """documentation_quality 근거 데이터 생성"""
    docs_info = details.get("docs", {})
    categories = docs_info.get("readme_categories", {})
    
    present = [k for k, v in categories.items() if v]
    missing = [k for k, v in categories.items() if not v]
    
    readme_metrics = details.get("readme_metrics", {})
    word_count = readme_metrics.get("word_count", 0)
    
    length_bucket = "short"
    if word_count > 1000:
        length_bucket = "long"
    elif word_count > 300:
        length_bucket = "medium"
    
    return {
        "score": scores.get("documentation_quality", 0),
        "present_sections": present,
        "missing_sections": missing,
        "section_count": len(present),
        "total_sections": 8,
        "readme_length_bucket": length_bucket,
        "word_count": word_count,
    }


def build_activity_reasoning(scores: dict, details: dict) -> dict:
    """activity_maintainability 근거 데이터 생성"""
    activity = details.get("activity", {})
    activity_scores = activity.get("scores", {})
    
    commit_data = activity.get("commit", {})
    issue_data = activity.get("issue", {})
    pr_data = activity.get("pr", {})
    
    commit_score = activity_scores.get("commit_score", 0)
    issue_score = activity_scores.get("issue_score", 0)
    pr_score = activity_scores.get("pr_score", 0)
    
    return {
        "score": scores.get("activity_maintainability", 0),
        "formula": ACTIVITY_SCORE_FORMULA,
        "commit": {
            "weight": 0.4,
            "score": commit_score,
            "contribution": round(commit_score * 0.4 * 100, 1),
            "total_commits": commit_data.get("total_commits", 0),
            "unique_authors": commit_data.get("unique_authors", 0),
            "days_since_last": commit_data.get("days_since_last_commit"),
            "commits_per_week": commit_data.get("commits_per_week", 0),
        },
        "issue": {
            "weight": 0.3,
            "score": issue_score,
            "contribution": round(issue_score * 0.3 * 100, 1),
            "open_issues": issue_data.get("open_issues", 0),
            "opened_in_window": issue_data.get("opened_issues_in_window", 0),
            "closed_in_window": issue_data.get("closed_issues_in_window", 0),
            "closure_ratio": issue_data.get("issue_closure_ratio"),
            "median_close_days": issue_data.get("median_time_to_close_days"),
        },
        "pr": {
            "weight": 0.3,
            "score": pr_score,
            "contribution": round(pr_score * 0.3 * 100, 1),
            "prs_in_window": pr_data.get("prs_in_window", 0),
            "merged_in_window": pr_data.get("merged_in_window", 0),
            "merge_ratio": pr_data.get("pr_merge_ratio"),
            "median_merge_days": pr_data.get("median_time_to_merge_days"),
        },
    }


def build_onboarding_reasoning(scores: dict, details: dict, onboarding_tasks: dict | None) -> dict:
    """onboarding_score 근거 데이터 생성"""
    doc = scores.get("documentation_quality", 0)
    activity = scores.get("activity_maintainability", 0)
    
    docs_info = details.get("docs", {})
    categories = docs_info.get("readme_categories", {})
    
    has_contributing = categories.get("contributing", False)
    has_code_of_conduct = categories.get("code_of_conduct", False)
    
    beginner_count = 0
    good_first_issue_count = 0
    
    if onboarding_tasks:
        beginner_tasks = onboarding_tasks.get("beginner", [])
        beginner_count = len(beginner_tasks)
        
        for task in beginner_tasks:
            labels = task.get("labels", [])
            if any("good" in label.lower() and "first" in label.lower() for label in labels):
                good_first_issue_count += 1
    
    return {
        "score": scores.get("onboarding_score", 0),
        "formula": ONBOARDING_SCORE_FORMULA,
        "components": {
            "documentation_quality": {
                "score": doc,
                "weight": 0.6,
                "contribution": round(0.6 * doc, 1),
            },
            "activity_maintainability": {
                "score": activity,
                "weight": 0.4,
                "contribution": round(0.4 * activity, 1),
            },
        },
        "good_first_issue_count": good_first_issue_count,
        "beginner_task_count": beginner_count,
        "has_contributing_guide": has_contributing,
        "has_code_of_conduct": has_code_of_conduct,
    }


def build_explain_context(diagnosis_result: dict[str, Any]) -> dict[str, dict]:
    """Diagnosis 결과에서 explain_context 생성."""
    scores = diagnosis_result.get("scores", {})
    details = diagnosis_result.get("details", {})
    onboarding_tasks = diagnosis_result.get("onboarding_tasks")
    
    return {
        "health_score": build_health_reasoning(scores, details),
        "documentation_quality": build_docs_reasoning(scores, details),
        "activity_maintainability": build_activity_reasoning(scores, details),
        "onboarding_score": build_onboarding_reasoning(scores, details, onboarding_tasks),
    }


def classify_explain_depth(user_query: str) -> str:
    """
    질문 깊이 분류: simple(짧은 확인) vs deep(심층 분석).
    
    Returns:
        "simple" or "deep"
    """
    deep_keywords = ["왜", "구체", "자세", "분석", "원인", "이유", "비교"]
    
    if len(user_query) <= 20:
        if not any(kw in user_query for kw in deep_keywords):
            return "simple"
    
    return "deep"


def build_warning_text(scores: dict[str, Any] | None) -> str | None:
    """
    점수 기반 경고 문구 생성. 임계값 미만일 때만 경고 반환.
    
    Returns:
        경고 문구 또는 None
    """
    if not scores:
        return None
    
    health = scores.get("health_score", 100)
    activity = scores.get("activity_maintainability", 100)
    docs = scores.get("documentation_quality", 100)
    
    if health < 50:
        return "현재 health_score가 50점 미만으로 장기 유지보수에 상당한 리스크가 있습니다."
    
    if activity < 40:
        return "활동성이 매우 낮아 신규 이슈/PR이 들어와도 처리되지 않을 가능성이 높습니다."
    
    if docs < 40:
        return "문서화가 부족하여 신규 기여자가 프로젝트를 이해하기 어려울 수 있습니다."
    
    if health < 60:
        return "health_score가 60점 미만으로 일부 개선이 필요한 상태입니다."
    
    return None
