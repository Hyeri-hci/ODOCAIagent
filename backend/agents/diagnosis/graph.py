"""DiagnosisAgent - LangGraph 서브그래프 (Refactored)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_documentation
from backend.core.activity_core import analyze_activity
from backend.core.structure_core import analyze_structure
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_diagnosis
from backend.core.models import RepoSnapshot

from backend.agents.supervisor.state import SupervisorState

logger = logging.getLogger(__name__)


def fetch_repo_data_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 1: GitHub 데이터 fetch → state['repo_snapshot']에 저장."""
    owner = state.get("owner", "")
    repo = state.get("repo", "")
    repo_ref = state.get("repo_ref", "HEAD")

    if not owner or not repo:
        return {"error_message": "owner/repo가 필요합니다."}

    try:
        snapshot = fetch_repo_snapshot(owner, repo, repo_ref)
    except Exception as e:
        logger.error("Failed to fetch repo snapshot: %s", e)
        return {"error_message": f"저장소 조회 실패: {e}"}

    return {"repo_snapshot": snapshot}


def run_diagnosis_core_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 2: Core 레이어 진단 실행."""
    snapshot: Optional[RepoSnapshot] = state.get("repo_snapshot")

    if not snapshot:
        return {"error_message": "저장소 스냅샷이 없습니다."}

    project_rules = state.get("project_rules")

    try:
        # 1. 의존성 파싱
        deps = parse_dependencies(snapshot)
        
        # 2. 문서 분석
        docs_result = analyze_documentation(snapshot.readme_content)
        
        # 3. 활동성 분석
        activity_result = analyze_activity(snapshot.owner, snapshot.repo)
        
        # 4. 구조 분석 (state에는 저장 안 하지만 로직상 실행)
        # structure_result = analyze_structure(snapshot.owner, snapshot.repo, snapshot.ref)

        # 5. 최종 진단 계산
        diagnosis = compute_diagnosis(
            repo_id=snapshot.repo_id,
            docs_result=docs_result,
            activity_result=activity_result,
            project_rules=project_rules,
        )
    except Exception as e:
        logger.error("Diagnosis core failed: %s", e)
        return {"error_message": f"진단 실행 실패: {e}"}

    return {
        "dependency_snapshot": deps,
        "diagnosis_result": diagnosis,
        "docs_result": docs_result,
    }


def summarize_diagnosis_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 3: LLM으로 진단 요약 메시지 생성 → messages에 추가."""
    diagnosis = state.get("diagnosis_result")
    guidelines = state.get("session_guidelines")

    if not diagnosis:
        return {
            "messages": [AIMessage(content="진단 결과가 없습니다.")],
            "last_answer_kind": "diagnosis", # Error but return diagnosis kind to end
        }

    user_level = guidelines.user_level if guidelines else "beginner"
    language = guidelines.preferred_language if guidelines else "ko"

    system_prompt = _build_diagnosis_system_prompt(user_level, language)
    user_prompt = _build_diagnosis_user_prompt(diagnosis)

    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatMessage, ChatRequest

        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        response = client.chat(request)
        summary = response.content.strip()
    except Exception as e:
        logger.error("LLM summarization failed: %s", e)
        summary = _build_fallback_summary(diagnosis)

    return {
        "messages": [AIMessage(content=summary)],
        "last_answer_kind": "diagnosis",
    }


def _build_diagnosis_system_prompt(user_level: str, language: str) -> str:
    if language == "ko":
        return f"""당신은 오픈소스 프로젝트 분석 전문가입니다.
사용자 수준: {user_level}
- beginner: 쉬운 용어로 설명, 다음 단계 안내
- intermediate: 기술적 세부사항 포함
- advanced: 메트릭 공식과 개선 제안 포함

진단 결과를 한국어로 명확하게 요약해 주세요."""
    return f"""You are an open source project analysis expert.
User level: {user_level}
Summarize the diagnosis results clearly."""


def _build_diagnosis_user_prompt(diagnosis) -> str:
    return f"""## 진단 결과

- 저장소: {diagnosis.repo_id}
- 건강 점수: {diagnosis.health_score}/100 ({diagnosis.health_level})
- 문서 품질: {diagnosis.documentation_quality}/100
- 활동성: {diagnosis.activity_maintainability}/100
- 온보딩 점수: {diagnosis.onboarding_score}/100 ({diagnosis.onboarding_level})
- 건강 상태: {'양호' if diagnosis.is_healthy else '개선 필요'}

### 이슈
- 문서: {', '.join(diagnosis.docs_issues) or '없음'}
- 활동성: {', '.join(diagnosis.activity_issues) or '없음'}

위 데이터를 바탕으로 사용자에게 요약을 제공해 주세요."""


def _build_fallback_summary(diagnosis) -> str:
    status = "양호" if diagnosis.is_healthy else "개선 필요"
    return f"""### {diagnosis.repo_id} 분석 결과

| 지표 | 점수 | 상태 |
|------|------|------|
| 건강 점수 | {diagnosis.health_score} | {diagnosis.health_level} |
| 문서 품질 | {diagnosis.documentation_quality} | - |
| 활동성 | {diagnosis.activity_maintainability} | - |
| 온보딩 | {diagnosis.onboarding_score} | {diagnosis.onboarding_level} |

**상태**: {status}"""


def build_diagnosis_agent_graph() -> StateGraph:
    """DiagnosisAgent 그래프 빌드."""
    graph = StateGraph(SupervisorState)

    graph.add_node("fetch_repo_data", fetch_repo_data_node)
    graph.add_node("run_diagnosis_core", run_diagnosis_core_node)
    graph.add_node("summarize_diagnosis", summarize_diagnosis_node)

    graph.set_entry_point("fetch_repo_data")
    graph.add_edge("fetch_repo_data", "run_diagnosis_core")
    graph.add_edge("run_diagnosis_core", "summarize_diagnosis")
    graph.add_edge("summarize_diagnosis", END)

    return graph


def get_diagnosis_agent():
    """컴파일된 DiagnosisAgent 반환."""
    graph = build_diagnosis_agent_graph()
    return graph.compile()
