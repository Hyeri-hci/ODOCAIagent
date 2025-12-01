"""Summarize Node."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional, Union

from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import (
    OnboardingTasks,
    TaskSuggestion,
    filter_tasks_for_user,
)
from backend.agents.diagnosis.tools.scoring.health_formulas import (
    SCORE_FORMULA_DESC,
)
from backend.agents.diagnosis.tools.scoring.reasoning_builder import (
    classify_explain_depth,
    build_warning_text,
)
from backend.agents.diagnosis.tools.scoring.metric_definitions import (
    get_metric_by_alias,
    get_all_aliases,
    format_metric_for_concept_qa,
    METRIC_DEFINITIONS,
)

from ..models import (
    SupervisorState,
    ExplainTarget,
    DEFAULT_INTENT,
    DEFAULT_SUB_INTENT,
    decide_explain_target,
)
from ..intent_config import (
    get_intent_meta,
    get_answer_kind,
    is_concept_qa,
    is_chat,
)

logger = logging.getLogger(__name__)


def _safe_round(value: Optional[Union[int, float]], digits: int = 1) -> str:
    """None-safe round 함수"""
    if value is None:
        return "N/A"
    try:
        return str(round(float(value), digits))
    except (TypeError, ValueError):
        return "N/A"


# Metric alias helpers

METRIC_ALIAS_MAP = get_all_aliases()
SORTED_ALIASES = sorted(METRIC_ALIAS_MAP.keys(), key=len, reverse=True)
METRIC_NAME_KR = {key: metric.name_ko for key, metric in METRIC_DEFINITIONS.items()}
AVAILABLE_METRICS = set(METRIC_DEFINITIONS.keys())
METRIC_LIST_TEXT = ", ".join(METRIC_NAME_KR.values())

METRIC_NOT_FOUND_MESSAGE = (
    "진단 결과에서 '{metrics}' 지표가 계산되지 않은 것으로 보입니다.\n"
    f"현재는 {METRIC_LIST_TEXT} 지표만 제공하고 있습니다."
)


def _extract_target_metrics(user_query: str) -> list[str]:
    """����� �������� ���� ��� metric ����."""
    query_lower = user_query.lower()
    found_metrics: list[str] = []
    
    for alias in SORTED_ALIASES:
        if alias in query_lower:
            metric_id = METRIC_ALIAS_MAP[alias]
            if metric_id not in found_metrics:
                found_metrics.append(metric_id)
    
    return found_metrics


def _ensure_metrics_exist(
    state: SupervisorState, 
    requested_metrics: list[str]
) -> tuple[list[str], str | None]:
    """
    요청된 metric이 실제로 존재하는지 검증.
    
    Returns:
        (valid_metrics, error_message)
        - valid_metrics: 존재하는 metric만 필터링된 리스트
        - error_message: 모든 metric이 없으면 에러 메시지, 있으면 None
    """
    diagnosis_result = state.get("diagnosis_result")
    if not diagnosis_result or not isinstance(diagnosis_result, dict):
        return [], "진단 결과가 없어 점수를 설명할 수 없습니다."
    
    scores = diagnosis_result.get("scores", {})
    available = set(scores.keys())
    
    valid = [m for m in requested_metrics if m in available]
    missing = [m for m in requested_metrics if m not in available and m not in AVAILABLE_METRICS]
    
    if not valid and missing:
        missing_names = ", ".join(missing)
        return [], METRIC_NOT_FOUND_MESSAGE.format(metrics=missing_names)
    
    if not valid and requested_metrics:
        unknown_names = ", ".join(requested_metrics)
        return [], METRIC_NOT_FOUND_MESSAGE.format(metrics=unknown_names)
    
    return valid, None


SUMMARIZE_SYSTEM_PROMPT = """
당신은 오픈소스 프로젝트 분석 결과를 요약하는 전문가입니다.
진단 결과를 사용자가 이해하기 쉽게 한국어로 요약해 주세요.

## 핵심 원칙
1. **제공된 데이터에 있는 숫자만 사용** - 데이터에 없는 숫자를 만들어 내지 마세요
2. 핵심 정보를 간결하게 전달
3. 마크다운 형식 사용
4. **이모지 절대 사용 금지**

## 점수 해석 가이드 (100점 만점)
- 90-100점: 매우 우수
- 80-89점: 우수
- 70-79점: 양호
- 60-69점: 보통
- 60점 미만: 개선 필요

## 출력 형식 (반드시 이 순서로)

### 한 줄 요약
전체적으로 [상태]한 프로젝트입니다. [핵심 특징 한 문장]

### 점수표
| 지표 | 점수 | 상태 |
|------|------|------|
| 건강 점수 | {health_score} | {해석} |
| 문서 품질 | {documentation_quality} | {해석} |
| 활동성 | {activity_maintainability} | {해석} |
| 온보딩 용이성 | {onboarding_score} | {해석} |

### 강점
- (데이터 기반 강점 2-3개)

### 개선 필요
- (데이터 기반 개선점 2-3개)

### 다음 행동 권장
- "기여하고 싶어요" - 초보자용 Task 5개 추천
- "온보딩 점수 설명해줘" - 점수 상세 해석
- "비슷한 저장소와 비교해줘" - 다른 프로젝트와 비교

### 참고: 시작 Task (3개)
{formatted_tasks}
(각 Task에 왜 초보자에게 적합한지 한 줄씩 추가)
"""

SUMMARIZE_ONBOARDING_PROMPT = """
당신은 오픈소스 프로젝트 온보딩 전문가입니다.
아래에 Python이 미리 선정하고 포맷팅한 Task 리스트가 제공됩니다.
당신의 역할은 각 Task에 "왜 {user_level}에게 적합한지" 한 줄 이유만 덧붙이는 것입니다.

## 핵심 원칙
1. **Task 리스트는 그대로 유지** - 순서, 형식, 링크를 변경하지 마세요
2. 각 Task 아래에 "추천 이유: ..." 한 줄만 추가
3. 이모지 사용 금지
4. (난이도 주의) 태그가 있는 Task는 "도전적이지만 학습에 좋습니다" 등의 안내 포함

## 출력 형식

## {{저장소명}} {level_kr} 온보딩 가이드

### 저장소 개요
- 프로젝트 한 줄 설명
- 온보딩 용이성: {{onboarding_score}}점

### 추천 시작 Task
{{formatted_tasks}}

각 Task 아래에 다음 형식으로 한 줄 추가:
   - **{level_kr}에게 좋은 이유**: (간단한 설명)

### 시작 전 체크리스트
- CONTRIBUTING.md 읽기
- 개발 환경 설정

---
**더 도움이 필요하시면**: "이 Task에 대해 더 자세히 설명해줘", "다른 난이도 Task도 보여줘"
"""

# Intent별 프롬프트

# 단일 metric explain 프롬프트
EXPLAIN_SINGLE_PROMPT = """오픈소스 프로젝트 건강 지표를 해설합니다.

## 규칙
- 결론부터 말하고 근거는 bullet 3-4개로 정리
- 제공된 데이터만 사용
- 이모지 금지
- 리포트 헤더("## 저장소 건강 상태" 등) 금지
"""

# 복수 metric explain 프롬프트
EXPLAIN_MULTI_PROMPT = """오픈소스 프로젝트 건강 지표를 비교 해설합니다.

## 규칙
- 핵심 2-3문장으로 요약 후, metric별 bullet 2-3개씩
- 전체 bullet 10개 이하
- 이모지 금지
"""

EXPLAIN_SCORES_PROMPT = EXPLAIN_SINGLE_PROMPT

COMPARE_REPOS_PROMPT = """[Compare 모드] 두 저장소의 건강 상태를 비교 분석합니다.

## 결론 (Python이 계산한 승자 정보 기반)
{winner_summary}

## 비교표
{comparison_table}

## 항목별 비교
{item_comparison}

## 상황별 추천
- 완전 초보자라면: {beginner_recommendation}
- 기여 경험이 있다면: {experienced_recommendation}

## 규칙
- Python이 제공한 승자 판정을 따르세요
- 점수 차이가 5점 미만이면 "비슷함"으로 표현
- 이모지 금지
"""

REFINE_TASKS_PROMPT = """사용자가 제시한 조건에 맞게 Task 목록을 필터링/정제합니다.

### 출력 형식
1. **[Task 이름]** - 선택 사유 한 문장
2. ...

## 규칙
- 제공된 Task 목록에서만 선택
- bullet 5개 이하
- 이모지 금지
"""

# ============================================================================
# Concept QA 프롬프트 (지식베이스 기반, Diagnosis 불필요)
# ============================================================================

CONCEPT_QA_METRIC_PROMPT = """당신은 오픈소스 프로젝트 건강 지표를 설명하는 전문가입니다.

## 중요 규칙
1. **아래 제공된 지표 정의만 사용하세요** - 새로운 정의를 만들지 마세요
2. 제공된 수식, 해석, 예시를 그대로 활용하세요
3. 이모지 사용 금지

{metric_definition}

## 출력 형식
위 지표 정의를 바탕으로:
1. 한글/영문 이름 소개
2. 수식 설명
3. 점수 구간별 해석
4. 예시로 마무리

정의가 제공되지 않은 지표를 물어보면:
"현재 시스템에서 정의된 지표는 건강 점수(health_score), 온보딩 용이성(onboarding_score), 활동성(activity_maintainability), 문서 품질(documentation_quality)입니다. 질문하신 '{metric_name}'은(는) 아직 정의되지 않았습니다."
"""

CONCEPT_QA_UNKNOWN_METRIC_MSG = """현재 시스템에서 정의된 지표는 다음과 같습니다:
- 건강 점수 (health_score)
- 온보딩 용이성 (onboarding_score)
- 활동성 (activity_maintainability)
- 문서 품질 (documentation_quality)

질문하신 내용은 위 지표에 해당하지 않습니다. 위 지표 중 하나를 선택해 질문해 주세요."""

CONCEPT_QA_PROCESS_PROMPT = """당신은 오픈소스 기여 프로세스를 안내하는 멘토입니다.

## 주요 주제
- Fork/Clone/Branch 생성
- PR 작성 및 리뷰 대응
- 이슈 작성법
- 커밋 메시지 작성법

## 형식
### {주제} 안내
**개요**: 한 줄 설명
**단계**:
1. {단계명} - 설명
2. {단계명} - 설명
**흔한 실수**: 주의사항

## 규칙
- 초보자 눈높이
- 이모지 금지
- 구체적 예시 포함
"""

# ============================================================================
# 프롬프트 빌더 함수들
# ============================================================================

def _validate_user_level(level: Optional[str]) -> str:
    """사용자 레벨 유효성 검사"""
    valid_levels = {"beginner", "intermediate", "advanced"}
    return level if level in valid_levels else "beginner"


# sub_intent -> 프롬프트 종류 매핑
SUB_INTENT_PROMPT_MAP = {
    "health": SUMMARIZE_SYSTEM_PROMPT,
    "onboarding": None,
    "compare": COMPARE_REPOS_PROMPT,
    "explain": EXPLAIN_SCORES_PROMPT,
    "refine": REFINE_TASKS_PROMPT,
    "concept": CONCEPT_QA_METRIC_PROMPT,
    "chat": CONCEPT_QA_PROCESS_PROMPT,
}

PROMPT_MAP = {
    "health": SUMMARIZE_SYSTEM_PROMPT,
    "explain_scores": EXPLAIN_SCORES_PROMPT,
    "compare": COMPARE_REPOS_PROMPT,
    "refine_tasks": REFINE_TASKS_PROMPT,
    "concept_qa_metric": CONCEPT_QA_METRIC_PROMPT,
    "concept_qa_process": CONCEPT_QA_PROCESS_PROMPT,
}


# ============================================================================
# Explain v3 핵심 함수들
# ============================================================================


def _format_diagnosis_for_explain(metric: str, explain_context: dict) -> str:
    """단일 metric explain용 컨텍스트 생성"""
    reasoning = explain_context.get(metric, {})
    if not reasoning:
        return f"{metric}에 대한 상세 데이터가 없습니다."
    
    parts = [f"## {METRIC_NAME_KR.get(metric, metric)} 분석 데이터"]
    
    # 공식 정보
    formula_desc = SCORE_FORMULA_DESC.get(metric, {})
    if formula_desc:
        parts.append(f"\n**공식**: {formula_desc.get('formula', 'N/A')}")
    
    # 점수
    parts.append(f"**점수**: {reasoning.get('score', 'N/A')}점")
    
    # metric별 상세 데이터
    if metric == "health_score":
        components = reasoning.get("components", {})
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict):
                parts.append(f"- {comp_name}: {comp_data.get('score')}점 (가중치 {comp_data.get('weight')}, 기여도 {comp_data.get('contribution')})")
        parts.append(f"- is_healthy: {reasoning.get('is_healthy')}")
    
    elif metric == "documentation_quality":
        parts.append(f"- 포함 섹션 ({reasoning.get('section_count', 0)}/{reasoning.get('total_sections', 8)}): {', '.join(reasoning.get('present_sections', []))}")
        missing = reasoning.get("missing_sections", [])
        if missing:
            parts.append(f"- 누락 섹션: {', '.join(missing)}")
        parts.append(f"- README 길이: {reasoning.get('readme_length_bucket', 'N/A')} ({reasoning.get('word_count', 0)} 단어)")
    
    elif metric == "activity_maintainability":
        for sub_metric in ["commit", "issue", "pr"]:
            sub_data = reasoning.get(sub_metric, {})
            if sub_data:
                parts.append(f"\n**{sub_metric.upper()}** (가중치 {sub_data.get('weight')})")
                if sub_metric == "commit":
                    parts.append(f"  - 총 커밋: {sub_data.get('total_commits', 0)}건, 기여자: {sub_data.get('unique_authors', 0)}명")
                    parts.append(f"  - 마지막 커밋: {sub_data.get('days_since_last', 'N/A')}일 전")
                elif sub_metric == "issue":
                    parts.append(f"  - 오픈: {sub_data.get('open_issues', 0)}건, 생성: {sub_data.get('opened_in_window', 0)}건, 해결: {sub_data.get('closed_in_window', 0)}건")
                    closure = sub_data.get("closure_ratio")
                    if closure is not None:
                        parts.append(f"  - 해결률: {_safe_round(closure * 100)}%")
                elif sub_metric == "pr":
                    parts.append(f"  - 생성: {sub_data.get('prs_in_window', 0)}건, 병합: {sub_data.get('merged_in_window', 0)}건")
                    merge = sub_data.get("merge_ratio")
                    if merge is not None:
                        parts.append(f"  - 병합률: {_safe_round(merge * 100)}%")
    
    elif metric == "onboarding_score":
        components = reasoning.get("components", {})
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict):
                parts.append(f"- {comp_name}: {comp_data.get('score')}점 (가중치 {comp_data.get('weight')})")
        parts.append(f"- good first issue: {reasoning.get('good_first_issue_count', 0)}개")
        parts.append(f"- 초보자용 Task: {reasoning.get('beginner_task_count', 0)}개")
        parts.append(f"- CONTRIBUTING 가이드: {'있음' if reasoning.get('has_contributing_guide') else '없음'}")
    
    return "\n".join(parts)


def _format_diagnosis_for_explain_multi(metrics: list[str], explain_context: dict) -> str:
    """복수 metric explain용 컨텍스트 생성"""
    parts = ["## 복수 점수 분석 데이터"]
    
    for metric in metrics:
        parts.append(f"\n---\n{_format_diagnosis_for_explain(metric, explain_context)}")
    
    return "\n".join(parts)


def _postprocess_explain_response(text: str) -> str:
    """explain 응답 후처리: 리포트 헤더 감지 시 로그만"""
    report_headers = ["## 저장소 건강 상태", "### 점수 요약", "### 주요 특징"]
    for header in report_headers:
        if header in text:
            logger.warning("[explain] 리포트 템플릿 헤더 감지: %s", header)
    return text


def _run_metric_explain(
    user_query: str,
    metrics: list[str],
    explain_context: dict,
    repo_id: str,
    last_brief: str = "",
) -> str:
    """metric 모드: 점수/지표 설명 (diagnosis_result 기반)"""
    import os
    
    if len(metrics) == 0:
        return "어떤 점수를 설명해 드릴까요? 예: '활동성 점수 설명해 줘', '문서 점수랑 온보딩 점수 비교해 줘'"
    
    if len(metrics) >= 4:
        metric_names = ", ".join(METRIC_NAME_KR.get(m, m) for m in metrics[:4])
        return f"최대 3개까지 설명 가능합니다. ({metric_names}... 중 3개를 선택해 주세요)"
    
    depth = classify_explain_depth(user_query)
    is_single = len(metrics) == 1
    prompt = EXPLAIN_SINGLE_PROMPT if is_single else EXPLAIN_MULTI_PROMPT
    
    if is_single:
        context = _format_diagnosis_for_explain(metrics[0], explain_context)
    else:
        context = _format_diagnosis_for_explain_multi(metrics, explain_context)
    
    scores = explain_context.get("scores", {})
    warning = build_warning_text(scores)
    
    depth_hint = "간단히 한두 문장으로" if depth == "simple" else "구체적인 근거와 함께"
    warning_line = f"\n\n주의: {warning}" if warning else ""

    user_message = f"""저장소: {repo_id}
질문: {user_query}
설명 깊이: {depth_hint}

{context}{warning_line}"""

    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    max_tokens = 400 if depth == "simple" else (800 if is_single else 1200)
    
    request = ChatRequest(
        model=model_name,
        messages=[
            ChatMessage(role="system", content=prompt),
            ChatMessage(role="user", content=user_message),
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    
    try:
        response = llm_client.chat(request, timeout=90)
        return _postprocess_explain_response(response.content)
    except Exception as e:
        logger.error("[explain] LLM 호출 실패: %s", e)
        return f"설명 생성 중 오류가 발생했습니다: {e}"


TASK_EXPLAIN_PROMPT = """온보딩 Task 추천 이유를 설명합니다.

## 규칙
- 결론부터 bullet 2-4개로 설명
- Task 속성(시간, 스킬, 난이도) 기반
- 이모지 금지
"""


def _run_task_explain(
    user_query: str,
    state: SupervisorState,
    repo_id: str,
) -> str:
    """task_recommendation 모드: 온보딩 Task 추천 근거 설명"""
    import os
    
    task_list = state.get("last_task_list", [])
    
    # dict인 경우 flat list로 변환 (onboarding_tasks 구조 대응)
    if isinstance(task_list, dict):
        flat_list = []
        for difficulty in ["beginner", "intermediate", "advanced"]:
            for task in task_list.get(difficulty, []):
                if isinstance(task, dict):
                    task_copy = dict(task)
                    task_copy["difficulty"] = difficulty
                    flat_list.append(task_copy)
        task_list = flat_list
    
    if not task_list:
        return "추천된 Task 목록이 없어서 설명할 수 없습니다. 먼저 저장소 분석을 요청해 주세요."
    
    # Task 정보 요약
    task_summary_lines = []
    for i, task in enumerate(task_list[:5], 1):
        if isinstance(task, dict):
            title = task.get("title", "N/A")
            hours = task.get("estimated_hours", "N/A")
            skills = task.get("required_skills", [])
            level = task.get("level", "N/A")
            skills_str = ", ".join(skills[:3]) if skills else "N/A"
            task_summary_lines.append(
                f"{i}. {title} (레벨 {level}, 예상 {hours}시간, 스킬: {skills_str})"
            )
    
    task_context = "\n".join(task_summary_lines) if task_summary_lines else "Task 정보 없음"
    
    user_context = state.get("user_context", {})
    user_level = user_context.get("level", "beginner") if isinstance(user_context, dict) else "beginner"
    
    user_message = f"""저장소: {repo_id}
사용자 레벨: {user_level}
사용자 질문: {user_query}

## 추천된 Task 목록
{task_context}

위 Task들을 추천한 이유를 설명해 주세요."""

    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    request = ChatRequest(
        model=model_name,
        messages=[
            ChatMessage(role="system", content=TASK_EXPLAIN_PROMPT),
            ChatMessage(role="user", content=user_message),
        ],
        temperature=0.3,
        max_tokens=600,
    )
    
    try:
        response = llm_client.chat(request, timeout=60)
        return response.content
    except Exception as e:
        logger.error("[task_explain] LLM 호출 실패: %s", e)
        return f"Task 추천 이유 설명 중 오류가 발생했습니다: {e}"


GENERAL_EXPLAIN_MESSAGE = """이 추천은 정량적인 점수 분석을 기반으로 한 것이 아니라, 일반적인 오픈소스 기여 베스트 프랙티스를 바탕으로 생성된 예시입니다.

초보자가 오픈소스에 기여를 시작하기 좋은 일반적인 패턴:
- 문서 개선 (오타 수정, 번역)
- good-first-issue 라벨이 붙은 이슈
- 테스트 코드 추가
- 작은 버그 수정

특정 저장소에 대한 구체적인 기여 추천을 원하시면, 저장소 URL과 함께 다시 질문해 주세요.
예: "facebook/react 저장소에서 초보자가 시작하기 좋은 이슈를 찾아줘"
"""


def infer_explain_target(state: dict) -> str:
    """
    Explain 모드에서 설명 대상을 추론. Python에서 완전히 제어.
    
    3분기 라우팅:
    - "metric": 특정 지표(health_score 등) 설명
    - "task_recommendation": Task 추천 근거 설명
    - "general": 일반적인 설명/맥락 없는 질문
    """
    user_query = state.get("user_query", "").lower()
    last_answer_kind = state.get("last_answer_kind")
    last_explain_target = state.get("last_explain_target")
    explain_metrics = state.get("explain_metrics", [])
    
    # 1. 현재 질문에서 metric 키워드 추출
    current_metrics = _extract_target_metrics(user_query)
    if current_metrics:
        state["explain_metrics"] = current_metrics
        return "metric"
    
    # 2. 점수/지표 관련 키워드 체크
    score_keywords = ["점수", "score", "왜", "낮", "높", "이유", "근거"]
    has_score_keyword = any(kw in user_query for kw in score_keywords)
    
    # 3. 후속 질문 판단 (무대명사 사용)
    followup_keywords = ["그게", "이게", "저게", "그건", "이건", "무슨", "뭐야", "뭔데", "어떻게"]
    is_followup = any(kw in user_query for kw in followup_keywords)
    
    # 4. Report 직후 점수 관련 질문 → metric
    if last_answer_kind == "report" and has_score_keyword:
        return "metric"
    
    # 5. 후속 질문: 이전 타겟 유지
    if is_followup and last_explain_target:
        if last_explain_target == "metric" and explain_metrics:
            state["explain_metrics"] = explain_metrics
        return last_explain_target
    
    # 6. Task 추천 관련 키워드
    task_keywords = ["task", "태스크", "이슈", "추천", "기여"]
    if any(kw in user_query for kw in task_keywords):
        return "task_recommendation"
    
    # 7. 맥락이 있으면 metric, 없으면 general
    if last_answer_kind in ("report", "explain") and explain_metrics:
        return "metric"
    
    return "general"


def _run_general_explain(user_query: str) -> str:
    """general 모드: 정량 점수 없는 일반 대화 기반 설명"""
    return GENERAL_EXPLAIN_MESSAGE


def _run_concept_qa_with_kb(user_query: str, user_level: str = "beginner") -> str:
    """
    지식베이스 기반 Concept QA.
    질문에서 지표 키워드를 추출하고, metric_definitions에서 정의를 조회하여 답변.
    """
    import os
    
    # 질문에서 지표 추출 (alias 포함)
    metrics = _extract_target_metrics(user_query)
    
    if metrics:
        # 첫 번째 매칭된 지표에 대해 지식베이스 조회
        metric_key = metrics[0]
        metric_def = METRIC_DEFINITIONS.get(metric_key)
        
        if metric_def:
            # 지식베이스에서 정의 포맷팅
            metric_definition = format_metric_for_concept_qa(metric_def)
            prompt = CONCEPT_QA_METRIC_PROMPT.format(
                metric_definition=metric_definition,
                metric_name=user_query,
            )
        else:
            # 키는 있지만 정의가 없는 경우 (이론상 발생하지 않음)
            return CONCEPT_QA_UNKNOWN_METRIC_MSG
    else:
        # 지표 키워드가 없는 경우 - alias로 다시 시도
        metric_def = get_metric_by_alias(user_query)
        if metric_def:
            metric_definition = format_metric_for_concept_qa(metric_def)
            prompt = CONCEPT_QA_METRIC_PROMPT.format(
                metric_definition=metric_definition,
                metric_name=user_query,
            )
        else:
            # 지표를 찾을 수 없음
            return CONCEPT_QA_UNKNOWN_METRIC_MSG
    
    # LLM 호출
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    request = ChatRequest(
        model=model_name,
        messages=[
            ChatMessage(role="system", content=prompt),
            ChatMessage(role="user", content=user_query),
        ],
        temperature=0.3,
        max_tokens=500,
    )
    
    try:
        response = llm_client.chat(request, timeout=60)
        return response.content
    except Exception as e:
        logger.error("[concept_qa] LLM 호출 실패: %s", e)
        return f"지표 설명 중 오류가 발생했습니다: {e}"


def _generate_explain_response(
    user_query: str,
    metrics: list[str],
    explain_context: dict,
    repo_id: str,
    last_brief: str = "",
) -> str:
    """explain 모드 전용 응답 생성 (레거시 호환)"""
    return _run_metric_explain(user_query, metrics, explain_context, repo_id, last_brief)


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


def _get_prompt_for_sub_intent(sub_intent: str, user_level: str = "beginner") -> str:
    """
    sub_intent에 따라 적절한 시스템 프롬프트 반환.
    
    Args:
        sub_intent: 세부 의도 (health | onboarding | compare | explain | refine | concept | chat)
        user_level: 사용자 레벨 (beginner/intermediate/advanced)
    
    Returns:
        해당 sub_intent에 맞는 시스템 프롬프트
    """
    # onboarding은 user_level이 필요하므로 별도 처리
    if sub_intent == "onboarding":
        return _get_onboarding_prompt(user_level)
    
    # 나머지는 SUB_INTENT_PROMPT_MAP에서 조회
    prompt = SUB_INTENT_PROMPT_MAP.get(sub_intent)
    if prompt:
        return prompt
    
    # fallback: health 프롬프트
    return SUMMARIZE_SYSTEM_PROMPT


def _get_prompt_for_intent(intent: str, user_level: str = "beginner") -> str:
    """
    [레거시 호환] intent에 따라 적절한 시스템 프롬프트 반환.
    
    새로운 코드에서는 _get_prompt_for_sub_intent()를 사용하세요.
    """
    # 레거시 intent → sub_intent 변환
    legacy_to_sub_intent = {
        "diagnose_repo_health": "health",
        "diagnose_repo_onboarding": "onboarding",
        "compare_two_repos": "compare",
        "explain_scores": "explain",
        "refine_onboarding_tasks": "refine",
        "concept_qa": "concept",
    }
    sub_intent = legacy_to_sub_intent.get(intent, "health")
    return _get_prompt_for_sub_intent(sub_intent, user_level)


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


def _generate_last_brief(summary: str, repo_id: str = "") -> str:
    """
    응답 요약(last_brief) 생성 - 다음 followup 턴에서 맥락 참조용.
    
    200자 이내로 응답의 핵심 내용을 추출합니다.
    - 마크다운 헤더 제거
    - 첫 번째 의미 있는 문장들 추출
    - 저장소 이름 포함
    
    Args:
        summary: LLM이 생성한 전체 응답
        repo_id: 저장소 식별자 (예: "facebook/react")
    
    Returns:
        200자 이내의 요약 문자열
    """
    import re
    
    if not summary or not summary.strip():
        return f"{repo_id} 분석 완료" if repo_id else ""
    
    # 마크다운 헤더(##, ###) 제거
    lines = summary.split("\n")
    content_lines = []
    for line in lines:
        stripped = line.strip()
        # 빈 줄, 헤더, 구분선 제외
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("---"):
            continue
        if stripped.startswith("**다음으로"):
            continue
        if stripped.startswith("**더 도움이"):
            continue
        if stripped.startswith("**추가 질문"):
            continue
        content_lines.append(stripped)
    
    if not content_lines:
        return f"{repo_id} 분석 완료" if repo_id else "분석 완료"
    
    # 첫 번째 의미 있는 내용들 연결 (200자 제한)
    result = " ".join(content_lines)
    
    # 마크다운 볼드(**) 제거
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    
    # 리스트 마커(-, *) 정리
    result = re.sub(r'^[-*]\s*', '', result)
    result = re.sub(r'\s[-*]\s', ' ', result)
    
    # 200자 제한 (마지막 완성된 문장에서 자르기)
    if len(result) > 200:
        result = result[:197]
        # 마지막 완성된 문장 찾기
        last_period = max(result.rfind("."), result.rfind("요"), result.rfind("다"))
        if last_period > 100:
            result = result[:last_period + 1]
        else:
            result = result[:197] + "..."
    
    return result


def summarize_node(state: SupervisorState) -> SupervisorState:
    """
    모든 Agent 결과를 종합하여 사용자에게 최종 응답을 생성합니다.
    
    새로운 3 Intent + SubIntent 구조:
    - intent: analyze | followup | general_qa
    - sub_intent: health | onboarding | compare | explain | refine | concept | chat
    
    error_message가 있으면 LLM 호출 없이 바로 반환합니다.
    """
    # ========================================
    # 0. error_message 체크 - LLM 호출 없이 바로 반환
    # ========================================
    error_message = state.get("error_message")
    if error_message:
        history = state.get("history", [])
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_history = list(history)
        new_history.append({"role": "assistant", "content": error_message})
        new_state["history"] = new_history
        new_state["llm_summary"] = error_message
        return new_state
    
    # ========================================
    # 1. 상태 추출
    # ========================================
    diagnosis_result = state.get("diagnosis_result")
    security_result = state.get("security_result")
    recommend_result = state.get("recommend_result")
    history = state.get("history", [])
    
    # 진행 상황 콜백
    progress_cb = state.get("_progress_callback")
    if progress_cb:
        progress_cb("응답 생성 중", "분석 결과를 요약하고 있습니다...")
    
    # Intent/SubIntent 추출 (새로운 구조)
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent") or DEFAULT_SUB_INTENT
    
    # 레거시 task_type (호환용)
    task_type = state.get("task_type", "diagnose_repo_health")
    
    user_context = state.get("user_context", {})
    
    # 사용자 레벨 추출 및 유효성 검사
    raw_level = user_context.get("level")
    user_level = _validate_user_level(raw_level)
    
    # 이전 응답 요약 (followup 맥락용)
    last_brief = state.get("last_brief", "")
    
    # 온보딩 모드 판단: sub_intent가 onboarding이거나 user_level이 beginner
    is_onboarding_mode = (
        sub_intent == "onboarding" or
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

    # ========================================
    # 2. 결과 조합
    # ========================================
    context_parts = []
    
    # Refine Tasks 결과 처리 (sub_intent == "refine")
    refine_summary = state.get("refine_summary")
    if refine_summary and sub_intent == "refine":
        context_parts.append(f"## Task 재필터링 결과\n{_format_refine_summary(refine_summary)}")

    if diagnosis_result:
        # 비교 모드인 경우 저장소 이름 명시
        if sub_intent == "compare":
            repo = state.get("repo", {})
            repo_name = f"{repo.get('owner', '')}/{repo.get('name', '')}"
            context_parts.append(f"## 저장소 A: {repo_name}\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")
        else:
            context_parts.append(f"## 진단 결과\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")

    # 비교 대상 저장소 결과 (compare 모드)
    compare_result = state.get("compare_diagnosis_result")
    if compare_result and sub_intent == "compare":
        compare_repo = state.get("compare_repo", {})
        compare_repo_name = f"{compare_repo.get('owner', '')}/{compare_repo.get('name', '')}"
        context_parts.append(f"## 저장소 B: {compare_repo_name}\n{_format_diagnosis(compare_result, is_onboarding_mode, user_level)}")

    if security_result:
        context_parts.append(f"## 보안 분석\n{_format_result(security_result)}")

    if recommend_result:
        context_parts.append(f"## 추천 정보\n{_format_result(recommend_result)}")

    # ========================================
    # 3. LLM 응답 생성
    # ========================================
    
    repo = state.get("repo", {})
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}" if repo else "unknown"
    
    # explain 모드: 3분기 파이프라인
    if sub_intent == "explain":
        explain_target = infer_explain_target(state)
        target_metrics = state.get("explain_metrics", [])
        
        logger.info("[explain] target=%s, metrics=%s", explain_target, target_metrics)
        
        if explain_target == "metric":
            if not target_metrics:
                target_metrics = _extract_target_metrics(user_query)
            valid_metrics, error_msg = _ensure_metrics_exist(state, target_metrics)
            
            if error_msg:
                summary = error_msg
            else:
                explain_context = diagnosis_result.get("explain_context", {}) if diagnosis_result else {}
                summary = _run_metric_explain(
                    user_query=user_query,
                    metrics=valid_metrics,
                    explain_context=explain_context,
                    repo_id=repo_id,
                    last_brief=last_brief,
                )
                state["last_explain_target"] = "metric"
        elif explain_target == "task_recommendation":
            summary = _run_task_explain(user_query, state, repo_id)
            state["last_explain_target"] = "task_recommendation"
        else:
            summary = _run_general_explain(user_query)
            state["last_explain_target"] = "general"
    elif not context_parts:
        # Concept QA / Chat은 diagnosis 없이 바로 LLM 응답
        if is_concept_qa(intent, sub_intent):
            # 지식베이스 기반 Concept QA
            summary = _run_concept_qa_with_kb(user_query, user_level)
        elif is_chat(intent, sub_intent):
            summary = _generate_summary_with_llm_v2(
                user_query=user_query,
                context="",
                sub_intent=sub_intent,
                user_level=user_level,
                intent=intent,
                last_brief=last_brief,
            )
        elif sub_intent == "compare":
            summary = "두 저장소를 비교하려면 두 개의 저장소 URL이 필요합니다. 예: 'facebook/react와 vuejs/vue를 비교해줘'"
        else:
            summary = _generate_summary_with_llm_v2(
                user_query=user_query,
                context="",
                sub_intent=sub_intent,
                user_level=user_level,
                intent=intent,
                last_brief=last_brief,
            )
    else:
        context = "\n\n".join(context_parts)
        summary = _generate_summary_with_llm_v2(
            user_query=user_query,
            context=context,
            sub_intent=sub_intent,
            user_level=user_level,
            intent=intent,
            last_brief=last_brief,
        )

    logger.info("[summarize_node] repo=%s, intent=%s, sub_intent=%s, user_level=%s, summary_length=%d", 
                repo_id, intent, sub_intent, user_level, len(summary))

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    # history에 assistant 응답 추가
    new_history = list(history)
    new_history.append({"role": "assistant", "content": summary})
    new_state["history"] = new_history
    new_state["llm_summary"] = summary
    
    # ========================================
    # 4. 응답 메타데이터 설정 (UI 표시용)
    # ========================================
    
    # answer_kind: UI 배지 표시용 (report/explain/refine/concept/chat)
    new_state["answer_kind"] = get_answer_kind(intent, sub_intent)
    
    # last_brief: 다음 followup에서 참조할 이전 응답 요약 (200자 이내)
    # - 응답의 첫 번째 의미 있는 문장들을 추출
    new_state["last_brief"] = _generate_last_brief(summary, repo_id)
    
    # ========================================
    # 5. 멀티턴 상태 업데이트 (다음 턴을 위한 컨텍스트 저장)
    # ========================================
    
    # last_repo: 현재 분석한 저장소 저장
    if repo:
        new_state["last_repo"] = repo
    
    # last_intent, last_sub_intent, last_answer_kind: 현재 컨텍스트 저장
    new_state["last_intent"] = intent
    new_state["last_sub_intent"] = sub_intent
    new_state["last_answer_kind"] = new_state["answer_kind"]
    
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


def _format_onboarding_tasks(
    tasks: list[TaskSuggestion],
    user_level: str,
    max_tasks: int = 5,
) -> tuple[str, bool]:
    """
    온보딩 Task를 테이블 형식으로 포맷팅. Python에서 완전히 제어.
    
    Returns:
        (formatted_table, has_mismatch): 포맷팅된 테이블, 난이도 불일치 여부
    """
    if not tasks:
        return "(추천 Task 없음)", False
    
    difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    difficulty_kr = {"beginner": "쉬움", "intermediate": "보통", "advanced": "어려움"}
    user_order = difficulty_order.get(user_level, 0)
    
    has_mismatch = False
    lines = []
    lines.append("| 번호 | 제목 | 난이도 | 예상시간 | 링크 |")
    lines.append("|------|------|--------|----------|------|")
    
    for i, task in enumerate(tasks[:max_tasks], 1):
        title = task.title[:40] + "..." if len(task.title) > 40 else task.title
        difficulty = getattr(task, "difficulty", "beginner")
        diff_kr = difficulty_kr.get(difficulty, difficulty)
        task_order = difficulty_order.get(difficulty, 0)
        
        if task_order > user_order:
            diff_kr += " ⚠️"
            has_mismatch = True
        
        est_time = getattr(task, "estimated_time", "1-2시간")
        url = getattr(task, "url", "#")
        issue_num = url.split("/")[-1] if url and "/" in url else str(i)
        
        lines.append(f"| {i} | {title} | {diff_kr} | {est_time} | [#{issue_num}]({url}) |")
    
    return "\n".join(lines), has_mismatch


def _format_health_top_tasks(tasks: list[TaskSuggestion], max_tasks: int = 3) -> str:
    """
    Health 모드 부록용 Task 3개를 간단한 리스트로 포맷팅.
    """
    if not tasks:
        return "(추천 Task 없음)"
    
    difficulty_kr = {"beginner": "쉬움", "intermediate": "보통", "advanced": "어려움"}
    lines = []
    
    for task in tasks[:max_tasks]:
        title = task.title[:50] + "..." if len(task.title) > 50 else task.title
        difficulty = getattr(task, "difficulty", "beginner")
        diff_kr = difficulty_kr.get(difficulty, difficulty)
        url = getattr(task, "url", "#")
        
        lines.append(f"- [{title}]({url}) | {diff_kr}")
    
    return "\n".join(lines)


def _compute_comparison_winners(
    scores_a: dict,
    scores_b: dict,
    repo_a: str,
    repo_b: str,
) -> dict:
    """
    Compare 모드에서 각 지표별 승자 계산. 점수 차이 기반.
    
    Returns:
        {
            "metrics": {metric: {"winner": repo, "diff": diff, "note": str}},
            "overall_winner": repo or "무승부",
            "table_md": 마크다운 테이블
        }
    """
    metric_names = {
        "health_score": "건강도",
        "onboarding_score": "온보딩",
        "activity": "활동성",
        "documentation": "문서화",
    }
    
    results = {"metrics": {}, "wins": {repo_a: 0, repo_b: 0}}
    table_lines = ["| 지표 | " + repo_a + " | " + repo_b + " | 승자 |"]
    table_lines.append("|------|------|------|------|")
    
    for metric, name_kr in metric_names.items():
        score_a = scores_a.get(metric, 0) or 0
        score_b = scores_b.get(metric, 0) or 0
        diff = abs(score_a - score_b)
        
        if diff < 5:
            winner = "무승부"
            note = "비슷함"
        elif score_a > score_b:
            winner = repo_a
            note = f"+{diff:.0f}점"
            results["wins"][repo_a] += 1
        else:
            winner = repo_b
            note = f"+{diff:.0f}점"
            results["wins"][repo_b] += 1
        
        results["metrics"][metric] = {"winner": winner, "diff": diff, "note": note}
        table_lines.append(f"| {name_kr} | {score_a:.0f} | {score_b:.0f} | {winner} ({note}) |")
    
    wins_a = results["wins"][repo_a]
    wins_b = results["wins"][repo_b]
    
    if wins_a > wins_b:
        results["overall_winner"] = repo_a
    elif wins_b > wins_a:
        results["overall_winner"] = repo_b
    else:
        results["overall_winner"] = "무승부"
    
    results["table_md"] = "\n".join(table_lines)
    return results


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
            # 온보딩 모드: Python에서 완전히 포맷팅된 Task 리스트 생성
            formatted_tasks, has_mismatch = _format_onboarding_tasks(
                tasks=filtered_tasks,
                user_level=user_level,
                max_tasks=5,
            )
            
            parts.append(f"\n### 추천 온보딩 Task ({level_kr}용)")
            if has_mismatch:
                parts.append(f"\n**참고**: {level_kr}용 Task가 부족하여 일부 난이도가 높은 Task도 포함되어 있습니다.")
            parts.append(f"\n{formatted_tasks}")
        else:
            # 일반 모드: 요약 + 레벨별 Task 3개 추천
            total = meta.get("total_count", 0)
            
            parts.append(f"\n### 온보딩 Task 요약")
            parts.append(f"- 총 Task 수: {total}개")
            parts.append(f"- 초보자용: {len(beginner_tasks)}개")
            parts.append(f"- 중급자용: {len(intermediate_tasks)}개")
            parts.append(f"- 고급자용: {len(advanced_tasks)}개")
            
            # 사용자 레벨에 따라 Task 3개 추천 (Health 모드 부록용)
            selected_tasks = filtered_tasks[:3]
            if selected_tasks:
                parts.append(f"\n### {level_kr} 추천 Task (참고용)")
                formatted_top3 = _format_health_top_tasks(selected_tasks, max_tasks=3)
                parts.append(formatted_top3)
    
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


def _generate_summary_with_llm_v2(
    user_query: str, 
    context: str, 
    sub_intent: str = "health",
    user_level: str = "beginner",
    intent: str = "analyze",
    last_brief: str = "",
) -> str:
    """
    LLM을 사용하여 최종 요약 생성 (v2 - sub_intent 기반).
    
    Args:
        user_query: 사용자 질문
        context: 진단 결과 컨텍스트
        sub_intent: 세부 의도 (health | onboarding | compare | explain | refine | concept | chat)
        user_level: 사용자 레벨 (beginner/intermediate/advanced)
        intent: 상위 의도 (analyze | followup | general_qa)
        last_brief: 이전 응답 요약 (followup 맥락용, 200자 이내)
    """
    import os
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    # sub_intent 기반 프롬프트 선택
    system_prompt = _get_prompt_for_sub_intent(sub_intent, user_level)
    
    # 로깅: 어떤 프롬프트 모드가 선택되었는지
    logger.debug("[_generate_summary_with_llm_v2] intent=%s, sub_intent=%s, user_level=%s, has_last_brief=%s", 
                 intent, sub_intent, user_level, bool(last_brief))

    # followup intent이고 last_brief가 있으면 맥락 정보 추가
    context_prefix = ""
    if intent == "followup" and last_brief:
        context_prefix = f"""## 이전 대화 맥락
{last_brief}

---

"""
    
    user_message = f"""
사용자 질문: {user_query}

{context_prefix}분석 결과:
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


def _generate_summary_with_llm(
    user_query: str, 
    context: str, 
    intent: str = "diagnose_repo_health",
    user_level: str = "beginner"
) -> str:
    """
    [레거시 호환] LLM을 사용하여 최종 요약 생성.
    
    새로운 코드에서는 _generate_summary_with_llm_v2()를 사용하세요.
    """
    import os
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    # Intent 기반 프롬프트 선택 (레거시)
    system_prompt = _get_prompt_for_intent(intent, user_level)
    
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
