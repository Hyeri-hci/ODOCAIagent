"""
레포트 생성 노드
"""
from typing import Dict, Any
from ..state import SecurityAnalysisState
from ..tools import generate_full_report


def generate_report_node(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    레포트 생성 노드: 최종 분석 레포트 생성

    Args:
        state: SecurityAnalysisState

    Returns:
        Dict: State 업데이트
    """
    owner = state.get("owner")
    repository = state.get("repository")
    dependencies = state.get("dependencies", {})
    security_score = state.get("security_score", {})
    recommendations = state.get("recommendations", [])
    dependency_count = state.get("dependency_count", 0)
    vulnerability_count = state.get("vulnerability_count", 0)
    
    print(f"\n[REPORT] Generating Final Report...")
    print(f"{'─' * 60}\n")
    
    try:
        result = generate_full_report.invoke({
            "owner": owner,
            "repo": repository,
            "dependency_count": dependency_count,
            "security_score": security_score,
            "analysis_result": dependencies,
            "suggestions": recommendations,
            "vulnerability_count": vulnerability_count
        })
        
        if result.get("success"):
            report = result.get("report", "")
            print("[OK] Report generated successfully!\n")
            print(f"{'='*60}")
            print(report)
            print(f"{'='*60}\n")
            
            return {
                "report": report,
                "current_step": "report_generated",
                "completed": True,
                "final_result": {
                    "owner": owner,
                    "repository": repository,
                    "dependency_count": dependency_count,
                    "security_score": security_score,
                    "recommendations": recommendations,
                    "report": report
                },
                "messages": ["최종 레포트 생성 완료"]
            }
        else:
            print(f"[ERROR] Report generation failed: {result.get('error')}\n")
            return {
                "errors": [f"레포트 생성 실패: {result.get('error')}"],
                "current_step": "report_failed",
                "completed": True,
                "messages": ["레포트 생성 중 오류 발생"]
            }
    
    except Exception as e:
        print(f"[ERROR] Exception during report generation: {str(e)}\n")
        return {
            "errors": [f"레포트 생성 중 오류: {str(e)}"],
            "current_step": "report_failed",
            "completed": True,
            "messages": [f"오류 발생: {str(e)}"]
        }
