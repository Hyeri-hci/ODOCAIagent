"""
Export 엔드포인트 - 리포트 내보내기
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ExportReportRequest(BaseModel):
    """리포트 내보내기 요청."""
    report_type: str = Field(..., description="diagnosis | onboarding | security")
    owner: str = Field(..., description="저장소 소유자")
    repo: str = Field(..., description="저장소 이름")
    data: Dict[str, Any] = Field(..., description="리포트 데이터")
    include_ai_trace: bool = Field(default=True, description="AI 판단 과정 포함")


@router.post("/export/report")
async def export_report(request: ExportReportRequest):
    """
    분석 결과를 Markdown 리포트로 내보내기.
    
    지원 리포트 유형:
    - diagnosis: 진단 리포트
    - onboarding: 온보딩 가이드
    - security: 보안 분석 리포트
    """
    from backend.common.report_exporter import (
        export_diagnosis_report,
        export_onboarding_guide,
        export_security_report
    )
    
    try:
        if request.report_type == "diagnosis":
            markdown_content = export_diagnosis_report(
                result=request.data,
                owner=request.owner,
                repo=request.repo,
                include_ai_trace=request.include_ai_trace
            )
        elif request.report_type == "onboarding":
            experience_level = request.data.get("experience_level", "beginner")
            markdown_content = export_onboarding_guide(
                plan=request.data,
                owner=request.owner,
                repo=request.repo,
                experience_level=experience_level
            )
        elif request.report_type == "security":
            markdown_content = export_security_report(
                result=request.data,
                owner=request.owner,
                repo=request.repo
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 리포트 유형: {request.report_type}"
            )
        
        # Markdown 파일로 반환
        filename = f"{request.owner}_{request.repo}_{request.report_type}_report.md"
        
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Report export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
