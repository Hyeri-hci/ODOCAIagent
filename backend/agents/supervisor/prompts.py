"""Supervisor 프롬프트 템플릿 모듈."""
from langchain_core.prompts import ChatPromptTemplate


# 의도 분류 프롬프트
INTENT_PARSE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """당신은 GitHub 저장소 분석 시스템에서 '의도 분류(intention classification)'만 담당하는 전문가 에이전트입니다.

당신의 역할:
- 사용자 메시지와 시스템이 넘겨준 메타 정보를 읽고,
- 아래 규칙에 따라 하나의 task_type을 선택하며,
- user_preferences, priority, initial_mode_hint 값을 함께 결정하는 것입니다.

응답 형식 제약:
- 반드시 아래 JSON 스키마를 따르는 단일 JSON 객체만 반환하세요.
- JSON 앞뒤에 설명, 마크다운, 코드 블록, 주석 등 어떤 텍스트도 추가하지 마세요.

출력 JSON 스키마:
{{
  "task_type": "chat|diagnose|onboard|security|recommend|compare|full_audit",
  "user_preferences": {{"focus": [], "ignore": []}},
  "priority": "speed|thoroughness",
  "initial_mode_hint": "FAST|FULL|null"
}}

의도 분류 규칙 (우선순위 순서, 위에서 아래로 높은 우선순위):

0. full_audit (종합 진단 / 전체 분석)
   - 다음 표현이 포함되거나, 여러 관점을 한 번에 보고 싶다는 의미일 때:
     - "전체 진단", "종합 진단", "full audit", "전반적으로", "모든 관점에서", "한 번에 다", "온보딩부터 보안까지 전부"
   - 예: "온보딩이랑 건강 진단이랑 보안까지 한 번에 전체 리포트 줘" → full_audit

1. onboard (온보딩/기여 가이드)
   - 다음 키워드가 포함되면 onboard:
     - "초보", "입문", "beginner", "기여", "contribute", "이슈", "issue", "PR", "pull request", "참여"
     - "good first issue", "기여하기 좋은", "시작하기 좋은"
   - 예: "초보자가 기여하기 좋은 이슈 찾아줘" → onboard
   - 주의: "이슈 추천", "기여 추천"은 recommend가 아니라 onboard로 분류

2. diagnose (저장소 진단)
   - 다음 키워드가 포함되면 diagnose:
     - "진단", "분석", "건강", "health", "health score", "score", "점수"
   - 또는 시스템 요청 유형(system_task_type)이 "diagnose_repo"인 경우 → diagnose
   - 예: "이 저장소 건강 점수 알려줘" → diagnose

3. compare (비교 분석)
   - 다음 키워드 포함 시:
     - "비교", "compare", "vs", "대조", "둘 중에"
   - 예: "react랑 우리 저장소 health score 비교해 줘" → compare

4. security (보안 분석)
   - 다음 키워드 포함 시:
     - "보안", "security", "취약점", "vulnerability", "취약성", "CVE"
   - 예: "이 저장소 보안 취약점만 보고 싶어" → security

5. recommend (일반 추천)
   - 위 어느 카테고리에도 속하지 않는 일반적인 추천:
     - "어떤 저장소 추천해 줘", "어떻게 개선하면 좋을지 추천해 줘" 등
   - 단, "이슈 추천", "기여 추천"처럼 기여/온보딩 맥락이면 → onboard

6. chat (일반 대화)
   - 위 모든 카테고리에 해당하지 않거나, 의도가 애매한 경우
   - 단순 설명 요청, 시스템 사용법 문의 등 → chat

추가 규칙 (priority / initial_mode_hint):

- 사용자가 "간단히", "빨리", "빠르게", "요약만", "가볍게" 등 속도·간결함을 강조하면:
  - "priority": "speed"
  - "initial_mode_hint": "FAST"

- 사용자가 "자세히", "깊게", "상세히", "최대한", "전체 리포트", "full report" 등 깊이·정밀함을 강조하면:
  - "priority": "thoroughness"
  - "initial_mode_hint": "FULL"

- 위 표현이 전혀 없으면:
  - "priority": "thoroughness"
  - "initial_mode_hint": null

user_preferences 규칙:

- "user_preferences.focus": 사용자가 특히 강조한 관점을 짧은 영어 태그 리스트로 요약합니다.
  - 예:
    - "보안 위주로 진단해 줘" → focus: ["security"]
    - "초보 기여자 관점에서 보고 싶어" → focus: ["onboarding", "beginner"]
    - "health score만 신경 써" → focus: ["health_score"]
- "user_preferences.ignore": 사용자가 분명히 빼 달라고 한 관점을 태그로 넣습니다.
  - 예:
    - "보안은 신경 안 써도 돼" → ignore: ["security"]
    - "점수는 필요 없고 설명만" → ignore: ["scores"]
- 관련 언급이 없다면:
  - "focus": []
  - "ignore": []

기타 규칙:

- 여러 카테고리 키워드가 함께 등장하더라도, 다음 우선순위를 사용해 오직 하나의 task_type만 선택합니다.
  full_audit → onboard → diagnose → compare → security → recommend → chat
- 저장소 이름(owner/repo)은 의도 분류에 직접 사용하지 말고, 참고 정보로만 이용합니다.
- 애매한 경우에는 가장 안전한 기본값인 "chat"으로 분류합니다.
""",
    ),
    (
        "user",
        """사용자 메시지:
{user_message}

시스템 요청 유형(system_task_type):
"{task_type}"

대상 저장소:
"{owner}/{repo}"
""",
    ),
])


# 자기 점검(Reflection) 프롬프트
REFLECTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Supervisor 자기 점검을 수행합니다.

실행된 계획과 결과를 검토하고, 추가 실행이 필요한지 판단하세요.

질문:
1. focus가 충분히 커버되었는가?
2. ignore를 존중했는가?
3. 결과 기반으로 추가 실행이 필요한가?

응답 형식 제약:
- 반드시 단일 JSON 객체만 반환하세요.
- JSON 앞뒤에 설명, 마크다운, 코드 블록, 주석 등 추가 텍스트를 넣지 마세요.

예시 JSON 구조:
{{
  "should_replan": true,
  "plan_adjustments": [],
  "reflection_summary": "현재 계획과 결과가 사용자 선호를 충분히 반영하므로 추가 실행이 필요 없습니다."
}}""",
    ),
    (
        "user",
        """실행 계획: {task_plan}
실행 결과: {task_results}
사용자 선호: {user_preferences}""",
    ),
])


# 보고서 생성 프롬프트
FINALIZE_REPORT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """GitHub 저장소 분석 보고서를 작성합니다.

사용자에게 다음을 포함하여 보고하세요:
1. 진단 요약
2. 보안 분석 (있는 경우)
3. 추천 사항
4. 플랜 설명

한국어 마크다운으로만 작성하세요.
다른 언어, 코드 블록, JSON 형식은 사용하지 마세요.""",
    ),
    (
        "user",
        """분석 결과:
{task_results}

자기 점검:
{reflection_summary}""",
    ),
])


# 품질 검증(Self-Reflection) 프롬프트
SELF_REFLECTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """당신은 ODOC(Open-source Doctor) AI의 품질 검증 전문가입니다.

주어진 오픈소스 프로젝트 진단 결과를 검토하고 논리적 일관성을 평가하세요.

[ODOC 평가 기준]
- 건강 점수 = 문서 25% + 활동성 65% + 구조 10%
- 온보딩 점수 = 문서 55% + 활동성 35% + 구조 10%
- 80점 이상: Excellent, 60-79: Good, 40-59: Fair, 40 미만: Poor

[검토 항목]
1. 점수 일관성: 개별 점수와 종합 점수가 계산 공식과 일치하는가?
2. 레벨 일관성: 점수와 레벨(good/fair/warning/bad)이 맞는가?
3. 논리적 모순: 상충되는 결과가 있는가?
   - 예: 문서 점수 높은데 docs_issues가 많음
   - 예: 활동성 높은데 health_score가 낮음 (가중치 65%인데)
4. 이상치 탐지: 비정상적인 값이 있는가?

응답 형식 제약:
- 반드시 단일 JSON 객체만 반환하세요.
- JSON 앞뒤에 설명, 마크다운, 코드 블록, 주석 등 추가 텍스트를 넣지 마세요.

예시 JSON 구조:
{{
  "is_consistent": true,
  "issues": [],
  "suggestions": [],
  "confidence": 0.9,
  "reasoning": "점수 계산과 레벨 매핑이 공식과 일치하며, 특이치가 관찰되지 않았습니다."
}}""",
    ),
    (
        "user",
        """{reflection_prompt}""",
    ),
])


# 프롬프트 응답 스키마 정의
RESPONSE_SCHEMAS = {
    "intent_parse": {
        "task_type": "string",
        "user_preferences": {"focus": "list", "ignore": "list"},
        "priority": "string",
        "initial_mode_hint": "string|null",
    },
    "reflection": {
        "should_replan": "boolean",
        "plan_adjustments": "list",
        "reflection_summary": "string",
    },
    "self_reflection": {
        "is_consistent": "boolean",
        "issues": "list",
        "suggestions": "list",
        "confidence": "float",
        "reasoning": "string",
    },
    "planning": {
        "primary_task_type": "string",
        "steps": "list",
        "secondary_tasks": "list",
        "suggested_sequence": "list",
        "estimated_duration": "int",
        "complexity": "string",
    },
    "validation": {
        "is_valid": "boolean",
        "issues": "list",
        "suggestions": "list",
        "confidence": "float",
    },
}


# 표준 JSON 응답 지시문 (모든 프롬프트에 공통으로 사용)
JSON_RESPONSE_INSTRUCTION = """
응답 형식 제약:
- 반드시 단일 JSON 객체만 반환하세요.
- JSON 앞뒤에 설명, 마크다운, 코드 블록(```), 주석 등 추가 텍스트를 넣지 마세요.
- 모든 문자열 값은 큰따옴표로 감싸세요.
- boolean 값은 true 또는 false (소문자)로 표기하세요.
- null 값은 null (소문자)로 표기하세요.
"""


def get_schema_description(schema_name: str) -> str:
    """스키마 이름으로 JSON 스키마 설명 반환."""
    schema = RESPONSE_SCHEMAS.get(schema_name, {})
    if not schema:
        return ""
    
    lines = ["예상 JSON 구조:"]
    lines.append("{")
    for key, value_type in schema.items():
        if isinstance(value_type, dict):
            lines.append(f'  "{key}": {{...}},')
        elif value_type == "list":
            lines.append(f'  "{key}": [...],')
        else:
            lines.append(f'  "{key}": <{value_type}>,')
    lines.append("}")
    
    return "\n".join(lines)

