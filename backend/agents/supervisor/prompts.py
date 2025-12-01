"""
듀얼 모드 프롬프트 템플릿.

Fast Chat: 경량/저지연, 도구 호출 금지
Expert Tool: 구조화 응답, 출처 강제
"""
from __future__ import annotations

from typing import Literal

# 라우팅 모드
RoutingMode = Literal["fast_chat", "expert_tool"]

# Fast Chat 신뢰도 임계값 (이하면 Fast Chat)
FAST_CHAT_THRESHOLD = 0.5

# LLM 파라미터
LLM_PARAMS = {
    "fast_chat": {
        "temperature": 0.7,
        "max_tokens": 300,
        "top_p": 0.9,
    },
    "expert_tool": {
        "temperature": 0.3,
        "max_tokens": 1024,
        "top_p": 0.9,
    },
}


# Fast Chat 시스템 프롬프트 (한국어)
FAST_CHAT_SYSTEM = """너는 공손하고 간결한 한국어 비서다.
- 불필요한 장황함 없이 한두 문단으로 답한다
- 지시가 모호하면 1문장으로 선택지를 제안한다
- 분석/진단 같은 무거운 작업은 사용자가 명확히 요청할 때만 권한다
- 반말, 이모지 사용 금지
- 종결어미: '~입니다', '~주세요', '~드릴까요?'"""

# 인사/잡담 템플릿
GREETING_TEMPLATE = """안녕하세요! ODOC입니다. 무엇을 도와드릴까요?

다음 중 하나를 시도해보세요:
- 레포 개요: 'facebook/react가 뭐야?'
- 진단 분석: 'react 상태 분석해줘'
- 비교: 'react랑 vue 비교해줘'"""

CHITCHAT_TEMPLATE = """네, 계속 도와드릴게요!

원하시면 다음을 시도해보세요:
- 레포 개요: 'vercel/next.js가 뭐야?'
- 진단: 'tensorflow 분석해줘'"""

# 도움말 템플릿
HELP_TEMPLATE = """제가 할 수 있는 일입니다:

**레포 개요**
'facebook/react가 뭐야?', 'next.js 알려줘'

**진단 분석**
'react 상태 분석해줘', 'tensorflow 진단해줘'

**비교 분석**
'react랑 vue 비교해줘', 'next.js vs nuxt.js'

**온보딩 추천**
'초보자인데 이 프로젝트에 기여하고 싶어'

어떤 걸 해볼까요?"""

# 개요 시스템 프롬프트
OVERVIEW_SYSTEM = """아래 사실(레포 메타+README 첫 단락)만 근거로 3~6문장 개요를 작성하라.
- 추측을 금지한다
- 존댓말 사용 (~입니다, ~합니다)
- 마지막에 "자세한 분석이 필요하시면 '진단해줘'라고 입력해주세요"를 추가한다"""

OVERVIEW_USER_TEMPLATE = """대상: {owner}/{repo}

[레포 정보]
{repo_facts}

[README 요약]
{readme_head}

위 사실만 근거로 3~6문장 개요를 작성하세요."""

# Expert Tool 시스템 프롬프트 (출처 강제)
EXPERT_SYSTEM = """반드시 다음 JSON 스키마로만 답하라:
{{
  "text": "마크다운 형식 응답",
  "sources": ["artifact_id_1", "artifact_id_2"],
  "source_kinds": ["diagnosis_raw", "python_metrics"]
}}

규칙:
- sources는 아래 artifacts의 id를 사용한다
- sources가 비면 실패로 간주한다
- 잡담 금지, 구조화된 분석만 제공
- 한국어 존댓말 사용"""

EXPERT_USER_TEMPLATE = """목표: {goal}
저장소: {owner}/{repo}
사용자 레벨: {user_level}

[수집된 Artifacts]
{artifacts}

위 데이터를 근거로 {goal}을 수행하고, JSON 형식으로 응답하세요."""


def get_fast_chat_params() -> dict:
    """Fast Chat LLM 파라미터."""
    return LLM_PARAMS["fast_chat"].copy()


def get_expert_params() -> dict:
    """Expert Tool LLM 파라미터."""
    return LLM_PARAMS["expert_tool"].copy()


def build_overview_prompt(owner: str, repo: str, facts: str, readme: str) -> tuple[str, str]:
    """개요 프롬프트 빌드. (system, user) 반환."""
    user = OVERVIEW_USER_TEMPLATE.format(
        owner=owner,
        repo=repo,
        repo_facts=facts or "(정보 없음)",
        readme_head=readme[:500] if readme else "(README 없음)",
    )
    return OVERVIEW_SYSTEM, user


def build_expert_prompt(
    goal: str,
    owner: str,
    repo: str,
    user_level: str,
    artifacts: str,
) -> tuple[str, str]:
    """Expert Tool 프롬프트 빌드. (system, user) 반환."""
    user = EXPERT_USER_TEMPLATE.format(
        goal=goal,
        owner=owner,
        repo=repo,
        user_level=user_level,
        artifacts=artifacts,
    )
    return EXPERT_SYSTEM, user
