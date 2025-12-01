"""Summarize Node."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Union

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
    UserProfile,
)
from ..intent_config import (
    get_intent_meta,
    get_answer_kind,
    is_concept_qa,
    is_chat,
)

logger = logging.getLogger(__name__)


def _build_persona_instruction(profile: Optional[Dict[str, Any]]) -> str:
    """Builds a persona injection prompt based on the user_profile."""
    if not profile:
        return ""
    
    instructions = []
    
    # 1. Instruction based on skill level
    level = profile.get("level")
    if level == "beginner":
        instructions.append("- The user is a 'beginner'. Avoid jargon and explain easily.")
    elif level == "advanced":
        instructions.append("- The user is an 'expert'. Focus on key technical details.")
    elif level == "intermediate":
        instructions.append("- The user is 'intermediate'. Explain with appropriate technical terms.")
    
    # 2. Instruction based on interests
    interests = profile.get("interests", [])
    if interests:
        interests_str = ", ".join(interests[:5])  # Max 5
        instructions.append(f"- It's good to relate the explanation to the user's interests: ({interests_str}).")
    
    # 3. Instruction based on response style
    persona = profile.get("persona")
    if persona == "simple":
        instructions.append("- The user prefers concise answers. Summarize the key points.")
    elif persona == "detailed":
        instructions.append("- The user wants detailed explanations. Be specific with examples.")
    
    if not instructions:
        return ""
    
    return "\n[User Profile]\n" + "\n".join(instructions) + "\n"


def _handle_fast_chat_direct(intent: str, sub_intent: str, state: Dict[str, Any]) -> str:
    """Handles Fast Chat directly: templates for smalltalk/help, GitHub+LLM for overview."""
    from backend.agents.supervisor.prompts import (
        GREETING_TEMPLATE,
        CHITCHAT_TEMPLATE,
        HELP_TEMPLATE,
        build_overview_prompt,
        get_fast_chat_params,
    )
    
    if intent == "smalltalk":
        return GREETING_TEMPLATE if sub_intent == "greeting" else CHITCHAT_TEMPLATE
    
    if intent == "help":
        return HELP_TEMPLATE
    
    if intent == "overview":
        repo = state.get("repo") or {}
        owner = repo.get("owner", "")
        name = repo.get("name", "")
        
        if not owner or not name:
            return "Repository information not found. Please provide it in 'owner/repo' format."
        
        try:
            from backend.common.github_client import fetch_repo_overview
            
            overview = fetch_repo_overview(owner, name)
            
            facts = (
                f"Name: {overview.get('full_name', f'{owner}/{name}')}\n"
                f"Description: {overview.get('description', '(None)')}\n"
                f"Language: {overview.get('primaryLanguage', '(None)')}\n"
                f"Stars: {overview.get('stargazers_count', 0):,} stars\n"
                f"Forks: {overview.get('forks_count', 0):,} forks\n"
                f"License: {overview.get('license', {}).get('spdx_id', '(None)')}"
            )
            readme = overview.get("readme_content", "")[:500]
            
            system_prompt, user_prompt = build_overview_prompt(owner, name, facts, readme)
            
            client = fetch_llm_client()
            llm_params = get_fast_chat_params()
            
            request = ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                temperature=llm_params["temperature"],
                max_tokens=llm_params["max_tokens"],
            )
            return client.chat(request).content
            
        except Exception as e:
            logger.error("Overview failed: %s", e)
            return f"An error occurred while fetching repository information: {e}"
    
    return "Unknown request."


def _safe_round(value: Optional[Union[int, float]], digits: int = 1) -> str:
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


def _generate_recommendation_prompt() -> str:
    """Generates an Active Inference prompt for recommendation requests."""
    return """프로젝트 추천을 위해 몇 가지 정보가 필요합니다.

### 알려주시면 좋은 정보
1. **기술 스택**: 어떤 언어나 프레임워크에 관심이 있으신가요? (예: Python, JavaScript, React)
2. **경험 수준**: 오픈소스 기여 경험이 있으신가요? (초보자/중급자/고급자)
3. **관심 분야**: 어떤 종류의 프로젝트에 관심이 있으신가요? (예: 웹 프론트엔드, 백엔드, CLI 도구, 머신러닝)

### 예시 질문
- "Python 초보자가 기여할 만한 프로젝트 추천해줘"
- "React 관련 프로젝트 중에서 문서화가 잘 되어있는 곳 알려줘"
- "facebook/react 분석해줘" (특정 저장소를 직접 지정)

원하시는 정보를 알려주시면, 맞춤형 프로젝트를 찾아드리겠습니다."""


# Common anti-parrot rule (prevent answering with unrelated content)
ANTI_PARROT_RULE = """
## [CRITICAL] Answer Coherence Rule
- You MUST answer the user's ACTUAL question
- If user asks for "recommendation", DO NOT explain metric definitions
- If user asks about "projects to contribute", suggest specific repositories or ask about their preferences
- If no analysis data is available, ask the user for more information (Active Inference)
- NEVER repeat the same template answer regardless of the question
"""

SUMMARIZE_SYSTEM_PROMPT = """
당신은 오픈소스 프로젝트 분석 결과를 요약하는 전문가입니다.
진단 결과를 사용자가 이해하기 쉽게 한국어로 요약해 주세요.

## 핵심 원칙
1. **제공된 데이터에 있는 숫자만 사용** - 데이터에 없는 숫자를 만들어 내지 마세요
2. 핵심 정보를 간결하게 전달
3. 마크다운 형식 사용
4. **이모지 절대 사용 금지**
5. **사용자의 질문에 맞는 답변만 제공** - 추천을 물었으면 추천을, 분석을 물었으면 분석을

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


# Single metric explain Prompt
EXPLAIN_SINGLE_PROMPT = """오픈소스 프로젝트 건강 지표를 해설합니다.

## 규칙
- 결론부터 말하고 근거는 bullet 3-4개로 정리
- 제공된 데이터만 사용
- 이모지 금지
- 리포트 헤더("## 저장소 건강 상태" 등) 금지
"""

# Multi metric explain Prompt
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

# Comes with unknown metric handling
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

# Project Building Concept QA Prompt
def _validate_user_level(level: Optional[str]) -> str:
    """사용자 레벨 유효성 검사"""
    valid_levels = {"beginner", "intermediate", "advanced"}
    return level if level in valid_levels else "beginner"


# sub_intent -> Prompt mapping
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


# Explain helpers
def _format_diagnosis_for_explain(metric: str, explain_context: dict) -> str:
    """Creates context for explaining a single metric."""
    reasoning = explain_context.get(metric, {})
    if not reasoning:
        return f"No detailed data available for {metric}."
    
    parts = [f"## {METRIC_NAME_KR.get(metric, metric)} Analysis Data"]
    
    # Formula info
    formula_desc = SCORE_FORMULA_DESC.get(metric, {})
    if formula_desc:
        parts.append(f"\n**Formula**: {formula_desc.get('formula', 'N/A')}")
    
    # Score
    parts.append(f"**Score**: {reasoning.get('score', 'N/A')} points")
    
    # Metric-specific details
    if metric == "health_score":
        components = reasoning.get("components", {})
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict):
                parts.append(f"- {comp_name}: {comp_data.get('score')} points (weight {comp_data.get('weight')}, contribution {comp_data.get('contribution')})")
        parts.append(f"- is_healthy: {reasoning.get('is_healthy')}")
    
    elif metric == "documentation_quality":
        parts.append(f"- Included Sections ({reasoning.get('section_count', 0)}/{reasoning.get('total_sections', 8)}): {', '.join(reasoning.get('present_sections', []))}")
        missing = reasoning.get("missing_sections", [])
        if missing:
            parts.append(f"- Missing Sections: {', '.join(missing)}")
        parts.append(f"- README Length: {reasoning.get('readme_length_bucket', 'N/A')} ({reasoning.get('word_count', 0)} words)")
    
    elif metric == "activity_maintainability":
        for sub_metric in ["commit", "issue", "pr"]:
            sub_data = reasoning.get(sub_metric, {})
            if sub_data:
                parts.append(f"\n**{sub_metric.upper()}** (weight {sub_data.get('weight')})")
                if sub_metric == "commit":
                    parts.append(f"  - Total commits: {sub_data.get('total_commits', 0)}, Contributors: {sub_data.get('unique_authors', 0)}")
                    parts.append(f"  - Days since last commit: {sub_data.get('days_since_last', 'N/A')}")
                elif sub_metric == "issue":
                    parts.append(f"  - Open: {sub_data.get('open_issues', 0)}, Created: {sub_data.get('opened_in_window', 0)}, Closed: {sub_data.get('closed_in_window', 0)}")
                    closure = sub_data.get("closure_ratio")
                    if closure is not None:
                        parts.append(f"  - Closure ratio: {_safe_round(closure * 100)}%")
                elif sub_metric == "pr":
                    parts.append(f"  - Created: {sub_data.get('prs_in_window', 0)}, Merged: {sub_data.get('merged_in_window', 0)}")
                    merge = sub_data.get("merge_ratio")
                    if merge is not None:
                        parts.append(f"  - Merge ratio: {_safe_round(merge * 100)}%")
    
    elif metric == "onboarding_score":
        components = reasoning.get("components", {})
        for comp_name, comp_data in components.items():
            if isinstance(comp_data, dict):
                parts.append(f"- {comp_name}: {comp_data.get('score')} points (weight {comp_data.get('weight')})")
        parts.append(f"- good first issue: {reasoning.get('good_first_issue_count', 0)} issues")
        parts.append(f"- Beginner-friendly tasks: {reasoning.get('beginner_task_count', 0)} tasks")
        parts.append(f"- CONTRIBUTING guide: {'Exists' if reasoning.get('has_contributing_guide') else 'Missing'}")
    
    return "\n".join(parts)


def _format_diagnosis_for_explain_multi(metrics: list[str], explain_context: dict) -> str:
    """Creates context for explaining multiple metrics."""
    parts = ["## Multi-Score Analysis Data"]
    
    for metric in metrics:
        parts.append(f"\n---\n{_format_diagnosis_for_explain(metric, explain_context)}")
    
    return "\n".join(parts)


def _postprocess_explain_response(text: str) -> str:
    """Post-processes explain response: logs if report headers are detected."""
    report_headers = ["## 저장소 건강 상태", "### 점수 요약", "### 주요 특징"]
    for header in report_headers:
        if header in text:
            logger.warning("[explain] Report template header detected: %s", header)
    return text


def _run_metric_explain(
    user_query: str,
    metrics: list[str],
    explain_context: dict,
    repo_id: str,
    last_brief: str = "",
) -> str:
    """'metric' mode: explains scores/metrics based on diagnosis_result."""
    import os
    
    if len(metrics) == 0:
        return "Which score would you like me to explain? For example: 'Explain the activity score', or 'Compare the documentation score and the onboarding score'."
    
    if len(metrics) >= 4:
        metric_names = ", ".join(METRIC_NAME_KR.get(m, m) for m in metrics[:4])
        return f"A maximum of 3 metrics can be explained at a time. Please choose 3 from ({metric_names}...).)"
    
    depth = classify_explain_depth(user_query)
    is_single = len(metrics) == 1
    prompt = EXPLAIN_SINGLE_PROMPT if is_single else EXPLAIN_MULTI_PROMPT
    
    if is_single:
        context = _format_diagnosis_for_explain(metrics[0], explain_context)
    else:
        context = _format_diagnosis_for_explain_multi(metrics, explain_context)
    
    scores = explain_context.get("scores", {})
    warning = build_warning_text(scores)
    
    depth_hint = "briefly in one or two sentences" if depth == "simple" else "with specific reasoning"
    warning_line = f"\n\nNote: {warning}" if warning else ""

    user_message = f"""Repository: {repo_id}
Question: {user_query}
Explanation Depth: {depth_hint}

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
        logger.error("[explain] LLM call failed: %s", e)
        # Degraded response: provide basic info at least
        return f"""A temporary error occurred while generating the explanation.

Basic Info:
- Repository: {repo_id}
- Question: {user_query[:100]}

Please try again in a moment."""


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
    """'task_recommendation' mode: explains the reasoning for onboarding task recommendations."""
    import os
    
    task_list = state.get("last_task_list", [])
    
    # Convert dict to flat list (for onboarding_tasks structure)
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
        return "No recommended tasks found to explain. Please request a repository analysis first."
    
    # Summarize task info
    task_summary_lines = []
    for i, task in enumerate(task_list[:5], 1):
        if isinstance(task, dict):
            title = task.get("title", "N/A")
            hours = task.get("estimated_hours", "N/A")
            skills = task.get("required_skills", [])
            level = task.get("level", "N/A")
            skills_str = ", ".join(skills[:3]) if skills else "N/A"
            task_summary_lines.append(
                f"{i}. {title} (Level {level}, Est. {hours}h, Skills: {skills_str})"
            )
    
    task_context = "\n".join(task_summary_lines) if task_summary_lines else "No task information"
    
    user_context = state.get("user_context", {})
    user_level = user_context.get("level", "beginner") if isinstance(user_context, dict) else "beginner"
    
    user_message = f"""Repository: {repo_id}
User Level: {user_level}
User Question: {user_query}

## Recommended Task List
{task_context}

Please explain why these tasks were recommended."""

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
        logger.error("[task_explain] LLM call failed: %s", e)
        return f"An error occurred while explaining task recommendations: {e}"


GENERAL_EXPLAIN_MESSAGE = """This recommendation is not based on a quantitative analysis but is an example based on general open-source contribution best practices.

Common patterns for beginners to start contributing to open source are:
- Improving documentation (fixing typos, translation)
- Issues labeled 'good-first-issue'
- Adding test code
- Fixing small bugs

If you want specific contribution recommendations for a particular repository, please ask again with the repository URL.
e.g., "Find good first issues for beginners in the facebook/react repository"
"""


def infer_explain_target(state: dict) -> str:
    """
    Infers the target for 'explain' mode. Fully controlled by Python.
    
    3-way routing:
    - "metric": Explain specific metrics (health_score, etc.)
    - "task_recommendation": Explain the reasoning for task recommendations
    - "general": General explanation/question without context
    """
    user_query = state.get("user_query", "").lower()
    last_answer_kind = state.get("last_answer_kind")
    last_explain_target = state.get("last_explain_target")
    explain_metrics = state.get("explain_metrics", [])
    
    # 1. Extract metric keywords from the current query
    current_metrics = _extract_target_metrics(user_query)
    if current_metrics:
        state["explain_metrics"] = current_metrics
        return "metric"
    
    # 2. Check for score/metric related keywords
    score_keywords = ["score", "why", "low", "high", "reason", "basis"]
    has_score_keyword = any(kw in user_query for kw in score_keywords)
    
    # 3. Detect follow-up questions (using pronouns)
    followup_keywords = ["that", "this", "what is", "how"]
    is_followup = any(kw in user_query for kw in followup_keywords)
    
    # 4. If a score-related question follows a report, it's about a metric
    if last_answer_kind == "report" and has_score_keyword:
        return "metric"
    
    # 5. Follow-up question: maintain the previous target
    if is_followup and last_explain_target:
        if last_explain_target == "metric" and explain_metrics:
            state["explain_metrics"] = explain_metrics
        return last_explain_target
    
    # 6. Keywords related to task recommendations
    task_keywords = ["task", "issue", "recommend", "contribute"]
    if any(kw in user_query for kw in task_keywords):
        return "task_recommendation"
    
    # 7. If there's context, it's about a metric; otherwise, general
    if last_answer_kind in ("report", "explain") and explain_metrics:
        return "metric"
    
    return "general"


def _run_general_explain(user_query: str) -> str:
    """'general' mode: explanation based on general conversation, no quantitative scores."""
    return GENERAL_EXPLAIN_MESSAGE


def _run_concept_qa_with_kb(user_query: str, user_level: str = "beginner") -> str:
    """
    Knowledge-based Concept QA.
    Extracts metric keywords from the query and looks up definitions from metric_definitions.
    """
    import os
    
    # Extract metrics from the query (including aliases)
    metrics = _extract_target_metrics(user_query)
    
    if metrics:
        # Look up the first matched metric in the knowledge base
        metric_key = metrics[0]
        metric_def = METRIC_DEFINITIONS.get(metric_key)
        
        if metric_def:
            # Format the definition from the knowledge base
            metric_definition = format_metric_for_concept_qa(metric_def)
            prompt = CONCEPT_QA_METRIC_PROMPT.format(
                metric_definition=metric_definition,
                metric_name=user_query,
            )
        else:
            # Key exists but no definition (should not happen in theory)
            return CONCEPT_QA_UNKNOWN_METRIC_MSG
    else:
        # If no metric keyword found, try again with aliases
        metric_def = get_metric_by_alias(user_query)
        if metric_def:
            metric_definition = format_metric_for_concept_qa(metric_def)
            prompt = CONCEPT_QA_METRIC_PROMPT.format(
                metric_definition=metric_definition,
                metric_name=user_query,
            )
        else:
            # Metric not found
            return CONCEPT_QA_UNKNOWN_METRIC_MSG
    
    # LLM call
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
        logger.error("[concept_qa] LLM call failed: %s", e)
        return f"An error occurred while explaining the metric: {e}"


def _generate_explain_response(
    user_query: str,
    metrics: list[str],
    explain_context: dict,
    repo_id: str,
    last_brief: str = "",
) -> str:
    """Generates a response for 'explain' mode (legacy compatibility)."""
    return _run_metric_explain(user_query, metrics, explain_context, repo_id, last_brief)


def _get_onboarding_prompt(user_level: str) -> str:
    """Creates the onboarding prompt for the user's level."""
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
    Returns the appropriate system prompt for a given sub_intent.
    
    Args:
        sub_intent: The detailed intent (health | onboarding | compare | etc.).
        user_level: The user's level (beginner/intermediate/advanced).
    
    Returns:
        The system prompt for the given sub_intent.
    """
    # 'onboarding' is handled separately as it requires user_level
    if sub_intent == "onboarding":
        return _get_onboarding_prompt(user_level)
    
    # Look up the rest in the SUB_INTENT_PROMPT_MAP
    prompt = SUB_INTENT_PROMPT_MAP.get(sub_intent)
    if prompt:
        return prompt
    
    # Fallback to the health prompt
    return SUMMARIZE_SYSTEM_PROMPT


def _get_prompt_for_intent(intent: str, user_level: str = "beginner") -> str:
    """
    [Legacy] Returns the appropriate system prompt for a given intent.
    
    New code should use _get_prompt_for_sub_intent().
    """
    # Legacy intent -> sub_intent conversion
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
    """Generates a message for unsupported intents."""
    intent_names = {
        "compare_two_repos": "Repository Comparison",
        "refine_onboarding_tasks": "Task Re-recommendation",
    }
    feature_name = intent_names.get(intent, intent)
    return f"""## Feature in Development

The **{feature_name}** feature is currently under development.

### Available Features
- **Repository Health Analysis**: "Analyze the health of facebook/react"
- **Onboarding Task Recommendation**: "I'm a beginner and want to contribute to react"
- **Detailed Score Explanation**: "Why did this repository get this score?"

More features will be added soon.
"""


def _generate_last_brief(summary: str, repo_id: str = "") -> str:
    """
    Generates a 'last_brief' summary for context in the next turn.
    
    Extracts the core content of the response within 200 characters.
    - Removes markdown headers
    - Extracts the first meaningful sentences
    - Includes the repository name
    
    Args:
        summary: The full response generated by the LLM.
        repo_id: The repository identifier (e.g., "facebook/react").
    
    Returns:
        A summary string of up to 200 characters.
    """
    import re
    
    if not summary or not summary.strip():
        return f"Analysis of {repo_id} complete" if repo_id else ""
    
    # Remove markdown headers (##, ###)
    lines = summary.split("\n")
    content_lines = []
    for line in lines:
        stripped = line.strip()
        # Exclude empty lines, headers, and separators
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("---"):
            continue
        if stripped.startswith("**Next:"):
            continue
        if stripped.startswith("**For more help:"):
            continue
        if stripped.startswith("**Additional questions:"):
            continue
        content_lines.append(stripped)
    
    if not content_lines:
        return f"Analysis of {repo_id} complete" if repo_id else "Analysis complete"
    
    # Join the first meaningful lines (limit 200 chars)
    result = " ".join(content_lines)
    
    # Remove markdown bold (**)
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    
    # Clean up list markers (-, *)
    result = re.sub(r'^[-*]\s*', '', result)
    result = re.sub(r'\s[-*]\s', ' ', result)
    
    # Limit to 200 chars (cut at the last completed sentence)
    if len(result) > 200:
        result = result[:197]
        # Find the last completed sentence
        last_period = max(result.rfind("."), result.rfind("요"), result.rfind("다"))
        if last_period > 100:
            result = result[:last_period + 1]
        else:
            result = result[:197] + "..."
    
    return result


def summarize_node(state: SupervisorState) -> SupervisorState:
    """Synthesizes agent results into a final response."""
    # Check for an error message
    error_message = state.get("error_message")
    if error_message:
        history = state.get("history", [])
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_history = list(history)
        new_history.append({"role": "assistant", "content": error_message})
        new_state["history"] = new_history
        new_state["llm_summary"] = error_message
        return new_state
    
    # Check for Fast Chat result (Agentic mode)
    fast_chat_result = state.get("_fast_chat_result")
    if fast_chat_result and "answer_contract" in fast_chat_result:
        answer_contract = fast_chat_result["answer_contract"]
        summary = answer_contract.get("text", "")
        
        history = state.get("history", [])
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_history = list(history)
        new_history.append({"role": "assistant", "content": summary})
        new_state["history"] = new_history
        new_state["llm_summary"] = summary
        new_state["answer_kind"] = get_answer_kind(
            state.get("intent", DEFAULT_INTENT),
            state.get("sub_intent") or DEFAULT_SUB_INTENT
        )
        return new_state
    
    # Handle Fast Chat directly (legacy graph v1)
    intent = state.get("intent", DEFAULT_INTENT)
    sub_intent = state.get("sub_intent") or DEFAULT_SUB_INTENT
    
    if intent in ("smalltalk", "help", "overview"):
        summary = _handle_fast_chat_direct(intent, sub_intent, state)
        
        history = state.get("history", [])
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_history = list(history)
        new_history.append({"role": "assistant", "content": summary})
        new_state["history"] = new_history
        new_state["llm_summary"] = summary
        new_state["answer_kind"] = get_answer_kind(intent, sub_intent)
        return new_state
    
    # Extract state
    diagnosis_result = state.get("diagnosis_result")
    security_result = state.get("security_result")
    recommend_result = state.get("recommend_result")
    history = state.get("history", [])
    
    # Progress callback
    progress_cb = state.get("_progress_callback")
    if progress_cb:
        progress_cb("Generating response", "Summarizing analysis results...")
    
    # Reuse extracted Intent/SubIntent
    # (For legacy task_type compatibility)
    task_type = state.get("task_type", "diagnose_repo_health")
    
    user_context = state.get("user_context", {})
    
    # Extract and validate user level
    raw_level = user_context.get("level")
    user_level = _validate_user_level(raw_level)
    
    # Previous response summary (for follow-up context)
    last_brief = state.get("last_brief", "")
    
    # Onboarding mode: if sub_intent is 'onboarding' or user_level is 'beginner'
    is_onboarding_mode = (
        sub_intent == "onboarding" or
        user_level == "beginner"
    )

    # Extract last user query (prefer history, fallback to state.user_query)
    user_query = ""
    for turn in reversed(history):
        if turn.get("role") == "user":
            user_query = turn.get("content", "")
            break
    
    # On the first turn, history is empty, so use user_query from state
    if not user_query:
        user_query = state.get("user_query", "")
    
    # Check for recommendation intent without repo (Active Inference)
    user_query_lower = user_query.lower()
    is_recommendation_request = any(kw in user_query_lower for kw in [
        "추천", "제안", "가이드", "프로젝트", "저장소", "suggest", "recommend"
    ])
    
    repo = state.get("repo")
    if is_recommendation_request and not repo and not diagnosis_result:
        # Active Inference: ask user for preferences
        summary = _generate_recommendation_prompt()
        
        history = state.get("history", [])
        new_state: SupervisorState = dict(state)  # type: ignore[assignment]
        new_history = list(history)
        new_history.append({"role": "assistant", "content": summary})
        new_state["history"] = new_history
        new_state["llm_summary"] = summary
        new_state["answer_kind"] = "chat"
        return new_state

    # 2. Combine results
    context_parts = []
    
    # Handle Refine Tasks result (sub_intent == "refine")
    refine_summary = state.get("refine_summary")
    if refine_summary and sub_intent == "refine":
        context_parts.append(f"## Task Refinement Result\n{_format_refine_summary(refine_summary)}")

    if diagnosis_result:
        # Specify repo name in compare mode
        if sub_intent == "compare":
            repo = state.get("repo", {})
            repo_name = f"{repo.get('owner', '')}/{repo.get('name', '')}"
            context_parts.append(f"## Repository A: {repo_name}\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")
        else:
            context_parts.append(f"## Diagnosis Result\n{_format_diagnosis(diagnosis_result, is_onboarding_mode, user_level)}")

    # Comparison target repository result (compare mode)
    compare_result = state.get("compare_diagnosis_result")
    if compare_result and sub_intent == "compare":
        compare_repo = state.get("compare_repo", {})
        compare_repo_name = f"{compare_repo.get('owner', '')}/{compare_repo.get('name', '')}"
        context_parts.append(f"## Repository B: {compare_repo_name}\n{_format_diagnosis(compare_result, is_onboarding_mode, user_level)}")

    if security_result:
        context_parts.append(f"## Security Analysis\n{_format_result(security_result)}")

    if recommend_result:
        context_parts.append(f"## Recommendation\n{_format_result(recommend_result)}")

    # 3. Generate LLM response
    repo = state.get("repo", {})
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}" if repo else "unknown"
    
    # 'explain' mode: 3-way pipeline
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
        # Concept QA / Chat respond directly without diagnosis
        if is_concept_qa(intent, sub_intent):
            # Knowledge-based Concept QA
            summary = _run_concept_qa_with_kb(user_query, user_level)
        elif is_chat(intent, sub_intent):
            summary = _generate_summary_with_llm_v2(
                user_query=user_query,
                context="",
                sub_intent=sub_intent,
                user_level=user_level,
                intent=intent,
                last_brief=last_brief,
                state=state,
            )
        elif sub_intent == "compare":
            summary = "To compare two repositories, please provide two repository URLs. e.g., 'compare facebook/react and vuejs/vue'"
        else:
            summary = _generate_summary_with_llm_v2(
                user_query=user_query,
                context="",
                sub_intent=sub_intent,
                user_level=user_level,
                intent=intent,
                last_brief=last_brief,
                state=state,
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
            state=state,
        )

    logger.info("[summarize_node] repo=%s, intent=%s, sub_intent=%s, user_level=%s, summary_length=%d", 
                repo_id, intent, sub_intent, user_level, len(summary))

    new_state: SupervisorState = dict(state)  # type: ignore[assignment]

    # Add assistant response to history
    new_history = list(history)
    new_history.append({"role": "assistant", "content": summary})
    new_state["history"] = new_history
    new_state["llm_summary"] = summary
    
    # 4. Set response metadata for UI
    
    # answer_kind: for UI badge display (report/explain/refine/concept/chat)
    new_state["answer_kind"] = get_answer_kind(intent, sub_intent)
    
    # last_brief: summary of the current response for next turn's context (under 200 chars)
    # - Extracts the first meaningful sentences from the response
    new_state["last_brief"] = _generate_last_brief(summary, repo_id)
    
    # 5. Update multi-turn state (context for the next turn)
    
    # last_repo: save the currently analyzed repository
    if repo:
        new_state["last_repo"] = repo
    
    # last_intent, last_sub_intent, last_answer_kind: save the current context
    new_state["last_intent"] = intent
    new_state["last_sub_intent"] = sub_intent
    new_state["last_answer_kind"] = new_state["answer_kind"]
    
    # last_task_list: save the list of onboarding tasks (for refining in the next turn)
    if diagnosis_result:
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        if onboarding_tasks:
            # Convert to a flat list before saving
            task_list = []
            for difficulty in ["beginner", "intermediate", "advanced"]:
                for task in onboarding_tasks.get(difficulty, []):
                    task_copy = dict(task)
                    if "difficulty" not in task_copy:
                        task_copy["difficulty"] = difficulty
                    task_list.append(task_copy)
            new_state["last_task_list"] = task_list

    # 6. Agentic mode: Create AgenticSupervisorOutput
    import os
    if os.getenv("ODOC_AGENTIC_MODE", "").lower() in ("1", "true"):
        new_state["_agentic_output"] = _build_agentic_output(new_state, summary)

    return new_state


def _build_agentic_output(state: SupervisorState, summary: str) -> dict:
    """Creates the AgenticSupervisorOutput."""
    from backend.agents.shared.contracts import (
        AgenticSupervisorOutput,
        AnswerContract,
    )
    
    # Extract sources from the executor result
    plan_result = state.get("_plan_execution_result", {})
    results = plan_result.get("results", {})
    artifacts = plan_result.get("artifacts", {})
    
    sources = []
    source_kinds = []
    plan_executed = []
    
    for step_id, step_result in results.items():
        plan_executed.append(step_id)
        if isinstance(step_result, dict):
            # Extract sources from answer_contract if it exists
            answer_contract = step_result.get("result", {}).get("answer_contract")
            if answer_contract and isinstance(answer_contract, dict):
                sources.extend(answer_contract.get("sources", []))
                source_kinds.extend(answer_contract.get("source_kinds", []))
    
    # Also collect from artifacts
    for step_id, artifact_ids in artifacts.items():
        sources.extend(artifact_ids)
    
    # Remove duplicates
    sources = list(dict.fromkeys(sources))
    source_kinds = list(dict.fromkeys(source_kinds))
    
    # Match lengths
    while len(source_kinds) < len(sources):
        source_kinds.append("unknown")
    
    answer = AnswerContract(
        text=summary,
        sources=sources[:10],  # Max 10
        source_kinds=source_kinds[:10],
    )
    
    output = AgenticSupervisorOutput(
        answer=answer,
        intent=state.get("intent", "analyze"),
        plan_executed=plan_executed,
        artifacts_used=sources,
        session_id=state.get("_session_id", ""),
        turn_id=state.get("_turn_id", ""),
        status="success" if not state.get("error_message") else "error",
        error_message=state.get("error_message"),
    )
    
    return output.model_dump()


def _format_onboarding_tasks(
    tasks: list[TaskSuggestion],
    user_level: str,
    max_tasks: int = 5,
) -> tuple[str, bool]:
    """
    Formats onboarding tasks into a table. Fully controlled by Python.
    
    Returns:
        A tuple of (formatted_table, has_mismatch)
    """
    if not tasks:
        return "(No recommended tasks)", False
    
    difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    difficulty_kr = {"beginner": "Easy", "intermediate": "Medium", "advanced": "Hard"}
    user_order = difficulty_order.get(user_level, 0)
    
    has_mismatch = False
    lines = []
    lines.append("| No. | Title | Difficulty | Est. Time | Link |")
    lines.append("|---|---|---|---|---|")
    
    for i, task in enumerate(tasks[:max_tasks], 1):
        title = task.title[:40] + "..." if len(task.title) > 40 else task.title
        difficulty = getattr(task, "difficulty", "beginner")
        diff_kr = difficulty_kr.get(difficulty, difficulty)
        task_order = difficulty_order.get(difficulty, 0)
        
        if task_order > user_order:
            diff_kr += " ⚠️"
            has_mismatch = True
        
        est_time = getattr(task, "estimated_time", "1-2h")
        url = getattr(task, "url", "#")
        issue_num = url.split("/")[-1] if url and "/" in url else str(i)
        
        lines.append(f"| {i} | {title} | {diff_kr} | {est_time} | [#{issue_num}]({url}) |")
    
    return "\n".join(lines), has_mismatch


def _format_health_top_tasks(tasks: list[TaskSuggestion], max_tasks: int = 3) -> str:
    """Formats top 3 tasks for the Health mode appendix."""
    if not tasks:
        return "(No recommended tasks)"
    
    difficulty_kr = {"beginner": "Easy", "intermediate": "Medium", "advanced": "Hard"}
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
    Calculates the winner for each metric in Compare mode based on score differences.
    
    Returns:
        A dict with metrics, overall winner, and a markdown table.
    """
    metric_names = {
        "health_score": "Health",
        "onboarding_score": "Onboarding",
        "activity": "Activity",
        "documentation": "Documentation",
    }
    
    results = {"metrics": {}, "wins": {repo_a: 0, repo_b: 0}}
    table_lines = ["| Metric | " + repo_a + " | " + repo_b + " | Winner |"]
    table_lines.append("|---|---|---|---|")
    
    for metric, name_en in metric_names.items():
        score_a = scores_a.get(metric, 0) or 0
        score_b = scores_b.get(metric, 0) or 0
        diff = abs(score_a - score_b)
        
        if diff < 5:
            winner = "Draw"
            note = "Similar"
        elif score_a > score_b:
            winner = repo_a
            note = f"+{diff:.0f}pts"
            results["wins"][repo_a] += 1
        else:
            winner = repo_b
            note = f"+{diff:.0f}pts"
            results["wins"][repo_b] += 1
        
        results["metrics"][metric] = {"winner": winner, "diff": diff, "note": note}
        table_lines.append(f"| {name_en} | {score_a:.0f} | {score_b:.0f} | {winner} ({note}) |")
    
    wins_a = results["wins"][repo_a]
    wins_b = results["wins"][repo_b]
    
    if wins_a > wins_b:
        results["overall_winner"] = repo_a
    elif wins_b > wins_a:
        results["overall_winner"] = repo_b
    else:
        results["overall_winner"] = "Draw"
    
    results["table_md"] = "\n".join(table_lines)
    return results


def _format_diagnosis(result: Any, is_onboarding_mode: bool = False, user_level: str = "beginner") -> str:
    """
    Formats the diagnosis result into a string to provide explicit data to the LLM.
    
    Args:
        result: The diagnosis result dictionary.
        is_onboarding_mode: If True, emphasizes 5 onboarding tasks.
        user_level: The user's level (beginner/intermediate/advanced).
    """
    if not isinstance(result, dict):
        return str(result)
    
    parts = []
    
    # 0. Repository Info
    details = result.get("details", {})
    repo_info = details.get("repo_info", {})
    if repo_info:
        parts.append("### Repository Info")
        parts.append(f"- Name: {repo_info.get('full_name', 'N/A')}")
        parts.append(f"- Description: {repo_info.get('description', 'N/A')}")
        parts.append(f"- Stars: {repo_info.get('stars', 'N/A')}")
        parts.append(f"- Forks: {repo_info.get('forks', 'N/A')}")
        parts.append(f"- Open Issues: {repo_info.get('open_issues', 'N/A')}")
    
    # 1. Score Info (Required)
    scores = result.get("scores", {})
    if scores:
        parts.append("\n### Scores (out of 100)")
        parts.append(f"- health_score (Overall Health): {scores.get('health_score', 'N/A')}")
        parts.append(f"- documentation_quality (Doc Quality): {scores.get('documentation_quality', 'N/A')}")
        parts.append(f"- activity_maintainability (Activity): {scores.get('activity_maintainability', 'N/A')}")
        parts.append(f"- onboarding_score (Onboarding Ease): {scores.get('onboarding_score', 'N/A')}")
        parts.append(f"- is_healthy: {scores.get('is_healthy', 'N/A')}")
    
    # 2. Label Info (Interpretation of scores)
    labels = result.get("labels", {})
    if labels:
        parts.append("\n### Diagnosis Labels (Score Interpretation)")
        for key, value in labels.items():
            if value:  # Only non-None values
                parts.append(f"- {key}: {value}")
    
    # 3. Activity Metrics (Raw numbers)
    activity = details.get("activity", {})
    if activity:
        parts.append("\n### Activity Data (last 90 days) - Use these numbers in your answer")
        
        commit = activity.get("commit", {})
        if commit:
            parts.append(f"- Total commits: {commit.get('total_commits', 'N/A')}")
            parts.append(f"- Unique authors: {commit.get('unique_authors', 'N/A')}")
            parts.append(f"- Daily commits avg: {_safe_round(commit.get('commits_per_day'))}")
            parts.append(f"- Days since last commit: {commit.get('days_since_last_commit', 'N/A')}")
        
        issue = activity.get("issue", {})
        if issue:
            parts.append(f"- Currently open issues: {issue.get('open_issues', 'N/A')}")
            parts.append(f"- Issues opened in window: {issue.get('opened_issues_in_window', 'N/A')}")
            parts.append(f"- Issues closed in window: {issue.get('closed_issues_in_window', 'N/A')}")
            closure_ratio = issue.get('issue_closure_ratio')
            if closure_ratio is not None:
                parts.append(f"- Issue closure ratio: {_safe_round(closure_ratio * 100)}%")
            avg_age = issue.get('avg_open_issue_age_days')
            if avg_age is not None:
                parts.append(f"- Avg open issue age: {_safe_round(avg_age, 0)} days")
        
        pr = activity.get("pr", {})
        if pr:
            parts.append(f"- PRs in window: {pr.get('prs_in_window', 'N/A')}")
            parts.append(f"- Merged PRs: {pr.get('merged_in_window', 'N/A')}")
            merge_ratio = pr.get('pr_merge_ratio')
            if merge_ratio is not None:
                parts.append(f"- PR merge ratio: {_safe_round(merge_ratio * 100)}%")
            parts.append(f"- Currently open PRs: {pr.get('open_prs', 'N/A')}")
    
    # 4. Documentation Info
    docs = details.get("docs", {})
    if docs:
        parts.append("\n### Documentation Analysis")
        readme_summary = docs.get("readme_summary_for_user", "")
        if readme_summary:
            # Summary is already length-limited during generation (300-500 chars)
            parts.append(f"- README Summary: {readme_summary}")
        categories = docs.get("readme_categories", {})
        if categories:
            present = [k for k, v in categories.items() if v]
            missing = [k for k, v in categories.items() if not v]
            if present:
                parts.append(f"- Included Sections: {', '.join(present)}")
            if missing:
                parts.append(f"- Missing Sections: {', '.join(missing)}")
    
    # 5. Onboarding Info
    onboarding_plan = result.get("onboarding_plan", {})
    if onboarding_plan:
        parts.append("\n### Onboarding Plan")
        setup_time = onboarding_plan.get("estimated_setup_time", "")
        if setup_time:
            parts.append(f"- Estimated Setup Time: {setup_time}")
        steps = onboarding_plan.get("steps", [])
        if steps:
            parts.append(f"- Number of Onboarding Steps: {len(steps)}")
    
    # 6. Onboarding Tasks (with level-based filtering)
    onboarding_tasks_raw = result.get("onboarding_tasks", {})
    if onboarding_tasks_raw:
        # Convert dict -> OnboardingTasks object
        onboarding_tasks_obj = _dict_to_onboarding_tasks(onboarding_tasks_raw)
        
        beginner_tasks = onboarding_tasks_raw.get("beginner", [])
        intermediate_tasks = onboarding_tasks_raw.get("intermediate", [])
        advanced_tasks = onboarding_tasks_raw.get("advanced", [])
        meta = onboarding_tasks_raw.get("meta", {})
        
        # Apply level-based filtering
        filtered_tasks = filter_tasks_for_user(
            tasks=onboarding_tasks_obj,
            user_level=user_level,
        )
        
        def get_difficulty_en(diff: str) -> str:
            return {"beginner": "Easy", "intermediate": "Medium", "advanced": "Hard"}.get(diff, diff)
        
        reason_map = {
            "good_first_issue": "Good First Issue",
            "help_wanted": "Help Wanted",
            "docs_issue": "Documentation",
            "test_issue": "Testing",
            "hacktoberfest": "Hacktoberfest",
            "difficulty_beginner": "Beginner Level",
        }
        
        level_en = {
            "beginner": "Beginner",
            "intermediate": "Intermediate", 
            "advanced": "Advanced"
        }.get(user_level, "Beginner")
        
        def get_difficulty_mismatch_note(task_difficulty: str) -> str:
            """Returns a note if user level and task difficulty mismatch."""
            difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
            user_order = difficulty_order.get(user_level, 0)
            task_order = difficulty_order.get(task_difficulty, 0)
            
            if task_order > user_order:
                diff = task_order - user_order
                if diff == 1:
                    return " (Note: a bit challenging)"
                else:
                    return " (Note: quite challenging)"
            return ""
        
        if is_onboarding_mode:
            # Onboarding mode: generate a fully formatted task list in Python
            formatted_tasks, has_mismatch = _format_onboarding_tasks(
                tasks=filtered_tasks,
                user_level=user_level,
                max_tasks=5,
            )
            
            parts.append(f"\n### Recommended Onboarding Tasks (for {level_en})")
            if has_mismatch:
                parts.append(f"\n**Note**: Since there are few tasks for {level_en}, some more difficult tasks are included.")
            parts.append(f"\n{formatted_tasks}")
        else:
            # Normal mode: summary + 3 recommended tasks for the user's level
            total = meta.get("total_count", 0)
            
            parts.append(f"\n### Onboarding Task Summary")
            parts.append(f"- Total Tasks: {total}")
            parts.append(f"- For Beginners: {len(beginner_tasks)}")
            parts.append(f"- For Intermediate: {len(intermediate_tasks)}")
            parts.append(f"- For Advanced: {len(advanced_tasks)}")
            
            # Recommend 3 tasks based on user level (for Health mode appendix)
            selected_tasks = filtered_tasks[:3]
            if selected_tasks:
                parts.append(f"\n### Recommended Tasks for {level_en} (for reference)")
                formatted_top3 = _format_health_top_tasks(selected_tasks, max_tasks=3)
                parts.append(formatted_top3)
    
    return "\n".join(parts) if parts else str(result)


def _dict_to_onboarding_tasks(data: dict) -> OnboardingTasks:
    """
    Converts a dict of onboarding_tasks to an OnboardingTasks object.
    Needed for the filter_tasks_for_user function.
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
    """Formats a generic result into a string."""
    import json
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


def _format_refine_summary(refine_summary: dict) -> str:
    """Formats the result of Refine Tasks into a string."""
    parts = []
    
    followup_type = refine_summary.get("followup_type", "unknown")
    original_count = refine_summary.get("original_count", 0)
    filtered_count = refine_summary.get("filtered_count", 0)
    
    parts.append(f"### Filtering Info")
    parts.append(f"- Filter Type: {_get_followup_type_en(followup_type)}")
    parts.append(f"- Original Task Count: {original_count}")
    parts.append(f"- Filtered Task Count: {filtered_count}")
    
    # Difficulty distribution
    dist = refine_summary.get("difficulty_distribution", {})
    if dist:
        parts.append(f"\n### Difficulty Distribution")
        parts.append(f"- Beginner: {dist.get('beginner', 0)}")
        parts.append(f"- Intermediate: {dist.get('intermediate', 0)}")
        parts.append(f"- Advanced: {dist.get('advanced', 0)}")
    
    # Filtered task list
    tasks = refine_summary.get("tasks", [])
    if tasks:
        parts.append(f"\n### Filtered Task List")
        for i, task in enumerate(tasks[:5], 1):
            title = task.get("title", "No title")
            difficulty = task.get("difficulty", "unknown")
            level = task.get("level", "?")
            url = task.get("url", "")
            parts.append(f"\n**{i}. {title}**")
            parts.append(f"- Difficulty: {difficulty} (Lv.{level})")
            if url:
                parts.append(f"- Link: {url}")
    
    # If no tasks
    if not tasks:
        message = refine_summary.get("message", "")
        if message:
            parts.append(f"\n{message}")
        else:
            parts.append("\nNo tasks match the criteria.")
    
    return "\n".join(parts)


def _get_followup_type_en(followup_type: str) -> str:
    """Translates followup_type to English."""
    mapping = {
        "refine_easier": "Easier Tasks",
        "refine_harder": "Harder Tasks",
        "refine_different": "Different Kind of Tasks",
        "ask_detail": "Detailed Explanation",
        "compare_similar": "Compare Similar Repos",
        "continue_same": "Further Analysis",
    }
    return mapping.get(followup_type, followup_type)


def _generate_summary_with_llm_v2(
    user_query: str, 
    context: str, 
    sub_intent: str = "health",
    user_level: str = "beginner",
    intent: str = "analyze",
    last_brief: str = "",
    state: Optional[dict] = None,
) -> str:
    """
    Generates the final summary using an LLM (v2 - sub_intent based).
    
    Args:
        user_query: The user's question.
        context: The context from the diagnosis results.
        sub_intent: The detailed intent (e.g., health, onboarding).
        user_level: The user's level (beginner/intermediate/advanced).
        intent: The parent intent (e.g., analyze, followup).
        last_brief: A summary of the previous response for context.
        state: The SupervisorState (needed for AnswerContract in Agentic mode).
    """
    import os
    from backend.common.events import get_artifact_store, persist_artifact
    
    # Agentic mode check: if answer_contract already exists, use it.
    if state:
        plan_result = state.get("_plan_execution_result", {})
        results = plan_result.get("results", {})
        for step_id, step_result in results.items():
            if isinstance(step_result, dict):
                answer_contract = step_result.get("result", {}).get("answer_contract")
                if answer_contract and isinstance(answer_contract, dict):
                    text = answer_contract.get("text", "")
                    if text:
                        logger.info("[summarize_node] Using AnswerContract from executor")
                        return text
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    # Select prompt based on sub_intent
    system_prompt = _get_prompt_for_sub_intent(sub_intent, user_level)
    
    # Inject persona based on user_profile
    if state:
        user_profile = state.get("user_profile")
        persona_instruction = _build_persona_instruction(user_profile)
        if persona_instruction:
            system_prompt = system_prompt + "\n" + persona_instruction
            logger.debug("[_generate_summary_with_llm_v2] Persona injected: %s", persona_instruction[:100])
    
    # Log which prompt mode was selected
    logger.debug("[_generate_summary_with_llm_v2] intent=%s, sub_intent=%s, user_level=%s, has_last_brief=%s", 
                 intent, sub_intent, user_level, bool(last_brief))

    # Add context from previous turn if it's a followup intent
    context_prefix = ""
    if intent == "followup" and last_brief:
        context_prefix = f"""## Previous Context
{last_brief}

---

"""
    
    # Agentic mode: attempt to call with a contract
    use_contract = os.getenv("ODOC_AGENTIC_MODE", "").lower() in ("1", "true")
    
    if use_contract and state:
        try:
            from backend.llm.contract_wrapper import generate_answer_with_contract
            from backend.agents.shared.contracts import ArtifactRef, ArtifactKind
            
            # Collect artifacts
            session_id = state.get("_session_id", "")
            artifact_refs = []
            
            if session_id:
                store = get_artifact_store()
                for kind in ["diagnosis_raw", "onboarding_tasks", "activity_metrics"]:
                    artifacts = store.get_by_kind(session_id, kind)
                    for art in artifacts:
                        try:
                            art_kind = ArtifactKind(art.kind)
                        except ValueError:
                            art_kind = ArtifactKind.SUMMARY
                        artifact_refs.append(ArtifactRef(
                            id=art.id,
                            kind=art_kind,
                            session_id=session_id,
                        ))
            
            # Add diagnosis_result as an inline artifact if it exists
            diagnosis_result = state.get("diagnosis_result")
            if diagnosis_result and not artifact_refs:
                inline_id = persist_artifact(
                    kind="diagnosis_raw",
                    content=diagnosis_result,
                )
                artifact_refs.append(ArtifactRef(
                    id=inline_id,
                    kind=ArtifactKind.DIAGNOSIS_RAW,
                    session_id=session_id or "inline",
                ))
            
            if artifact_refs:
                prompt = f"""User Question: {user_query}

{context_prefix}Analysis Result:
{context}

Based on the results above, please answer the user's question.
Structure your answer with an introduction, main body (data analysis), and conclusion (suggestions), using at least three paragraphs."""

                answer = generate_answer_with_contract(
                    prompt=prompt,
                    context_artifacts=artifact_refs,
                    require_sources=True,
                    max_tokens=4096,
                    temperature=0.3,
                )
                
                logger.info("[summarize_node] Contract-based answer generated, sources=%d", len(answer.sources))
                return answer.text
                
        except Exception as e:
            logger.warning("[summarize_node] Contract-based generation failed, falling back: %s", e)
    
    # Default LLM call (fallback)
    user_message = f"""
User Question: {user_query}

{context_prefix}Analysis Result:
{context}

Based on the results above, please answer the user's question.
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
        logger.error("[summarize_node] LLM call failed: %s", e)
        return f"An error occurred while generating the summary: {e}"


def _generate_summary_with_llm(
    user_query: str, 
    context: str, 
    intent: str = "diagnose_repo_health",
    user_level: str = "beginner"
) -> str:
    """
    [Legacy] Generates the final summary using an LLM.
    
    New code should use _generate_summary_with_llm_v2().
    """
    import os
    
    llm_client = fetch_llm_client()
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    
    # Select prompt based on intent (legacy)
    system_prompt = _get_prompt_for_intent(intent, user_level)
    
    logger.debug("[_generate_summary_with_llm] intent=%s, user_level=%s", intent, user_level)

    user_message = f"""
User Question: {user_query}

Analysis Result:
{context}

Based on the results above, please answer the user's question.
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
        logger.error("[summarize_node] LLM call failed: %s", e)
        return f"An error occurred while generating the summary: {e}"