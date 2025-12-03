# Security Agent 구축 계획서

## 📋 목차
1. [현재 상태 분석](#1-현재-상태-분석)
2. [목표 아키텍처](#2-목표-아키텍처)
3. [LangGraph 기반 에이전트 설계](#3-langgraph-기반-에이전트-설계)
4. [필요한 툴 목록](#4-필요한-툴-목록)
5. [State 정의](#5-state-정의)
6. [노드(Node) 정의](#6-노드node-정의)
7. [엣지(Edge) 및 조건부 라우팅](#7-엣지edge-및-조건부-라우팅)
8. [ReAct 패턴 구현](#8-react-패턴-구현)
9. [사람 개입(Human-in-the-Loop)](#9-사람-개입human-in-the-loop)
10. [구현 단계](#10-구현-단계)
11. [파일 구조](#11-파일-구조)
12. [예상 실행 흐름](#12-예상-실행-흐름)

---

## 1. 현재 상태 분석

### 1.1 현재 코드 구조

```
backend/agents/security/
├── service.py                          # 순차적 메인 서비스
├── github/
│   ├── client.py                       # GitHub API 클라이언트
│   └── analyzer.py                     # 레포지토리 분석기 (순차적)
├── extractors/                         # 언어별 의존성 추출기
│   ├── python.py, javascript.py, ...
├── tools/
│   ├── dependency_analyzer.py          # 의존성 분석 툴 (기초 함수들)
│   └── vulnerability_checker.py        # 취약점 체크 (미구현)
├── models/
│   └── dependency.py                   # 데이터 모델
└── config/
    └── dependency_files.py             # 설정
```

### 1.2 현재 실행 흐름 (순차적)

```python
# 현재 방식
service = SecurityAnalysisService(github_token)
results = service.analyze_repository("owner", "repo")  # 1. 의존성 분석
# ... 2. 취약점 체크 (미구현)
# ... 3. 점수 산출 (미구현)
# ... 4. 레포트 생성 (미구현)
```

**문제점:**
1. ❌ **순차적 실행**: 각 단계가 하드코딩된 순서로 실행
2. ❌ **자율성 부족**: 에이전트가 판단할 수 없음
3. ❌ **유연성 부족**: 상황에 따른 계획 조정 불가
4. ❌ **사람 개입 불가**: 도움이 필요해도 질문 불가
5. ❌ **통합된 도구**: 작은 단위로 분리되지 않음

### 1.3 기존 기능 현황

**✅ 구현 완료:**
- GitHub 레포지토리 조회
- 의존성 파일 탐지 (30+ 언어 지원)
- Lock 파일 우선 처리
- 의존성 파싱 및 추출
- 기본 보안 점수 계산 (간단한 로직)

**🔨 미구현:**
- CPE 데이터베이스 연동
- NVD API 연동
- 실제 취약점 조회
- 상세 레포트 생성
- 대응 방법 제안

---

## 2. 목표 아키텍처

### 2.1 전체 시스템 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                     Security Analysis Agent                       │
│                      (LangGraph + LangChain)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Planning   │───▶│ Validation  │───▶│  Execution  │        │
│  │    Node      │    │    Node     │    │    Nodes    │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                   │                   │               │
│         └───────────────────┴───────────────────┘               │
│                         │                                        │
│                    ┌────▼────┐                                  │
│                    │ ReAct   │  (Think → Act → Observe)        │
│                    │ Loop    │                                  │
│                    └────┬────┘                                  │
│                         │                                        │
│              ┌──────────┼──────────┐                           │
│              │          │          │                            │
│         ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐                      │
│         │ Tools  │ │ Human  │ │ Memory │                      │
│         │        │ │ Input  │ │        │                      │
│         └────┬───┘ └───┬────┘ └──┬─────┘                      │
│              │          │          │                            │
└──────────────┼──────────┼──────────┼────────────────────────────┘
               │          │          │
        ┌──────▼──────────▼──────────▼──────┐
        │  External Systems & APIs          │
        ├───────────────────────────────────┤
        │  • GitHub API                     │
        │  • CPE Database                   │
        │  • NVD API                        │
        │  • LangSmith (Observability)      │
        └───────────────────────────────────┘
```

### 2.2 핵심 설계 원칙

1. **🧠 Agentic**: 에이전트가 자율적으로 판단하고 행동
2. **🔄 Adaptive**: 상황에 따라 계획 수정 가능
3. **🔧 Modular**: 작은 단위의 툴로 분리
4. **👤 Human-in-the-Loop**: 필요 시 사람에게 질문
5. **📊 Observable**: LangSmith로 모든 단계 추적

---

## 3. LangGraph 기반 에이전트 설계

### 3.1 LangGraph 개념

LangGraph는 **상태 기반 그래프**로 에이전트를 구성합니다:
- **State**: 에이전트의 현재 상태 (데이터 저장소)
- **Node**: 각 작업 단위 (함수)
- **Edge**: 노드 간 연결 및 흐름 제어
- **Conditional Edge**: 조건에 따른 분기

### 3.2 에이전트 그래프 구조

```
                    [START]
                       │
                       ▼
              ┌────────────────┐
              │  Initialize    │  입력 검증 및 초기화
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │  Plan          │  작업 계획 수립
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │  Validate Plan │  계획 타당성 검증
              └────────┬───────┘
                       │
                ┌──────┴──────┐
                │             │
        [Valid] │             │ [Invalid]
                │             │
                ▼             ▼
        ┌───────────┐   ┌─────────────┐
        │  Execute  │   │  Replan     │──┐
        │  Tools    │   └─────────────┘  │
        └─────┬─────┘                    │
              │            ┌─────────────┘
              │            │
              ▼            ▼
        ┌────────────────────────┐
        │  Observe & Reflect     │  결과 관찰 및 판단
        └────────┬───────────────┘
                 │
          ┌──────┴──────┐
          │             │
   [Continue]        [Need Help?]
          │             │
          │             ▼
          │      ┌──────────────┐
          │      │  Ask Human   │
          │      └──────┬───────┘
          │             │
          │             ▼
          │      ┌──────────────┐
          │      │ Wait for     │
          │      │ Response     │
          │      └──────┬───────┘
          │             │
          └─────────────┘
                 │
                 ▼
          [Complete?]
                 │
         ┌───────┴────────┐
         │                │
    [Yes]│                │[No] → Back to Execute
         │                │
         ▼                └───┐
   ┌──────────┐               │
   │ Generate │◀──────────────┘
   │ Report   │
   └────┬─────┘
        │
        ▼
     [END]
```

### 3.3 ReAct 패턴 통합

각 실행 사이클에서 ReAct 패턴 적용:

```
┌─────────────────────────────────────┐
│         ReAct Cycle                 │
├─────────────────────────────────────┤
│                                     │
│  1. 💭 Thought (Think)              │
│     "어떤 작업을 해야 하는가?"         │
│     "다음 단계는 무엇인가?"            │
│                                     │
│  2. 🔧 Action (Act)                 │
│     "적절한 툴을 선택하고 실행"         │
│     - analyze_dependencies()        │
│     - query_cpe_database()          │
│     - fetch_nvd_vulnerabilities()   │
│                                     │
│  3. 👁️ Observation (Observe)        │
│     "실행 결과 확인 및 분석"           │
│     "다음에 무엇을 해야 하는가?"        │
│                                     │
│  4. 🤔 Reflection (Reflect)         │
│     "목표 달성 여부 판단"              │
│     "계획 수정 필요 여부"              │
│                                     │
└─────────────────────────────────────┘
            │
            ▼
      [Repeat or End]
```

---

## 4. 필요한 툴 목록

### 4.1 현재 존재하는 함수를 툴로 분리

#### 4.1.1 GitHub 관련 툴

**현재 위치**: `github/client.py`, `github/analyzer.py`

| 툴 이름 | 현재 함수 | 설명 | Input | Output |
|--------|----------|------|-------|--------|
| `fetch_repository_tree` | `GitHubClient.get_repository_tree()` | 레포지토리 파일 트리 조회 | owner, repo | List[파일정보] |
| `fetch_file_content` | `GitHubClient.get_file_content()` | 파일 내용 가져오기 | owner, repo, path | 파일 내용(str) |
| `find_dependency_files` | `RepositoryAnalyzer.get_dependency_files()` | 의존성 파일 찾기 | owner, repo | List[의존성파일경로] |
| `check_is_lockfile` | `RepositoryAnalyzer.is_lockfile()` | Lock 파일 여부 확인 | path | bool |

#### 4.1.2 의존성 분석 툴

**현재 위치**: `tools/dependency_analyzer.py`, `extractors/`

| 툴 이름 | 현재 함수 | 설명 | Input | Output |
|--------|----------|------|-------|--------|
| `analyze_dependencies` | `analyze_repository_dependencies()` | 전체 의존성 분석 | owner, repo | 분석 결과 Dict |
| `extract_dependencies_from_file` | `DependencyExtractor.extract()` | 단일 파일 의존성 추출 | content, filename | List[Dependency] |
| `filter_by_source` | `get_dependencies_by_source()` | 소스별 필터링 | result, source | List[Dependency] |
| `filter_by_type` | `get_dependencies_by_type()` | 타입별 필터링 | result, type | List[Dependency] |
| `find_outdated_deps` | `get_outdated_dependencies()` | 구버전 의존성 찾기 | result, pattern | List[Dependency] |
| `count_by_language` | `count_dependencies_by_language()` | 언어별 집계 | result | Dict[언어, 개수] |
| `summarize_analysis` | `summarize_dependency_analysis()` | 분석 요약 생성 | result | str |

#### 4.1.3 취약점 조회 툴 (신규 구현 필요)

**현재 위치**: `tools/vulnerability_checker.py` (미구현)

| 툴 이름 | 설명 | Input | Output |
|--------|------|-------|--------|
| `query_cpe_database` | CPE 데이터베이스에서 패키지 조회 | package_name, version | List[CPE ID] |
| `fetch_nvd_vulnerabilities` | NVD API로 CVE 조회 | cpe_id | List[CVE 정보] |
| `check_vulnerability_severity` | 취약점 심각도 평가 | cve_list | Dict[심각도별 개수] |
| `get_vulnerability_details` | 특정 CVE 상세 조회 | cve_id | CVE 상세 정보 |
| `search_exploit_db` | Exploit 존재 여부 확인 | cve_id | bool, exploit_info |

#### 4.1.4 보안 평가 툴

**현재 위치**: `tools/vulnerability_checker.py` (부분 구현)

| 툴 이름 | 현재 함수 | 설명 | Input | Output |
|--------|----------|------|-------|--------|
| `calculate_security_score` | `get_security_score()` | 보안 점수 계산 | dependencies, vulnerabilities | Dict[score, grade, factors] |
| `suggest_improvements` | `suggest_security_improvements()` | 개선 사항 제안 | analysis_result, vuln_result | List[제안사항] |
| `check_license_compliance` | `check_license_compliance()` | 라이센스 체크 | result, allowed_licenses | Dict[준수여부] |

#### 4.1.5 레포트 생성 툴 (신규 구현 필요)

| 툴 이름 | 설명 | Input | Output |
|--------|------|-------|--------|
| `generate_executive_summary` | 요약 레포트 생성 | 전체 분석 결과 | str (요약문) |
| `generate_vulnerability_report` | 취약점 상세 레포트 | vulnerabilities | str (Markdown) |
| `generate_remediation_guide` | 대응 가이드 생성 | vulnerabilities | List[대응방법] |
| `generate_risk_matrix` | 위험도 매트릭스 생성 | score, vulnerabilities | Dict[매트릭스] |
| `export_report` | 레포트 파일 저장 | report_data, format | file_path |

#### 4.1.6 유틸리티 툴

| 툴 이름 | 설명 | Input | Output |
|--------|------|-------|--------|
| `validate_repository_access` | 레포지토리 접근 가능 여부 확인 | owner, repo | bool, error_msg |
| `estimate_analysis_time` | 분석 소요 시간 예측 | dependency_count | int (초) |
| `cache_results` | 분석 결과 캐싱 | key, data | bool |
| `load_cached_results` | 캐시된 결과 로드 | key | data or None |

### 4.2 툴 설계 원칙

1. **단일 책임**: 각 툴은 하나의 명확한 작업만 수행
2. **독립성**: 다른 툴에 의존하지 않고 독립적 실행 가능
3. **명확한 I/O**: 입력과 출력이 명확히 정의됨
4. **에러 처리**: 실패 시 명확한 에러 메시지 반환
5. **LangChain 호환**: `@tool` 데코레이터로 LangChain 툴화

### 4.3 툴 구현 예시

```python
from langchain.tools import tool
from typing import Dict, Any, List

@tool
def fetch_repository_tree(owner: str, repo: str) -> Dict[str, Any]:
    """
    GitHub 레포지토리의 파일 트리를 조회합니다.

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름

    Returns:
        Dict containing:
        - success: bool
        - files: List[Dict[path, sha, size]]
        - error: str (if failed)
    """
    try:
        from ..github import GitHubClient
        client = GitHubClient()
        files = client.get_repository_tree(owner, repo)
        return {
            "success": True,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "files": []
        }

@tool
def query_cpe_database(package_name: str, version: str, source: str) -> Dict[str, Any]:
    """
    CPE 데이터베이스에서 패키지에 해당하는 CPE ID를 조회합니다.

    Args:
        package_name: 패키지 이름 (예: "django")
        version: 패키지 버전 (예: "3.2.0")
        source: 패키지 소스 (예: "pypi", "npm")

    Returns:
        Dict containing:
        - success: bool
        - cpe_ids: List[str] (CPE ID 목록)
        - found: bool
        - error: str (if failed)
    """
    try:
        # TODO: 실제 DB 연동
        # 예시: SELECT cpe_id FROM cpe_mapping WHERE name=? AND version=?
        return {
            "success": True,
            "cpe_ids": ["cpe:2.3:a:djangoproject:django:3.2.0:*:*:*:*:*:*:*"],
            "found": True
        }
    except Exception as e:
        return {
            "success": False,
            "cpe_ids": [],
            "found": False,
            "error": str(e)
        }

@tool
def fetch_nvd_vulnerabilities(cpe_id: str) -> Dict[str, Any]:
    """
    NVD API를 통해 특정 CPE의 취약점 정보를 조회합니다.

    Args:
        cpe_id: CPE 식별자

    Returns:
        Dict containing:
        - success: bool
        - vulnerabilities: List[Dict[cve_id, severity, description]]
        - count: int
        - error: str (if failed)
    """
    try:
        # TODO: NVD API 연동
        # import requests
        # response = requests.get(f"https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName={cpe_id}")
        return {
            "success": True,
            "vulnerabilities": [
                {
                    "cve_id": "CVE-2023-1234",
                    "severity": "HIGH",
                    "cvss_score": 7.5,
                    "description": "SQL Injection vulnerability",
                    "published_date": "2023-01-15"
                }
            ],
            "count": 1
        }
    except Exception as e:
        return {
            "success": False,
            "vulnerabilities": [],
            "count": 0,
            "error": str(e)
        }
```

---

## 5. State 정의

### 5.1 AgentState 구조

```python
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class SecurityAnalysisState(TypedDict):
    """보안 분석 에이전트의 상태"""

    # 입력 정보
    owner: str
    repository: str
    github_token: Optional[str]

    # 진행 상태
    current_step: str  # "planning", "analyzing", "checking", "reporting"
    iteration: int
    max_iterations: int

    # 계획
    plan: List[str]  # 작업 계획 리스트
    plan_valid: bool
    plan_feedback: str

    # 메시지 (ReAct 대화)
    messages: Annotated[List[BaseMessage], add_messages]

    # 분석 결과
    dependencies: Optional[Dict[str, Any]]  # 의존성 분석 결과
    dependency_count: int
    lock_files_found: List[str]

    # 취약점 정보
    vulnerabilities: List[Dict[str, Any]]
    vulnerability_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

    # CPE 매핑
    cpe_mappings: Dict[str, List[str]]  # {package_name: [cpe_ids]}

    # 보안 평가
    security_score: Optional[Dict[str, Any]]
    security_grade: str  # A, B, C, D, F
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"

    # 레포트
    report: Optional[str]
    recommendations: List[str]

    # 에이전트 판단
    needs_human_input: bool
    human_question: Optional[str]
    human_response: Optional[str]

    # 에러 및 로그
    errors: List[str]
    warnings: List[str]

    # 완료 여부
    completed: bool
    final_result: Optional[Dict[str, Any]]
```

### 5.2 State 업데이트 예시

```python
# 초기 State
initial_state = SecurityAnalysisState(
    owner="facebook",
    repository="react",
    github_token="ghp_xxxxx",
    current_step="initializing",
    iteration=0,
    max_iterations=10,
    plan=[],
    plan_valid=False,
    messages=[],
    dependency_count=0,
    vulnerabilities=[],
    vulnerability_count=0,
    needs_human_input=False,
    completed=False
)

# State 업데이트 (의존성 분석 완료 후)
updated_state = {
    "current_step": "dependency_analysis_complete",
    "dependencies": {...},
    "dependency_count": 150,
    "lock_files_found": ["package-lock.json", "yarn.lock"]
}
```

---

## 6. 노드(Node) 정의

### 6.1 노드 목록 및 역할

#### 6.1.1 초기화 노드

**노드명**: `initialize_node`

**역할**: 입력 검증 및 초기 설정

**Input State**:
- `owner`, `repository`, `github_token`

**Output State**:
- `current_step`: "initialized"
- `plan`: []
- `messages`: [SystemMessage("분석을 시작합니다...")]

**로직**:
1. 레포지토리 접근 가능 여부 확인
2. GitHub 토큰 유효성 검증
3. 초기 State 설정
4. 시작 메시지 추가

**코드 예시**:
```python
def initialize_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """초기화 노드"""
    from langchain_core.messages import SystemMessage

    # 1. 레포지토리 검증
    validation_result = validate_repository_access(
        state["owner"],
        state["repository"]
    )

    if not validation_result["success"]:
        return {
            "errors": [validation_result["error"]],
            "completed": True
        }

    # 2. 초기 메시지
    init_message = SystemMessage(
        content=f"보안 분석을 시작합니다: {state['owner']}/{state['repository']}"
    )

    return {
        "current_step": "initialized",
        "messages": [init_message],
        "iteration": 0
    }
```

---

#### 6.1.2 계획 수립 노드

**노드명**: `planning_node`

**역할**: LLM을 사용하여 분석 계획 수립

**Input State**:
- `owner`, `repository`
- `dependencies` (있는 경우)
- `messages`

**Output State**:
- `plan`: List[작업 단계]
- `current_step`: "planned"
- `messages`: [계획 내용]

**로직**:
1. LLM에 현재 상황 전달
2. 필요한 작업 단계 도출
3. 계획을 State에 저장

**프롬프트 예시**:
```python
PLANNING_PROMPT = """
당신은 보안 분석 전문가입니다. 다음 레포지토리의 보안 분석 계획을 수립하세요.

레포지토리: {owner}/{repository}

현재 상황:
{current_situation}

사용 가능한 도구:
- analyze_dependencies: 의존성 분석
- query_cpe_database: CPE 데이터베이스 조회
- fetch_nvd_vulnerabilities: NVD에서 취약점 조회
- calculate_security_score: 보안 점수 계산
- generate_vulnerability_report: 레포트 생성

다음 형식으로 계획을 작성하세요:
1. [작업명]: [작업 설명]
2. [작업명]: [작업 설명]
...

계획:
"""

def planning_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """계획 수립 노드"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage

    llm = ChatOpenAI(model="gpt-4", temperature=0)

    # 현재 상황 정리
    current_situation = f"""
    - 레포지토리: {state['owner']}/{state['repository']}
    - 의존성 분석 완료: {state.get('dependencies') is not None}
    - 취약점 조회 완료: {len(state.get('vulnerabilities', []))} 개 발견
    """

    # LLM에 계획 요청
    prompt = PLANNING_PROMPT.format(
        owner=state['owner'],
        repository=state['repository'],
        current_situation=current_situation
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    plan_text = response.content

    # 계획 파싱
    plan = parse_plan_from_text(plan_text)

    return {
        "plan": plan,
        "current_step": "planned",
        "messages": [AIMessage(content=f"계획을 수립했습니다:\n{plan_text}")]
    }
```

---

#### 6.1.3 계획 검증 노드

**노드명**: `validate_plan_node`

**역할**: 계획의 타당성 검증

**Input State**:
- `plan`
- `current_step`

**Output State**:
- `plan_valid`: bool
- `plan_feedback`: str
- `current_step`: "plan_validated" or "plan_invalid"

**로직**:
1. 계획의 논리적 순서 확인
2. 필수 단계 포함 여부 확인
3. 불필요한 중복 작업 확인

**코드 예시**:
```python
def validate_plan_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """계획 검증 노드"""
    plan = state["plan"]

    # 필수 단계
    required_steps = [
        "의존성 분석",
        "취약점 조회",
        "보안 점수 계산",
        "레포트 생성"
    ]

    feedback = []

    # 1. 필수 단계 확인
    for required in required_steps:
        if not any(required in step for step in plan):
            feedback.append(f"필수 단계 누락: {required}")

    # 2. 논리적 순서 확인
    if "취약점 조회" in plan[0] and "의존성 분석" not in plan[0]:
        feedback.append("의존성 분석이 취약점 조회보다 먼저 수행되어야 합니다.")

    # 3. 검증 결과
    is_valid = len(feedback) == 0

    return {
        "plan_valid": is_valid,
        "plan_feedback": "\n".join(feedback) if feedback else "계획이 타당합니다.",
        "current_step": "plan_validated" if is_valid else "plan_invalid"
    }
```

---

#### 6.1.4 실행 노드 (Tool Executor)

**노드명**: `execute_tools_node`

**역할**: LLM이 선택한 툴을 실행

**Input State**:
- `plan`
- `current_step`
- `messages`

**Output State**:
- `dependencies`, `vulnerabilities`, etc. (실행 결과)
- `messages`: [실행 결과 메시지]
- `current_step`: 업데이트

**로직**:
1. LLM이 다음 행동 결정
2. 적절한 툴 선택 및 실행
3. 결과를 State에 저장

**코드 예시**:
```python
from langgraph.prebuilt import ToolExecutor
from langchain.agents import create_openai_functions_agent

def execute_tools_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """도구 실행 노드 (ReAct 패턴)"""
    from langchain_openai import ChatOpenAI
    from langchain.agents import AgentExecutor

    llm = ChatOpenAI(model="gpt-4", temperature=0)

    # 사용 가능한 툴 목록
    tools = [
        analyze_dependencies,
        query_cpe_database,
        fetch_nvd_vulnerabilities,
        calculate_security_score,
        generate_vulnerability_report
    ]

    # 에이전트 생성
    agent = create_openai_functions_agent(llm, tools, AGENT_PROMPT)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # 현재 계획에 따라 다음 작업 결정
    current_plan_step = state["plan"][state["iteration"]]

    # 에이전트 실행
    result = agent_executor.invoke({
        "input": f"다음 작업을 수행하세요: {current_plan_step}",
        "chat_history": state["messages"]
    })

    # State 업데이트 (결과에 따라)
    return {
        "messages": [result["output"]],
        "iteration": state["iteration"] + 1
    }
```

---

#### 6.1.5 관찰 및 반성 노드

**노드명**: `observe_and_reflect_node`

**역할**: 실행 결과를 관찰하고 다음 행동 결정

**Input State**:
- `messages`
- `plan`
- `iteration`

**Output State**:
- `current_step`: "continue", "completed", "need_help"
- `needs_human_input`: bool
- `human_question`: str (필요 시)

**로직**:
1. 최근 실행 결과 분석
2. 목표 달성 여부 판단
3. 다음 행동 결정 (계속 / 완료 / 도움 요청)

**코드 예시**:
```python
def observe_and_reflect_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """관찰 및 반성 노드"""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4", temperature=0)

    # 최근 결과 분석
    last_message = state["messages"][-1].content

    reflect_prompt = f"""
    최근 실행 결과:
    {last_message}

    현재 진행 상황:
    - 완료된 단계: {state['iteration']}/{len(state['plan'])}
    - 의존성 분석: {'완료' if state.get('dependencies') else '미완료'}
    - 취약점 조회: {state.get('vulnerability_count', 0)}개 발견

    다음 중 하나를 선택하세요:
    1. CONTINUE: 계획대로 계속 진행
    2. COMPLETE: 모든 작업 완료
    3. NEED_HELP: 사람의 도움 필요

    선택:
    """

    response = llm.invoke([HumanMessage(content=reflect_prompt)])
    decision = response.content.strip()

    # 결정에 따라 State 업데이트
    if "COMPLETE" in decision:
        return {"current_step": "completed", "completed": True}
    elif "NEED_HELP" in decision:
        return {
            "current_step": "need_help",
            "needs_human_input": True,
            "human_question": "분석 중 확인이 필요합니다. 계속 진행할까요?"
        }
    else:
        return {"current_step": "continue"}
```

---

#### 6.1.6 사람 개입 노드

**노드명**: `ask_human_node`

**역할**: 사람에게 질문하고 응답 대기

**Input State**:
- `human_question`

**Output State**:
- `human_response`
- `needs_human_input`: False
- `current_step`: "human_response_received"

**로직**:
1. 질문 출력
2. 사용자 입력 대기
3. 응답을 State에 저장

**코드 예시**:
```python
def ask_human_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """사람 개입 노드"""
    question = state["human_question"]

    # 질문 출력
    print(f"\n{'='*60}")
    print(f"[에이전트 질문]")
    print(f"{question}")
    print(f"{'='*60}\n")

    # 사용자 입력 대기
    response = input("답변을 입력하세요: ")

    return {
        "human_response": response,
        "needs_human_input": False,
        "current_step": "human_response_received",
        "messages": [HumanMessage(content=f"사용자 응답: {response}")]
    }
```

---

#### 6.1.7 레포트 생성 노드

**노드명**: `generate_report_node`

**역할**: 최종 보안 분석 레포트 생성

**Input State**:
- `dependencies`
- `vulnerabilities`
- `security_score`

**Output State**:
- `report`: str (Markdown)
- `recommendations`: List[str]
- `final_result`: Dict
- `completed`: True

**로직**:
1. 모든 분석 결과 통합
2. Markdown 형식의 레포트 생성
3. 개선 권장 사항 추가

**코드 예시**:
```python
def generate_report_node(state: SecurityAnalysisState) -> SecurityAnalysisState:
    """레포트 생성 노드"""

    # 1. 요약 정보
    summary = f"""
# 보안 분석 레포트

## 레포지토리 정보
- **소유자/이름**: {state['owner']}/{state['repository']}
- **분석 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 종합 평가
- **보안 등급**: {state.get('security_grade', 'N/A')}
- **보안 점수**: {state.get('security_score', {}).get('score', 'N/A')}/100
- **위험도**: {state.get('risk_level', 'N/A')}

## 의존성 분석 결과
- **전체 의존성**: {state.get('dependency_count', 0)}개
- **Lock 파일**: {', '.join(state.get('lock_files_found', []))}

## 취약점 분석 결과
- **전체 취약점**: {state.get('vulnerability_count', 0)}개
  - Critical: {state.get('critical_count', 0)}개
  - High: {state.get('high_count', 0)}개
  - Medium: {state.get('medium_count', 0)}개
  - Low: {state.get('low_count', 0)}개
"""

    # 2. 취약점 상세
    vuln_details = "\n## 취약점 상세\n"
    for vuln in state.get('vulnerabilities', []):
        vuln_details += f"""
### {vuln['cve_id']}
- **심각도**: {vuln['severity']}
- **CVSS 점수**: {vuln.get('cvss_score', 'N/A')}
- **설명**: {vuln.get('description', 'N/A')}
- **영향받는 패키지**: {vuln.get('package', 'N/A')}
"""

    # 3. 권장 사항
    recommendations = state.get('recommendations', [])
    rec_text = "\n## 개선 권장 사항\n"
    for i, rec in enumerate(recommendations, 1):
        rec_text += f"{i}. {rec}\n"

    # 최종 레포트
    report = summary + vuln_details + rec_text

    # 파일 저장
    report_path = f"security_report_{state['owner']}_{state['repository']}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return {
        "report": report,
        "completed": True,
        "final_result": {
            "report_path": report_path,
            "summary": summary,
            "vulnerabilities": state.get('vulnerabilities', []),
            "score": state.get('security_score')
        }
    }
```

---

## 7. 엣지(Edge) 및 조건부 라우팅

### 7.1 엣지 정의

```python
from langgraph.graph import StateGraph, END

# 그래프 생성
workflow = StateGraph(SecurityAnalysisState)

# 노드 추가
workflow.add_node("initialize", initialize_node)
workflow.add_node("plan", planning_node)
workflow.add_node("validate_plan", validate_plan_node)
workflow.add_node("execute_tools", execute_tools_node)
workflow.add_node("observe", observe_and_reflect_node)
workflow.add_node("ask_human", ask_human_node)
workflow.add_node("generate_report", generate_report_node)

# 엣지 추가
workflow.add_edge("initialize", "plan")
workflow.add_edge("plan", "validate_plan")
workflow.add_edge("ask_human", "execute_tools")
workflow.add_edge("execute_tools", "observe")
```

### 7.2 조건부 라우팅

```python
def route_after_validation(state: SecurityAnalysisState) -> str:
    """계획 검증 후 라우팅"""
    if state["plan_valid"]:
        return "execute_tools"
    else:
        return "plan"  # 계획 재수립

def route_after_observation(state: SecurityAnalysisState) -> str:
    """관찰 후 라우팅"""
    current = state["current_step"]

    if current == "completed":
        return "generate_report"
    elif current == "need_help":
        return "ask_human"
    elif state["iteration"] >= state["max_iterations"]:
        return "generate_report"  # 최대 반복 초과
    else:
        return "execute_tools"  # 계속 진행

def route_after_report(state: SecurityAnalysisState) -> str:
    """레포트 생성 후 라우팅"""
    return END  # 종료

# 조건부 엣지 추가
workflow.add_conditional_edges(
    "validate_plan",
    route_after_validation,
    {
        "execute_tools": "execute_tools",
        "plan": "plan"
    }
)

workflow.add_conditional_edges(
    "observe",
    route_after_observation,
    {
        "execute_tools": "execute_tools",
        "ask_human": "ask_human",
        "generate_report": "generate_report"
    }
)

workflow.add_conditional_edges(
    "generate_report",
    route_after_report
)

# 시작 노드 설정
workflow.set_entry_point("initialize")
```

---

## 8. ReAct 패턴 구현

### 8.1 ReAct 프롬프트

```python
REACT_AGENT_PROMPT = """
당신은 보안 분석 전문 에이전트입니다. ReAct 패턴(Reason + Act)을 사용하여 작업을 수행합니다.

현재 작업: {current_task}

진행 상황:
{progress}

사용 가능한 도구:
{tools}

다음 형식으로 응답하세요:

Thought: [무엇을 해야 하는지 생각]
Action: [사용할 도구와 입력]
Observation: [도구 실행 결과]
... (필요한 만큼 반복)
Final Answer: [최종 답변 또는 다음 단계]

시작하세요:
"""
```

### 8.2 ReAct 에이전트 구현

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

def create_security_react_agent(tools: List):
    """ReAct 패턴 보안 에이전트 생성"""

    llm = ChatOpenAI(model="gpt-4", temperature=0)

    # ReAct 프롬프트 템플릿
    prompt = PromptTemplate(
        template=REACT_AGENT_PROMPT,
        input_variables=["current_task", "progress", "tools", "agent_scratchpad"]
    )

    # ReAct 에이전트 생성
    agent = create_react_agent(llm, tools, prompt)

    # 에이전트 실행기
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True
    )

    return agent_executor

# 실행 예시
def execute_with_react(state: SecurityAnalysisState):
    """ReAct 패턴으로 작업 실행"""

    tools = [
        analyze_dependencies,
        query_cpe_database,
        fetch_nvd_vulnerabilities
    ]

    agent = create_security_react_agent(tools)

    result = agent.invoke({
        "current_task": state["plan"][state["iteration"]],
        "progress": f"완료: {state['iteration']}/{len(state['plan'])}",
        "tools": [t.name for t in tools]
    })

    return result
```

---

## 9. 사람 개입(Human-in-the-Loop)

### 9.1 개입이 필요한 시나리오

1. **모호한 상황**: 다음 행동을 결정하기 어려운 경우
2. **중요한 결정**: 보안 등급이 낮은 경우 계속 진행할지 확인
3. **에러 발생**: 복구 불가능한 에러 발생 시
4. **권한 필요**: 추가 API 호출이나 데이터베이스 접근 필요
5. **검증 필요**: 분석 결과의 정확성 확인 필요

### 9.2 질문 유형

```python
HUMAN_QUESTION_TEMPLATES = {
    "ambiguous": "다음 상황에서 어떻게 진행할까요? {situation}",
    "critical_finding": "심각한 취약점 {count}개가 발견되었습니다. 상세 분석을 계속할까요?",
    "error": "오류가 발생했습니다: {error}. 재시도할까요? (yes/no/skip)",
    "permission": "{action}을 실행하려면 추가 권한이 필요합니다. 계속할까요?",
    "validation": "분석 결과가 예상과 다릅니다. 검증이 필요할까요?"
}
```

### 9.3 사람 개입 구현

```python
def check_if_human_input_needed(state: SecurityAnalysisState) -> bool:
    """사람 개입 필요 여부 판단"""

    # 1. 심각한 취약점 발견
    if state.get('critical_count', 0) > 10:
        state["human_question"] = HUMAN_QUESTION_TEMPLATES["critical_finding"].format(
            count=state['critical_count']
        )
        return True

    # 2. 에러 발생
    if len(state.get('errors', [])) > 3:
        state["human_question"] = HUMAN_QUESTION_TEMPLATES["error"].format(
            error=state['errors'][-1]
        )
        return True

    # 3. 최대 반복 횟수 근접
    if state['iteration'] >= state['max_iterations'] - 2:
        state["human_question"] = "최대 반복 횟수에 도달했습니다. 계속 진행할까요?"
        return True

    return False

def handle_human_response(state: SecurityAnalysisState) -> Dict:
    """사람 응답 처리"""
    response = state["human_response"].lower()

    if response in ["yes", "y", "계속", "진행"]:
        return {"current_step": "continue"}
    elif response in ["no", "n", "중단", "종료"]:
        return {"current_step": "completed", "completed": True}
    elif response == "skip":
        return {"current_step": "skip_step", "iteration": state["iteration"] + 1}
    else:
        # 응답을 LLM에 전달하여 해석
        return {"messages": [HumanMessage(content=response)]}
```

---

## 10. 구현 단계

### Phase 1: 기초 인프라 구축 (1-2주)

#### 1.1 LangGraph 환경 설정
- [ ] LangGraph, LangChain, LangSmith 설치
- [ ] 환경 변수 설정 (.env)
- [ ] LangSmith 프로젝트 생성

```bash
pip install langgraph langchain langchain-openai langsmith
```

#### 1.2 State 정의
- [ ] `SecurityAnalysisState` TypedDict 구현
- [ ] State 초기화 함수 작성
- [ ] State 업데이트 유틸리티 함수

**파일**: `backend/agents/security/agent/state.py`

#### 1.3 기본 노드 구현
- [ ] `initialize_node`
- [ ] `planning_node` (간단한 규칙 기반)
- [ ] `execute_tools_node` (기초 버전)
- [ ] `generate_report_node`

**파일**: `backend/agents/security/agent/nodes/`

---

### Phase 2: 툴 분리 및 통합 (2-3주)

#### 2.1 GitHub 툴 분리
- [ ] `fetch_repository_tree` 툴화
- [ ] `fetch_file_content` 툴화
- [ ] `find_dependency_files` 툴화
- [ ] 에러 처리 및 재시도 로직

**파일**: `backend/agents/security/agent/tools/github_tools.py`

#### 2.2 의존성 분석 툴 분리
- [ ] `analyze_dependencies` 툴화
- [ ] `extract_dependencies_from_file` 툴화
- [ ] `filter_by_source` 툴화
- [ ] `count_by_language` 툴화

**파일**: `backend/agents/security/agent/tools/dependency_tools.py`

#### 2.3 취약점 조회 툴 구현
- [ ] `query_cpe_database` 구현
  - CPE 데이터베이스 스키마 설계
  - 패키지 → CPE 매핑 테이블
- [ ] `fetch_nvd_vulnerabilities` 구현
  - NVD API 연동
  - Rate limiting 처리
  - 캐싱 로직
- [ ] `check_vulnerability_severity` 구현

**파일**: `backend/agents/security/agent/tools/vulnerability_tools.py`

#### 2.4 보안 평가 툴 개선
- [ ] `calculate_security_score` 고도화
  - 취약점 심각도 반영
  - Lock 파일 존재 여부
  - 버전 명시 비율
- [ ] `suggest_improvements` 고도화

**파일**: `backend/agents/security/agent/tools/assessment_tools.py`

#### 2.5 레포트 생성 툴 구현
- [ ] `generate_executive_summary`
- [ ] `generate_vulnerability_report`
- [ ] `generate_remediation_guide`
- [ ] `export_report` (Markdown, PDF, HTML)

**파일**: `backend/agents/security/agent/tools/report_tools.py`

---

### Phase 3: 에이전트 로직 구현 (2-3주)

#### 3.1 계획 수립 로직
- [ ] LLM 기반 계획 수립
- [ ] 프롬프트 엔지니어링
- [ ] Few-shot 예시 추가

#### 3.2 계획 검증 로직
- [ ] 규칙 기반 검증
- [ ] LLM 기반 검증
- [ ] 피드백 생성

#### 3.3 ReAct 패턴 구현
- [ ] ReAct 프롬프트 작성
- [ ] 에이전트 실행 루프
- [ ] Thought-Action-Observation 로그

#### 3.4 관찰 및 반성 로직
- [ ] 결과 분석 로직
- [ ] 다음 행동 결정 로직
- [ ] 목표 달성 여부 판단

---

### Phase 4: 사람 개입 및 고급 기능 (1-2주)

#### 4.1 Human-in-the-Loop
- [ ] 질문 생성 로직
- [ ] 응답 대기 메커니즘
- [ ] 응답 처리 로직

#### 4.2 에러 처리 및 복구
- [ ] 에러 감지
- [ ] 자동 복구 시도
- [ ] 대체 경로 실행

#### 4.3 캐싱 및 최적화
- [ ] 분석 결과 캐싱
- [ ] NVD API 응답 캐싱
- [ ] 중복 작업 방지

---

### Phase 5: 통합 및 테스트 (2주)

#### 5.1 그래프 통합
- [ ] 모든 노드 연결
- [ ] 조건부 라우팅 구현
- [ ] 엣지 검증

#### 5.2 테스트
- [ ] 단위 테스트 (각 툴)
- [ ] 통합 테스트 (전체 플로우)
- [ ] 엣지 케이스 테스트

#### 5.3 모니터링
- [ ] LangSmith 추적 설정
- [ ] 로깅 구현
- [ ] 성능 메트릭

---

### Phase 6: 배포 및 문서화 (1주)

#### 6.1 배포 준비
- [ ] API 엔드포인트 생성
- [ ] 도커 이미지 빌드
- [ ] 환경 변수 설정

#### 6.2 문서화
- [ ] API 문서
- [ ] 사용 가이드
- [ ] 아키텍처 문서

---

## 11. 파일 구조

```
backend/agents/security/
├── agent/                                  # 새로운 에이전트 디렉토리
│   ├── __init__.py
│   ├── state.py                           # State 정의
│   ├── graph.py                           # LangGraph 그래프 정의
│   ├── prompts.py                         # 프롬프트 템플릿
│   │
│   ├── nodes/                             # 노드 구현
│   │   ├── __init__.py
│   │   ├── initialize.py                 # 초기화 노드
│   │   ├── planning.py                   # 계획 수립 노드
│   │   ├── validation.py                 # 계획 검증 노드
│   │   ├── execution.py                  # 실행 노드
│   │   ├── observation.py                # 관찰 노드
│   │   ├── human_input.py                # 사람 개입 노드
│   │   └── reporting.py                  # 레포트 생성 노드
│   │
│   ├── tools/                             # 툴 구현
│   │   ├── __init__.py
│   │   ├── github_tools.py               # GitHub 관련 툴
│   │   ├── dependency_tools.py           # 의존성 분석 툴
│   │   ├── vulnerability_tools.py        # 취약점 조회 툴
│   │   ├── assessment_tools.py           # 보안 평가 툴
│   │   ├── report_tools.py               # 레포트 생성 툴
│   │   └── utils.py                      # 유틸리티 툴
│   │
│   └── utils/                             # 유틸리티
│       ├── __init__.py
│       ├── cpe_mapper.py                 # CPE 매핑 유틸
│       ├── nvd_client.py                 # NVD API 클라이언트
│       ├── cache.py                      # 캐싱 유틸
│       └── validators.py                 # 검증 유틸
│
├── github/                                # 기존 유지
├── extractors/                            # 기존 유지
├── models/                                # 기존 유지
├── config/                                # 기존 유지
├── tools/                                 # 기존 유지 (레거시)
│
├── database/                              # 새로운 데이터베이스 디렉토리
│   ├── __init__.py
│   ├── schema.sql                        # CPE 매핑 스키마
│   ├── models.py                         # SQLAlchemy 모델
│   └── queries.py                        # 데이터베이스 쿼리
│
├── tests/                                 # 테스트
│   ├── test_agent.py
│   ├── test_tools.py
│   └── test_integration.py
│
└── examples/                              # 사용 예시
    ├── simple_analysis.py
    ├── with_human_input.py
    └── batch_analysis.py
```

---

## 12. 예상 실행 흐름

### 12.1 성공적인 실행 예시

```python
from backend.agents.security.agent import SecurityAnalysisAgent

# 1. 에이전트 초기화
agent = SecurityAnalysisAgent(
    github_token="ghp_xxxxx",
    enable_human_input=True,
    langsmith_project="security-analysis"
)

# 2. 분석 실행
result = agent.analyze(
    owner="facebook",
    repository="react"
)

# 3. 실행 흐름 (내부)
"""
[Step 1] Initialize
  └─ 레포지토리 검증: ✓

[Step 2] Planning
  💭 Thought: 레포지토리의 의존성을 먼저 분석해야 합니다.
  📋 Plan:
      1. 의존성 파일 탐지 및 분석
      2. CPE 매핑으로 취약점 후보 식별
      3. NVD API로 취약점 상세 조회
      4. 보안 점수 계산
      5. 레포트 생성

[Step 3] Validate Plan
  ✓ 계획이 타당합니다.

[Step 4] Execute - Iteration 1
  💭 Thought: package.json과 lock 파일을 먼저 찾아야 합니다.
  🔧 Action: find_dependency_files(owner="facebook", repo="react")
  👁️ Observation: 3개의 의존성 파일 발견
      - package.json
      - package-lock.json
      - yarn.lock

[Step 5] Execute - Iteration 2
  💭 Thought: 의존성을 추출하고 분석합니다.
  🔧 Action: analyze_dependencies(owner="facebook", repo="react")
  👁️ Observation:
      - 전체 의존성: 125개
      - Lock 파일: package-lock.json, yarn.lock
      - Lock 파일 의존성: 110개 (정확한 버전)

[Step 6] Execute - Iteration 3
  💭 Thought: 각 의존성에 대해 CPE를 조회합니다.
  🔧 Action: query_cpe_database(packages=[...])
  👁️ Observation:
      - CPE 매핑 성공: 95개
      - CPE 없음: 30개

[Step 7] Execute - Iteration 4
  💭 Thought: CPE가 있는 패키지의 취약점을 NVD에서 조회합니다.
  🔧 Action: fetch_nvd_vulnerabilities(cpe_ids=[...])
  👁️ Observation:
      - 취약점 발견: 15개
      - Critical: 2개
      - High: 5개
      - Medium: 6개
      - Low: 2개

[Step 8] Observe & Reflect
  🤔 Reflection: Critical 취약점이 2개 발견되었습니다.
  ❓ Decision: 사용자에게 확인이 필요합니다.

[Step 9] Ask Human
  ❓ Question: Critical 취약점 2개가 발견되었습니다. 상세 분석을 계속할까요?
  👤 Human: yes
  ✓ Response: 계속 진행합니다.

[Step 10] Execute - Iteration 5
  💭 Thought: 취약점 상세 정보를 조회합니다.
  🔧 Action: get_vulnerability_details(cve_ids=[...])
  👁️ Observation: 상세 정보 수집 완료

[Step 11] Execute - Iteration 6
  💭 Thought: 보안 점수를 계산합니다.
  🔧 Action: calculate_security_score(deps=[...], vulns=[...])
  👁️ Observation:
      - 점수: 65/100
      - 등급: D
      - 위험도: HIGH

[Step 12] Observe & Reflect
  🤔 Reflection: 모든 분석이 완료되었습니다.
  ✓ Decision: 레포트를 생성합니다.

[Step 13] Generate Report
  📄 Report: security_report_facebook_react.md 생성 완료
  ✓ 분석 완료

[Step 14] End
  🎉 최종 결과:
      - 보안 등급: D (65/100)
      - 취약점: 15개 (Critical: 2, High: 5, Medium: 6, Low: 2)
      - 권장 사항: 10개
      - 레포트: security_report_facebook_react.md
"""
```

### 12.2 계획 재수립 예시

```python
"""
[Step 2] Planning
  📋 Initial Plan:
      1. 취약점 조회
      2. 의존성 분석  # ← 순서가 잘못됨

[Step 3] Validate Plan
  ❌ 계획이 타당하지 않습니다.
  💬 Feedback: 의존성 분석이 취약점 조회보다 먼저 수행되어야 합니다.

[Step 4] Replan
  📋 Revised Plan:
      1. 의존성 분석  # ← 수정됨
      2. 취약점 조회
      3. 보안 점수 계산
      4. 레포트 생성

[Step 5] Validate Plan
  ✓ 계획이 타당합니다.

  → 실행 계속...
"""
```

### 12.3 에러 복구 예시

```python
"""
[Step 5] Execute - Iteration 3
  🔧 Action: fetch_nvd_vulnerabilities(cpe_ids=[...])
  ❌ Error: NVD API rate limit exceeded (429)

[Step 6] Observe & Reflect
  🤔 Reflection: API rate limit에 도달했습니다.
  💭 Thought: 잠시 대기 후 재시도하거나 캐시된 데이터를 사용할 수 있습니다.
  ❓ Decision: 사용자에게 확인이 필요합니다.

[Step 7] Ask Human
  ❓ Question: NVD API rate limit에 도달했습니다. 어떻게 할까요?
      1. 30초 대기 후 재시도
      2. 캐시된 데이터 사용 (최대 7일 전)
      3. 취약점 조회 건너뛰기
  👤 Human: 1
  ✓ Response: 30초 대기 후 재시도합니다.

[Step 8] Execute - Retry
  ⏳ Waiting: 30 seconds...
  🔧 Action: fetch_nvd_vulnerabilities(cpe_ids=[...])
  ✓ Success: 취약점 조회 성공

  → 실행 계속...
"""
```

---

## 13. 추가 고려사항

### 13.1 LangSmith 통합

```python
from langsmith import Client
from langsmith.run_helpers import traceable

# LangSmith 클라이언트
langsmith_client = Client()

@traceable(run_type="agent", project_name="security-analysis")
def analyze_with_tracking(owner: str, repo: str):
    """LangSmith 추적이 활성화된 분석"""
    agent = SecurityAnalysisAgent()
    return agent.analyze(owner, repo)
```

### 13.2 성능 최적화

1. **병렬 처리**: 여러 의존성의 취약점을 동시에 조회
2. **캐싱**: NVD API 응답, CPE 매핑 캐시
3. **배치 처리**: 여러 레포지토리를 한 번에 분석
4. **Rate Limiting**: API 호출 제한 관리

### 13.3 확장 가능성

1. **다양한 DB**: PostgreSQL, MongoDB, Redis 지원
2. **다양한 소스**: GitLab, Bitbucket 지원
3. **커스텀 툴**: 사용자 정의 툴 추가 가능
4. **플러그인 시스템**: 언어별 확장 가능

---

## 14. 시작하기

### 14.1 최소 구현 (MVP)

가장 먼저 구현할 핵심 기능:

1. ✅ **State 정의** (`state.py`)
2. ✅ **기본 그래프** (`graph.py`)
   - Initialize → Plan → Execute → Report → End
3. ✅ **2-3개 핵심 툴**
   - `analyze_dependencies`
   - `calculate_security_score`
   - `generate_report`
4. ✅ **간단한 실행 스크립트**

### 14.2 첫 번째 PR

```python
# examples/mvp_example.py
from backend.agents.security.agent import SecurityAnalysisAgent

agent = SecurityAnalysisAgent()
result = agent.analyze("facebook", "react")
print(result["report"])
```

목표: **2주 내에 MVP 완성**

---

## 15. 결론

이 계획서는 현재의 순차적 보안 분석 시스템을 **LangGraph 기반의 자율적인 에이전트**로 전환하는 로드맵을 제공합니다.

**핵심 가치:**
1. 🤖 **자율성**: 에이전트가 스스로 판단하고 행동
2. 🔄 **적응성**: 상황에 따라 계획 수정 가능
3. 🧩 **모듈화**: 작은 툴로 분리되어 재사용 가능
4. 👤 **협업**: 필요 시 사람에게 질문 가능
5. 📊 **관찰 가능**: 모든 단계를 추적하고 분석

**다음 단계:**
1. Phase 1 시작: LangGraph 환경 설정
2. State 정의 및 기본 노드 구현
3. MVP 완성 후 점진적 개선

이 문서를 기반으로 단계별로 구현을 진행하시면 됩니다! 🚀
