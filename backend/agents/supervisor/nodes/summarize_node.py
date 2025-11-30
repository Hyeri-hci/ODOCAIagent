from __future__ import annotations

import logging
from typing import Any, Optional, Union

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.diagnosis.tools.onboarding_tasks import (
    OnboardingTasks,
    TaskSuggestion,
    filter_tasks_for_user,
)

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
4. **이모지/이모티콘 절대 사용 금지** - 별, 하트, 체크마크, 화살표, 불꽃, 로켓 등 모든 이모지 기호 사용 금지

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

### 추천 시작 Task
- "추천 Task" 섹션에 있는 Task를 간략히 소개 (제목, 난이도, 링크)
- 왜 이 Task가 적합한지 한 줄 설명

### 개선이 필요한 부분
- 문서에서 누락된 섹션 기반 개선점
- 이슈/PR 처리 속도 관련 개선점

---
**다음으로 이런 것도 해드릴 수 있어요:**
- "이 저장소에서 초보자가 시작하기 좋은 이슈를 찾아줘"
- "비슷한 다른 저장소와 비교해줘"  
- "온보딩 학습 계획을 세워줘"
"""

SUMMARIZE_ONBOARDING_PROMPT = """
당신은 오픈소스 프로젝트에 기여할 수 있도록 도와주는 온보딩 전문가입니다.
진단 결과와 온보딩 Task 데이터를 바탕으로, 사용자 레벨에 맞는 기여 방법을 추천해 주세요.

## 핵심 원칙
1. **온보딩 Task 추천이 주요 목적** - 점수 설명은 간략히
2. 제공된 데이터에 있는 숫자만 사용
3. 마크다운 형식 사용
4. **이모지/이모티콘 절대 사용 금지** - 별, 하트, 체크마크, 화살표, 불꽃, 로켓 등 모든 이모지 기호 사용 금지
5. **사용자 레벨({user_level})에 맞는 Task를 추천** - "추천 Task" 섹션에 있는 Task 사용

## 사용자 레벨별 추천 방향
- **초보자(beginner)**: 문서, 테스트, 간단한 버그 수정 위주
- **중급자(intermediate)**: 버그 수정, 기능 개선, 코드 리팩토링
- **고급자(advanced)**: 코어 아키텍처, 성능 최적화, 복잡한 문제 해결

## 난이도 안내 (중요!)
- 사용자 레벨에 맞는 Task가 부족할 경우, 다른 레벨의 Task가 포함될 수 있습니다.
- Task에 "(난이도 주의)" 표시가 있으면, 해당 Task가 사용자 레벨보다 어렵다는 것을 알려주세요.
- 예: 초보자에게 중급/고급 Task를 추천할 때 → "이 Task는 난이도가 조금 있지만, 도전해볼 만합니다" 등의 안내 추가

## 출력 형식

## {{저장소명}} {level_kr} 기여 가이드

### 저장소 개요
- 프로젝트 설명 (1-2문장)
- **온보딩 용이성**: {{onboarding_score}}점
- **예상 설정 시간**: {{estimated_setup_time}}

### 추천 시작 Task ({level_kr}용)
각 Task를 다음 형식으로 작성:

**1. [이슈 제목]**
- 링크: (GitHub 이슈 URL)
- 난이도: 쉼움/보통/어려움
- 예상 시간: N시간
- {level_kr}에게 좋은 이유: (간단한 설명)

### 시작하기 전 체크리스트
- CONTRIBUTING.md 읽기
- 개발 환경 설정
- 기존 코드 구조 파악

---
**더 도움이 필요하시면:**
- "이 Task에 대해 더 자세히 설명해줘"
- "온보딩 학습 계획을 세워줘"
- "비슷한 다른 저장소도 추천해줘"
"""


def _get_onboarding_prompt(user_level: str) -> str:
    """사용자 레벨에 맞는 온보딩 프롬프트 생성"""
    level_kr = {
        "beginner": "초보자",
        "intermediate": "중급자",
        "advanced": "고급자"
    }.get(user_level, "초보자")
    
    return SUMMARIZE_ONBOARDING_PROMPT.format(
        user_level=user_level,
        level_kr=level_kr,
    )


def summarize_node(state: SupervisorState) -> SupervisorState:
    """
    모든 Agent 결과를 종합하여 사용자에게 최종 응답을 생성합니다.
    """
    diagnosis_result = state.get("diagnosis_result")
    security_result = state.get("security_result")
    recommend_result = state.get("recommend_result")
    history = state.get("history", [])
    
    # 온보딩 모드 판단: intent가 onboarding이거나 user_context.level이 beginner
    intent = state.get("intent", "")
    user_context = state.get("user_context", {})
    is_onboarding_mode = (
        intent == "diagnose_repo_onboarding" or
        user_context.get("level") == "beginner"
    )

    # 마지막 사용자 질문 추출 (history 우선, 없으면 state의 user_query fallback)
    user_query = ""
    for turn in reversed(history):
        if turn.get("role") == "user":
            user_query = turn.get("content", "")
            break
    
    # 첫 턴에서는 history가 비어있으므로 state의 user_query 사용
    if not user_query:
        user_query = state.get("user_query", "")

    # 사용자 레벨 추출 (beginner/intermediate/advanced)
    user_level = user_context.get("level", "beginner")  # 기본값: beginner

    # 결과 조합
    context_parts = []

    if diagnosis_result:
        context_parts.append(f"## 진단 결과\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")

    if security_result:
        context_parts.append(f"## 보안 분석\n{_format_result(security_result)}")

    if recommend_result:
        context_parts.append(f"## 추천 정보\n{_format_result(recommend_result)}")

    if not context_parts:
        summary = "분석 결과가 없습니다. 다시 시도해 주세요."
    else:
        context = "\n\n".join(context_parts)
        summary = _generate_summary_with_llm(user_query, context, is_onboarding_mode, user_level)

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


def _format_diagnosis(result: Any, is_onboarding_mode: bool = False, user_level: str = "beginner") -> str:
    """
    진단 결과를 문자열로 포맷팅 - LLM에게 명시적으로 데이터 제공
    
    Args:
        result: 진단 결과 딕셔너리
        is_onboarding_mode: 온보딩 모드 여부 (True이면 온보딩 Task 5개 강조)
        user_level: 사용자 레벨 (beginner/intermediate/advanced)
    """
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
    
    # 6. 온보딩 Task (레벨별 필터링 적용)
    onboarding_tasks_raw = result.get("onboarding_tasks", {})
    if onboarding_tasks_raw:
        # dict -> OnboardingTasks 객체로 변환
        onboarding_tasks_obj = _dict_to_onboarding_tasks(onboarding_tasks_raw)
        
        beginner_tasks = onboarding_tasks_raw.get("beginner", [])
        intermediate_tasks = onboarding_tasks_raw.get("intermediate", [])
        advanced_tasks = onboarding_tasks_raw.get("advanced", [])
        meta = onboarding_tasks_raw.get("meta", {})
        
        # filter_tasks_for_user 함수로 레벨별 필터링 적용
        filtered_tasks = filter_tasks_for_user(
            tasks=onboarding_tasks_obj,
            user_level=user_level,
        )
        
        # 난이도 한글 변환 함수
        def get_difficulty_kr(diff: str) -> str:
            return {"beginner": "쉬움", "intermediate": "보통", "advanced": "어려움"}.get(diff, diff)
        
        # 추천 이유 태그 한글 변환
        reason_map = {
            "good_first_issue": "초보자 환영 이슈",
            "help_wanted": "도움 필요",
            "docs_issue": "문서 관련",
            "test_issue": "테스트 관련",
            "hacktoberfest": "Hacktoberfest 대상",
            "difficulty_beginner": "초보자 난이도",
        }
        
        level_kr = {
            "beginner": "초보자",
            "intermediate": "중급자", 
            "advanced": "고급자"
        }.get(user_level, "초보자")
        
        # 난이도 불일치 체크 함수
        def get_difficulty_mismatch_note(task_difficulty: str) -> str:
            """사용자 레벨과 Task 난이도가 다를 때 안내 문구 반환"""
            difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
            user_order = difficulty_order.get(user_level, 0)
            task_order = difficulty_order.get(task_difficulty, 0)
            
            if task_order > user_order:
                diff = task_order - user_order
                if diff == 1:
                    return " (난이도 주의: 약간 도전적)"
                else:
                    return " (난이도 주의: 상당히 도전적)"
            return ""
        
        if is_onboarding_mode:
            # 온보딩 모드: 상위 5개 Task 상세 정보
            parts.append(f"\n### 추천 온보딩 Task ({level_kr}용) - 아래 정보를 답변에 활용하세요")
            
            # 다른 레벨 Task가 포함되어 있는지 체크
            has_higher_difficulty = any(
                task.difficulty != user_level and 
                {"beginner": 0, "intermediate": 1, "advanced": 2}.get(task.difficulty, 0) > 
                {"beginner": 0, "intermediate": 1, "advanced": 2}.get(user_level, 0)
                for task in filtered_tasks[:5]
            )
            if has_higher_difficulty:
                parts.append(f"\n**참고**: {level_kr}용 Task가 부족하여 일부 난이도가 높은 Task도 포함되어 있습니다.")
            
            selected_tasks = filtered_tasks[:5]
            for i, task in enumerate(selected_tasks, 1):
                mismatch_note = get_difficulty_mismatch_note(task.difficulty)
                parts.append(f"\n**{i}. {task.title}**")
                if task.url:
                    parts.append(f"- 링크: {task.url}")
                parts.append(f"- 난이도: {get_difficulty_kr(task.difficulty)}{mismatch_note}")
                if task.labels:
                    parts.append(f"- 라벨: {', '.join(task.labels[:3])}")
                if task.reason_tags:
                    reasons = [reason_map.get(tag, tag) for tag in task.reason_tags[:2]]
                    parts.append(f"- 추천 이유: {', '.join(reasons)}")
                parts.append(f"- Task 점수: {_safe_round(task.task_score, 0)}점")
        else:
            # 일반 모드: 요약 + 레벨별 Task 3개 추천
            total = meta.get("total_count", 0)
            
            parts.append(f"\n### 온보딩 Task 요약")
            parts.append(f"- 총 Task 수: {total}개")
            parts.append(f"- 초보자용: {len(beginner_tasks)}개")
            parts.append(f"- 중급자용: {len(intermediate_tasks)}개")
            parts.append(f"- 고급자용: {len(advanced_tasks)}개")
            
            # 사용자 레벨에 따라 Task 3개 추천
            selected_tasks = filtered_tasks[:3]
            if selected_tasks:
                parts.append(f"\n### {level_kr} 추천 Task (3개)")
                
                # 다른 레벨 Task가 포함되어 있는지 체크
                has_higher_difficulty = any(
                    task.difficulty != user_level and 
                    {"beginner": 0, "intermediate": 1, "advanced": 2}.get(task.difficulty, 0) > 
                    {"beginner": 0, "intermediate": 1, "advanced": 2}.get(user_level, 0)
                    for task in selected_tasks
                )
                if has_higher_difficulty:
                    parts.append(f"\n**참고**: {level_kr}용 Task가 부족하여 일부 난이도가 높은 Task도 포함되어 있습니다.")
                
                for i, task in enumerate(selected_tasks, 1):
                    mismatch_note = get_difficulty_mismatch_note(task.difficulty)
                    parts.append(f"\n**{i}. {task.title}**")
                    if task.url:
                        parts.append(f"- 링크: {task.url}")
                    parts.append(f"- 난이도: {get_difficulty_kr(task.difficulty)}{mismatch_note}")
    
    return "\n".join(parts) if parts else str(result)


def _dict_to_onboarding_tasks(data: dict) -> OnboardingTasks:
    """
    dict 형태의 onboarding_tasks를 OnboardingTasks 객체로 변환.
    filter_tasks_for_user 함수에서 사용하기 위함.
    """
    def dict_to_task(d: dict) -> TaskSuggestion:
        return TaskSuggestion(
            kind=d.get("kind", "issue"),
            difficulty=d.get("difficulty", "beginner"),
            level=d.get("level", 1),
            id=d.get("id", ""),
            title=d.get("title", ""),
            url=d.get("url"),
            labels=d.get("labels", []),
            reason_tags=d.get("reason_tags", []),
            meta_flags=d.get("meta_flags", []),
            fallback_reason=d.get("fallback_reason"),
            intent=d.get("intent", "contribute"),
            task_score=d.get("task_score", 0.0),
            recency_days=d.get("recency_days"),
            comment_count=d.get("comment_count", 0),
        )
    
    beginner = [dict_to_task(t) for t in data.get("beginner", [])]
    intermediate = [dict_to_task(t) for t in data.get("intermediate", [])]
    advanced = [dict_to_task(t) for t in data.get("advanced", [])]
    meta = data.get("meta", {})
    
    return OnboardingTasks(
        beginner=beginner,
        intermediate=intermediate,
        advanced=advanced,
        total_count=meta.get("total_count", 0),
        issue_count=meta.get("issue_count", 0),
        meta_count=meta.get("meta_count", 0),
    )


def _format_result(result: Any) -> str:
    """일반 결과를 문자열로 포맷팅"""
    import json
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


def _generate_summary_with_llm(
    user_query: str, 
    context: str, 
    is_onboarding_mode: bool = False,
    user_level: str = "beginner"
) -> str:
    """
    LLM을 사용하여 최종 요약 생성
    
    Args:
        user_query: 사용자 질문
        context: 진단 결과 컨텍스트
        is_onboarding_mode: 온보딩 모드 여부 (True면 온보딩 프롬프트 사용)
        user_level: 사용자 레벨 (beginner/intermediate/advanced)
    """
    import os
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    # 온보딩 모드에 따라 프롬프트 선택 (레벨 반영)
    if is_onboarding_mode:
        system_prompt = _get_onboarding_prompt(user_level)
    else:
        system_prompt = SUMMARIZE_SYSTEM_PROMPT

    user_message = f"""
사용자 질문: {user_query}

분석 결과:
{context}

위 결과를 바탕으로 사용자 질문에 답변해 주세요.
"""

    request = ChatRequest(
        model=model_name,
        messages=[
            ChatMessage(role="system", content=system_prompt),
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
