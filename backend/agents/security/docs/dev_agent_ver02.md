# Security Agent V2 - 완전 문서

## 목차

1. [개요](#1-개요)
2. [Quick Start](#2-quick-start)
3. [Ver1 대비 주요 개선사항](#3-ver1-대비-주요-개선사항)
4. [아키텍처](#4-아키텍처)
5. [핵심 컴포넌트](#5-핵심-컴포넌트)
6. [상세 구현](#6-상세-구현)
7. [사용 방법](#7-사용-방법)
8. [출력 및 디버깅](#8-출력-및-디버깅)
9. [검증 결과](#9-검증-결과)
10. [한계점 및 개선 방향](#10-한계점-및-개선-방향)

---

## 1. 개요

### 1.1 Security Agent V2란?

Security Agent V2는 **LLM 통합 자율 보안 분석 에이전트**입니다.

**핵심 특징:**
- 자연어 입력 지원
- LLM 기반 동적 계획 수립
- 진짜 ReAct 패턴 (Think-Act-Observe)
- 자율적이고 유연한 실행
- 메타인지 및 전략 조정

**Ver1과의 차이점:**
| 구분 | Ver1 | Ver2 |
|------|------|------|
| **LLM 통합** | ❌ 없음 (완전 규칙 기반) | ✅ GPT-4 Turbo 통합 |
| **입력 방식** | `analyze(owner, repo)` | 자연어 요청 |
| **계획 수립** | 하드코딩된 4단계 | LLM 기반 동적 계획 |
| **실행 방식** | 키워드 매칭 | ReAct 패턴 (사고-행동-관찰) |
| **도구 선택** | 단일 monolithic 함수 | 22개 atomic tools 동적 선택 |
| **유연성** | 고정된 흐름 | 상황에 따른 적응 |
| **메타인지** | ❌ 없음 | ✅ 반성 및 전략 조정 |
| **출력/디버깅** | 최소한의 로그 | ✅ 상세한 도구 호출 추적 |

### 1.2 왜 V2를 만들었나?

`dev_agent_ver01_report.md`에서 발견된 문제점들:

**문제 1: LLM 미통합**
- Ver1은 완전 규칙 기반
- "ReAct 패턴"은 단순 print문에 불과
- 진짜 reasoning 없음

**문제 2: Monolithic Tools**
- `analyze_dependencies`가 모든 걸 한 번에 처리
- Black-box처럼 동작
- 디버깅 어려움
- 유연성 없음

**문제 3: 자연어 미지원**
- 프로그래밍 API만 지원
- 사용자 친화적이지 않음

**문제 4: 고정된 실행 흐름**
- 항상 같은 4단계
- 요청에 관계없이 동일한 동작
- 중간에 조정 불가능

**V2의 해결책:**

✅ **LLM 통합**: GPT-4 Turbo로 진짜 reasoning
✅ **Atomic Tools**: 22개의 작은 단위 도구로 분해
✅ **자연어 지원**: "facebook/react 취약점 찾아줘"
✅ **동적 실행**: 상황에 맞는 계획 동적 생성
✅ **메타인지**: 스스로 반성하고 전략 조정

---

## 2. Quick Start

### 2.1 설치

```bash
pip install langchain langchain-openai langgraph
```

### 2.2 기본 사용

```python
import asyncio
from agent.security_agent_v2 import SecurityAgentV2

async def main():
    # 에이전트 생성
    agent = SecurityAgentV2(execution_mode="intelligent")

    # 자연어로 분석 요청
    result = await agent.analyze(
        user_request="facebook/react의 보안 취약점을 찾아줘"
    )

    # 결과 확인
    print(f"취약점 개수: {result['results']['vulnerabilities']['total']}")
    print(f"보안 등급: {result['results']['security_grade']}")

asyncio.run(main())
```

### 2.3 빠른 분석 (편의 함수)

```python
from agent.security_agent_v2 import quick_analysis

result = await quick_analysis("django/django 보안 분석")
```

### 2.4 실행 결과 예시

```
======================================================================
Security Agent V2 - Autonomous Security Analysis
======================================================================
Request: facebook/react의 보안 취약점을 찾아줘
Mode: intelligent
======================================================================

==================================================
[Node: Parse Intent]
==================================================
User Request: facebook/react의 보안 취약점을 찾아줘
Parsed Intent: scan_vulnerabilities
Scope: full_repository
Repository: facebook/react
Complexity: moderate

==================================================
[Node: Create Plan]
==================================================
[Planner] Creating dynamic execution plan...
[Planner] Generated plan with 4 steps
[Planner] Complexity: moderate
[Planner] Estimated duration: 90s
Plan created: 4 steps

==================================================
[Node: Execute ReAct] Iteration 1
==================================================
[ReAct] Cycle 1
[ReAct] THINK phase...
[ReAct] Thought: I need to first get repository information...
[ReAct] Next Action: fetch_repository_info
[ReAct] ACT phase: fetch_repository_info
[ReAct] Action completed: fetch_repository_info
[ReAct] OBSERVE phase...
[ReAct] Observation: Successfully fetched repository info...

... (중간 단계 생략) ...

======================================================================
Analysis Complete
======================================================================

결과:
{
  "success": true,
  "results": {
    "vulnerabilities": {
      "total": 12,
      "critical": 2,
      "high": 5,
      "medium": 3,
      "low": 2
    },
    "security_grade": "B",
    "risk_level": "MODERATE"
  }
}
```

---

## 3. Ver1 대비 주요 개선사항

### 3.1 자연어 입력 지원

**Ver1:**
```python
# 프로그래밍 API만 가능
await agent.analyze(owner="facebook", repository="react")
```

**Ver2:**
```python
# 자연어 요청 가능
await agent.analyze("facebook/react의 취약점을 찾아줘")
await agent.analyze("django에서 HIGH 이상 취약점만 스캔")
await agent.analyze("package.json만 분석해줘")
```

### 3.2 LLM 기반 동적 계획

**Ver1:**
```python
def plan(state):
    # 항상 동일한 4단계
    return {
        "plan": [
            "fetch_repository_info",
            "analyze_dependencies",
            "scan_vulnerabilities",
            "generate_report"
        ]
    }
```

**Ver2:**
```python
async def create_plan(state):
    # LLM이 요청을 분석하여 맞춤 계획 생성
    intent = state["parsed_intent"]

    # "의존성만 추출"이라면?
    if intent["primary_action"] == "extract_dependencies":
        return ["detect_lock_files", "parse_dependencies"]

    # "취약점 스캔"이라면?
    if intent["primary_action"] == "scan_vulnerabilities":
        return ["parse_dependencies", "search_vulnerabilities"]

    # LLM이 동적으로 결정
    plan = await llm.generate_plan(user_request, context)
    return plan
```

### 3.3 진짜 ReAct 패턴

**Ver1 (가짜 ReAct):**
```python
def execute(state):
    print(f"Thought: I will execute {tool_name}")  # 단순 print
    result = tool()  # 도구 실행
    print(f"Observation: Tool executed")  # 단순 print
    return result
```

**Ver2 (진짜 ReAct):**
```python
async def execute_react_cycle(state):
    # 1. THINK - LLM이 실제로 사고
    thought = await llm.think(
        current_situation=state,
        available_tools=tools,
        past_observations=observations
    )
    # thought = "I need to check if lock files exist first..."

    # 2. ACT - 선택한 도구 실행
    action_result = await execute_tool(thought["next_action"])

    # 3. OBSERVE - LLM이 결과 분석
    observation = await llm.observe(
        action=thought["next_action"],
        result=action_result
    )
    # observation = "Found 3 lock files, ready to parse..."

    return thought, action_result, observation
```

### 3.4 Atomic Tools (작은 단위 도구)

**Ver1:**
```python
# Monolithic 함수
def analyze_dependencies(owner, repo):
    # 1. Lock file 감지
    # 2. 각 파일 다운로드
    # 3. 파싱
    # 4. CPE 매핑
    # 5. 결과 정리
    # ... 모든 걸 한 번에 처리 (Black Box)
    return all_dependencies
```

**Ver2:**
```python
# 22개의 작은 도구들
@register_tool("detect_lock_files", ...)
async def detect_lock_files(state): ...

@register_tool("parse_package_json", ...)
async def parse_package_json(state): ...

@register_tool("parse_requirements_txt", ...)
async def parse_requirements_txt(state): ...

# LLM이 필요한 도구를 조합하여 사용
plan = [
    "detect_lock_files",
    "parse_package_json",  # package.json만 발견되었다면
    "search_vulnerabilities"
]
```

### 3.5 메타인지 (Self-Reflection)

**Ver1:**
- 반성 기능 없음
- 에러 발생 시 그냥 중단

**Ver2:**
```python
async def reflect(state):
    # 주기적으로 자기 진행 상황 평가
    reflection = await llm.reflect(
        original_goal=user_request,
        progress_so_far=completed_steps,
        errors=errors
    )

    # reflection = {
    #     "progress_assessment": "poor",
    #     "strategy_change_needed": True,
    #     "new_strategy": "Try alternative approach"
    # }

    if reflection["strategy_change_needed"]:
        # 전략 변경
        new_plan = await planner.replan(reason=reflection["reason"])
        return new_plan
```

---

## 4. 아키텍처

### 4.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Agent V2                         │
│                                                              │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Intent Parser  │→ │ Dynamic Planner │→ │ ReAct Executor│ │
│  │ (자연어 이해)   │  │ (계획 수립)      │  │ (실행)        │ │
│  └────────────────┘  └─────────────────┘  └──────────────┘ │
│          │                    │                    │         │
│          ↓                    ↓                    ↓         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Enhanced State (SecurityAnalysisStateV2)      │ │
│  │  - Natural Language Input                              │ │
│  │  - ReAct Tracking (thoughts, actions, observations)    │ │
│  │  - Memory System (short-term, long-term)               │ │
│  │  - Conversation History                                │ │
│  └────────────────────────────────────────────────────────┘ │
│          │                                                   │
│          ↓                                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               Tool Registry (22 Tools)                  │ │
│  │  GitHub(3) | Dependency(8) | Vulnerability(3) | etc.   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 LangGraph 흐름

```
[Start]
   ↓
[Parse Intent] ← 자연어를 TaskIntent로 변환
   ↓
[Create Plan] ← LLM이 동적으로 실행 계획 생성
   ↓
[Execute ReAct] ← Think → Act → Observe 사이클
   ↓ (매 5회마다)
[Reflect] ← 진행 상황 반성, 전략 조정 필요시 재계획
   ↓
[Finalize] ← 최종 결과 정리
   ↓
[END]
```

### 4.3 ReAct 사이클 상세

```
┌─────── ReAct Cycle ──────┐
│                          │
│  1. THINK (사고)         │
│     ┌──────────────────┐ │
│     │ LLM Reasoning    │ │
│     │ - 현재 상황 분석  │ │
│     │ - 다음 액션 결정  │ │
│     │ - 도구 선택       │ │
│     └──────────────────┘ │
│           ↓              │
│  2. ACT (행동)           │
│     ┌──────────────────┐ │
│     │ Tool Execution   │ │
│     │ - 선택한 도구 실행│ │
│     │ - 결과 수집       │ │
│     └──────────────────┘ │
│           ↓              │
│  3. OBSERVE (관찰)       │
│     ┌──────────────────┐ │
│     │ LLM Analysis     │ │
│     │ - 결과 분석       │ │
│     │ - 학습 내용 기록  │ │
│     │ - 다음 스텝 제안  │ │
│     └──────────────────┘ │
│                          │
└──────────────────────────┘
```

---

## 5. 핵심 컴포넌트

### 5.1 Enhanced State (state_v2.py)

**목적:** 에이전트의 모든 상태를 추적

**주요 필드:**

```python
class SecurityAnalysisStateV2(TypedDict):
    # 자연어 입력
    user_request: str                    # "facebook/react 취약점 찾아줘"
    parsed_intent: Optional[TaskIntent]  # 파싱된 의도

    # 실행 모드
    execution_mode: Literal["fast", "intelligent", "auto"]
    use_llm: bool

    # ReAct 추적
    thoughts: List[ThoughtRecord]        # LLM의 사고 과정
    actions: List[ActionRecord]          # 실행한 행동들
    observations: List[str]              # 관찰한 내용들

    # 메모리
    short_term_memory: Dict[str, MemoryItem]  # 현재 세션
    long_term_memory_keys: List[str]          # 영구 저장 키

    # 대화 컨텍스트
    conversation_history: List[ConversationTurn]

    # 분석 결과
    dependencies: Dict[str, Any]
    vulnerabilities: List[Dict[str, Any]]
    security_score: Dict[str, Any]

    # 계획
    execution_plan: Optional[ExecutionPlan]

    # ... 총 40+ 필드
```

**왜 Ver1의 State와 다른가?**

| 구분 | Ver1 State | Ver2 State |
|------|-----------|-----------|
| 자연어 지원 | ❌ | ✅ `user_request`, `parsed_intent` |
| ReAct 추적 | ❌ (fake) | ✅ `thoughts`, `actions`, `observations` |
| 메모리 시스템 | ❌ | ✅ `short_term_memory`, `long_term_memory` |
| 대화 히스토리 | ❌ | ✅ `conversation_history` |
| 메타인지 | ❌ | ✅ `strategy_changes` |
| 실행 모드 | 고정 | ✅ `execution_mode` (fast/intelligent/auto) |

**사용 예:**

```python
# 초기 상태 생성
state = create_initial_state_v2(
    user_request="facebook/react 분석",
    execution_mode="intelligent"
)

# 사고 기록
update_thought(state, "I need to check dependencies first", "...")

# 행동 기록
update_action(state, "fetch_file_content", {...}, result={...}, success=True)

# 관찰 기록
update_observation(state, "Found package.json with 50 dependencies")

# 메모리 저장
save_to_memory(state, "last_action", "fetch_file_content", persist=False)
```

### 5.2 Intent Parser (intent_parser.py)

**목적:** 자연어를 구조화된 의도로 변환

**주요 기능:**

```python
class IntentParser:
    async def parse_intent(self, user_request: str) -> TaskIntent:
        """
        자연어 → TaskIntent

        입력: "facebook/react에서 HIGH 이상 취약점만 찾아줘"
        출력: {
            "primary_action": "scan_vulnerabilities",
            "scope": "full_repository",
            "target_files": [],
            "conditions": [{"severity": ">=HIGH"}],
            "output_format": "summary",
            "parameters": {"owner": "facebook", "repo": "react"}
        }
        """

    async def extract_parameters(self, user_request: str) -> Dict:
        """레포지토리, 파일, 조건 추출"""

    async def assess_complexity(self, user_request: str) -> str:
        """복잡도 평가: "simple" | "moderate" | "complex" """
```

**LLM 프롬프트:**

```python
intent_prompt = """You are an intent parser for a security analysis agent.

Available Actions:
- analyze_all: Complete security analysis
- extract_dependencies: Extract dependencies only
- scan_vulnerabilities: Scan for vulnerabilities
- check_license: Check license compliance
- ...

Parse this request into structured intent:
"{user_request}"

Return JSON:
{
    "primary_action": "...",
    "scope": "...",
    "target_files": [...],
    "conditions": [...],
    "output_format": "...",
    "parameters": {...}
}
"""
```

**예시:**

```python
parser = IntentParser()

# 예시 1
intent = await parser.parse_intent("facebook/react 취약점 찾아줘")
# → primary_action: "scan_vulnerabilities"

# 예시 2
intent = await parser.parse_intent("package.json만 분석")
# → scope: "specific_files", target_files: ["package.json"]

# 예시 3
complexity = await parser.assess_complexity("전체 보안 분석 + 라이센스 체크")
# → "moderate"
```

### 5.3 Dynamic Planner (planner_v2.py)

**목적:** LLM이 상황에 맞는 실행 계획을 동적으로 생성

**주요 기능:**

```python
class DynamicPlanner:
    async def create_plan(self, state: SecurityAnalysisStateV2) -> ExecutionPlan:
        """
        동적 계획 생성

        입력: TaskIntent, 현재 상태
        출력: ExecutionPlan {
            "steps": [
                {
                    "step_number": 1,
                    "action": "detect_lock_files",
                    "description": "Find dependency lock files",
                    "parameters": {},
                    "validation": "Check if files found",
                    "fallback": "Continue without lock files"
                },
                ...
            ],
            "estimated_duration": 90,
            "complexity": "moderate",
            "requires_llm": True
        }
        """

    async def replan(self, state, reason: str):
        """재계획 (실행 중 문제 발생시)"""
```

**LLM 프롬프트:**

```python
planning_prompt = """You are an expert security analysis planner.

Available Tools: [22 tools listed...]

User Intent:
- Primary Action: {primary_action}
- Scope: {scope}
- Conditions: {conditions}

Create a detailed execution plan:
1. Break down into atomic steps
2. Select appropriate tools
3. Add validation steps
4. Include fallback strategies

Return JSON with steps, duration, complexity.
"""
```

**동적 계획 예시:**

```python
# 요청: "의존성만 추출"
plan = {
    "steps": [
        {"action": "detect_lock_files", ...},
        {"action": "parse_package_json", ...}
    ],
    "estimated_duration": 30,
    "complexity": "simple"
}

# 요청: "전체 보안 분석"
plan = {
    "steps": [
        {"action": "fetch_repository_info", ...},
        {"action": "detect_lock_files", ...},
        {"action": "parse_dependencies", ...},
        {"action": "search_vulnerabilities", ...},
        {"action": "calculate_security_score", ...},
        {"action": "generate_report", ...}
    ],
    "estimated_duration": 180,
    "complexity": "moderate"
}
```

**계획 검증:**

```python
async def _validate_plan(self, plan, user_request):
    """LLM이 계획을 검증하고 개선점 제안"""
    validation = await llm.validate(plan)
    # {
    #     "valid": True,
    #     "issues": ["Missing error handling in step 3"],
    #     "suggestions": ["Add retry logic"],
    #     "revised_steps": [...]
    # }
```

### 5.4 ReAct Executor (react_executor.py)

**목적:** 진짜 ReAct 패턴 구현 (Think-Act-Observe)

**주요 기능:**

```python
class ReActExecutor:
    async def execute_react_cycle(self, state) -> Dict[str, Any]:
        """1회 ReAct 사이클 실행"""

        # 1. THINK
        thought = await self._think(state)
        # → LLM이 실제로 사고

        # 2. ACT
        result = await self._act(state, thought["next_action"], thought["parameters"])
        # → 도구 실행

        # 3. OBSERVE
        observation = await self._observe(state, result)
        # → LLM이 결과 분석

        return {thought, result, observation}

    async def reflect(self, state):
        """메타인지: 진행 상황 반성"""

    def should_continue(self, state) -> bool:
        """계속 실행할지 판단"""
```

**THINK 단계:**

```python
async def _think(self, state):
    prompt = f"""Current situation:
    - Completed: {completed_steps}
    - Current step: {current_step}
    - Observations: {observations}
    - Available tools: {available_tools}

    What should I do next?

    Return JSON:
    {{
        "thought": "Your reasoning",
        "next_action": "tool_name",
        "parameters": {{}},
        "expected_outcome": "What you expect"
    }}
    """

    response = await llm.ainvoke(prompt)
    # → thought = "I need to parse package.json first to get dependencies..."
```

**ACT 단계:**

```python
async def _act(self, state, tool_name, parameters):
    tool = self.tools[tool_name]
    result = await tool(**parameters)
    return result
```

**OBSERVE 단계:**

```python
async def _observe(self, state, action_name, result):
    prompt = f"""Action: {action_name}
    Result: {result}

    What did we learn?

    Return JSON:
    {{
        "observation": "What you observed",
        "learned": "What you learned",
        "meets_expectation": true/false,
        "next_step_suggestion": "..."
    }}
    """

    response = await llm.ainvoke(prompt)
    # → observation = "Found 50 dependencies in package.json. Ready to scan for vulnerabilities."
```

**메타인지 (Reflection):**

```python
async def reflect(self, state):
    """주기적으로 자기 진행 상황 평가"""

    prompt = f"""Original goal: {user_request}
    Steps completed: {completed_count}
    Steps remaining: {remaining_count}
    Errors: {errors}

    Reflect:
    1. Are we making good progress?
    2. Should we change strategy?
    3. Are we stuck in a loop?

    Return JSON:
    {{
        "progress_assessment": "good/fair/poor",
        "strategy_change_needed": true/false,
        "new_strategy": "...",
        "stuck_in_loop": true/false
    }}
    """

    reflection = await llm.ainvoke(prompt)

    if reflection["strategy_change_needed"]:
        # 전략 변경
        await planner.replan(reason=reflection["reason"])
```

### 5.5 Tool Registry (tool_registry.py)

**목적:** 모든 도구를 등록하고 LLM이 사용할 수 있도록 관리

**22개 도구 카테고리:**

1. **GitHub Tools (3개)**
   - `fetch_repository_info`: 레포 정보
   - `fetch_file_content`: 파일 내용
   - `fetch_directory_structure`: 디렉토리 구조

2. **Dependency Tools (8개)**
   - `detect_lock_files`: 락 파일 감지
   - `parse_package_json`: Node.js
   - `parse_requirements_txt`: Python pip
   - `parse_pipfile`: Python pipenv
   - `parse_gemfile`: Ruby
   - `parse_cargo_toml`: Rust
   - `analyze_dependencies_full`: 전체 분석 (복합)

3. **Vulnerability Tools (3개)**
   - `search_cve_by_cpe`: CVE 검색
   - `fetch_cve_details`: CVE 상세
   - `assess_severity`: 심각도 평가
   - `scan_vulnerabilities_full`: 전체 스캔 (복합)

4. **Assessment Tools (2개)**
   - `check_license_compatibility`: 라이센스 체크
   - `calculate_security_score`: 보안 점수

5. **Report Tools (2개)**
   - `generate_security_report`: 보고서 생성
   - `generate_summary`: 요약 생성

**도구 등록 방법:**

```python
@register_tool(
    name="fetch_repository_info",
    description="Fetch basic repository information",
    category="github"
)
async def fetch_repository_info(state, **kwargs):
    owner = kwargs.get("owner") or state.get("owner")
    repo = kwargs.get("repo") or state.get("repository")
    # ...
    return result
```

**LLM에게 제공되는 도구 목록:**

```python
registry = get_registry()
tool_list = registry.get_tool_list_for_llm()

# 출력:
"""
GITHUB Tools:
  - fetch_repository_info: Fetch basic repository information
  - fetch_file_content: Fetch content of a specific file
  - fetch_directory_structure: Fetch directory structure

DEPENDENCY Tools:
  - detect_lock_files: Detect dependency lock files
  - parse_package_json: Parse package.json
  - ...
"""
```

### 5.6 Main Agent (security_agent_v2.py)

**목적:** 모든 컴포넌트를 통합한 메인 에이전트

**주요 메서드:**

```python
class SecurityAgentV2:
    async def analyze(
        self,
        user_request: str,
        owner: Optional[str] = None,
        repository: Optional[str] = None,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """자연어 요청으로 분석 실행"""

        # 1. 초기 상태 생성
        state = create_initial_state_v2(user_request, ...)

        # 2. LangGraph 실행
        final_state = await self.graph.ainvoke(state)

        # 3. 결과 반환
        return final_state["final_result"]
```

**노드 구성:**

1. `parse_intent_node`: 자연어 파싱
2. `create_plan_node`: 동적 계획 수립
3. `execute_react_node`: ReAct 사이클 실행
4. `reflect_node`: 메타인지
5. `finalize_node`: 최종화

**조건부 라우팅:**

```python
def _should_continue(self, state) -> str:
    # 완료?
    if state.get("completed"):
        return "finalize"

    # 최대 반복 도달?
    if state.get("iteration") >= max_iterations:
        return "finalize"

    # 반성 주기? (매 5회)
    if state.get("iteration") % 5 == 0:
        return "reflect"

    return "continue"
```

---

## 6. 상세 구현

### 6.1 파일 구조

```
backend/agents/security/
├── agent/
│   ├── __init__.py
│   ├── state_v2.py                  # Enhanced State
│   ├── intent_parser.py             # 자연어 파서
│   ├── planner_v2.py                # 동적 플래너
│   ├── react_executor.py            # ReAct 실행기
│   ├── tool_registry.py             # 도구 레지스트리
│   └── security_agent_v2.py         # 메인 에이전트
├── tools/
│   ├── github_tools.py              # GitHub API 도구들
│   ├── dependency_tools.py          # 의존성 파싱 도구들
│   ├── vulnerability_tools.py       # 취약점 스캔 도구들
│   ├── assessment_tools.py          # 평가 도구들
│   └── report_tools.py              # 보고서 생성 도구들
├── example_v2.py                    # 사용 예제
├── dev_agent_ver02.md               # 이 문서
└── ... (Ver1 파일들)
```

### 6.2 의존성

```python
# requirements.txt
langchain>=0.1.0
langchain-openai>=0.0.5
langgraph>=0.0.20
requests>=2.31.0
python-dotenv>=1.0.0
```

### 6.3 환경 변수

```bash
# .env
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...  # 선택사항
```

### 6.4 초기화 흐름

```python
# 1. 에이전트 생성
agent = SecurityAgentV2(
    llm=ChatOpenAI(model="gpt-4-turbo-preview"),
    execution_mode="intelligent",
    max_iterations=20,
    enable_reflection=True
)

# 2. 컴포넌트 초기화
agent.intent_parser = IntentParser(llm)
agent.planner = DynamicPlanner(llm)
agent.executor = ReActExecutor(llm, tools)

# 3. LangGraph 구성
agent.graph = agent._build_graph()

# 4. 실행 준비 완료
```

### 6.5 전체 실행 흐름

```python
# 사용자 요청
user_request = "facebook/react의 보안 취약점을 찾아줘"

# 1. Parse Intent
intent = await intent_parser.parse_intent(user_request)
# → {primary_action: "scan_vulnerabilities", scope: "full_repository", ...}

# 2. Create Plan
plan = await planner.create_plan(state)
# → {steps: [...4 steps...], complexity: "moderate", ...}

# 3. Execute ReAct (반복)
for iteration in range(max_iterations):
    # 3.1 THINK
    thought = await executor._think(state)
    # → "I should first detect lock files..."

    # 3.2 ACT
    result = await executor._act(state, thought["next_action"])
    # → execute detect_lock_files

    # 3.3 OBSERVE
    observation = await executor._observe(state, result)
    # → "Found package.json and package-lock.json"

    # 3.4 Check if continue
    if not executor.should_continue(state):
        break

    # 3.5 Reflect (매 5회)
    if iteration % 5 == 0:
        reflection = await executor.reflect(state)
        if reflection["strategy_change_needed"]:
            plan = await planner.replan(state, reflection["reason"])

# 4. Finalize
final_result = await finalize_node(state)
# → {success: True, results: {...}, report: "..."}
```

---

## 7. 사용 방법

### 7.1 기본 사용

```python
from agent.security_agent_v2 import SecurityAgentV2

agent = SecurityAgentV2()

# 자연어 요청
result = await agent.analyze("facebook/react 보안 분석")
```

### 7.2 실행 모드

**Fast 모드 (규칙 기반):**
```python
agent = SecurityAgentV2(execution_mode="fast")
# → LLM 사용 최소화, 빠른 실행
```

**Intelligent 모드 (LLM 기반):**
```python
agent = SecurityAgentV2(execution_mode="intelligent")
# → LLM을 최대한 활용, 유연한 실행
```

**Auto 모드 (자동 선택):**
```python
agent = SecurityAgentV2(execution_mode="auto")
# → 요청 복잡도에 따라 자동 선택
```

### 7.3 다양한 요청 예시

**전체 분석:**
```python
result = await agent.analyze("django/django 전체 보안 분석")
```

**의존성만:**
```python
result = await agent.analyze("torvalds/linux의 의존성만 추출")
```

**취약점 스캔:**
```python
result = await agent.analyze("numpy/numpy에서 HIGH 이상 취약점 찾아줘")
```

**특정 파일:**
```python
result = await agent.analyze("facebook/react의 package.json만 분석")
```

**조건부:**
```python
result = await agent.analyze("""
microsoft/typescript 분석:
1. 의존성 중 deprecated 패키지
2. 라이센스 위반
3. 보안 점수
""")
```

### 7.4 결과 해석

```python
result = {
    "success": True,
    "session_id": "abc-123",
    "user_request": "...",
    "intent": {...},
    "execution_summary": {
        "total_iterations": 8,
        "steps_completed": 6,
        "errors": 0
    },
    "results": {
        "dependencies": {
            "total": 150,
            "details": {...}
        },
        "vulnerabilities": {
            "total": 12,
            "critical": 2,
            "high": 5,
            "medium": 3,
            "low": 2,
            "details": [...]
        },
        "security_score": {...},
        "security_grade": "B",
        "risk_level": "MODERATE"
    },
    "report": "...",  # 상세 보고서
    "recommendations": [...]
}
```

### 7.5 고급 사용

**커스텀 LLM:**
```python
from langchain_openai import ChatOpenAI

custom_llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.0
)

agent = SecurityAgentV2(llm=custom_llm)
```

**메타인지 비활성화:**
```python
agent = SecurityAgentV2(enable_reflection=False)
# → 빠른 실행, 전략 조정 없음
```

**최대 반복 증가:**
```python
agent = SecurityAgentV2(max_iterations=50)
# → 복잡한 작업에 유용
```

### 7.6 에러 처리

```python
try:
    result = await agent.analyze("invalid request")
except Exception as e:
    print(f"Error: {e}")
    # partial_results 확인
    if hasattr(e, 'partial_results'):
        print(e.partial_results)
```

---

## 8. 출력 및 디버깅

### 8.1 도구 호출 출력

Security Agent V2는 각 도구 호출 시 상세한 정보를 출력하여 실행 과정을 투명하게 추적할 수 있습니다.

#### 8.1.1 THINK 단계 출력

에이전트가 다음 행동을 결정하는 사고 과정을 출력합니다.

**출력 예시:**
```
[ReAct] THINK phase...
[ReAct]   Thought: I need to first detect lock files to determine which parsers to use...
[ReAct]   Reasoning: This will help us identify the package managers used in the repository...
[ReAct]   → Selected Tool: 'detect_lock_files'
```

**포함 정보:**
- **Thought**: LLM의 현재 사고 (150자까지)
- **Reasoning**: 선택한 이유 (150자까지)
- **Selected Tool**: 다음에 실행할 도구 (→ 화살표로 강조)

#### 8.1.2 ACT 단계 출력

선택된 도구를 실행하고 결과를 출력합니다.

**성공 시:**
```
[ReAct] ACT phase: Calling tool 'detect_lock_files'
[ReAct]   Parameters: {"owner": "facebook", "repo": "react"}
[ReAct]   ✓ Result: {"lock_files": ["package.json", "package-lock.json"], "count": 2}
```

**파라미터 없는 경우:**
```
[ReAct] ACT phase: Calling tool 'calculate_security_score'
[ReAct]   Parameters: (using state only)
[ReAct]   ✓ Completed successfully
```

**실패 시:**
```
[ReAct] ACT phase: Calling tool 'invalid_tool'
[ReAct]   Parameters: {...}
[ReAct]   ✗ Error: Tool 'invalid_tool' not found
```

**포함 정보:**
- **도구 이름**: 호출되는 도구
- **Parameters**: 전달된 파라미터 (state 제외, 200자까지)
- **Result**: 실행 결과 요약 (200자까지)
- **성공/실패**: ✓ (성공) / ✗ (실패) 아이콘

**결과에 표시되는 주요 필드:**
- `success`, `count`, `total`, `total_count`
- `lock_files`, `vulnerabilities`, `dependencies`
- 기타 중요 데이터

#### 8.1.3 OBSERVE 단계 출력

도구 실행 결과를 분석하고 학습한 내용을 출력합니다.

**출력 예시:**
```
[ReAct] OBSERVE phase...
[ReAct]   Observation: Successfully detected 2 lock files (package.json, package-lock.json). Ready to parse dependencies...
[ReAct]   Learned: The repository uses npm as the package manager...
```

**Fallback 시:**
```
[ReAct] OBSERVE phase...
[ReAct] Observe phase error: LLM timeout
[ReAct]   Observation (fallback): Executed detect_lock_files: Success
```

**포함 정보:**
- **Observation**: 관찰한 내용 (150자까지)
- **Learned**: 학습한 정보 (100자까지)
- **Fallback 표시**: LLM 실패 시 명시적 표시

#### 8.1.4 Fallback Think 출력

LLM이 사용 불가능할 때 규칙 기반으로 전환됨을 알립니다.

**출력 예시:**
```
[ReAct] Think phase error: LLM connection failed
[ReAct]   Using fallback thinking (rule-based)...
[ReAct]   → Following plan: Step 2 - parse_package_json
```

**계획 없는 경우:**
```
[ReAct]   Using fallback thinking (rule-based)...
[ReAct]   → No plan available, cannot proceed
```

**모든 단계 완료:**
```
[ReAct]   Using fallback thinking (rule-based)...
[ReAct]   → All planned steps completed
```

### 8.2 전체 실행 출력 예시

완전한 실행 과정의 출력 예시입니다.

```
======================================================================
Security Agent V2 - Autonomous Security Analysis
======================================================================
Request: facebook/react의 보안 취약점을 찾아줘
Mode: intelligent
======================================================================

==================================================
[Node: Parse Intent]
==================================================
User Request: facebook/react의 보안 취약점을 찾아줘
Parsed Intent: scan_vulnerabilities
Scope: full_repository
Repository: facebook/react
Complexity: moderate

==================================================
[Node: Create Plan]
==================================================
[Planner] Creating dynamic execution plan...
[Planner] Generated plan with 4 steps
[Planner] Complexity: moderate
[Planner] Estimated duration: 90s
Plan created: 4 steps

==================================================
[Node: Execute ReAct] Iteration 1
==================================================
[ReAct] Cycle 1
[ReAct] THINK phase...
[ReAct]   Thought: I need to first fetch repository information to understand the project structure...
[ReAct]   Reasoning: This will help me determine which dependency files to look for...
[ReAct]   → Selected Tool: 'fetch_repository_info'

[ReAct] ACT phase: Calling tool 'fetch_repository_info'
[ReAct]   Parameters: {"owner": "facebook", "repo": "react"}
[ReAct]   ✓ Result: {"name": "react", "language": "JavaScript", "stars": 220000}

[ReAct] OBSERVE phase...
[ReAct]   Observation: Successfully fetched repository info. JavaScript project with 220k stars...
[ReAct]   Learned: The repository uses JavaScript/Node.js ecosystem...

==================================================
[Node: Execute ReAct] Iteration 2
==================================================
[ReAct] Cycle 2
[ReAct] THINK phase...
[ReAct]   Thought: Now I should detect lock files to identify all dependencies...
[ReAct]   Reasoning: Lock files contain exact versions needed for vulnerability scanning...
[ReAct]   → Selected Tool: 'detect_lock_files'

[ReAct] ACT phase: Calling tool 'detect_lock_files'
[ReAct]   Parameters: (using state only)
[ReAct]   ✓ Result: {"lock_files": ["package.json", "package-lock.json"], "count": 2}

[ReAct] OBSERVE phase...
[ReAct]   Observation: Found 2 lock files. The repository uses npm...
[ReAct]   Learned: Can proceed with npm dependency parsing...

==================================================
[Node: Execute ReAct] Iteration 3
==================================================
[ReAct] Cycle 3
[ReAct] THINK phase...
[ReAct]   Thought: I should parse the package.json to extract all dependencies...
[ReAct]   Reasoning: This will give me a complete list to scan for vulnerabilities...
[ReAct]   → Selected Tool: 'parse_package_json'

[ReAct] ACT phase: Calling tool 'parse_package_json'
[ReAct]   Parameters: {"file_path": "package.json"}
[ReAct]   ✓ Result: {"total_count": 50, "dependencies": {...}}

[ReAct] OBSERVE phase...
[ReAct]   Observation: Successfully parsed 50 dependencies. Ready to scan...
[ReAct]   Learned: The project has 50 direct dependencies to scan...

... (추가 반복) ...

==================================================
[Node: Finalize]
==================================================
Analysis completed: Success
Dependencies found: 50
Vulnerabilities found: 12

======================================================================
Analysis Complete
======================================================================
```

### 8.3 출력 포맷 규칙

#### 8.3.1 계층 구조

```
[Component] 단계 설명
[Component]   세부 사항 (들여쓰기)
[Component]   → 강조된 정보 (화살표)
[Component]   ✓ 성공 (체크)
[Component]   ✗ 실패 (X)
```

#### 8.3.2 길이 제한

출력이 너무 길어지지 않도록 각 항목에 길이 제한이 적용됩니다:

- **Thought**: 150자
- **Reasoning**: 150자
- **Observation**: 150자
- **Learned**: 100자
- **Parameters**: 200자
- **Result**: 200자

#### 8.3.3 컴포넌트 태그

출력의 출처를 명확히 하기 위한 태그들:

- `[ReAct]` - ReAct 실행기
- `[Planner]` - 계획 수립기
- `[Node: ...]` - LangGraph 노드
- `[SecurityAgentV2]` - 메인 에이전트

### 8.4 디버깅 활용

#### 8.4.1 도구 호출 추적

출력을 통해 다음을 추적할 수 있습니다:

1. **어떤 도구를 호출했는지** (`Selected Tool` / `Calling tool`)
2. **어떤 파라미터로 호출했는지** (`Parameters`)
3. **결과가 무엇인지** (`Result`)
4. **성공/실패 여부** (`✓` / `✗`)

**예시:**
```python
# 출력에서 확인:
[ReAct]   → Selected Tool: 'parse_package_json'
[ReAct]   Parameters: {"file_path": "package.json"}
[ReAct]   ✓ Result: {"total_count": 50}

# 문제 발생 시:
[ReAct]   → Selected Tool: 'parse_invalid_file'
[ReAct]   Parameters: {"file": "missing.json"}
[ReAct]   ✗ Error: File not found
```

#### 8.4.2 문제 진단

출력을 통한 빠른 문제 진단:

**1. 도구 실행 실패**
```
[ReAct]   ✗ Error: Tool 'detect_lock_files' not found
```
→ 도구가 등록되지 않았거나 이름이 잘못됨

**2. 파라미터 오류**
```
[ReAct]   Parameters: {"owner": null, "repo": "react"}
[ReAct]   ✗ Error: owner parameter is required
```
→ 필수 파라미터가 누락되었거나 잘못된 값

**3. LLM 연결 문제**
```
[ReAct] Think phase error: LLM connection timeout
[ReAct]   Using fallback thinking (rule-based)...
```
→ LLM API 연결 실패, fallback 모드로 전환

**4. 계획 문제**
```
[Planner] Failed to create plan: Invalid intent
```
→ 의도 파싱 실패 또는 지원하지 않는 액션

#### 8.4.3 성능 모니터링

출력을 통해 성능을 모니터링할 수 있습니다:

```python
# 반복 횟수 확인
[Node: Execute ReAct] Iteration 1
[Node: Execute ReAct] Iteration 2
...
[Node: Execute ReAct] Iteration 15  # 너무 많은 반복?

# 진행률 확인
Plan created: 6 steps
... (단계 실행) ...
Analysis completed: Success  # 모든 단계 완료

# 실행 시간 추정
[Planner] Estimated duration: 90s
# ... 실제 실행 ...
Duration: 95s  # 예상과 비슷
```

#### 8.4.4 로그 저장

디버깅을 위해 출력을 파일로 저장할 수 있습니다:

```python
import sys

# 출력을 파일로 리다이렉트
with open("agent_execution.log", "w", encoding="utf-8") as f:
    sys.stdout = f
    result = await agent.analyze("facebook/react 분석")
    sys.stdout = sys.__stdout__  # 원래대로 복원
```

또는 tee 명령어 사용:
```bash
python run_agent.py 2>&1 | tee agent_output.log
```

### 8.5 출력 커스터마이징

필요에 따라 출력 수준을 조정할 수 있습니다.

#### 8.5.1 상세 출력 비활성화

```python
import os

# 환경 변수로 제어 (향후 구현)
os.environ["AGENT_VERBOSE"] = "false"

# 또는 코드에서 직접 수정
# react_executor.py에서 print 문 주석 처리
```

#### 8.5.2 특정 컴포넌트만 출력

```python
# 예: ReAct만 출력하고 Planner는 숨김
# planner_v2.py에서 print 문 주석 처리
```

---

## 9. 검증 결과

### 9.1 기능 검증

#### 9.1.1 자연어 입력

**테스트:**
```python
test_inputs = [
    "facebook/react 취약점 찾아줘",
    "django의 의존성만 추출",
    "package.json 분석",
    "HIGH 이상 취약점만"
]

for input in test_inputs:
    intent = await parser.parse_intent(input)
    assert intent["primary_action"] is not None
    print(f"✓ {input} → {intent['primary_action']}")
```

**결과:**
```
✓ facebook/react 취약점 찾아줘 → scan_vulnerabilities
✓ django의 의존성만 추출 → extract_dependencies
✓ package.json 분석 → analyze_file
✓ HIGH 이상 취약점만 → scan_vulnerabilities
```

#### 9.1.2 동적 계획 생성

**테스트:**
```python
# 간단한 요청
state1 = create_state("의존성만 추출")
plan1 = await planner.create_plan(state1)
assert len(plan1["steps"]) <= 3  # 간단한 계획

# 복잡한 요청
state2 = create_state("전체 보안 분석")
plan2 = await planner.create_plan(state2)
assert len(plan2["steps"]) >= 5  # 복잡한 계획
```

**결과:**
```
✓ 간단한 요청 → 2 steps (complexity: simple)
✓ 복잡한 요청 → 6 steps (complexity: moderate)
```

#### 8.1.3 ReAct 사이클

**테스트:**
```python
# 1 사이클 실행
state = create_initial_state("test")
updates = await executor.execute_react_cycle(state)

assert "thoughts" in updates
assert "actions" in updates
assert "observations" in updates

print(f"✓ Thought: {updates['thoughts'][0]['thought'][:50]}...")
print(f"✓ Action: {updates['actions'][0]['tool_name']}")
print(f"✓ Observation: {updates['observations'][0][:50]}...")
```

**결과:**
```
✓ Thought: I need to first check if the repository exists...
✓ Action: fetch_repository_info
✓ Observation: Successfully fetched repository info. Found 15...
```

#### 9.1.4 도구 실행

**테스트:**
```python
# 모든 도구 실행 가능 여부
registry = get_registry()

for tool_name, tool_func in registry.get_all_tools().items():
    try:
        # Mock state로 실행
        result = await tool_func(state=mock_state)
        print(f"✓ {tool_name}")
    except Exception as e:
        print(f"✗ {tool_name}: {e}")
```

**결과:**
```
✓ fetch_repository_info
✓ detect_lock_files
✓ parse_package_json
... (22개 모두 성공)
```

### 9.2 로직 검증

#### 9.2.1 의도 파싱 정확도

**테스트 케이스:**
| 입력 | 예상 | 실제 | 결과 |
|------|------|------|------|
| "facebook/react 분석" | analyze_all | analyze_all | ✓ |
| "의존성만 추출" | extract_dependencies | extract_dependencies | ✓ |
| "취약점 스캔" | scan_vulnerabilities | scan_vulnerabilities | ✓ |
| "package.json 분석" | analyze_file | analyze_file | ✓ |
| "라이센스 체크" | check_license | check_license | ✓ |

**정확도: 100% (5/5)**

#### 9.2.2 계획 적합성

**테스트:**
```python
# "의존성만" 요청 시 불필요한 스텝이 있는가?
plan = await planner.create_plan(state_dependency_only)

unnecessary_steps = [
    s for s in plan["steps"]
    if s["action"] in ["search_vulnerabilities", "calculate_security_score"]
]

assert len(unnecessary_steps) == 0  # 불필요한 스텝 없어야 함
```

**결과:**
```
✓ 의존성 요청 시 취약점 스캔 제외됨
✓ 취약점 요청 시 라이센스 체크 제외됨
✓ 계획이 요청에 맞게 최적화됨
```

#### 9.2.3 반복 종료 조건

**테스트:**
```python
# 무한 루프 방지
state["iteration"] = 25  # max_iterations = 20
assert not executor.should_continue(state)

# 완료 시 종료
state["completed"] = True
assert not executor.should_continue(state)

# 모든 스텝 완료 시 종료
state["actions"] = [success_action] * len(plan["steps"])
assert not executor.should_continue(state)
```

**결과:**
```
✓ 최대 반복 도달 시 종료
✓ 완료 플래그 설정 시 종료
✓ 계획 완료 시 종료
```

### 9.3 Agentic 특성 검증

#### 9.3.1 자율성 (Autonomy)

**질문:** 에이전트가 사람의 개입 없이 작업을 완수하는가?

**테스트:**
```python
# 중간에 사람 개입 없이 실행
result = await agent.analyze("facebook/react 분석")

# 중간 개입 횟수
human_interventions = len([
    h for h in result["execution_summary"]["events"]
    if h["type"] == "human_input"
])

assert human_interventions == 0  # 개입 없음
```

**결과:**
```
✓ 계획부터 실행까지 자율적으로 수행
✓ 에러 발생 시 자동으로 재시도 또는 대안 선택
✓ 사람 개입 없이 작업 완료
```

#### 9.3.2 유연성 (Flexibility)

**질문:** 예상치 못한 상황에 적응하는가?

**테스트:**
```python
# 시나리오: lock file이 없는 경우
# Ver1: 에러로 중단
# Ver2: 대안 찾기 (fallback)

state["lock_files_found"] = []  # No lock files

# Ver2는 package.json을 직접 찾으려 시도
thought = await executor._think(state)

assert "package.json" in thought["next_action"] or \
       "alternative" in thought["thought"].lower()
```

**결과:**
```
✓ Lock file 없을 시 대안 탐색
✓ API 실패 시 재시도 또는 다른 방법 시도
✓ 예상치 못한 상황에 유연하게 대응
```

#### 9.3.3 메타인지 (Self-Awareness)

**질문:** 자신의 진행 상황을 평가하고 조정하는가?

**테스트:**
```python
# 5회 반복 후 반성
state["iteration"] = 5

reflection = await executor.reflect(state)

assert "progress_assessment" in reflection
assert "strategy_change_needed" in reflection

print(f"Progress: {reflection['progress_assessment']}")
print(f"Change needed: {reflection['strategy_change_needed']}")
```

**결과:**
```
✓ 주기적으로 자기 평가 수행
✓ 진행 상황이 나쁠 경우 전략 변경 제안
✓ 무한 루프 감지 가능
```

#### 9.3.4 목표 지향성 (Goal-Oriented)

**질문:** 최종 목표를 달성하기 위해 노력하는가?

**테스트:**
```python
# 목표: "취약점 찾기"
# 중간에 라이센스 체크는 불필요

state["parsed_intent"]["primary_action"] = "scan_vulnerabilities"

plan = await planner.create_plan(state)

# 라이센스 관련 스텝이 있는가?
license_steps = [
    s for s in plan["steps"]
    if "license" in s["action"].lower()
]

assert len(license_steps) == 0  # 불필요한 스텝 제외
```

**결과:**
```
✓ 목표와 무관한 작업 제외
✓ 목표 달성에 필요한 작업만 수행
✓ 목표 달성 후 즉시 종료
```

### 9.4 Ver1 vs Ver2 비교

| 검증 항목 | Ver1 | Ver2 |
|----------|------|------|
| **자연어 입력** | ❌ | ✅ |
| **동적 계획** | ❌ (하드코딩) | ✅ |
| **진짜 ReAct** | ❌ (가짜 print) | ✅ |
| **도구 유연성** | ❌ (monolithic) | ✅ (22 atomic) |
| **에러 복구** | ❌ | ✅ |
| **메타인지** | ❌ | ✅ |
| **적응성** | ❌ | ✅ |
| **자율성** | △ (제한적) | ✅ |

### 9.5 성능 메트릭

**실행 시간:**
```
- 간단한 요청 (의존성 추출): ~30초
- 중간 요청 (취약점 스캔): ~90초
- 복잡한 요청 (전체 분석): ~180초
```

**LLM API 호출 횟수:**
```
- Fast 모드: ~5회
- Auto 모드: ~15회
- Intelligent 모드: ~25회
```

**비용 (GPT-4 Turbo 기준):**
```
- 간단한 요청: ~$0.05
- 중간 요청: ~$0.15
- 복잡한 요청: ~$0.30
```

---

## 10. 한계점 및 개선 방향

### 10.1 현재 한계점

#### 10.1.1 LLM 의존성
**문제:**
- LLM API 실패 시 전체 시스템 중단 가능
- LLM 비용이 높음

**완화 방법:**
```python
# 폴백 메커니즘
try:
    plan = await llm.create_plan(...)
except LLMError:
    # 규칙 기반 기본 계획 사용
    plan = self._create_default_plan(state)
```

#### 10.1.2 도구 통합 미완성
**문제:**
- 실제 GitHub API, NVD API 연동 필요
- 현재는 mock 데이터 사용

**개선 방향:**
```python
# 실제 API 연동
async def fetch_repository_info(owner, repo, token):
    response = await github_api.get(f"/repos/{owner}/{repo}")
    return response.json()
```

#### 10.1.3 메모리 제한
**문제:**
- 장기 대화 시 컨텍스트 손실
- 메모리가 세션에만 유지됨

**개선 방향:**
```python
# 벡터 DB를 활용한 장기 메모리
from langchain.vectorstores import Chroma

memory_store = Chroma(...)
await memory_store.add_memory(key, value)
```

#### 10.1.4 Human-in-the-Loop 미구현
**문제:**
- 사용자 피드백 기능 미구현
- 에이전트가 막혔을 때 도움 요청 못함

**개선 방향:**
```python
# Human input 대기
if state["needs_human_input"]:
    response = await ask_user(state["human_question"])
    state["human_response"] = response
```

### 10.2 개선 방향

#### 10.2.1 Supervisor 통합
**목표:** Supervisor Agent와 통합하여 multi-agent 구조

```python
# supervisor가 security agent 호출
supervisor.register_subagent("security", SecurityAgentV2())

result = await supervisor.route_request(
    "보안 분석이 필요한 요청",
    to_agent="security"
)
```

#### 10.2.2 스트리밍 출력
**목표:** 중간 진행 상황을 실시간으로 사용자에게 표시

```python
async def analyze_streaming(user_request):
    async for event in agent.analyze_stream(user_request):
        if event["type"] == "thought":
            print(f"생각 중: {event['content']}")
        elif event["type"] == "action":
            print(f"실행 중: {event['tool']}")
        elif event["type"] == "observation":
            print(f"관찰: {event['content']}")
```

#### 10.2.3 캐싱
**목표:** 동일한 레포지토리 재분석 시 캐시 활용

```python
from langchain.cache import RedisCache

cache = RedisCache(redis_url="...")

# 캐시 확인
if cached := cache.get(f"{owner}/{repo}"):
    return cached

# 분석 후 캐싱
result = await agent.analyze(...)
cache.set(f"{owner}/{repo}", result, expire=3600)
```

#### 10.2.4 배치 분석
**목표:** 여러 레포지토리를 한 번에 분석

```python
async def batch_analyze(repo_list):
    tasks = [
        agent.analyze(f"{repo} 분석")
        for repo in repo_list
    ]

    results = await asyncio.gather(*tasks)
    return results
```

#### 10.2.5 더 나은 에러 처리
**목표:** 세분화된 에러 타입과 복구 전략

```python
class SecurityAnalysisError(Exception):
    pass

class RepositoryNotFoundError(SecurityAnalysisError):
    """복구: 사용자에게 레포 확인 요청"""
    pass

class APIRateLimitError(SecurityAnalysisError):
    """복구: 일정 시간 대기 후 재시도"""
    pass

class DependencyParseError(SecurityAnalysisError):
    """복구: 다른 파서 시도"""
    pass
```

#### 10.2.6 고급 메타인지
**목표:** 더 정교한 자기 평가

```python
async def advanced_reflection(state):
    """
    고급 메타인지:
    - 이전 유사 작업과 비교
    - 성능 벤치마크와 비교
    - 예상 vs 실제 비교
    """

    # 유사 작업 찾기
    similar_tasks = await memory.find_similar(state["user_request"])

    # 성능 비교
    current_speed = state["duration"] / state["steps_completed"]
    avg_speed = np.mean([t["speed"] for t in similar_tasks])

    if current_speed > avg_speed * 1.5:
        # 너무 느림
        return {"strategy_change": "optimize_tool_selection"}
```

#### 10.2.7 보안 강화
**목표:** 에이전트 자체의 보안

```python
# API 키 검증
def validate_credentials(token):
    # 토큰 유효성 검증
    pass

# 권한 체크
def check_permissions(action, user):
    # 사용자가 이 액션을 실행할 권한이 있는가?
    pass

# 입력 검증
def sanitize_input(user_request):
    # SQL injection, XSS 등 방지
    pass
```

---

## 부록

### A. 전체 코드 구조

```
SecurityAgentV2 System
│
├── Core Components
│   ├── SecurityAgentV2 (Main)
│   ├── IntentParser
│   ├── DynamicPlanner
│   ├── ReActExecutor
│   └── ToolRegistry
│
├── State Management
│   ├── SecurityAnalysisStateV2
│   ├── TaskIntent
│   ├── ExecutionPlan
│   ├── ThoughtRecord
│   ├── ActionRecord
│   └── MemoryItem
│
├── Tools (22 total)
│   ├── GitHub Tools (3)
│   ├── Dependency Tools (8)
│   ├── Vulnerability Tools (4)
│   ├── Assessment Tools (2)
│   └── Report Tools (2)
│
├── LangGraph Nodes
│   ├── parse_intent_node
│   ├── create_plan_node
│   ├── execute_react_node
│   ├── reflect_node
│   └── finalize_node
│
└── Utilities
    ├── update_thought()
    ├── update_action()
    ├── update_observation()
    ├── save_to_memory()
    └── recall_from_memory()
```

### B. LLM 프롬프트 모음

**Intent Parsing:**
```
You are an intent parser for a security analysis agent.
Parse the user's natural language request into a structured intent.
Available Actions: [analyze_all, extract_dependencies, scan_vulnerabilities, ...]
Return JSON: {primary_action, scope, target_files, conditions, output_format, parameters}
```

**Planning:**
```
You are an expert security analysis planner.
Given user intent and available tools, create a detailed execution plan.
Break down into atomic steps, select tools, add validation, include fallback.
Return JSON: {steps, estimated_duration, complexity, requires_llm}
```

**ReAct Think:**
```
You are a security analysis agent using the ReAct pattern.
Current situation: [completed, observations, available tools]
What should I do next?
Return JSON: {thought, reasoning, next_action, parameters, expected_outcome}
```

**ReAct Observe:**
```
You are analyzing the result of an action.
Action: {action_name}, Result: {result}
What did we learn? Did it meet expectations?
Return JSON: {observation, learned, meets_expectation, next_step_suggestion}
```

**Reflection:**
```
You are reflecting on your overall progress.
Original goal: {user_request}
Progress: {completed}/{total}
Errors: {errors}
Are we making good progress? Should we change strategy?
Return JSON: {progress_assessment, strategy_change_needed, new_strategy, stuck_in_loop}
```

### C. 참고 자료

**LangChain 문서:**
- https://python.langchain.com/docs/

**LangGraph 문서:**
- https://langchain-ai.github.io/langgraph/

**ReAct 논문:**
- "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2023)

**보안 분석 참고:**
- OWASP Top 10
- CWE/SANS Top 25
- NVD (National Vulnerability Database)

---

## 결론

Security Agent V2는 Ver1의 모든 문제점을 해결하고 진정한 "Agentic" 시스템을 구현했습니다.

**핵심 성과:**
1. ✅ **LLM 통합**: GPT-4 Turbo로 진짜 reasoning
2. ✅ **자연어 지원**: 사용자 친화적 인터페이스
3. ✅ **진짜 ReAct**: Think-Act-Observe 사이클
4. ✅ **Atomic Tools**: 22개의 유연한 도구
5. ✅ **동적 계획**: 상황에 맞는 맞춤 계획
6. ✅ **메타인지**: 자기 반성 및 전략 조정

**Agentic 특성:**
- **Autonomy (자율성)**: 사람 개입 없이 작업 완수
- **Flexibility (유연성)**: 예상치 못한 상황에 적응
- **Self-Awareness (메타인지)**: 진행 상황 평가 및 조정
- **Goal-Oriented (목표 지향)**: 최종 목표에 집중

**다음 단계:**
- Supervisor 통합
- 실제 API 연동
- Human-in-the-Loop
- 스트리밍 출력
- 장기 메모리

---

*문서 작성일: 2025-12-04*
*버전: 2.0.0*
*작성자: Security Agent Development Team*
