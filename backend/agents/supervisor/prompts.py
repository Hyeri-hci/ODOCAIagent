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


# =============================================================================
# 3-2. Mode-specific Prompts
# =============================================================================

# -----------------------------------------------------------------------------
# Health Report: intent=analyze, sub_intent=health/onboarding
# -----------------------------------------------------------------------------
SYSTEM_HEALTH_REPORT = """You are an expert at summarizing open-source project analysis results.
Summarize the diagnosis results in easy-to-understand Korean.

## Score Interpretation Guide (out of 100)
- 90-100: Excellent
- 80-89: Good  
- 70-79: Fair
- 60-69: Average
- Below 60: Needs Improvement

## Output Format (follow this order)

### One-line Summary
Overall, this is a [status] project. [Key characteristic in one sentence]

### Score Table
| Metric | Score | Status |
|--------|-------|--------|
| Health Score | {health_score} | {interpretation} |
| Documentation Quality | {documentation_quality} | {interpretation} |
| Activity | {activity_maintainability} | {interpretation} |
| Onboarding Ease | {onboarding_score} | {interpretation} |

### Strengths
- (2-3 data-based strengths)

### Areas for Improvement
- (2-3 data-based improvements)

### Recommended Next Actions
- "I want to contribute" - Recommend 5 beginner tasks
- "Explain the onboarding score" - Detailed score interpretation
- "Compare with similar repos" - Compare with other projects

### Reference: Starting Tasks (3)
{formatted_tasks}
(Add one line per task explaining why it's suitable for beginners)
"""

# -----------------------------------------------------------------------------
# Score Explain: intent=followup, sub_intent=explain
# -----------------------------------------------------------------------------
SYSTEM_SCORE_EXPLAIN = """You explain specific metrics/scores from open-source project analysis.

## Your Role
- Explain WHY a specific score was calculated
- Use only the provided metric data
- Keep explanations concise and actionable

## Output Format

### {metric_name}: {score} points

**Why this score?**
- (Reason 1 based on data)
- (Reason 2 based on data)
- (Reason 3 if applicable)

**What you can do**
- (1-2 actionable suggestions)

---
Need more details? Ask "Tell me more about {metric_name}" or "What other metrics are there?"
"""

# -----------------------------------------------------------------------------
# General QA / Greeting: intent=general_qa or smalltalk
# -----------------------------------------------------------------------------
SYSTEM_CHAT = """You are ODOC, a friendly open-source onboarding assistant.

## Your Role
- Answer questions briefly and kindly
- Help users understand open-source contribution
- If they want analysis, guide them to provide a repository

## Guidelines
- Keep responses short (2-3 paragraphs max)
- Don't force diagnosis data into the conversation
- If repo analysis would help, mention: "If you'd like, I can analyze a specific repository for you"

## For Greetings
Respond warmly and suggest what you can help with:
- Repository overview: "What is facebook/react?"
- Health analysis: "Analyze facebook/react"
- Contribution guide: "I want to contribute to this project"
"""


# =============================================================================
# Template Messages
# =============================================================================

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


# =============================================================================
# Helper Functions
# =============================================================================

def build_health_report_prompt(diagnosis_result: Dict[str, Any]) -> tuple[str, str]:
    """Builds prompt for health report mode. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_HEALTH_REPORT
    
    # Format diagnosis data for user prompt
    scores = diagnosis_result.get("scores", {})
    repo_info = diagnosis_result.get("details", {}).get("repo_info", {})
    tasks = diagnosis_result.get("onboarding_tasks", {})
    
    user = f"""## Analysis Target
Repository: {repo_info.get('full_name', 'Unknown')}
Description: {repo_info.get('description', 'N/A')}

## Scores
- Health Score: {scores.get('health_score', 'N/A')}
- Documentation Quality: {scores.get('documentation_quality', 'N/A')}
- Activity/Maintainability: {scores.get('activity_maintainability', 'N/A')}
- Onboarding Score: {scores.get('onboarding_score', 'N/A')}

## Labels
- Health Level: {diagnosis_result.get('labels', {}).get('health_level', 'N/A')}
- Onboarding Level: {diagnosis_result.get('labels', {}).get('onboarding_level', 'N/A')}

## Beginner Tasks (Top 3)
{_format_tasks_brief(tasks)}

Please summarize this analysis result following the output format."""
    
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
    
    user = f"""## User Question
{user_query}

## Metric to Explain
- Name: {metric_name}
- Score: {metric_score}

## Context Data
{_format_explain_context(metric_context)}

Please explain why this score was calculated and what actions the user can take."""
    
    return system, user


def build_chat_prompt(user_query: str, repo_summary: str = "") -> tuple[str, str]:
    """Builds prompt for chat/greeting mode. Returns (system, user)."""
    system = COMMON_RULES + "\n" + SYSTEM_CHAT
    
    user = f"User: {user_query}"
    if repo_summary:
        user += f"\n\n[Previous analysis context]\n{repo_summary}"
    
    return system, user


def _format_tasks_brief(tasks: Dict[str, list]) -> str:
    """Formats top 3 beginner tasks for the prompt."""
    beginner_tasks = tasks.get("beginner", [])[:3]
    if not beginner_tasks:
        return "(No beginner tasks found)"
    
    lines = []
    for i, task in enumerate(beginner_tasks, 1):
        title = task.get("title", "Untitled")
        url = task.get("url", "")
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   Link: {url}")
    
    return "\n".join(lines)


def _format_explain_context(context: Dict[str, Any]) -> str:
    """Formats explain context for a specific metric."""
    if not context:
        return "(No detailed context available)"
    
    lines = []
    for key, value in context.items():
        if isinstance(value, dict):
            lines.append(f"- {key}:")
            for k, v in value.items():
                lines.append(f"  - {k}: {v}")
        else:
            lines.append(f"- {key}: {value}")
    
    return "\n".join(lines)


# =============================================================================
# LLM Parameters (kept for compatibility)
# =============================================================================

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
