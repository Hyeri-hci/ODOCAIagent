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
- 난이도: 쉬움/보통/어려움
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

# ============================================================================
# Intent별 프롬프트 정의
# ============================================================================

EXPLAIN_SCORES_PROMPT = """
당신은 오픈소스 프로젝트 건강 지표를 설명하는 전문가입니다.
사용자가 특정 점수에 대해 질문하면, 해당 점수가 어떻게 계산되었는지 상세히 설명해 주세요.

## 핵심 원칙
1. **점수 계산 방식을 명확히 설명** - 어떤 요소들이 점수에 영향을 미쳤는지
2. 제공된 데이터의 숫자를 근거로 설명
3. 마크다운 형식 사용
4. **이모지/이모티콘 절대 사용 금지**

## 점수별 설명 가이드

### health_score (전체 건강 점수)
- 다른 모든 점수의 가중 평균
- 문서 품질, 활동성, 온보딩 용이성 등을 종합

### documentation_quality (문서 품질)
- README 존재 여부 및 완성도
- CONTRIBUTING.md, CODE_OF_CONDUCT.md 등 기여 가이드 문서
- 필수 섹션 포함 여부 (설치 방법, 사용 예시, 라이선스 등)

### activity_maintainability (활동성/유지보수성)
- 최근 90일간 커밋 수, 기여자 수
- 이슈/PR 처리 속도 및 비율
- 마지막 커밋 이후 경과 시간

### onboarding_score (온보딩 용이성)
- 초보자 친화적 이슈 라벨 (good first issue, help wanted 등)
- 문서 품질과 기여 가이드 완성도
- 예상 설정 시간

## 출력 형식

## {저장소명} 점수 상세 설명

### 질문하신 점수: {점수명}
- **현재 점수**: {N}점 ({해석: 매우 우수/우수/양호/보통/개선 필요})

### 점수 산정 근거
1. **{요소1}**: {상세 설명 + 실제 데이터}
2. **{요소2}**: {상세 설명 + 실제 데이터}
...

### 점수 개선 방법
- {구체적인 개선 제안}

---
**추가 질문:**
- "다른 점수도 설명해줘"
- "이 점수를 올리려면 어떻게 해야 해?"
"""

COMPARE_REPOS_PROMPT = """
당신은 오픈소스 프로젝트를 비교 분석하는 전문가입니다.
두 저장소의 건강 상태를 비교하여 각각의 장단점을 분석해 주세요.

## 핵심 원칙
1. **객관적 비교** - 두 저장소를 공정하게 비교
2. 제공된 데이터의 숫자를 근거로 비교
3. 마크다운 표 형식 활용
4. **이모지/이모티콘 절대 사용 금지**

## 출력 형식

## 저장소 비교: {저장소A} vs {저장소B}

### 점수 비교표
| 지표 | {저장소A} | {저장소B} | 우위 |
|------|----------|----------|------|
| 전체 건강 점수 | N점 | M점 | {A/B} |
| 문서 품질 | N점 | M점 | {A/B} |
| 활동성 | N점 | M점 | {A/B} |
| 온보딩 용이성 | N점 | M점 | {A/B} |

### {저장소A}의 강점
- ...

### {저장소B}의 강점
- ...

### 기여자 관점 추천
- 초보자에게 더 적합한 저장소: {추천 및 이유}
- 활발한 커뮤니티를 원한다면: {추천 및 이유}

---
**추가 분석:**
- "각 저장소의 온보딩 Task를 비교해줘"
- "어떤 저장소가 더 활발해?"
"""

REFINE_TASKS_PROMPT = """
당신은 오픈소스 기여 Task를 추천하는 전문가입니다.
사용자의 추가 조건에 맞게 Task 목록을 필터링하고 재정렬해 주세요.

## 핵심 원칙
1. **사용자 조건 최우선** - 시간, 난이도, 유형 등 조건 반영
2. 제공된 Task 목록에서만 선택
3. 마크다운 형식 사용
4. **이모지/이모티콘 절대 사용 금지**

## 필터링 기준
- **시간**: 사용자가 투자할 수 있는 시간
- **난이도**: 쉬움/보통/어려움
- **유형**: 문서, 테스트, 버그 수정, 기능 추가 등
- **라벨**: good first issue, help wanted, hacktoberfest 등

## 출력 형식

## 맞춤 Task 추천

### 적용된 필터
- 시간: {N}시간 이내
- 난이도: {조건}
- 유형: {조건}

### 추천 Task (필터 적용 후)

**1. [Task 제목]**
- 링크: (URL)
- 난이도: {난이도}
- 예상 시간: {N}시간
- 선택 이유: {왜 이 조건에 맞는지}

...

### 필터에 맞는 Task가 부족한 경우
- 조건을 완화하면 더 많은 Task를 찾을 수 있습니다
- 예: "시간을 2시간 더 늘리면 N개의 Task 추가 가능"

---
**조건 변경:**
- "시간을 더 늘려줘"
- "더 쉬운 Task만 보여줘"
"""

# ============================================================================
# 프롬프트 빌더 함수들
# ============================================================================

# INTENT_CONFIG 기반 프롬프트 매핑
from ..intent_config import (
    get_prompt_kind,
    is_intent_ready,
    validate_user_level,
    validate_intent,
)

# 프롬프트 종류 -> 프롬프트 상수 매핑
PROMPT_MAP = {
    "health": SUMMARIZE_SYSTEM_PROMPT,
    "explain_scores": EXPLAIN_SCORES_PROMPT,
    "compare": COMPARE_REPOS_PROMPT,
    "refine_tasks": REFINE_TASKS_PROMPT,
    # onboarding은 user_level이 필요하므로 별도 처리
}


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


def _get_prompt_for_intent(intent: str, user_level: str = "beginner") -> str:
    """
    intent에 따라 적절한 시스템 프롬프트 반환
    
    INTENT_CONFIG의 prompt_kind를 기반으로 프롬프트를 선택합니다.
    
    Args:
        intent: 사용자 의도 (diagnose_repo_health, diagnose_repo_onboarding, etc.)
        user_level: 사용자 레벨 (beginner/intermediate/advanced)
    
    Returns:
        해당 intent에 맞는 시스템 프롬프트
    """
    prompt_kind = get_prompt_kind(intent)
    
    # onboarding은 user_level이 필요하므로 별도 처리
    if prompt_kind == "onboarding":
        return _get_onboarding_prompt(user_level)
    
    # 나머지는 PROMPT_MAP에서 조회
    return PROMPT_MAP.get(prompt_kind, SUMMARIZE_SYSTEM_PROMPT)


def _get_not_ready_message(intent: str) -> str:
    """미지원 Intent에 대한 안내 메시지 생성"""
    intent_names = {
        "compare_two_repos": "저장소 비교",
        "refine_onboarding_tasks": "Task 재추천",
    }
    feature_name = intent_names.get(intent, intent)
    return f"""## 기능 준비 중

**{feature_name}** 기능은 현재 개발 중입니다.

### 지금 사용 가능한 기능
- **저장소 건강 상태 분석**: "facebook/react 건강 상태 분석해줘"
- **온보딩 Task 추천**: "초보자인데 react에 기여하고 싶어요"
- **점수 상세 설명**: "이 저장소 점수가 왜 이렇게 나왔어?"

곧 더 많은 기능이 추가될 예정입니다.
"""


def summarize_node(state: SupervisorState) -> SupervisorState:
    """
    모든 Agent 결과를 종합하여 사용자에게 최종 응답을 생성합니다.
    
    Intent별 요약 모드:
    - diagnose_repo_health: Health 리포트 모드
    - diagnose_repo_onboarding: 온보딩 가이드 모드
    - compare_two_repos: 비교 리포트 모드
    - refine_onboarding_tasks: 리랭킹/필터링 모드
    - explain_scores: 지표 설명 모드
    """
    diagnosis_result = state.get("diagnosis_result")
    security_result = state.get("security_result")
    recommend_result = state.get("recommend_result")
    history = state.get("history", [])
    
    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")
    if progress_cb:
        progress_cb("응답 생성 중", "분석 결과를 요약하고 있습니다...")
    
    # Intent 추출 및 유효성 검사
    raw_intent = state.get("intent", "diagnose_repo_health")
    intent = validate_intent(raw_intent)
    user_context = state.get("user_context", {})
    
    # 사용자 레벨 추출 및 유효성 검사
    raw_level = user_context.get("level")
    user_level = validate_user_level(raw_level)
    
    # 미지원 Intent 가드
    if not is_intent_ready(intent):
        summary = _get_not_ready_message(intent)
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_history = list(history)
        new_history.append({"role": "assistant", "content": summary})
        new_state["history"] = new_history
        new_state["llm_summary"] = summary
        return new_state
    
    # 온보딩 모드 판단: intent가 onboarding이거나 user_level이 beginner
    is_onboarding_mode = (
        intent == "diagnose_repo_onboarding" or
        user_level == "beginner"
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

    # 결과 조합
    context_parts = []
    
    # Refine Tasks 결과 처리 (refine_onboarding_tasks intent)
    refine_summary = state.get("refine_summary")
    if refine_summary and intent == "refine_onboarding_tasks":
        context_parts.append(f"## Task 재필터링 결과\n{_format_refine_summary(refine_summary)}")

    if diagnosis_result:
        # 비교 모드인 경우 저장소 이름 명시
        if intent == "compare_two_repos":
            repo = state.get("repo", {})
            repo_name = f"{repo.get('owner', '')}/{repo.get('name', '')}"
            context_parts.append(f"## 저장소 A: {repo_name}\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")
        else:
            context_parts.append(f"## 진단 결과\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")

    # 비교 대상 저장소 결과 (compare_two_repos 모드)
    compare_result = state.get("compare_diagnosis_result")
    if compare_result and intent == "compare_two_repos":
        compare_repo = state.get("compare_repo", {})
        compare_repo_name = f"{compare_repo.get('owner', '')}/{compare_repo.get('name', '')}"
        context_parts.append(f"## 저장소 B: {compare_repo_name}\n{_format_diagnosis(compare_result, is_onboarding_mode, user_level)}")

    if security_result:
        context_parts.append(f"## 보안 분석\n{_format_result(security_result)}")

    if recommend_result:
        context_parts.append(f"## 추천 정보\n{_format_result(recommend_result)}")

    # 진단 결과 없음 가드 (explain_scores 등에서 필요)
    if not context_parts:
        if intent == "explain_scores":
            summary = "점수를 설명하려면 먼저 저장소 분석이 필요합니다. 저장소 URL과 함께 다시 질문해 주세요."
        elif intent == "compare_two_repos":
            summary = "두 저장소를 비교하려면 두 개의 저장소 URL이 필요합니다. 예: 'facebook/react와 vuejs/vue를 비교해줘'"
        else:
            summary = "분석 결과가 없습니다. 다시 시도해 주세요."
    else:
        context = "\n\n".join(context_parts)
        # intent 기반 프롬프트 선택
        summary = _generate_summary_with_llm(
            user_query=user_query,
            context=context,
            intent=intent,
            user_level=user_level,
        )

    # 벤치마크용 로깅: repo 정보와 함께 기록
    repo = state.get("repo", {})
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}" if repo else "unknown"
    logger.info("[summarize_node] repo=%s, intent=%s, user_level=%s, summary_length=%d", repo_id, intent, user_level, len(summary))

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    # history에 assistant 응답 추가
    new_history = list(history)
    new_history.append({"role": "assistant", "content": summary})
    new_state["history"] = new_history
    new_state["llm_summary"] = summary
    
    # ========================================
    # 멀티턴 상태 업데이트 (다음 턴을 위한 컨텍스트 저장)
    # ========================================
    
    # last_repo: 현재 분석한 저장소 저장
    if repo:
        new_state["last_repo"] = repo
    
    # last_intent: 현재 intent 저장
    new_state["last_intent"] = intent
    
    # last_task_list: 온보딩 Task 목록 저장 (다음 턴에서 refine할 때 사용)
    if diagnosis_result:
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        if onboarding_tasks:
            # flat list로 변환하여 저장
            task_list = []
            for difficulty in ["beginner", "intermediate", "advanced"]:
                for task in onboarding_tasks.get(difficulty, []):
                    task_copy = dict(task)
                    if "difficulty" not in task_copy:
                        task_copy["difficulty"] = difficulty
                    task_list.append(task_copy)
            new_state["last_task_list"] = task_list

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


def _format_refine_summary(refine_summary: dict) -> str:
    """Refine Tasks 결과를 문자열로 포맷팅"""
    parts = []
    
    followup_type = refine_summary.get("followup_type", "unknown")
    original_count = refine_summary.get("original_count", 0)
    filtered_count = refine_summary.get("filtered_count", 0)
    
    parts.append(f"### 필터링 정보")
    parts.append(f"- 필터 유형: {_get_followup_type_kr(followup_type)}")
    parts.append(f"- 원본 Task 수: {original_count}개")
    parts.append(f"- 필터링 후 Task 수: {filtered_count}개")
    
    # 난이도 분포
    dist = refine_summary.get("difficulty_distribution", {})
    if dist:
        parts.append(f"\n### 난이도 분포")
        parts.append(f"- 초보자용: {dist.get('beginner', 0)}개")
        parts.append(f"- 중급자용: {dist.get('intermediate', 0)}개")
        parts.append(f"- 고급자용: {dist.get('advanced', 0)}개")
    
    # 필터링된 Task 목록
    tasks = refine_summary.get("tasks", [])
    if tasks:
        parts.append(f"\n### 필터링된 Task 목록")
        for i, task in enumerate(tasks[:5], 1):
            title = task.get("title", "제목 없음")
            difficulty = task.get("difficulty", "unknown")
            level = task.get("level", "?")
            url = task.get("url", "")
            parts.append(f"\n**{i}. {title}**")
            parts.append(f"- 난이도: {difficulty} (Lv.{level})")
            if url:
                parts.append(f"- 링크: {url}")
    
    # Task가 없는 경우
    if not tasks:
        message = refine_summary.get("message", "")
        if message:
            parts.append(f"\n{message}")
        else:
            parts.append("\n조건에 맞는 Task가 없습니다.")
    
    return "\n".join(parts)


def _get_followup_type_kr(followup_type: str) -> str:
    """followup_type을 한국어로 변환"""
    mapping = {
        "refine_easier": "더 쉬운 Task",
        "refine_harder": "더 어려운 Task",
        "refine_different": "다른 종류의 Task",
        "ask_detail": "상세 설명",
        "compare_similar": "비슷한 저장소 비교",
        "continue_same": "추가 분석",
    }
    return mapping.get(followup_type, followup_type)


def _generate_summary_with_llm(
    user_query: str, 
    context: str, 
    intent: str = "diagnose_repo_health",
    user_level: str = "beginner"
) -> str:
    """
    LLM을 사용하여 최종 요약 생성
    
    Args:
        user_query: 사용자 질문
        context: 진단 결과 컨텍스트
        intent: 사용자 의도 (diagnose_repo_health, diagnose_repo_onboarding, explain_scores, etc.)
        user_level: 사용자 레벨 (beginner/intermediate/advanced)
    """
    import os
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    # Intent 기반 프롬프트 선택
    system_prompt = _get_prompt_for_intent(intent, user_level)
    
    # 로깅: 어떤 프롬프트 모드가 선택되었는지
    logger.debug("[_generate_summary_with_llm] intent=%s, user_level=%s", intent, user_level)

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
