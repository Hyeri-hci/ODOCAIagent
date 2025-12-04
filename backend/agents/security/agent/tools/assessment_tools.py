"""
보안 평가 툴
"""
from langchain_core.tools import tool
from typing import Dict, Any, List, Optional


@tool
def calculate_security_score(
    analysis_result: Dict[str, Any],
    vulnerability_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    보안 점수를 계산합니다.

    Args:
        analysis_result: analyze_dependencies의 결과
        vulnerability_result: 취약점 조회 결과 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - score: int (0-100)
        - grade: str (A, B, C, D, F)
        - factors: Dict (점수 구성 요소)
        - error: str (if failed)
    """
    try:
        from ...tools.vulnerability_checker import get_security_score
        
        score_result = get_security_score(analysis_result, vulnerability_result)
        
        return {
            "success": True,
            **score_result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "score": 0,
            "grade": "F",
            "factors": {}
        }


@tool
def suggest_improvements(
    analysis_result: Dict[str, Any],
    vulnerability_result: Optional[Dict[str, Any]] = None,
    security_score: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    보안 개선 사항을 제안합니다.

    Args:
        analysis_result: analyze_dependencies의 결과
        vulnerability_result: 취약점 조회 결과 (옵션)
        security_score: 보안 점수 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - suggestions: List[str] (개선 제안 목록)
        - count: int
        - error: str (if failed)
    """
    try:
        from ...tools.vulnerability_checker import suggest_security_improvements
        
        suggestions = suggest_security_improvements(
            analysis_result,
            vulnerability_result,
            security_score
        )
        
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestions": [],
            "count": 0
        }


@tool
def check_license_compliance(
    analysis_result: Dict[str, Any],
    allowed_licenses: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    라이센스 준수 여부를 확인합니다. (향후 구현 예정)

    Args:
        analysis_result: analyze_dependencies의 결과
        allowed_licenses: 허용된 라이센스 목록 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - compliant: bool
        - violations: List[Dict] (위반 항목)
        - error: str (if failed)
    """
    # 향후 구현 예정
    return {
        "success": False,
        "error": "License checking not implemented yet",
        "compliant": True,
        "violations": []
    }


@tool
def assess_risk_level(security_score: Dict[str, Any], vulnerability_count: int = 0) -> Dict[str, Any]:
    """
    위험도 수준을 평가합니다.

    Args:
        security_score: 보안 점수
        vulnerability_count: 취약점 개수 (옵션)

    Returns:
        Dict containing:
        - success: bool
        - risk_level: str ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        - description: str
    """
    try:
        score = security_score.get("score", 0)
        
        # 점수 기반 위험도 평가
        if score >= 90:
            risk_level = "LOW"
            description = "보안 상태가 매우 양호합니다."
        elif score >= 75:
            risk_level = "MEDIUM"
            description = "보안 상태가 양호하나 일부 개선이 필요합니다."
        elif score >= 50:
            risk_level = "HIGH"
            description = "보안 위험이 높습니다. 즉각적인 개선이 필요합니다."
        else:
            risk_level = "CRITICAL"
            description = "심각한 보안 위험이 있습니다. 긴급 조치가 필요합니다."
        
        # 취약점 수에 따라 위험도 상향 조정
        if vulnerability_count > 10:
            if risk_level == "LOW":
                risk_level = "MEDIUM"
            elif risk_level == "MEDIUM":
                risk_level = "HIGH"
            elif risk_level == "HIGH":
                risk_level = "CRITICAL"
        
        return {
            "success": True,
            "risk_level": risk_level,
            "description": description,
            "score": score,
            "vulnerability_count": vulnerability_count
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "risk_level": "UNKNOWN",
            "description": ""
        }
