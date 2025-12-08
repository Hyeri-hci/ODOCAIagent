# Security Agent V2

**자연어 기반 자율 보안 분석 에이전트**

Security Agent V2는 LangGraph와 ReAct 패턴을 활용하여 GitHub 레포지토리의 보안을 자동으로 분석하는 AI 에이전트입니다.

---

## ✨ 주요 기능

### 1. **자연어 요청 지원**
```python
await agent.analyze("facebook/react의 보안 취약점을 찾아줘")
```

### 2. **자율적 계획 수립 및 실행**
- LLM 기반 동적 계획 생성
- ReAct 패턴 (Think → Act → Observe)
- 자동 재시도 및 대안 도구 선택

### 3. **실제 NVD API 연동**
- NVD (National Vulnerability Database) 실시간 조회
- CVE, CVSS, CWE 정보 추출
- 위험도별 취약점 분류 (CRITICAL, HIGH, MEDIUM, LOW)

### 4. **다양한 실행 모드**
- **Fast 모드**: 규칙 기반, LLM 최소화 (빠름)
- **Intelligent 모드**: LLM 기반 자율 판단 (유연함)
- **Auto 모드**: 요청 복잡도에 따라 자동 선택

### 5. **메타인지 (Reflection)**
- 매 5회 반복마다 진행 상황 평가
- 전략 조정 및 재계획
- Human-in-the-Loop 지원

---

## 🚀 빠른 시작

### 설치

```bash
# 필수 라이브러리 설치
pip install langchain langchain-openai langgraph requests python-dotenv
```

### 환경 설정

1. **backend/.env 파일 생성 또는 확인**
```bash
# LLM 설정
LLM_BASE_URL=https://api.your-llm-provider.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
LLM_TEMPERATURE=0.1

# GitHub 설정
GITHUB_TOKEN=github_pat_xxxxx

# NVD 설정 (선택, 10배 빠름)
NVD_API_KEY=your-nvd-api-key
```

### Jupyter에서 실행

```python
# Cell 1: 환경 설정
%load_ext autoreload
%autoreload 2

import os
import sys
from dotenv import load_dotenv

# ⚠️ 중요: backend/.env 경로 명시
load_dotenv("backend/.env")

sys.path.insert(0, os.path.abspath('.'))
from backend.agents.security.agent.security_agent_v2 import SecurityAgentV2

# Cell 2: 에이전트 생성
agent = SecurityAgentV2(
    llm_base_url=os.getenv("LLM_BASE_URL"),
    llm_api_key=os.getenv("LLM_API_KEY"),
    llm_model=os.getenv("LLM_MODEL"),
    llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
    execution_mode="intelligent"
)

# Cell 3: 분석 실행
result = await agent.analyze(
    user_request="facebook/react의 의존성 패키지를 조회해줘",
    github_token=os.getenv("GITHUB_TOKEN")
)

# Cell 4: 결과 확인
print(f"Dependencies: {result['results']['dependencies']['total']}")
print(f"Vulnerabilities: {result['results']['vulnerabilities']['total']}")
```

### Python 스크립트에서 실행

```python
import asyncio
import os
from dotenv import load_dotenv
from backend.agents.security.agent.security_agent_v2 import SecurityAgentV2

load_dotenv("backend/.env")

async def main():
    agent = SecurityAgentV2(
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_temperature=0.1,
        execution_mode="intelligent"
    )

    result = await agent.analyze(
        user_request="facebook/react의 보안 취약점을 찾아줘",
        github_token=os.getenv("GITHUB_TOKEN")
    )

    return result

if __name__ == "__main__":
    result = asyncio.run(main())
    print(result)
```

---

## 📖 자세한 예제

더 많은 예제는 [EXAMPLES.md](./EXAMPLES.md)를 참고하세요:
- 기본 사용법
- 취약점 스캔
- 빠른 실행 모드
- 고급 설정
- 문제 해결 (Troubleshooting)

---

## 🏗️ 아키텍처

```
User Request (자연어)
    ↓
SecurityAgentV2
    ├── IntentParser (의도 파싱)
    ├── DynamicPlanner (계획 수립)
    └── ReActExecutor (실행)
         ├── Think (사고)
         ├── Act (행동)
         │    └── ToolRegistry (도구 실행)
         │         ├── GitHub API
         │         ├── NVD API
         │         └── Dependency Parsers
         └── Observe (관찰)
    ↓
Final Result
```

### 주요 컴포넌트

| 컴포넌트 | 역할 | 파일 |
|---------|------|------|
| **SecurityAgentV2** | 메인 에이전트, LangGraph 워크플로우 관리 | `security_agent_v2.py` |
| **IntentParser** | 자연어 요청 파싱, 복잡도 평가 | `intent_parser.py` |
| **DynamicPlanner** | 실행 계획 동적 생성 | `planner_v2.py` |
| **ReActExecutor** | Think-Act-Observe 사이클 실행 | `react_executor_improved.py` |
| **ToolRegistry** | 도구 등록/관리 (37개 도구) | `tool_registry.py` |
| **NvdClient** | NVD API 연동, 취약점 조회 | `nvd_client.py` |
| **State** | 상태 관리 (TypedDict) | `state_v2.py` |

---

## 🛠️ 개선 사항 (V2)

### V1에서 개선된 점

| 항목 | V1 | V2 |
|------|----|----|
| 입력 방식 | 구조화된 파라미터 | 자연어 요청 |
| 계획 수립 | 정적 계획 | LLM 기반 동적 계획 |
| 실행 패턴 | 순차 실행 | ReAct 패턴 (Think-Act-Observe) |
| 도구 선택 | 수동 지정 | LLM이 자율 선택 |
| 실패 처리 | 즉시 종료 | 재시도 + 대안 도구 시도 |
| 취약점 조회 | Mock 구현 | 실제 NVD API 연동 |
| 메타인지 | 없음 | Reflection 단계 추가 |

### Fix 01에서 해결한 문제

1. **ReAct 조기 종료 문제**
   - 이전: 2회 시도 후 종료
   - 개선: 최소 5회 시도, 대안 도구 자동 선택

2. **취약점 스캔 Mock 구현**
   - 이전: 빈 결과 반환
   - 개선: 실제 NVD API 연동 (580줄 구현)

3. **캐시 파일 불일치**
   - 이전: `.pyc` 파일 오류
   - 개선: 캐시 관리 가이드 제공

---

## 📊 도구 목록 (37개)

### GitHub API (11개)
- `fetch_repository_info`: 레포지토리 정보 조회
- `fetch_directory_structure`: 디렉토리 구조 조회
- `fetch_file_content`: 파일 내용 조회
- `detect_lock_files`: Lock 파일 탐지
- `fetch_all_lock_files`: 모든 Lock 파일 조회
- `search_files_by_pattern`: 패턴으로 파일 검색
- 등...

### Dependency Parsing (13개)
- `parse_package_json`: package.json 파싱
- `parse_requirements_txt`: requirements.txt 파싱
- `parse_poetry_lock`: poetry.lock 파싱
- `parse_go_mod`: go.mod 파싱
- `parse_cargo_toml`: Cargo.toml 파싱
- 등...

### Vulnerability Scanning (6개)
- `search_cve_by_cpe`: CPE로 CVE 검색 (NVD)
- `fetch_cve_details`: CVE ID로 상세 정보 조회
- `scan_vulnerabilities_full`: 전체 의존성 취약점 스캔
- `check_security_advisories`: GitHub Security Advisory 조회
- 등...

### Analysis & Reporting (7개)
- `analyze_dependencies_full`: 전체 의존성 분석
- `generate_security_report`: 보안 리포트 생성
- `calculate_security_score`: 보안 점수 계산
- `prioritize_vulnerabilities`: 취약점 우선순위 지정
- 등...

---

## 🐛 알려진 문제 및 개선 계획

### 현재 제한 사항

1. **순차 처리 성능**
   - 100개 패키지 스캔 시 600초 소요 (API 키 없을 때)
   - **계획**: 병렬 처리 구현으로 10배 향상 (60초)

2. **CPE 매핑 정확도**
   - Vendor 정보 항상 "*" (와일드카드)
   - **계획**: CPE 매핑 데이터베이스 구축

3. **캐싱 시스템 부재**
   - 동일 패키지 반복 조회 시 API 낭비
   - **계획**: 메모리 캐시 또는 Redis 도입

### 향후 계획

**즉시 (1주):**
- 병렬 처리 구현 (asyncio.gather)
- CPE 매핑 DB 구축
- 메모리 캐시 구현

**단기 (1개월):**
- Go, Java/Maven, PHP 생태계 지원
- 지식 베이스 구축 (취약점 패턴)
- 테스트 커버리지 80%+

**중기 (3-6개월):**
- 웹 대시보드 (React + FastAPI)
- CI/CD 통합 (GitHub Actions, GitLab CI)
- 이메일/Slack 알림

**장기 (6-12개월):**
- AI 기반 취약점 예측
- 자동 패치 제안
- 엔터프라이즈 기능 (SSO, 멀티테넌시)

---

## 📚 문서

- [EXAMPLES.md](./EXAMPLES.md) - 실행 예제 및 문제 해결
- [docs/dev_agent_ver02_fix01.md](./docs/dev_agent_ver02_fix01.md) - 개발 가이드 및 상세 설명
- [docs/dev_agent_ver02_report_03.md](./docs/dev_agent_ver02_report_03.md) - 검증 및 평가 보고서

---

## 🤝 기여

버그 리포트, 기능 제안, 풀 리퀘스트를 환영합니다!

---

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

---

## 📞 문의

문제가 발생하거나 질문이 있으시면 이슈를 생성해주세요.

---

**Version:** 2.0 (Fix 01)
**Last Updated:** 2025-12-05
