"""
레포트 생성 툴
"""
from langchain_core.tools import tool
from typing import Dict, Any, List, Optional
from datetime import datetime


@tool
def generate_executive_summary(
    owner: str,
    repo: str,
    dependency_count: int,
    security_score: Dict[str, Any],
    vulnerability_count: int = 0
) -> Dict[str, Any]:
    """
    요약 레포트를 생성합니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        dependency_count: 의존성 개수
        security_score: 보안 점수
        vulnerability_count: 취약점 개수 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - summary: str (요약문)
        - error: str (if failed)
    """
    try:
        grade = security_score.get("grade", "N/A")
        score = security_score.get("score", 0)
        
        summary = f"""
# Security Analysis Report

**Repository**: {owner}/{repo}  
**Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

- **Total Dependencies**: {dependency_count}
- **Security Score**: {score}/100
- **Security Grade**: {grade}
- **Vulnerabilities Found**: {vulnerability_count}

"""
        
        # 등급에 따른 요약 추가
        if grade == "A":
            summary += "✅ **Excellent security posture.** The repository demonstrates best practices in dependency management.\n"
        elif grade == "B":
            summary += "👍 **Good security posture.** Some minor improvements recommended.\n"
        elif grade == "C":
            summary += "⚠️ **Fair security posture.** Several improvements needed.\n"
        elif grade == "D":
            summary += "⚠️ **Poor security posture.** Significant improvements required.\n"
        else:
            summary += "❌ **Critical security issues detected.** Immediate action required.\n"
        
        return {
            "success": True,
            "summary": summary
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": ""
        }


@tool
def generate_dependency_report(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    의존성 상세 레포트를 생성합니다.

    Args:
        analysis_result: analyze_dependencies의 결과

    Returns:
        Dict containing:
        - success: bool
        - report: str (레포트 내용)
        - error: str (if failed)
    """
    try:
        total_deps = analysis_result.get("total_dependencies", 0)
        total_files = analysis_result.get("total_files", 0)
        summary = analysis_result.get("summary", {})
        
        report = f"""
## Dependency Analysis

**Total Dependency Files**: {total_files}  
**Total Unique Dependencies**: {total_deps}

### Dependencies by Package Manager

"""
        
        by_source = summary.get("by_source", {})
        for source, count in by_source.items():
            report += f"- **{source}**: {count} packages\n"
        
        report += f"""

### Dependencies by Type

- **Runtime**: {summary.get('runtime_dependencies', 0)}
- **Development**: {summary.get('dev_dependencies', 0)}
- **Total Unique**: {summary.get('total_unique', 0)}

"""
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "report": ""
        }


@tool
def generate_recommendations_report(suggestions: List[str]) -> Dict[str, Any]:
    """
    개선 권장사항 레포트를 생성합니다.

    Args:
        suggestions: 개선 제안 목록

    Returns:
        Dict containing:
        - success: bool
        - report: str (레포트 내용)
        - error: str (if failed)
    """
    try:
        report = """
## Recommendations

"""
        
        if not suggestions or len(suggestions) == 0:
            report += "No specific recommendations at this time. Keep up the good work!\n"
        else:
            for i, suggestion in enumerate(suggestions, 1):
                report += f"{i}. {suggestion}\n"
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "report": ""
        }


@tool
def generate_full_report(
    owner: str,
    repo: str,
    dependency_count: int,
    security_score: Dict[str, Any],
    analysis_result: Dict[str, Any],
    suggestions: List[str],
    vulnerability_count: int = 0
) -> Dict[str, Any]:
    """
    전체 레포트를 생성합니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        dependency_count: 의존성 개수
        security_score: 보안 점수
        analysis_result: 의존성 분석 결과
        suggestions: 개선 제안 목록
        vulnerability_count: 취약점 개수 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - report: str (전체 레포트)
        - error: str (if failed)
    """
    try:
        # 각 섹션 생성
        exec_summary = generate_executive_summary.invoke({
            "owner": owner,
            "repo": repo,
            "dependency_count": dependency_count,
            "security_score": security_score,
            "vulnerability_count": vulnerability_count
        })

        dep_report = generate_dependency_report.invoke({
            "analysis_result": analysis_result
        })

        rec_report = generate_recommendations_report.invoke({
            "suggestions": suggestions
        })
        
        # 전체 레포트 조합
        full_report = ""
        if exec_summary.get("success"):
            full_report += exec_summary.get("summary", "")
        
        if dep_report.get("success"):
            full_report += dep_report.get("report", "")
        
        if rec_report.get("success"):
            full_report += rec_report.get("report", "")
        
        full_report += f"""
---

*Report generated by Security Analysis Agent*  
*Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        return {
            "success": True,
            "report": full_report
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "report": ""
        }


@tool
def export_report(report_content: str, output_format: str = "markdown", file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    레포트를 파일로 저장합니다.

    Args:
        report_content: 레포트 내용
        output_format: 출력 형식 ("markdown", "text")
        file_path: 저장 경로 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - file_path: str
        - error: str (if failed)
    """
    try:
        import os
        
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = "md" if output_format == "markdown" else "txt"
            file_path = f"security_report_{timestamp}.{ext}"
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # 절대 경로 반환
        abs_path = os.path.abspath(file_path)
        
        return {
            "success": True,
            "file_path": abs_path,
            "format": output_format
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "file_path": ""
        }
