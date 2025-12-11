"""
커뮤니티 활동도 분석 모듈

PR 리뷰 시간, 메인테이너 반응률, 기여 친화도 점수 계산
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def analyze_community_activity(
    owner: str,
    repo: str,
    recent_prs: Optional[List[Dict[str, Any]]] = None,
    recent_issues: Optional[List[Dict[str, Any]]] = None,
    contributors: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    커뮤니티 활동도 분석
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        recent_prs: 최근 PR 목록 (GitHub API 응답)
        recent_issues: 최근 이슈 목록
        contributors: 기여자 목록
    
    Returns:
        커뮤니티 활동도 분석 결과
    """
    result = {
        "owner": owner,
        "repo": repo,
        "pr_metrics": {},
        "issue_metrics": {},
        "contributor_metrics": {},
        "friendliness_score": 0,
        "friendliness_level": "unknown",
        "recommendations": []
    }
    
    # PR 메트릭 분석
    if recent_prs:
        pr_metrics = _analyze_pr_metrics(recent_prs)
        result["pr_metrics"] = pr_metrics
    
    # 이슈 메트릭 분석
    if recent_issues:
        issue_metrics = _analyze_issue_metrics(recent_issues)
        result["issue_metrics"] = issue_metrics
    
    # 기여자 메트릭 분석
    if contributors:
        contributor_metrics = _analyze_contributor_metrics(contributors)
        result["contributor_metrics"] = contributor_metrics
    
    # 기여 친화도 점수 계산
    friendliness = _calculate_friendliness_score(
        result["pr_metrics"],
        result["issue_metrics"],
        result["contributor_metrics"]
    )
    result["friendliness_score"] = friendliness["score"]
    result["friendliness_level"] = friendliness["level"]
    result["friendliness_factors"] = friendliness["factors"]
    
    # 권장사항 생성
    result["recommendations"] = _generate_recommendations(result)
    
    return result


def _analyze_pr_metrics(prs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """PR 메트릭 분석"""
    if not prs:
        return {"count": 0}
    
    merge_times = []
    review_times = []
    merged_count = 0
    
    for pr in prs:
        created_at = pr.get("created_at")
        merged_at = pr.get("merged_at")
        
        if merged_at and created_at:
            merged_count += 1
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                merged = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                merge_time = (merged - created).total_seconds() / 86400  # 일 단위
                merge_times.append(merge_time)
            except (ValueError, TypeError):
                pass
        
        # 첫 리뷰 시간 (리뷰 데이터가 있는 경우)
        reviews = pr.get("reviews", [])
        if reviews and created_at:
            try:
                first_review = min(reviews, key=lambda r: r.get("submitted_at", ""))
                review_at = first_review.get("submitted_at")
                if review_at:
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    reviewed = datetime.fromisoformat(review_at.replace("Z", "+00:00"))
                    review_time = (reviewed - created).total_seconds() / 86400
                    review_times.append(review_time)
            except (ValueError, TypeError):
                pass
    
    avg_merge_time = sum(merge_times) / len(merge_times) if merge_times else None
    avg_review_time = sum(review_times) / len(review_times) if review_times else None
    merge_rate = merged_count / len(prs) if prs else 0
    
    return {
        "count": len(prs),
        "merged_count": merged_count,
        "merge_rate": round(merge_rate, 2),
        "avg_merge_days": round(avg_merge_time, 1) if avg_merge_time else None,
        "avg_review_days": round(avg_review_time, 1) if avg_review_time else None,
        "median_merge_days": _median(merge_times) if merge_times else None
    }


def _analyze_issue_metrics(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """이슈 메트릭 분석"""
    if not issues:
        return {"count": 0}
    
    response_times = []
    closed_count = 0
    has_good_first_issue = 0
    
    for issue in issues:
        # Pull Request는 제외
        if issue.get("pull_request"):
            continue
        
        if issue.get("state") == "closed":
            closed_count += 1
        
        # Good first issue 태그 체크
        labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
        if any("good first issue" in label or "beginner" in label for label in labels):
            has_good_first_issue += 1
        
        # 첫 응답 시간 (코멘트)
        created_at = issue.get("created_at")
        comments = issue.get("comments_data", [])
        if comments and created_at:
            try:
                first_comment = min(comments, key=lambda c: c.get("created_at", ""))
                comment_at = first_comment.get("created_at")
                if comment_at:
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    commented = datetime.fromisoformat(comment_at.replace("Z", "+00:00"))
                    response_time = (commented - created).total_seconds() / 86400
                    response_times.append(response_time)
            except (ValueError, TypeError):
                pass
    
    avg_response_time = sum(response_times) / len(response_times) if response_times else None
    close_rate = closed_count / len(issues) if issues else 0
    
    return {
        "count": len(issues),
        "closed_count": closed_count,
        "close_rate": round(close_rate, 2),
        "good_first_issue_count": has_good_first_issue,
        "avg_response_days": round(avg_response_time, 1) if avg_response_time else None,
        "median_response_days": _median(response_times) if response_times else None
    }


def _analyze_contributor_metrics(contributors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """기여자 메트릭 분석"""
    if not contributors:
        return {"count": 0}
    
    total_contributions = sum(c.get("contributions", 0) for c in contributors)
    top_contributor_ratio = contributors[0].get("contributions", 0) / total_contributions if total_contributions > 0 else 0
    
    # 최근 신규 기여자 수 추정 (기여 횟수 1~5회인 기여자)
    new_contributors = len([c for c in contributors if 1 <= c.get("contributions", 0) <= 5])
    
    return {
        "count": len(contributors),
        "total_contributions": total_contributions,
        "top_contributor_ratio": round(top_contributor_ratio, 2),
        "new_contributors": new_contributors,
        "diversity_score": min(100, len(contributors) * 5)  # 기여자 다양성 점수
    }


def _calculate_friendliness_score(
    pr_metrics: Dict[str, Any],
    issue_metrics: Dict[str, Any],
    contributor_metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """
    기여 친화도 점수 계산 (0-100)
    """
    factors = []
    scores = []
    
    # PR 리뷰 속도 (30%)
    avg_review_days = pr_metrics.get("avg_review_days")
    if avg_review_days is not None:
        if avg_review_days <= 1:
            pr_score = 100
            factors.append({"name": "PR 리뷰 속도", "value": "매우 빠름 (1일 이내)", "score": 100})
        elif avg_review_days <= 3:
            pr_score = 80
            factors.append({"name": "PR 리뷰 속도", "value": "빠름 (3일 이내)", "score": 80})
        elif avg_review_days <= 7:
            pr_score = 60
            factors.append({"name": "PR 리뷰 속도", "value": "보통 (1주일 이내)", "score": 60})
        else:
            pr_score = 30
            factors.append({"name": "PR 리뷰 속도", "value": "느림 (1주일 이상)", "score": 30})
        scores.append(pr_score * 0.3)
    
    # 이슈 응답 속도 (25%)
    avg_response_days = issue_metrics.get("avg_response_days")
    if avg_response_days is not None:
        if avg_response_days <= 1:
            issue_score = 100
            factors.append({"name": "이슈 응답 속도", "value": "매우 빠름 (1일 이내)", "score": 100})
        elif avg_response_days <= 3:
            issue_score = 80
            factors.append({"name": "이슈 응답 속도", "value": "빠름 (3일 이내)", "score": 80})
        elif avg_response_days <= 7:
            issue_score = 60
            factors.append({"name": "이슈 응답 속도", "value": "보통 (1주일 이내)", "score": 60})
        else:
            issue_score = 30
            factors.append({"name": "이슈 응답 속도", "value": "느림 (1주일 이상)", "score": 30})
        scores.append(issue_score * 0.25)
    
    # Good First Issue 존재 (20%)
    gfi_count = issue_metrics.get("good_first_issue_count", 0)
    if gfi_count >= 5:
        gfi_score = 100
        factors.append({"name": "Good First Issue", "value": f"{gfi_count}개 있음", "score": 100})
    elif gfi_count >= 2:
        gfi_score = 70
        factors.append({"name": "Good First Issue", "value": f"{gfi_count}개 있음", "score": 70})
    elif gfi_count >= 1:
        gfi_score = 50
        factors.append({"name": "Good First Issue", "value": f"{gfi_count}개 있음", "score": 50})
    else:
        gfi_score = 20
        factors.append({"name": "Good First Issue", "value": "없음", "score": 20})
    scores.append(gfi_score * 0.2)
    
    # 기여자 다양성 (15%)
    diversity = contributor_metrics.get("diversity_score", 50)
    factors.append({"name": "기여자 다양성", "value": f"{contributor_metrics.get('count', 0)}명", "score": diversity})
    scores.append(diversity * 0.15)
    
    # PR 병합률 (10%)
    merge_rate = pr_metrics.get("merge_rate", 0)
    merge_score = int(merge_rate * 100)
    factors.append({"name": "PR 병합률", "value": f"{int(merge_rate * 100)}%", "score": merge_score})
    scores.append(merge_score * 0.1)
    
    # 최종 점수
    final_score = int(sum(scores)) if scores else 50
    
    # 레벨 결정
    if final_score >= 80:
        level = "very_friendly"
        level_text = "매우 친화적"
    elif final_score >= 60:
        level = "friendly"
        level_text = "친화적"
    elif final_score >= 40:
        level = "moderate"
        level_text = "보통"
    else:
        level = "challenging"
        level_text = "도전적"
    
    return {
        "score": final_score,
        "level": level,
        "level_text": level_text,
        "factors": factors
    }


def _generate_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """분석 결과 기반 권장사항 생성"""
    recommendations = []
    
    pr_metrics = analysis.get("pr_metrics", {})
    issue_metrics = analysis.get("issue_metrics", {})
    friendliness_score = analysis.get("friendliness_score", 0)
    
    # PR 리뷰 속도
    if pr_metrics.get("avg_review_days") and pr_metrics["avg_review_days"] > 7:
        recommendations.append("PR 리뷰가 오래 걸릴 수 있으니 인내심을 가지세요.")
    
    # Good First Issue
    if issue_metrics.get("good_first_issue_count", 0) == 0:
        recommendations.append("Good First Issue가 없습니다. 직접 간단한 개선점을 찾아보세요.")
    elif issue_metrics.get("good_first_issue_count", 0) >= 5:
        recommendations.append("Good First Issue가 충분합니다. 먼저 시작하기 좋은 프로젝트입니다!")
    
    # 친화도 점수
    if friendliness_score >= 70:
        recommendations.append("기여 친화적인 프로젝트입니다. 적극적으로 참여해보세요!")
    elif friendliness_score < 40:
        recommendations.append("활동이 적은 프로젝트일 수 있습니다. 다른 프로젝트도 고려해보세요.")
    
    # 이슈 해결률
    if issue_metrics.get("close_rate", 0) < 0.3:
        recommendations.append("이슈 해결률이 낮습니다. 미해결 이슈를 해결하면 큰 기여가 될 수 있습니다.")
    
    return recommendations


def _median(values: List[float]) -> Optional[float]:
    """중간값 계산"""
    if not values:
        return None
    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 0:
        return round((sorted_values[mid - 1] + sorted_values[mid]) / 2, 1)
    return round(sorted_values[mid], 1)


def format_community_analysis_as_markdown(analysis: Dict[str, Any]) -> str:
    """커뮤니티 분석 결과를 Markdown으로 변환"""
    md = f"# {analysis['owner']}/{analysis['repo']} 커뮤니티 활동 분석\n\n"
    
    # 기여 친화도
    friendliness = analysis.get("friendliness_score", 0)
    level_text = {"very_friendly": "매우 친화적", "friendly": "친화적", "moderate": "보통", "challenging": "도전적"}.get(
        analysis.get("friendliness_level"), "알 수 없음"
    )
    md += f"## 기여 친화도 점수: {friendliness}/100 ({level_text})\n\n"
    
    # 세부 요소
    factors = analysis.get("friendliness_factors", [])
    if factors:
        md += "| 요소 | 상태 | 점수 |\n|------|------|------|\n"
        for factor in factors:
            md += f"| {factor['name']} | {factor['value']} | {factor['score']} |\n"
        md += "\n"
    
    # 권장사항
    recommendations = analysis.get("recommendations", [])
    if recommendations:
        md += "## 권장사항\n\n"
        for rec in recommendations:
            md += f"- {rec}\n"
        md += "\n"
    
    return md
