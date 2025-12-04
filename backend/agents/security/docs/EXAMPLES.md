# Security Agent - Usage Examples

이 문서는 Security Agent를 AI 에이전트 툴로 사용하는 방법을 설명합니다.

## 목차
1. [직접 툴 사용](#직접-툴-사용)
2. [Service 레벨 사용](#service-레벨-사용)
3. [Supervisor 통합](#supervisor-통합)
4. [개별 툴 함수 사용](#개별-툴-함수-사용)

---

## 직접 툴 사용

각 툴은 독립적으로 사용할 수 있습니다.

### 의존성 분석

```python
from backend.agents.security.tools import analyze_repository_dependencies

# 기본 사용
result = analyze_repository_dependencies(
    owner="facebook",
    repo="react"
)

print(f"Total dependencies: {result['total_dependencies']}")
print(f"Dependency files: {result['total_files']}")

# 결과 구조
# {
#     'owner': 'facebook',
#     'repo': 'react',
#     'total_files': 5,
#     'total_dependencies': 150,
#     'files': [...],
#     'all_dependencies': [...],
#     'summary': {
#         'by_source': {'npm': 150},
#         'runtime_dependencies': 120,
#         'dev_dependencies': 30,
#         'total_unique': 150
#     }
# }
```

### 자연어 요약 생성

```python
from backend.agents.security.tools import (
    analyze_repository_dependencies,
    summarize_dependency_analysis
)

result = analyze_repository_dependencies("facebook", "react")
summary = summarize_dependency_analysis(result)
print(summary)

# 출력:
# Repository: facebook/react
# Total dependency files analyzed: 5
# Total unique dependencies: 150
# Runtime dependencies: 120
# Development dependencies: 30
#
# Dependencies by package manager:
#   - npm: 150
```

### 의존성 필터링

```python
from backend.agents.security.tools import (
    analyze_repository_dependencies,
    get_dependencies_by_source,
    get_dependencies_by_type,
    get_outdated_dependencies
)

result = analyze_repository_dependencies("facebook", "react")

# npm 의존성만 추출
npm_deps = get_dependencies_by_source(result, "npm")
print(f"NPM dependencies: {len(npm_deps)}")

# Runtime 의존성만 추출
runtime_deps = get_dependencies_by_type(result, "runtime")
print(f"Runtime dependencies: {len(runtime_deps)}")

# 버전이 명시되지 않은 의존성 찾기
unversioned = get_outdated_dependencies(result)
print(f"Unversioned dependencies: {len(unversioned)}")
```

### 보안 점수 계산

```python
from backend.agents.security.tools import (
    analyze_repository_dependencies,
    get_security_score
)

result = analyze_repository_dependencies("facebook", "react")
security_score = get_security_score(result)

print(f"Security Grade: {security_score['grade']}")
print(f"Security Score: {security_score['score']}/100")

# 결과:
# {
#     'score': 85,
#     'grade': 'B',
#     'factors': {
#         'total_dependencies': 150,
#         'unversioned_dependencies': 5,
#         'unversioned_penalty': 10
#     }
# }
```

### 개선 제안 생성

```python
from backend.agents.security.tools import (
    analyze_repository_dependencies,
    get_security_score,
    suggest_security_improvements
)

result = analyze_repository_dependencies("facebook", "react")
score = get_security_score(result)
suggestions = suggest_security_improvements(result, None, score)

print("Security Improvement Suggestions:")
for i, suggestion in enumerate(suggestions, 1):
    print(f"{i}. {suggestion}")
```

---

## Service 레벨 사용

`run_security_analysis` 함수는 모든 툴을 통합하여 전체 워크플로우를 실행합니다.

### 전체 분석

```python
from backend.agents.security.service import run_security_analysis

# 전체 보안 분석 실행
result = run_security_analysis({
    "owner": "facebook",
    "repo": "react",
    "analysis_type": "full",  # 'dependencies', 'vulnerabilities', 'full'
    "max_workers": 5,
    "include_suggestions": True
})

# 결과 확인
print(result["summary"])
print(f"Security Grade: {result['security_score']['grade']}")
print(f"Total Dependencies: {result['dependency_analysis']['total_dependencies']}")

# 개선 제안
for suggestion in result['suggestions']:
    print(f"- {suggestion}")
```

### 의존성 분석만 실행

```python
result = run_security_analysis({
    "owner": "facebook",
    "repo": "react",
    "analysis_type": "dependencies",  # 의존성 분석만
    "include_suggestions": False  # 제안 없이
})

print(result["dependency_analysis"])
```

### 하위 호환성 클래스 사용

```python
from backend.agents.security.service import SecurityAnalysisService

service = SecurityAnalysisService()

# 분석 실행
result = service.analyze_repository("facebook", "react")

# 요약 출력
service.print_summary(result)

# 파일로 저장
service.save_results(result, "output.json")
```

---

## Supervisor 통합

LangGraph Supervisor와 통합하여 사용하는 방법입니다.

### Supervisor 노드 추가

```python
# backend/agents/supervisor/graph.py

from backend.agents.supervisor.nodes.run_security import run_security_node

def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    # 기존 노드들
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("map_task_types", map_task_types_node)
    graph.add_node("run_diagnosis", run_diagnosis_node)

    # Security 노드 추가
    graph.add_node("run_security", run_security_node)

    graph.add_node("summarize", summarize_node)

    # ... 나머지 그래프 구성
```

### Intent 설정 추가

```python
# backend/agents/supervisor/intent_config.py

INTENT_CONFIG = {
    # ... 기존 intents
    "analyze_security": {
        "needs_diagnosis": False,
        "needs_security": True,  # 새로운 플래그
        "is_ready": True,
        "description": "Check repository security and dependencies"
    },
    "check_dependencies": {
        "needs_diagnosis": False,
        "needs_security": True,
        "is_ready": True,
        "description": "Analyze project dependencies"
    },
}

def needs_security(task_type: str) -> bool:
    """Security 분석이 필요한지 확인"""
    return INTENT_CONFIG.get(task_type, {}).get("needs_security", False)
```

### State 타입 확장

```python
# backend/agents/supervisor/models.py

class SupervisorState(TypedDict, total=False):
    # ... 기존 필드들

    # Security 관련 필드
    security_task_type: str  # 'dependencies_only', 'vulnerabilities_only', 'full'
    security_result: Dict[str, Any]
```

### 라우팅 로직 업데이트

```python
# backend/agents/supervisor/graph.py

def route_after_mapping(state: SupervisorState) -> str:
    task_type = state.get("task_type", "diagnose_repo_health")

    # Security 분석이 필요한 경우
    if needs_security(task_type):
        return "run_security"

    # Diagnosis가 필요한 경우
    if needs_diagnosis(task_type):
        return "run_diagnosis"

    return "summarize"

graph.add_conditional_edges(
    "map_task_types",
    route_after_mapping,
    {
        "run_diagnosis": "run_diagnosis",
        "run_security": "run_security",
        "summarize": "summarize",
    },
)

# Security → Summarize 엣지
graph.add_edge("run_security", "summarize")
```

---

## 개별 툴 함수 사용

각 툴 함수는 독립적으로 호출 가능합니다.

### 의존성 파일만 찾기

```python
from backend.agents.security.tools import find_dependency_files

files = find_dependency_files("facebook", "react")
print(f"Found {len(files)} dependency files:")
for file_path in files:
    print(f"  - {file_path}")
```

### 언어별 의존성 개수 확인

```python
from backend.agents.security.tools import (
    analyze_repository_dependencies,
    count_dependencies_by_language
)

result = analyze_repository_dependencies("facebook", "react")
counts = count_dependencies_by_language(result)

for language, count in counts.items():
    print(f"{language}: {count} dependencies")
```

### 취약점 체크 (향후 구현)

```python
from backend.agents.security.tools import check_vulnerabilities

result = analyze_repository_dependencies("facebook", "react")
vulnerabilities = check_vulnerabilities(result, severity_threshold="high")

print(f"Critical: {vulnerabilities['critical']}")
print(f"High: {vulnerabilities['high']}")
print(f"Medium: {vulnerabilities['medium']}")
```

---

## 에러 핸들링

모든 툴 함수는 에러 발생 시 에러 정보를 포함한 결과를 반환합니다.

```python
result = analyze_repository_dependencies("invalid", "repo")

if "error" in result:
    print(f"Error occurred: {result['error']}")
    print(f"Dependencies found: {result['total_dependencies']}")  # 0
else:
    print("Analysis successful")
```

---

## 병렬 처리

여러 레포지토리를 병렬로 분석할 수 있습니다.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.agents.security.tools import analyze_repository_dependencies

repos = [
    ("facebook", "react"),
    ("vuejs", "vue"),
    ("angular", "angular"),
]

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(analyze_repository_dependencies, owner, repo): (owner, repo)
        for owner, repo in repos
    }

    for future in as_completed(futures):
        owner, repo = futures[future]
        try:
            result = future.result()
            print(f"{owner}/{repo}: {result['total_dependencies']} dependencies")
        except Exception as e:
            print(f"{owner}/{repo}: Error - {e}")
```

---

## 캐싱 및 최적화

### GitHub 토큰 사용

```python
# .env 파일에 설정
GITHUB_TOKEN=your_token_here

# 또는 직접 전달
result = analyze_repository_dependencies(
    owner="facebook",
    repo="react",
    github_token="your_token_here"
)
```

### 워커 수 조정

```python
# 빠른 분석 (워커 많이 사용)
result = analyze_repository_dependencies(
    owner="facebook",
    repo="react",
    max_workers=10
)

# 안정적인 분석 (워커 적게 사용)
result = analyze_repository_dependencies(
    owner="facebook",
    repo="react",
    max_workers=3
)
```

---

## 결과 저장 및 공유

```python
from backend.agents.security.service import SecurityAnalysisService
import json

service = SecurityAnalysisService()
result = service.analyze_repository("facebook", "react")

# JSON 파일로 저장
file_path = service.save_results(result, "react_security.json")

# 특정 정보만 추출하여 저장
summary_data = {
    "repository": f"{result['owner']}/{result['repo']}",
    "total_dependencies": result['total_dependencies'],
    "security_grade": result.get('security_score', {}).get('grade'),
    "suggestions": result.get('suggestions', [])
}

with open("react_summary.json", "w") as f:
    json.dump(summary_data, f, indent=2)
```

---

## 통합 예제: CI/CD 파이프라인

```python
#!/usr/bin/env python3
"""
CI/CD에서 사용할 수 있는 보안 검사 스크립트
"""
import sys
from backend.agents.security.service import run_security_analysis

def main():
    # 레포지토리 정보
    owner = sys.argv[1] if len(sys.argv) > 1 else "facebook"
    repo = sys.argv[2] if len(sys.argv) > 2 else "react"

    # 보안 분석 실행
    result = run_security_analysis({
        "owner": owner,
        "repo": repo,
        "analysis_type": "full",
        "include_suggestions": True
    })

    # 보안 점수 확인
    security_score = result.get("security_score", {})
    grade = security_score.get("grade", "F")
    score = security_score.get("score", 0)

    print(f"\n{'='*60}")
    print(result.get("summary", ""))
    print(f"{'='*60}\n")

    # 보안 점수가 낮으면 실패
    if score < 70:
        print(f"❌ Security check failed: Grade {grade} (Score: {score}/100)")
        print("\nImprovement suggestions:")
        for suggestion in result.get("suggestions", []):
            print(f"  - {suggestion}")
        sys.exit(1)
    else:
        print(f"✅ Security check passed: Grade {grade} (Score: {score}/100)")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## 더 많은 예제

더 많은 예제와 사용 사례는 다음 파일을 참고하세요:
- `backend/agents/security/dev-ipynb/test.ipynb` - 원본 노트북 예제
- `backend/agents/security/tools/` - 각 툴 함수의 docstring
- `backend/agents/security/service.py` - 서비스 레벨 통합
