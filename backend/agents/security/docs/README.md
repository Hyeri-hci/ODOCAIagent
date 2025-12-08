# Security Agent - AI 에이전트 툴

GitHub 레포지토리의 의존성 및 보안을 분석하는 AI 에이전트 툴입니다.

## 📋 목차

- [개요](#개요)
- [아키텍처](#아키텍처)
- [설치](#설치)
- [빠른 시작](#빠른-시작)
- [주요 기능](#주요-기능)
- [AI 에이전트 통합](#ai-에이전트-통합)
- [API 문서](#api-문서)
- [향후 계획](#향후-계획)

---

## 개요

Security Agent는 GitHub 레포지토리의 의존성을 자동으로 분석하고, 보안 점수를 계산하며, 개선 제안을 제공하는 도구입니다. AI 에이전트가 사용할 수 있는 독립적인 툴 함수들로 구성되어 있습니다.

### 지원 언어 및 패키지 매니저

- **JavaScript/Node.js**: package.json, yarn.lock, npm
- **Python**: requirements.txt, Pipfile, poetry, conda
- **Ruby**: Gemfile, Bundler
- **Java/JVM**: Maven (pom.xml), Gradle, SBT, Leiningen
- **.NET/C#**: NuGet, paket
- **Go**: go.mod, dep
- **Rust**: Cargo
- **Swift/iOS**: Swift PM, CocoaPods, Carthage
- **Dart/Flutter**: pub
- **C/C++**: Conan, vcpkg, CMake
- **PHP**: Composer
- **기타**: Elixir, Haskell, Julia, Elm, Crystal, Deno, R 등 30+ 언어 지원

---

## 아키텍처

```
backend/agents/security/
├── models/                    # 데이터 모델
│   ├── dependency.py          # Dependency, DependencyFile
│   └── __init__.py
├── config/                    # 설정
│   ├── dependency_files.py    # 지원하는 의존성 파일 패턴
│   └── __init__.py
├── extractors/                # 언어별 파서
│   ├── base.py                # BaseExtractor 추상 클래스
│   ├── javascript.py          # JS/Node.js
│   ├── python.py              # Python
│   ├── ruby.py                # Ruby
│   ├── jvm.py                 # Java/Scala/Clojure
│   ├── dotnet.py              # .NET/C#
│   ├── go.py                  # Go
│   ├── rust.py                # Rust
│   ├── mobile.py              # Swift/Dart
│   ├── cpp.py                 # C/C++
│   ├── others.py              # PHP, Elixir 등
│   └── __init__.py            # DependencyExtractor 통합
├── github/                    # GitHub API 통합
│   ├── client.py              # GitHubClient
│   ├── analyzer.py            # RepositoryAnalyzer
│   └── __init__.py
├── tools/                     # AI 에이전트 툴 함수
│   ├── dependency_analyzer.py # 의존성 분석 툴
│   ├── vulnerability_checker.py # 보안 체크 툴
│   └── __init__.py
├── service.py                 # 메인 서비스 (run_security_analysis)
├── __init__.py
├── README.md                  # 이 파일
└── EXAMPLES.md                # 사용 예제 모음
```

### 설계 원칙

1. **모듈화**: 각 언어별 파서를 독립적으로 관리
2. **툴 기반**: AI 에이전트가 독립적으로 호출 가능한 함수들
3. **확장성**: 새로운 언어/기능 추가가 용이
4. **재사용성**: 각 컴포넌트를 다른 곳에서도 사용 가능
5. **에러 핸들링**: 모든 함수는 에러 발생 시에도 결과 반환

---

## 설치

### 필수 요구사항

```bash
# Python 3.9 이상
python --version

# 필요한 패키지 설치
pip install -r requirements.txt
```

### 환경 변수 설정

```bash
# .env 파일 생성
GITHUB_TOKEN=your_github_token_here
GITHUB_BASE_URL=https://api.github.com  # 옵션
```

---

## 빠른 시작

### 1. 기본 사용

```python
from backend.agents.security.tools import analyze_repository_dependencies

# 의존성 분석
result = analyze_repository_dependencies(
    owner="facebook",
    repo="react"
)

print(f"Total dependencies: {result['total_dependencies']}")
```

### 2. 전체 보안 분석

```python
from backend.agents.security.service import run_security_analysis

# 전체 분석 실행
result = run_security_analysis({
    "owner": "facebook",
    "repo": "react",
    "analysis_type": "full"
})

# 결과 확인
print(result["summary"])
print(f"Security Grade: {result['security_score']['grade']}")
```

### 3. AI 에이전트에서 사용

```python
# Supervisor 노드에서 호출
from backend.agents.supervisor.nodes.run_security import run_security_node

def route_after_mapping(state):
    if needs_security(state.get("task_type")):
        return "run_security"
    # ...

graph.add_node("run_security", run_security_node)
```

---

## 주요 기능

### 1. 의존성 분석

- 30개 이상의 언어 및 패키지 매니저 지원
- 병렬 처리를 통한 빠른 분석
- Runtime/Dev/Peer/Optional 의존성 구분
- 버전 정보 추출

### 2. 보안 점수 계산

- 0-100 점수 (A-F 등급)
- 버전 미명시 의존성 페널티
- 향후 취약점 데이터 통합 예정

### 3. 개선 제안

- 버전 고정 권장
- Lock 파일 추가 권장
- 패키지 매니저 업그레이드 권장
- 보안 점수 기반 제안

### 4. 향후 기능 (계획)

- **취약점 스캔**: CVE 데이터베이스 연동
- **라이센스 체크**: 라이센스 준수 확인
- **의존성 트리**: 간접 의존성 분석
- **자동 업데이트**: Dependabot 스타일 PR 생성

---

## AI 에이전트 통합

### 독립적인 툴 함수

각 함수는 독립적으로 호출 가능하며, 명확한 입력/출력을 가집니다.

```python
from backend.agents.security.tools import (
    # 분석 툴
    analyze_repository_dependencies,
    find_dependency_files,
    summarize_dependency_analysis,

    # 필터링 툴
    get_dependencies_by_source,
    get_dependencies_by_type,
    get_outdated_dependencies,

    # 보안 툴
    get_security_score,
    check_vulnerabilities,
    suggest_security_improvements,
)
```

### LangGraph 통합

```python
# 1. Supervisor State에 필드 추가
class SupervisorState(TypedDict, total=False):
    security_result: Dict[str, Any]
    security_task_type: str

# 2. 노드 추가
from backend.agents.supervisor.nodes.run_security import run_security_node
graph.add_node("run_security", run_security_node)

# 3. 라우팅 설정
graph.add_conditional_edges("map_task_types", route_after_mapping, {...})
graph.add_edge("run_security", "summarize")
```

### Intent 설정

```python
# backend/agents/supervisor/intent_config.py
INTENT_CONFIG = {
    "analyze_security": {
        "needs_security": True,
        "is_ready": True,
        "description": "Check repository security and dependencies"
    },
}
```

---

## API 문서

### 주요 함수

#### `analyze_repository_dependencies`

의존성 분석의 핵심 함수입니다.

```python
def analyze_repository_dependencies(
    owner: str,
    repo: str,
    max_workers: int = 5,
    github_token: Optional[str] = None,
    github_base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    GitHub 레포지토리의 의존성 분석

    Returns:
        {
            'owner': str,
            'repo': str,
            'total_files': int,
            'total_dependencies': int,
            'files': List[Dict],
            'all_dependencies': List[Dict],
            'summary': Dict
        }
    """
```

#### `run_security_analysis`

전체 보안 분석 워크플로우를 실행합니다.

```python
def run_security_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Security Agent 진입점

    Args:
        payload: {
            'owner': str,           # 필수
            'repo': str,            # 필수
            'analysis_type': str,   # 'dependencies', 'vulnerabilities', 'full'
            'max_workers': int,     # 기본값: 5
            'include_suggestions': bool  # 기본값: True
        }

    Returns:
        {
            'dependency_analysis': Dict,
            'security_score': Dict,
            'vulnerabilities': Dict,
            'suggestions': List[str],
            'summary': str
        }
    """
```

#### `get_security_score`

보안 점수를 계산합니다.

```python
def get_security_score(
    analysis_result: Dict[str, Any],
    vulnerability_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    보안 점수 계산

    Returns:
        {
            'score': int,        # 0-100
            'grade': str,        # A, B, C, D, F
            'factors': Dict      # 점수 구성 요소
        }
    """
```

전체 API 문서는 각 함수의 docstring을 참고하세요.

---

## 사용 예제

자세한 예제는 [EXAMPLES.md](EXAMPLES.md)를 참고하세요.

### 기본 예제

```python
# 의존성 분석
from backend.agents.security.tools import analyze_repository_dependencies

result = analyze_repository_dependencies("facebook", "react")
print(f"Dependencies: {result['total_dependencies']}")
```

### 필터링 예제

```python
# npm 의존성만 추출
from backend.agents.security.tools import get_dependencies_by_source

result = analyze_repository_dependencies("facebook", "react")
npm_deps = get_dependencies_by_source(result, "npm")
```

### 전체 분석 예제

```python
# 전체 보안 분석 + 개선 제안
from backend.agents.security.service import run_security_analysis

result = run_security_analysis({
    "owner": "facebook",
    "repo": "react",
    "analysis_type": "full",
    "include_suggestions": True
})

print(result["summary"])
for suggestion in result["suggestions"]:
    print(f"- {suggestion}")
```

---

## 향후 계획

### Phase 1: 취약점 스캔 (진행 중)
- [ ] GitHub Security Advisories API 연동
- [ ] OSV (Open Source Vulnerabilities) 통합
- [ ] Snyk API 연동 (옵션)
- [ ] 취약점 심각도별 분류

### Phase 2: 라이센스 관리
- [ ] 라이센스 정보 추출
- [ ] 허용/불허 라이센스 체크
- [ ] 라이센스 충돌 감지

### Phase 3: 고급 분석
- [ ] 의존성 트리 분석 (간접 의존성)
- [ ] 중복 의존성 감지
- [ ] 의존성 업데이트 제안
- [ ] 자동 PR 생성 (Dependabot 스타일)

### Phase 4: 대시보드 & 리포트
- [ ] 웹 대시보드 구현
- [ ] PDF 리포트 생성
- [ ] 트렌드 분석
- [ ] CI/CD 통합

---

## 기여하기

새로운 언어 지원이나 기능 추가는 다음 단계를 따르세요:

1. **새 언어 추가**:
   - `extractors/`에 새 파일 생성 (예: `kotlin.py`)
   - `BaseExtractor` 상속
   - `extract()` 메서드 구현
   - `extractors/__init__.py`에 추가

2. **새 툴 추가**:
   - `tools/`에 새 파일 생성
   - 독립적인 함수로 구현
   - Docstring 작성 (입력/출력 명시)
   - `tools/__init__.py`에 추가

3. **테스트 작성**:
   - 단위 테스트 추가
   - 통합 테스트 추가

---

## 라이센스

이 프로젝트는 카카오 엔터프라이즈의 내부 프로젝트입니다.

---

## 문의

문제나 질문이 있으면 이슈를 생성해주세요.
