"""
Diagnosis Service - 진단 에이전트의 메인 진입점
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.agents.diagnosis.models import DiagnosisInput, DiagnosisOutput
from backend.agents.diagnosis.graph import run_diagnosis as run_diagnosis_graph

logger = logging.getLogger(__name__)


async def run_diagnosis(input_data: DiagnosisInput) -> DiagnosisOutput:
    """진단 서비스 메인 진입점 - DiagnosisInput을 받아 DiagnosisOutput 반환."""
    owner = input_data.owner
    repo = input_data.repo
    ref = input_data.ref or "main"
    analysis_depth = input_data.analysis_depth or "standard"
    
    logger.info(f"Running diagnosis for {owner}/{repo} (depth={analysis_depth})")
    
    try:
        result_dict = await run_diagnosis_graph(
            owner=owner,
            repo=repo,
            ref=ref,
            user_message=f"{owner}/{repo} 저장소를 진단해주세요",
            supervisor_intent={
                "task_type": "diagnose_repo",
                "analysis_depth": analysis_depth
            }
        )
        
        if result_dict.get("error"):
            raise RuntimeError(result_dict["error"])
        
        output = DiagnosisOutput(
            repo_id=result_dict.get("repo_id", f"{owner}/{repo}"),
            health_score=float(result_dict.get("health_score", 0)),
            health_level=result_dict.get("health_level", "Fair"),
            onboarding_score=float(result_dict.get("onboarding_score", 0)),
            onboarding_level=result_dict.get("onboarding_level", "Fair"),
            docs=result_dict.get("docs", {}),
            activity=result_dict.get("activity", {}),
            structure=result_dict.get("structure", {}),
            dependency_complexity_score=result_dict.get("dependency_complexity_score", 0),
            dependency_flags=list(result_dict.get("dependency_flags", [])),
            stars=result_dict.get("stars", 0),
            forks=result_dict.get("forks", 0),
            summary_for_user=result_dict.get("summary_for_user", "진단이 완료되었습니다."),
            raw_metrics=result_dict.get("raw_metrics", {})
        )
        
        logger.info(f"Diagnosis completed: {owner}/{repo}, health={output.health_score}")
        return output
        
    except Exception as e:
        logger.error(f"Diagnosis failed for {owner}/{repo}: {e}", exc_info=True)
        raise RuntimeError(f"진단 실행 실패: {e}")
