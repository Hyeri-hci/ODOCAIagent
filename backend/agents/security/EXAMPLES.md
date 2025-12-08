# Security Agent V2 - 실행 예제

## Jupyter Notebook 실행 방법

### 예제 1: 기본 사용법 (수정됨)

```python
# Jupyter Cell 1: 환경 설정
%load_ext autoreload
%autoreload 2

import os
import sys
from dotenv import load_dotenv

# 중요: backend/.env 파일 경로 명시
load_dotenv("backend/.env")

# backend 폴더를 Python path에 추가
sys.path.insert(0, os.path.abspath('.'))

from backend.agents.security.agent.security_agent_v2 import SecurityAgentV2

# Jupyter Cell 2: 환경 변수 확인
print("=" * 50)
print("Environment Variables Check")
print("=" * 50)
print(f"LLM_MODEL: {os.getenv('LLM_MODEL')}")
print(f"LLM_BASE_URL: {os.getenv('LLM_BASE_URL')}")
print(f"LLM_API_KEY: {'***' + os.getenv('LLM_API_KEY')[-4:] if os.getenv('LLM_API_KEY') else 'NOT SET'}")
print(f"LLM_TEMPERATURE: {os.getenv('LLM_TEMPERATURE')}")
print(f"GITHUB_TOKEN: {'***' + os.getenv('GITHUB_TOKEN')[-4:] if os.getenv('GITHUB_TOKEN') else 'NOT SET'}")
print("=" * 50)

# Jupyter Cell 3: 에이전트 생성
agent = SecurityAgentV2(
    llm_base_url=os.getenv("LLM_BASE_URL"),
    llm_api_key=os.getenv("LLM_API_KEY"),
    llm_model=os.getenv("LLM_MODEL"),
    llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
    execution_mode="intelligent"  # fast, intelligent, auto 중 선택
)

print("[OK] Agent initialized successfully!")

# Jupyter Cell 4: 분석 실행
result = await agent.analyze(
    user_request="facebook/react 프로젝트에서 사용한 의존성 패키지는 뭐가 있는지 알려줘",
    github_token=os.getenv("GITHUB_TOKEN")  # GitHub 토큰 전달
)

# Jupyter Cell 5: 결과 확인
print("\n" + "=" * 70)
print("Analysis Result")
print("=" * 70)
print(f"Success: {result.get('success', False)}")
print(f"Dependencies found: {result.get('results', {}).get('dependencies', {}).get('total', 0)}")
print(f"Vulnerabilities found: {result.get('results', {}).get('vulnerabilities', {}).get('total', 0)}")
print("\nDependencies:")
for ecosystem, packages in result.get('results', {}).get('dependencies', {}).get('details', {}).items():
    print(f"\n  {ecosystem}:")
    for pkg in packages[:5]:  # 처음 5개만 표시
        print(f"    - {pkg['name']} ({pkg.get('version', 'N/A')})")
```

### 예제 2: 취약점 스캔

```python
# Jupyter Cell: 취약점 스캔 실행
result = await agent.analyze(
    user_request="facebook/react의 보안 취약점을 찾아서 위험도별로 분류해줘",
    github_token=os.getenv("GITHUB_TOKEN")
)

# 결과 확인
vulns = result.get('results', {}).get('vulnerabilities', {})
print(f"\n총 취약점: {vulns.get('total', 0)}")
print(f"  🔴 CRITICAL: {vulns.get('critical', 0)}")
print(f"  🟠 HIGH: {vulns.get('high', 0)}")
print(f"  🟡 MEDIUM: {vulns.get('medium', 0)}")
print(f"  🟢 LOW: {vulns.get('low', 0)}")

# 상위 5개 취약점 출력
for vuln in vulns.get('details', [])[:5]:
    print(f"\n{vuln.get('cve_id', 'N/A')}")
    print(f"  Package: {vuln.get('package_name', 'N/A')} v{vuln.get('package_version', 'N/A')}")
    print(f"  Severity: {vuln.get('severity', 'N/A')} (CVSS: {vuln.get('cvss_v3_score', 'N/A')})")
    print(f"  Description: {vuln.get('description', 'N/A')[:100]}...")
```

### 예제 3: 빠른 실행 모드

```python
# Fast 모드: 규칙 기반 실행 (LLM 최소화)
agent_fast = SecurityAgentV2(
    llm_base_url=os.getenv("LLM_BASE_URL"),
    llm_api_key=os.getenv("LLM_API_KEY"),
    llm_model=os.getenv("LLM_MODEL"),
    llm_temperature=0.0,
    execution_mode="fast"
)

result = await agent_fast.analyze(
    user_request="lodash 라이브러리의 취약점 조회",
    github_token=os.getenv("GITHUB_TOKEN")
)
```

### 예제 4: 단순 분석 (후방 호환성)

```python
# 단순 API 사용
result = await agent.analyze_simple(
    primary_action="analyze_all",
    owner="facebook",
    repository="react",
    github_token=os.getenv("GITHUB_TOKEN")
)
```

---

## Python 스크립트 실행 방법

### 기본 실행

```python
import asyncio
import os
from dotenv import load_dotenv
from backend.agents.security.agent.security_agent_v2 import SecurityAgentV2

# 환경 변수 로드
load_dotenv("backend/.env")

async def main():
    # 에이전트 생성
    agent = SecurityAgentV2(
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        execution_mode="intelligent"
    )

    # 분석 실행
    result = await agent.analyze(
        user_request="facebook/react의 의존성 패키지를 조회해줘",
        github_token=os.getenv("GITHUB_TOKEN")
    )

    # 결과 출력
    print(f"Dependencies: {result.get('results', {}).get('dependencies', {}).get('total', 0)}")
    print(f"Vulnerabilities: {result.get('results', {}).get('vulnerabilities', {}).get('total', 0)}")

    return result

# 실행
if __name__ == "__main__":
    result = asyncio.run(main())
```

---

## 문제 해결 (Troubleshooting)

### 1. 환경 변수가 로드되지 않는 경우

**증상:** `LLM_MODEL`, `LLM_API_KEY` 등이 `None`

**해결:**
```python
# ❌ 잘못된 방법
load_dotenv()  # 루트의 .env를 찾지만 없음

# ✅ 올바른 방법
load_dotenv("backend/.env")  # 명시적 경로 지정
```

### 2. Module not found 에러

**증상:** `ModuleNotFoundError: No module named 'backend'`

**해결:**
```python
import sys
import os

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.abspath('.'))
```

### 3. LangChain 관련 에러

**증상:** `ModuleNotFoundError: No module named 'langchain_openai'`

**해결:**
```bash
pip install langchain langchain-openai langgraph
```

### 4. GitHub API Rate Limit

**증상:** `API rate limit exceeded`

**해결:**
```python
# GitHub 토큰을 반드시 전달
result = await agent.analyze(
    user_request="...",
    github_token=os.getenv("GITHUB_TOKEN")  # 필수!
)
```

### 5. NVD API Rate Limit

**증상:** 취약점 조회가 매우 느림 (6초마다 1개)

**해결:**
- backend/.env에 `NVD_API_KEY` 추가 (API 키가 있으면 0.6초마다 1개로 10배 빠름)
```bash
NVD_API_KEY=your-nvd-api-key-here
```

---

## 고급 사용법

### 메타인지 비활성화

```python
agent = SecurityAgentV2(
    llm_base_url=os.getenv("LLM_BASE_URL"),
    llm_api_key=os.getenv("LLM_API_KEY"),
    llm_model=os.getenv("LLM_MODEL"),
    llm_temperature=0.1,
    execution_mode="intelligent",
    enable_reflection=False  # 반성 단계 비활성화
)
```

### 최대 반복 횟수 조정

```python
agent = SecurityAgentV2(
    llm_base_url=os.getenv("LLM_BASE_URL"),
    llm_api_key=os.getenv("LLM_API_KEY"),
    llm_model=os.getenv("LLM_MODEL"),
    llm_temperature=0.1,
    execution_mode="intelligent",
    max_iterations=10  # 기본값: 20
)
```

### 상태 내보내기

```python
# 분석 실행
final_state = await agent.graph.ainvoke(initial_state)

# 상태를 JSON으로 내보내기
state_json = agent.export_state(final_state, format="json")

# 파일로 저장
with open("analysis_state.json", "w") as f:
    f.write(state_json)
```

---

## 주의사항

1. **환경 변수 필수:**
   - `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`은 필수
   - `GITHUB_TOKEN`은 선택이지만, 없으면 API Rate Limit 발생

2. **.env 파일 경로:**
   - 반드시 `load_dotenv("backend/.env")`로 명시적 경로 지정
   - 루트에 .env가 없으면 환경 변수가 로드되지 않음

3. **비동기 함수:**
   - `analyze()` 메서드는 `async` 함수
   - Jupyter에서는 `await`로 직접 호출 가능
   - Python 스크립트에서는 `asyncio.run()` 사용

4. **LLM 모델 호환성:**
   - OpenAI API 호환 모델 사용 (Kakao Kanana, Upstage Solar, OpenAI 등)
   - `base_url` + `api_key` + `model` 조합 필수

5. **GitHub 레포지토리:**
   - Public 레포지토리는 토큰 없이도 조회 가능 (Rate Limit 있음)
   - Private 레포지토리는 토큰 필수
