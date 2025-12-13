"""
리포트 내보내기 모듈

진단 결과, 온보딩 가이드 등을 Markdown 형식으로 내보내기
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def export_diagnosis_report(
    result: Dict[str, Any],
    owner: str,
    repo: str,
    include_ai_trace: bool = True
) -> str:
    """
    진단 결과를 Markdown 리포트로 변환
    
    Args:
        result: 진단 결과 딕셔너리
        owner: 저장소 소유자
        repo: 저장소 이름
        include_ai_trace: AI 판단 과정 포함 여부
    
    Returns:
        Markdown 형식 문자열
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    health_score = result.get("health_score", 0)
    onboarding_score = result.get("onboarding_score", 0)
    docs_score = result.get("docs_score", 0)
    activity_score = result.get("activity_score", 0)
    health_level = result.get("health_level", "")
    
    # 점수 기반 등급
    def get_grade(score: int) -> str:
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B"
        if score >= 60: return "C"
        if score >= 50: return "D"
        return "F"
    
    report = f"""# {owner}/{repo} 진단 리포트

**생성일시:** {timestamp}

---

## 종합 점수

| 항목 | 점수 | 등급 |
|------|------|------|
| 건강도 | {health_score}/100 | {get_grade(health_score)} |
| 온보딩 친화도 | {onboarding_score}/100 | {get_grade(onboarding_score)} |
| 문서화 품질 | {docs_score}/100 | {get_grade(docs_score)} |
| 활동성 | {activity_score}/100 | {get_grade(activity_score)} |

**종합 상태:** {health_level}

---

## 주요 발견사항

"""
    
    # 주요 발견사항
    key_findings = result.get("key_findings", [])
    if key_findings:
        for finding in key_findings:
            title = finding.get("title", "")
            desc = finding.get("description", "")
            severity = finding.get("severity", "info")
            icon = {"critical": "", "warning": "", "info": ""}.get(severity, "")
            report += f"### {icon} {title}\n{desc}\n\n"
    else:
        report += "특이사항 없음\n\n"
    
    # 권장사항
    recommendations = result.get("recommendations", [])
    if recommendations:
        report += "---\n\n## 권장사항\n\n"
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
        report += "\n"
    
    # 경고
    warnings = result.get("warnings", [])
    if warnings:
        report += "---\n\n## 주의사항\n\n"
        for warning in warnings:
            report += f"- {warning}\n"
        report += "\n"
    
    # AI 판단 과정 (선택)
    if include_ai_trace:
        llm_summary = result.get("llm_summary", "")
        if llm_summary:
            report += f"""---

## AI 분석 요약

{llm_summary}

"""
    
    # 다음 단계
    report += """---

## 다음 단계

1. **기여 시작하기**: 이 저장소에 기여하고 싶다면 온보딩 가이드를 생성해보세요.
2. **보안 점검**: 보안 취약점이 걱정된다면 보안 분석을 실행하세요.
3. **정기 점검**: 프로젝트 건강 상태를 정기적으로 모니터링하세요.

---

*이 리포트는 ODOCAIagent에 의해 자동 생성되었습니다.*
"""
    
    return report


def export_onboarding_guide(
    plan: Dict[str, Any],
    owner: str,
    repo: str,
    experience_level: str = "beginner"
) -> str:
    """
    온보딩 가이드를 Markdown 리포트로 변환
    
    Args:
        plan: 온보딩 플랜 딕셔너리
        owner: 저장소 소유자
        repo: 저장소 이름
        experience_level: 사용자 경험 수준
    
    Returns:
        Markdown 형식 문자열
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    level_name = {
        "beginner": "입문자",
        "intermediate": "중급자", 
        "advanced": "숙련자"
    }.get(experience_level, "입문자")
    
    report = f"""# {owner}/{repo} 온보딩 가이드

**생성일시:** {timestamp}
**대상 수준:** {level_name}

---

## 개요

이 가이드는 {owner}/{repo} 프로젝트에 기여하고자 하는 {level_name}를 위해 작성되었습니다.

---

## 주차별 학습 계획

"""
    
    # 주차별 계획
    weeks = plan.get("plan", [])
    if isinstance(weeks, list):
        for week in weeks:
            if isinstance(week, dict):
                week_num = week.get("week", "?")
                title = week.get("title", "")
                tasks = week.get("tasks", [])
                
                report += f"### {week_num}주차: {title}\n\n"
                
                if tasks:
                    for task in tasks:
                        report += f"- [ ] {task}\n"
                report += "\n"
    
    # 추천 이슈
    recommended_issues = plan.get("recommended_issues", [])
    if recommended_issues:
        report += "---\n\n## 추천 이슈\n\n"
        for issue in recommended_issues[:5]:
            title = issue.get("title", "")
            url = issue.get("url", "")
            labels = issue.get("labels", [])
            
            label_text = ", ".join(labels) if labels else ""
            if url:
                report += f"- [{title}]({url})"
            else:
                report += f"- {title}"
            if label_text:
                report += f" `{label_text}`"
            report += "\n"
        report += "\n"
    
    # 요약
    summary = plan.get("summary", "")
    if summary:
        report += f"""---

## 요약

{summary}

"""
    
    report += """---

*이 온보딩 가이드는 ODOCAIagent에 의해 자동 생성되었습니다.*
"""
    
    return report


def export_security_report(
    result: Dict[str, Any],
    owner: str,
    repo: str
) -> str:
    """
    보안 분석 결과를 Markdown 리포트로 변환
    
    Args:
        result: 보안 분석 결과
        owner: 저장소 소유자
        repo: 저장소 이름
    
    Returns:
        Markdown 형식 문자열
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    results = result.get("results", result)
    security_score = results.get("security_score", 0)
    security_grade = results.get("security_grade", "N/A")
    risk_level = results.get("risk_level", "unknown")
    
    vulnerabilities = results.get("vulnerabilities", {})
    # vulnerabilities가 list인 경우 처리
    if isinstance(vulnerabilities, list):
        vuln_total = len(vulnerabilities)
        vuln_critical = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "critical")
        vuln_high = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "high")
        vuln_medium = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "medium")
        vuln_low = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "low")
    else:
        vuln_total = vulnerabilities.get("total", 0) if vulnerabilities else 0
        vuln_critical = vulnerabilities.get("critical", 0) if vulnerabilities else 0
        vuln_high = vulnerabilities.get("high", 0) if vulnerabilities else 0
        vuln_medium = vulnerabilities.get("medium", 0) if vulnerabilities else 0
        vuln_low = vulnerabilities.get("low", 0) if vulnerabilities else 0
    
    report = f"""# {owner}/{repo} 보안 분석 리포트

**생성일시:** {timestamp}

---

## 보안 점수

| 항목 | 값 |
|------|-----|
| 보안 점수 | {security_score}/100 |
| 등급 | {security_grade} |
| 위험도 | {risk_level} |

---

## 취약점 현황

| 심각도 | 개수 |
|--------|------|
| Critical | {vuln_critical} |
| High | {vuln_high} |
| Medium | {vuln_medium} |
| Low | {vuln_low} |
| **총합** | **{vuln_total}** |

"""
    
    # 상세 취약점 목록
    vuln_details = vulnerabilities.get("details", [])
    if vuln_details:
        report += "---\n\n## 상세 취약점 목록\n\n"
        for vuln in vuln_details[:10]:  # 최대 10개
            cve_id = vuln.get("cve_id", "Unknown")
            package = vuln.get("package", "")
            severity = vuln.get("severity", "")
            desc = vuln.get("description", "")
            
            report += f"### {cve_id}\n"
            report += f"- **패키지:** {package}\n"
            report += f"- **심각도:** {severity}\n"
            report += f"- **설명:** {desc}\n\n"
    
    report += """---

*이 보안 리포트는 ODOCAIagent에 의해 자동 생성되었습니다.*
"""
    
    return report
