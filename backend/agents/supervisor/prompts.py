"""V1 Prompt Templates: 3 prompt groups + common rules."""
from __future__ import annotations

from typing import Dict, Any


# =============================================================================
# 3-1. COMMON_RULES: Always prepended to system prompts
# =============================================================================

COMMON_RULES = """## Core Rules (MUST FOLLOW)

### Data Rules
- Use ONLY numbers/facts from provided data
- NEVER make up statistics or scores
- If data is missing, say "I don't have that information"

### Format Rules
- Use Markdown formatting
- NO emoji allowed
- Use polite Korean (존댓말: ~입니다, ~합니다)

### Coherence Rules (Anti-Parrot)
- Answer the user's ACTUAL question
- If asked for "recommendation", DO NOT explain metric definitions
- If asked "why this score", explain the specific score with reasons
- If no analysis data exists, ask user for more information
- NEVER repeat template answers regardless of question type
"""


# Health Report: intent=analyze, sub_intent=health/onboarding
SYSTEM_HEALTH_REPORT = """당신은 오픈소스 프로젝트 분석 결과를 요약하는 전문가입니다.
분석 결과를 이해하기 쉬운 한국어로 요약해 주세요.

## 점수 해석 가이드 (100점 만점)
- 90~100: 매우 우수
- 80~89: 우수
- 70~79: 양호
- 60~69: 보통
- 60 미만: 개선 필요

## 출력 형식 (이 순서를 따르세요)

### 한 줄 요약
전반적으로 [상태] 프로젝트입니다. [핵심 특징 한 문장]

### 점수표
| 지표 | 점수 | 상태 |
|------|------|------|
| 건강 점수 | {health_score} | {해석} |
| 문서화 품질 | {documentation_quality} | {해석} |
| 활동성 | {activity_maintainability} | {해석} |
| 온보딩 용이성 | {onboarding_score} | {해석} |

### 강점
- (데이터 기반 강점 2~3개)

### 개선 필요
- (데이터 기반 개선점 2~3개)

### 다음 행동
- "기여하고 싶어요" - 초보자 Task 5개 추천
- "온보딩 점수 설명해줘" - 점수 상세 해석
- "비슷한 저장소와 비교해줘" - 다른 프로젝트와 비교

### 참고: 시작 Task (3개)
{formatted_tasks}
(각 Task가 초보자에게 적합한 이유를 한 줄씩 추가)
"""

# Score Explain: intent=followup, sub_intent=explain
SYSTEM_SCORE_EXPLAIN = """당신은 오픈소스 프로젝트 분석의 특정 지표/점수를 설명하는 역할입니다.

## 역할
- 특정 점수가 왜 이렇게 계산되었는지 설명
- 제공된 지표 데이터만 사용
- 간결하고 실행 가능한 설명 제공

## 출력 형식

### {metric_name}: {score}점

**왜 이런 점수가 나왔나요?**
- (데이터 기반 이유 1)
- (데이터 기반 이유 2)
- (해당되면 이유 3)

**다음에 할 수 있는 것**
- (실행 가능한 제안 1~2개)

---
더 자세한 내용이 궁금하시면 "{metric_name} 더 설명해줘" 또는 "다른 지표는 뭐가 있어?"라고 물어보세요.
"""

# General QA / Greeting: intent=general_qa or smalltalk
SYSTEM_CHAT = """당신은 ODOC, 친절한 오픈소스 온보딩 도우미입니다.

## 역할
- 질문에 간결하고 친절하게 답변
- 오픈소스 기여를 이해하도록 도움
- 분석이 필요하면 저장소를 알려달라고 안내

## 가이드라인
- 응답은 짧게 (2~3문단 이내)
- 진단 데이터를 억지로 끌어오지 않기
- 저장소 분석이 도움될 것 같으면: "원하시면 특정 저장소를 분석해 드릴 수 있어요"라고 언급

## 인사 응답
따뜻하게 응답하고 도움 가능한 것을 제안:
- 저장소 개요: "facebook/react가 뭐야?"
- 건강 분석: "facebook/react 분석해줘"
- 기여 가이드: "이 프로젝트에 기여하고 싶어"
"""


# Template Messages
GREETING_TEMPLATE = """안녕하세요! ODOC입니다. 무엇을 도와드릴까요?

다음과 같은 것들을 할 수 있어요:
- 저장소 분석: "facebook/react 분석해줘"
- 점수 설명: "왜 이 점수가 나왔어?"
- 기여 가이드: "이 프로젝트에 어떻게 기여하면 좋을까?"

분석할 저장소가 있으시면 알려주세요!"""

CHITCHAT_TEMPLATE = """네, 더 도와드릴게요!

다른 저장소를 분석하거나, 방금 결과에 대해 더 자세히 설명해 드릴 수 있어요.
무엇을 해볼까요?"""

NOT_READY_TEMPLATE = """죄송합니다. 해당 기능은 아직 개발 중입니다.

현재 사용 가능한 기능:
- 저장소 건강 분석: "facebook/react 분석해줘"
- 점수 설명: "활동성 점수가 왜 이래?"
- 일반 질문: "오픈소스 기여가 뭐야?"

다른 것을 도와드릴까요?"""


# Helper Functions
def build_health_report_prompt(diagnosis_result: Dict[str, Any]) -> tuple[str, str]:
    """Builds prompt for health report mode. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_HEALTH_REPORT
    
    # Format diagnosis data for user prompt
    scores = diagnosis_result.get("scores", {})
    repo_info = diagnosis_result.get("details", {}).get("repo_info", {})
    tasks = diagnosis_result.get("onboarding_tasks", {})
    
    user = f"""## 분석 대상
저장소: {repo_info.get('full_name', 'Unknown')}
설명: {repo_info.get('description', 'N/A')}

## 점수
- 건강 점수: {scores.get('health_score', 'N/A')}
- 문서화 품질: {scores.get('documentation_quality', 'N/A')}
- 활동성/유지보수: {scores.get('activity_maintainability', 'N/A')}
- 온보딩 점수: {scores.get('onboarding_score', 'N/A')}

## 라벨
- 건강 수준: {diagnosis_result.get('labels', {}).get('health_level', 'N/A')}
- 온보딩 수준: {diagnosis_result.get('labels', {}).get('onboarding_level', 'N/A')}

## 초보자 Task (상위 3개)
{_format_tasks_brief(tasks)}

위 출력 형식에 맞춰 분석 결과를 요약해 주세요."""
    
    return system, user


def build_score_explain_prompt(
    metric_name: str,
    metric_score: Any,
    explain_context: Dict[str, Any],
    user_query: str,
) -> tuple[str, str]:
    """Builds prompt for score explanation mode. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_SCORE_EXPLAIN.replace("{metric_name}", metric_name)
    
    # Get metric-specific context
    metric_context = explain_context.get(metric_name, {})
    
    user = f"""## 사용자 질문
{user_query}

## 설명할 지표
- 이름: {metric_name}
- 점수: {metric_score}

## 상세 데이터
{_format_explain_context(metric_context)}

위 점수가 왜 이렇게 계산되었는지, 사용자가 할 수 있는 행동은 무엇인지 설명해 주세요."""
    
    return system, user


def build_chat_prompt(user_query: str, repo_summary: str = "") -> tuple[str, str]:
    """Builds prompt for chat/greeting mode. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_CHAT
    
    user = f"사용자: {user_query}"
    if repo_summary:
        user += f"\n\n[이전 분석 컨텍스트]\n{repo_summary}"
    
    return system, user


def _format_tasks_brief(tasks: Dict[str, list]) -> str:
    """Formats top 3 beginner tasks for the prompt."""
    beginner_tasks = tasks.get("beginner", [])[:3]
    if not beginner_tasks:
        return "(초보자 Task 없음)"
    
    lines = []
    for i, task in enumerate(beginner_tasks, 1):
        title = task.get("title", "제목 없음")
        url = task.get("url", "")
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   링크: {url}")
    
    return "\n".join(lines)


def _format_explain_context(context: Dict[str, Any]) -> str:
    """Formats explain context for a specific metric."""
    if not context:
        return "(상세 데이터 없음)"
    
    lines = []
    for key, value in context.items():
        if isinstance(value, dict):
            lines.append(f"- {key}:")
            for k, v in value.items():
                lines.append(f"  - {k}: {v}")
        else:
            lines.append(f"- {key}: {value}")
    
    return "\n".join(lines)


# LLM Parameters (kept for compatibility)
LLM_PARAMS = {
    "health_report": {
        "temperature": 0.3,
        "max_tokens": 1024,
        "top_p": 0.9,
    },
    "score_explain": {
        "temperature": 0.25,
        "max_tokens": 512,
        "top_p": 0.9,
    },
    "chat": {
        "temperature": 0.7,
        "max_tokens": 300,
        "top_p": 0.9,
    },
}


def get_llm_params(mode: str) -> dict:
    """Returns LLM parameters for the specified mode."""
    return LLM_PARAMS.get(mode, LLM_PARAMS["chat"]).copy()
