"""V1 Prompt Templates: 3 prompt groups + common rules."""
from __future__ import annotations

from typing import Dict, Any


# 3-1. COMMON_RULES: Always prepended to system prompts
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


# Follow-up Evidence: 직전 턴 결과에 대한 근거 설명
SYSTEM_FOLLOWUP_EVIDENCE = """당신은 직전 분석 결과의 근거를 설명하는 역할입니다.

## 역할
- 직전 턴에서 제공한 결과의 근거/출처를 설명
- 제공된 아티팩트 데이터만 사용 (추측 금지)
- 3-5문장으로 간결하게 설명

## 출력 형식

### 근거 설명

[3-5문장: 직전 결과가 왜 그렇게 나왔는지 설명]

**참조 데이터**
- [아티팩트 출처 1]: [값/요약]
- [아티팩트 출처 2]: [값/요약]
- (필요시 추가)

**다음 행동**
- (관련 후속 질문 1-2개 제안)
"""

# Follow-up No Artifacts Template
FOLLOWUP_NO_ARTIFACTS_TEMPLATE = """이전 분석 결과가 없어 근거를 설명하기 어렵습니다.

**다음 행동**
- 저장소 분석하기: `facebook/react 분석해줘`
- 이전에 분석한 저장소가 있다면 다시 물어봐 주세요"""

FOLLOWUP_SOURCE_ID = "SYS:TEMPLATES:FOLLOWUP"


# Refine Templates (온보딩 Task 재정렬/발췌)
SYSTEM_REFINE = """당신은 온보딩 Task 목록을 사용자 요청에 맞게 재정렬·발췌하는 역할입니다.

## 역할
- 주어진 Task 목록에서 요청된 개수만큼 선별
- priority 기준 정렬 (낮을수록 높은 우선순위)
- 각 Task가 왜 선택되었는지 간단히 설명

## 출력 형식

### 추천 Task {count}개

{task_list}

**선정 기준**
- (선정 이유 1-2줄)

**다음 행동**
- 더 쉬운 Task: `더 쉬운 거 없어?`
- 상세 분석: `{task_title} 자세히 알려줘`
"""

REFINE_NO_TASKS_TEMPLATE = """이전 분석에서 추천된 Task가 없습니다.

**다음 행동**
- 저장소 온보딩 분석: `facebook/react 온보딩 분석해줘`
- 건강도 분석부터 시작: `facebook/react 분석해줘`"""

REFINE_EMPTY_RESULT_TEMPLATE = """요청하신 조건에 맞는 Task를 찾지 못했습니다.

**다음 행동**
- 조건 완화: `아무 Task나 3개 알려줘`
- 다른 저장소 분석: `vuejs/core 분석해줘`"""

REFINE_SOURCE_ID = "SYS:TEMPLATES:REFINE"
REFINE_TASKS_SOURCE_KIND = "onboarding_tasks"


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


# Smalltalk/Help Templates (경량 경로: LLM 호출 없이 즉답)
SMALLTALK_GREETING_TEMPLATE = """안녕하세요! ODOC입니다.

오픈소스 프로젝트의 건강도를 진단하고, 기여에 적합한 Task를 추천해 드려요.

**다음 행동**
- 저장소 분석하기: `facebook/react 분석해줘`
- 사용법 알아보기: `뭘 할 수 있어?`"""

SMALLTALK_CHITCHAT_TEMPLATE = """네, 알겠습니다!

**다음 행동**
- 저장소 분석하기: `owner/repo 분석해줘`
- 이전 분석 더 보기: `점수 자세히 설명해줘`"""

HELP_GETTING_STARTED_TEMPLATE = """ODOC은 오픈소스 저장소 건강도 진단 도구입니다.

**주요 기능**
1. **건강 분석**: 저장소 활동성, 문서화, 커뮤니티를 진단합니다.
2. **온보딩 추천**: 초보자에게 적합한 기여 Task를 찾아드립니다.
3. **점수 설명**: 각 지표가 왜 그런 점수인지 설명합니다.

**다음 행동**
- 저장소 분석: `facebook/react 분석해줘`
- 개념 질문: `Health Score가 뭐야?`"""

OVERVIEW_REPO_TEMPLATE = """**{owner}/{repo}** 저장소입니다.

상세한 건강도와 기여 가이드가 필요하시면 분석을 요청해 주세요.

**다음 행동**
- 건강도 분석: `{owner}/{repo} 분석해줘`
- 온보딩 Task 추천: `{owner}/{repo} 기여하고 싶어`"""

# Source constants for Smalltalk/Help
SMALLTALK_SOURCE_ID = "SYS:TEMPLATES:SMALLTALK"
HELP_SOURCE_ID = "SYS:TEMPLATES:HELP"
OVERVIEW_SOURCE_ID = "SYS:TEMPLATES:OVERVIEW"


# Missing Repo Template (저장소 미지정 시)
MISSING_REPO_TEMPLATE = """어떤 저장소를 분석할까요?

저장소 이름을 `owner/repo` 형식으로 알려주세요.

**예시**
- `facebook/react 분석해줘`
- `vuejs/core 건강도 확인해줘`
- `microsoft/vscode 기여하고 싶어`"""

MISSING_REPO_SOURCE_ID = "SYS:TEMPLATES:MISSING_REPO"

# Disambiguation with Candidates Template (후보 제시)
DISAMBIGUATION_CANDIDATES_TEMPLATE = """**{keyword}**로 검색된 저장소가 여러 개 있습니다.

어떤 저장소를 분석할까요?

{candidates}

원하는 저장소를 선택하거나, 정확한 이름을 입력해 주세요."""

DISAMBIGUATION_SOURCE_ID = "SYS:DISAMBIGUATION:CANDIDATES"


# Overview LLM Prompt (아티팩트 기반 3-6문장 개요)
SYSTEM_OVERVIEW = """당신은 GitHub 저장소를 간결하게 소개하는 전문가입니다.

## 역할
- 저장소의 핵심 정보를 3-6문장으로 요약
- 제공된 데이터(repo_facts, readme_head, recent_activity)만 사용
- 추측하거나 데이터 없이 주장하지 않음

## 출력 형식

### {repo_name}

[3-6문장 개요: 프로젝트 목적, 주요 기술, 현재 상태]

**근거**
- [데이터 기반 근거 1]
- [데이터 기반 근거 2]

**다음 행동**
- 건강도 분석: `{owner}/{repo} 분석해줘`
- 기여 가이드: `{owner}/{repo}에 기여하고 싶어`
"""

OVERVIEW_FALLBACK_TEMPLATE = """**{owner}/{repo}**

{description}

| 항목 | 값 |
|------|-----|
| 언어 | {language} |
| Stars | {stars:,} |
| Forks | {forks:,} |

**다음 행동**
- 건강도 분석: `{owner}/{repo} 분석해줘`
- 기여 가이드: `{owner}/{repo}에 기여하고 싶어`"""


def build_overview_prompt(
    owner: str,
    repo: str,
    repo_facts: Dict[str, Any],
    readme_head: str,
    recent_activity: Dict[str, Any],
) -> tuple[str, str]:
    """Builds prompt for Overview mode. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_OVERVIEW.format(
        repo_name=f"{owner}/{repo}",
        owner=owner,
        repo=repo,
    )
    
    user_parts = [f"## 저장소: {owner}/{repo}\n"]
    
    # repo_facts
    user_parts.append("### repo_facts")
    user_parts.append(f"- 설명: {repo_facts.get('description') or '(없음)'}")
    user_parts.append(f"- 언어: {repo_facts.get('language') or '(없음)'}")
    user_parts.append(f"- Stars: {repo_facts.get('stars', 0):,}")
    user_parts.append(f"- Forks: {repo_facts.get('forks', 0):,}")
    user_parts.append(f"- Open Issues: {repo_facts.get('open_issues', 0)}")
    user_parts.append(f"- License: {repo_facts.get('license') or '(없음)'}")
    user_parts.append(f"- Archived: {repo_facts.get('archived', False)}")
    user_parts.append("")
    
    # readme_head
    if readme_head:
        user_parts.append("### readme_head (처음 ~2KB)")
        user_parts.append("```")
        user_parts.append(readme_head[:1500])  # 토큰 절약
        user_parts.append("```")
        user_parts.append("")
    
    # recent_activity
    if recent_activity:
        user_parts.append("### recent_activity (최근 30일)")
        user_parts.append(f"- 커밋 수: {recent_activity.get('commit_count_30d', 0)}")
        user_parts.append(f"- 기여자 수: {recent_activity.get('unique_authors_30d', 0)}")
        user_parts.append(f"- Open PRs: {recent_activity.get('open_prs', 0)}")
        user_parts.append(f"- 마지막 커밋: {recent_activity.get('last_commit_date') or '(없음)'}")
    
    return system, "\n".join(user_parts)


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


def build_followup_evidence_prompt(
    user_query: str,
    prev_intent: str,
    prev_answer_kind: str,
    repo_id: str,
    artifacts: Dict[str, Any],
) -> tuple[str, str]:
    """Builds prompt for follow-up evidence explanation. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_FOLLOWUP_EVIDENCE
    
    user_parts = [f"## 사용자 질문\n{user_query}\n"]
    
    # 직전 턴 정보
    user_parts.append(f"## 직전 턴 정보")
    user_parts.append(f"- 저장소: {repo_id}")
    user_parts.append(f"- 이전 intent: {prev_intent}")
    user_parts.append(f"- 응답 유형: {prev_answer_kind}")
    user_parts.append("")
    
    # 아티팩트 데이터
    user_parts.append("## 참조 가능한 아티팩트")
    
    if "scores" in artifacts:
        user_parts.append("### scores")
        for k, v in artifacts["scores"].items():
            user_parts.append(f"- {k}: {v}")
        user_parts.append("")
    
    if "labels" in artifacts:
        user_parts.append("### labels")
        for k, v in artifacts["labels"].items():
            if isinstance(v, list):
                user_parts.append(f"- {k}: {', '.join(v) if v else '(없음)'}")
            else:
                user_parts.append(f"- {k}: {v}")
        user_parts.append("")
    
    if "explain_context" in artifacts:
        user_parts.append("### explain_context (주요 지표)")
        ctx = artifacts["explain_context"]
        for metric_key, metric_data in list(ctx.items())[:3]:
            user_parts.append(f"- {metric_key}:")
            if isinstance(metric_data, dict):
                for k, v in list(metric_data.items())[:5]:
                    user_parts.append(f"  - {k}: {v}")
        user_parts.append("")
    
    user_parts.append("위 아티팩트를 기반으로 사용자의 질문에 답해 주세요.")
    
    return system, "\n".join(user_parts)


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


def build_refine_prompt(
    task_list: list,
    user_query: str,
    requested_count: int = 3,
) -> tuple[str, str]:
    """Builds prompt for refine mode (Task 재정렬/발췌).
    
    Returns: (system_prompt, user_prompt)
    """
    system = COMMON_RULES + "\n\n" + SYSTEM_REFINE
    
    # Format task list for prompt
    task_lines = []
    for i, task in enumerate(task_list[:10], 1):
        title = task.get("title", "제목 없음")
        priority = task.get("priority", 99)
        difficulty = task.get("difficulty", "unknown")
        rationale = task.get("rationale", "")
        
        task_lines.append(f"{i}. **{title}** (난이도: {difficulty}, 우선순위: {priority})")
        if rationale:
            task_lines.append(f"   - {rationale[:100]}")
    
    task_text = "\n".join(task_lines) if task_lines else "(Task 없음)"
    
    user_parts = [
        "## 사용자 요청",
        user_query,
        "",
        "## 현재 Task 목록",
        task_text,
        "",
        f"## 요청 사항",
        f"위 목록에서 {requested_count}개를 선별해 주세요.",
        "priority가 낮을수록 높은 우선순위입니다.",
    ]
    
    return system.format(count=requested_count, task_list="{결과}", task_title="{Task 제목}"), "\n".join(user_parts)


def extract_requested_count(query: str) -> int:
    """Extracts requested task count from user query."""
    import re
    
    # 숫자 + 개 패턴
    match = re.search(r"(\d+)\s*개", query)
    if match:
        return min(int(match.group(1)), 10)
    
    # top N 패턴
    match = re.search(r"top\s*(\d+)", query, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 10)
    
    # 상위 N개 패턴
    match = re.search(r"상위\s*(\d+)", query)
    if match:
        return min(int(match.group(1)), 10)
    
    return 3  # default


# LLM Parameters (Step 9: Fast vs Expert 모드별 파라미터)
# Fast mode: temp=0.7, Expert mode: temp=0.2-0.3, 공통 top_p=0.9

LLM_PARAMS = {
    # Expert Mode (건조·정확, 데이터 기반)
    "health_report": {
        "temperature": 0.25,
        "max_tokens": 1024,
        "top_p": 0.9,
    },
    "score_explain": {
        "temperature": 0.2,
        "max_tokens": 512,
        "top_p": 0.9,
    },
    "followup_evidence": {
        "temperature": 0.2,
        "max_tokens": 400,
        "top_p": 0.9,
    },
    "refine": {
        "temperature": 0.2,
        "max_tokens": 600,
        "top_p": 0.9,
    },
    "compare": {
        "temperature": 0.25,
        "max_tokens": 1200,
        "top_p": 0.9,
    },
    
    # Fast Mode (공손·간결)
    "overview": {
        "temperature": 0.5,
        "max_tokens": 400,
        "top_p": 0.9,
    },
    "chat": {
        "temperature": 0.7,
        "max_tokens": 300,
        "top_p": 0.9,
    },
    "greeting": {
        "temperature": 0.7,
        "max_tokens": 200,
        "top_p": 0.9,
    },
}


def get_llm_params(mode: str) -> dict:
    """Returns LLM parameters for the specified mode."""
    return LLM_PARAMS.get(mode, LLM_PARAMS["chat"]).copy()
