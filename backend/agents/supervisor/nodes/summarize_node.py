from __future__ import annotations

import logging
from typing import Any, Optional, Union

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client

from ..models import SupervisorState

logger = logging.getLogger(__name__)


def _safe_round(value: Optional[Union[int, float]], digits: int = 1) -> str:
    """None-safe round 함수. None이면 'N/A' 반환."""
    if value is None:
        return "N/A"
    try:
        return str(round(float(value), digits))
    except (TypeError, ValueError):
        return "N/A"


SUMMARIZE_SYSTEM_PROMPT = """
당신은 오픈소스 프로젝트 분석 결과를 요약하는 전문가입니다.
진단 결과 JSON 데이터를 사용자가 이해하기 쉽게 한국어로 요약해 주세요.

## 핵심 원칙
1. **제공된 데이터에 있는 숫자만 사용** - 데이터에 없는 숫자를 만들어 내지 마세요
2. 핵심 정보를 간결하게 전달
3. 마크다운 형식 사용 (##, ###, -, ** 등)
4. 이모지나 이모티콘 사용 금지

## 숫자 사용 규칙 (매우 중요!)
- "활동성 데이터" 섹션에 있는 숫자를 그대로 인용하세요
- 예: "총 커밋 수: 100건" → "최근 90일간 100건의 커밋"
- 예: "고유 기여자 수: 19명" → "19명의 기여자"
- 예: "기간 내 생성된 이슈: 229건" → "229건의 이슈 생성"
- 예: "기간 내 PR 수: 616건, 병합된 PR: 386건" → "616건의 PR 중 386건 병합"

## 점수 해석 가이드 (100점 만점) - 반드시 이 표현만 사용!
- 90-100점: 매우 우수
- 80-89점: 우수
- 70-79점: 양호
- 60-69점: 보통
- 60점 미만: 개선 필요

점수 설명에 사용할 표현은 위 구간 정의(매우 우수/우수/양호/보통/개선 필요) 중 하나로 제한하세요.

## 출력 형식

## {저장소명} 저장소 건강 상태 요약

### 점수 요약
- **전체 건강 점수**: {health_score}점 ({해석})
- **문서 품질**: {documentation_quality}점 ({이유})
- **활동성**: {activity_maintainability}점 ({이유, 활동성 데이터의 숫자 활용})
- **온보딩 용이성**: {onboarding_score}점 ({이유})

### 주요 특징
- 저장소 설명과 기술적 특징
- 활동성 요약 (제공된 숫자 사용: 커밋 수, 기여자 수, 이슈/PR 현황)

### 개선이 필요한 부분
- 문서에서 누락된 섹션 기반 개선점
- 이슈/PR 처리 속도 관련 개선점

---
**다음으로 이런 것도 해드릴 수 있어요:**
- "이 저장소에서 초보자가 시작하기 좋은 이슈를 찾아줘"
- "비슷한 다른 저장소와 비교해줘"  
- "온보딩 학습 계획을 세워줘"
"""


def summarize_node(state: SupervisorState) -> SupervisorState:
    """
    모든 Agent 결과를 종합하여 사용자에게 최종 응답을 생성합니다.
    """
    diagnosis_result = state.get("diagnosis_result")
    security_result = state.get("security_result")
    recommend_result = state.get("recommend_result")
    history = state.get("history", [])

    # 마지막 사용자 질문 추출 (history 우선, 없으면 state의 user_query fallback)
    user_query = ""
    for turn in reversed(history):
        if turn.get("role") == "user":
            user_query = turn.get("content", "")
            break
    
    # 첫 턴에서는 history가 비어있으므로 state의 user_query 사용
    if not user_query:
        user_query = state.get("user_query", "")

    # 결과 조합
    context_parts = []

    if diagnosis_result:
        context_parts.append(f"## 진단 결과\n{_format_diagnosis(diagnosis_result)}")

    if security_result:
        context_parts.append(f"## 보안 분석\n{_format_result(security_result)}")

    if recommend_result:
        context_parts.append(f"## 추천 정보\n{_format_result(recommend_result)}")

    if not context_parts:
        summary = "분석 결과가 없습니다. 다시 시도해 주세요."
    else:
        context = "\n\n".join(context_parts)
        summary = _generate_summary_with_llm(user_query, context)

    # 벤치마크용 로깅: repo 정보와 함께 기록
    repo = state.get("repo", {})
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}" if repo else "unknown"
    logger.info("[summarize_node] repo=%s, summary_length=%d", repo_id, len(summary))

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    # history에 assistant 응답 추가
    new_history = list(history)
    new_history.append({"role": "assistant", "content": summary})
    new_state["history"] = new_history
    new_state["llm_summary"] = summary

    return new_state


def _format_diagnosis(result: Any) -> str:
    """진단 결과를 문자열로 포맷팅 - LLM에게 명시적으로 데이터 제공"""
    if not isinstance(result, dict):
        return str(result)
    
    parts = []
    
    # 0. 저장소 정보
    details = result.get("details", {})
    repo_info = details.get("repo_info", {})
    if repo_info:
        parts.append("### 저장소 정보")
        parts.append(f"- 이름: {repo_info.get('full_name', 'N/A')}")
        parts.append(f"- 설명: {repo_info.get('description', 'N/A')}")
        parts.append(f"- 스타: {repo_info.get('stars', 'N/A')}")
        parts.append(f"- 포크: {repo_info.get('forks', 'N/A')}")
        parts.append(f"- 오픈 이슈: {repo_info.get('open_issues', 'N/A')}")
    
    # 1. 점수 정보 (필수)
    scores = result.get("scores", {})
    if scores:
        parts.append("\n### 점수 (100점 만점)")
        parts.append(f"- health_score (전체 건강 점수): {scores.get('health_score', 'N/A')}")
        parts.append(f"- documentation_quality (문서 품질): {scores.get('documentation_quality', 'N/A')}")
        parts.append(f"- activity_maintainability (활동성): {scores.get('activity_maintainability', 'N/A')}")
        parts.append(f"- onboarding_score (온보딩 용이성): {scores.get('onboarding_score', 'N/A')}")
        parts.append(f"- is_healthy: {scores.get('is_healthy', 'N/A')}")
    
    # 2. 라벨 정보 (진단 결과 해석)
    labels = result.get("labels", {})
    if labels:
        parts.append("\n### 진단 라벨 (점수 해석)")
        for key, value in labels.items():
            if value:  # None이 아닌 값만
                parts.append(f"- {key}: {value}")
    
    # 3. Activity 메트릭 (실제 숫자 데이터)
    activity = details.get("activity", {})
    if activity:
        parts.append("\n### 활동성 데이터 (최근 90일) - 아래 숫자를 답변에 활용하세요")
        
        commit = activity.get("commit", {})
        if commit:
            parts.append(f"- 총 커밋 수: {commit.get('total_commits', 'N/A')}건")
            parts.append(f"- 고유 기여자 수: {commit.get('unique_authors', 'N/A')}명")
            parts.append(f"- 일 평균 커밋: {_safe_round(commit.get('commits_per_day'))}건")
            parts.append(f"- 마지막 커밋 이후: {commit.get('days_since_last_commit', 'N/A')}일")
        
        issue = activity.get("issue", {})
        if issue:
            parts.append(f"- 현재 오픈 이슈: {issue.get('open_issues', 'N/A')}건")
            parts.append(f"- 기간 내 생성된 이슈: {issue.get('opened_issues_in_window', 'N/A')}건")
            parts.append(f"- 기간 내 해결된 이슈: {issue.get('closed_issues_in_window', 'N/A')}건")
            closure_ratio = issue.get('issue_closure_ratio')
            if closure_ratio is not None:
                parts.append(f"- 이슈 해결 비율: {_safe_round(closure_ratio * 100)}%")
            avg_age = issue.get('avg_open_issue_age_days')
            if avg_age is not None:
                parts.append(f"- 오픈 이슈 평균 수명: {_safe_round(avg_age, 0)}일")
        
        pr = activity.get("pr", {})
        if pr:
            parts.append(f"- 기간 내 PR 수: {pr.get('prs_in_window', 'N/A')}건")
            parts.append(f"- 병합된 PR: {pr.get('merged_in_window', 'N/A')}건")
            merge_ratio = pr.get('pr_merge_ratio')
            if merge_ratio is not None:
                parts.append(f"- PR 병합 비율: {_safe_round(merge_ratio * 100)}%")
            parts.append(f"- 현재 오픈 PR: {pr.get('open_prs', 'N/A')}건")
    
    # 4. 문서 정보
    docs = details.get("docs", {})
    if docs:
        parts.append("\n### 문서 분석")
        readme_summary = docs.get("readme_summary_for_user", "")
        if readme_summary:
            # 요약은 생성 단계에서 이미 길이 제한됨 (300~500자)
            parts.append(f"- README 요약: {readme_summary}")
        categories = docs.get("readme_categories", {})
        if categories:
            present = [k for k, v in categories.items() if v]
            missing = [k for k, v in categories.items() if not v]
            if present:
                parts.append(f"- 포함된 섹션: {', '.join(present)}")
            if missing:
                parts.append(f"- 누락된 섹션: {', '.join(missing)}")
    
    # 5. 온보딩 정보
    onboarding_plan = result.get("onboarding_plan", {})
    if onboarding_plan:
        parts.append("\n### 온보딩 계획")
        setup_time = onboarding_plan.get("estimated_setup_time", "")
        if setup_time:
            parts.append(f"- 예상 설정 시간: {setup_time}")
        steps = onboarding_plan.get("steps", [])
        if steps:
            parts.append(f"- 온보딩 단계 수: {len(steps)}")
    
    return "\n".join(parts) if parts else str(result)


def _format_result(result: Any) -> str:
    """일반 결과를 문자열로 포맷팅"""
    import json
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


def _generate_summary_with_llm(user_query: str, context: str) -> str:
    """LLM을 사용하여 최종 요약 생성"""
    import os
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

    user_message = f"""
사용자 질문: {user_query}

분석 결과:
{context}

위 결과를 바탕으로 사용자 질문에 답변해 주세요.
"""

    request = ChatRequest(
        model=model_name,
        messages=[
            ChatMessage(role="system", content=SUMMARIZE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        ],
        temperature=0.3,
    )

    try:
        response = llm_client.chat(request, timeout=90)
        return response.content

    except Exception as e:
        logger.error("[summarize_node] LLM 호출 실패: %s", e)
        return f"요약 생성 중 오류가 발생했습니다: {e}"
