# 목차

---

1. [**현재 아키텍처 이해**](#1-현재-아키텍처)
2. [**새 Agent 추가 방법**](#2-새-agent-추가-방법)
3. [**Frontend 연결 방법**](#3-frontend-연결-방법)
4. [**테스트 방법**](#4-테스트-방법)

---

## 1. 현재 아키텍처

### 1. 전체 흐름

```
Frontend (React)
     │
     │  POST /api/analyze, /api/chat/stream, /api/analyze/compare
     ▼
http_router.py (FastAPI)
     │
     │  run_agent_task() / compare_repositories()
     ▼
agent_service.py (통합 진입점)
     │
     │  run_supervisor_diagnosis()
     ▼
Supervisor Graph (LangGraph) - Agentic 오케스트레이터
     │
     ├── intent_analysis_node (의도 분석)
     ├── decision_node (다음 행동 결정)
     │      │
     │      ├── run_diagnosis_node (진단 실행)
     │      ├── use_cached_result_node (캐시 사용)
     │      ├── batch_diagnosis_node (비교 분석)
     │      └── chat_response_node (채팅 응답)
     │
     ├── quality_check_node (품질 검사)
     ├── fetch_issues_node (이슈 수집)
     ├── plan_onboarding_node (플랜 생성)
     ├── summarize_onboarding_plan_node (요약)
     └── compare_results_node (비교 결과 생성)
           │
           ▼
      Core Layer (순수 Python)
           │
           ▼
      GitHub API / LLM
```

### 2. Agentic 라우팅 흐름

```
[Entry Point]
      │
      ▼
intent_analysis_node
      │  - 사용자 메시지/task_type 분석
      │  - detected_intent 설정 (diagnose/onboard/explain/compare/chat)
      ▼
decision_node
      │  - 캐시 확인
      │  - 동적 플로우 조정 (flow_adjustments)
      │  - next_node_override 설정
      │
      ├─[diagnose]──► run_diagnosis_node ──► quality_check_node ──► END
      │                                            │
      │                                   (재실행 필요시)
      │                                            │
      │                                            ▼
      │                                   run_diagnosis_node
      │
      ├─[onboard]───► run_diagnosis_node ──► quality_check_node
      │                                            │
      │                                            ▼
      │                                   fetch_issues_node
      │                                            │
      │                                            ▼
      │                                   plan_onboarding_node
      │                                            │
      │                                            ▼
      │                                   summarize_onboarding_plan_node ──► END
      │
      ├─[compare]───► batch_diagnosis_node ──► compare_results_node ──► END
      │
      ├─[explain/chat]──► chat_response_node ──► END
      │
      └─[cache hit]─► use_cached_result_node ──► quality_check_node ──► ...
```

### 3. 주요 파일 위치

```
backend/
├── api/
│   ├── http_router.py      # API 엔드포인트 정의
│   ├── agent_service.py    # 통합 진입점
│   ├── chat_stream.py      # 채팅 SSE 스트리밍
│   └── schemas.py          # 요청/응답 스키마
│
├── agents/
│   └── supervisor/
│       ├── graph.py        # LangGraph 정의 (노드 등록)
│       ├── models.py       # SupervisorState 정의
│       ├── service.py      # 실행 함수
│       ├── memory.py       # 대화 컨텍스트 메모리 (Redis/In-Memory)
│       └── nodes/
│           ├── diagnosis_nodes.py   # 진단 노드
│           ├── onboarding_nodes.py  # 온보딩 노드들
│           ├── routing_nodes.py     # Agentic 라우팅 노드 (NEW)
│           ├── comparison_nodes.py  # 비교 분석 노드 (NEW)
│           └── chat_nodes.py        # 채팅 응답 노드 (NEW)
│
├── core/                   # 비즈니스 로직 (LLM 무의존)
│   ├── docs_core.py
│   ├── activity_core.py
│   ├── structure_core.py   # 구조 분석 (NEW)
│   ├── scoring_core.py     # 점수 계산
│   └── ...
│
├── common/
│   ├── cache.py            # 분석 결과 캐시
│   ├── metrics.py          # 성능 메트릭 추적 (NEW)
│   └── github_client.py    # GitHub API 클라이언트
│
└── llm/                    # LLM 래퍼
    ├── factory.py
    └── base.py
```

### 4. SupervisorState 주요 필드

```python
class SupervisorState(BaseModel):
    # 기본 입력
    task_type: TaskType
    owner: str
    repo: str
    user_context: Dict[str, Any] = {}

    # 진단 결과
    diagnosis_result: Optional[Dict[str, Any]] = None

    # 온보딩 관련
    candidate_issues: List[Dict[str, Any]] = []
    onboarding_plan: Optional[List[Dict[str, Any]]] = None
    onboarding_summary: Optional[str] = None

    # Agentic 판단 관련 (NEW)
    detected_intent: Optional[str] = None      # diagnose/onboard/explain/compare/chat
    intent_confidence: float = 0.0
    decision_reason: Optional[str] = None
    next_node_override: Optional[str] = None

    # 품질 검사 및 재실행 (NEW)
    rerun_count: int = 0
    max_rerun: int = 2
    quality_issues: List[str] = []

    # 캐시 제어 (NEW)
    use_cache: bool = True
    cache_hit: bool = False

    # 동적 플로우 조정 (NEW)
    flow_adjustments: List[str] = []
    warnings: List[str] = []

    # 비교 분석 (NEW)
    compare_repos: List[str] = []
    compare_results: Dict[str, Any] = {}
    compare_summary: Optional[str] = None

    # 채팅 (NEW)
    chat_message: Optional[str] = None
    chat_response: Optional[str] = None
    chat_context: Dict[str, Any] = {}
```

---

## 2. 새 Agent 추가 방법

### 0. 단계 요약

| **단계** | **작업** | **파일** |
| --- | --- | --- |
| 1 | State에 필드 추가 | `supervisor/models.py` |
| 2 | 노드 함수 작성 | `supervisor/nodes/새파일.py` |
| 3 | 그래프에 노드 등록 | `supervisor/graph.py` |
| 4 | 라우팅 로직 추가 | `supervisor/nodes/routing_nodes.py` |
| 5 | API 응답에 포함 | `api/http_router.py` |
| 6 | Frontend에서 호출/표시 | `frontend/src/lib/api.js` |

### 1. SupervisorState 필드 추가

```python
# backend/agents/supervisor/models.py

class SupervisorState(BaseModel):
    # 기존 필드들...
    
    # 새 Agent 결과 필드 추가
    security_result: Optional[Dict[str, Any]] = None
```

### 2. 노드 함수 작성 (예시)

```python
# backend/agents/supervisor/nodes/security_nodes.py

from backend.agents.supervisor.models import SupervisorState
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def run_security_scan_node(state: SupervisorState) -> Dict[str, Any]:
    """
    보안 스캔 노드.

    Args:
        state: 현재 Supervisor 상태

    Returns:
        상태 업데이트 딕셔너리 (LangGraph가 state에 merge)
    """
    try:
        from backend.core.security_core import scan_dependencies

        result = scan_dependencies(
            owner=state.owner,
            repo=state.repo
        )

        logger.info(f"Security scan completed for {state.owner}/{state.repo}")

        return {
            "security_result": result,
            "step": state.step + 1,
        }

    except Exception as e:
        logger.error(f"Security scan failed: {e}")
        return {
            "security_result": None,
            "error": f"Security scan failed: {str(e)}",
            "step": state.step + 1,
        }
```

### 3. 그래프에 노드 등록

```python
# backend/agents/supervisor/graph.py

from backend.agents.supervisor.nodes.security_nodes import run_security_scan_node

def build_supervisor_graph() -> StateGraph:
    graph = StateGraph(SupervisorState)

    # 기존 노드들
    graph.add_node("intent_analysis_node", intent_analysis_node)
    graph.add_node("decision_node", decision_node)
    graph.add_node("run_diagnosis_node", run_diagnosis_node)
    # ...

    # 새 노드 추가
    graph.add_node("run_security_scan_node", run_security_scan_node)

    # 엣지 연결 (예: 진단 후 보안 스캔)
    graph.add_edge("run_security_scan_node", END)

    return graph
```

### 4. 라우팅 로직 추가

```python
# backend/agents/supervisor/nodes/routing_nodes.py

# Intent 키워드 추가
INTENT_KEYWORDS = {
    # 기존...
    "security": ["보안", "취약점", "security", "vulnerability", "scan"],
}

def decision_node(state: SupervisorState) -> Dict[str, Any]:
    intent = state.detected_intent or "unknown"
    
    # 기존 로직...
    
    elif intent == "security":
        next_node = "run_security_scan_node"
        reason = f"Intent is security for {state.owner}/{state.repo}"
    
    # ...
```

### 5. API 응답에 포함

```python
# backend/api/http_router.py

@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest) -> AnalyzeResponse:
    # ... 기존 코드 ...

    data = result.get("data", {})

    response = AnalyzeResponse(
        job_id=f"{owner}/{repo}",
        score=data.get("health_score", 0),
        analysis={...},
        risks=_generate_risks_from_issues(...),

        # 새 필드 추가
        security=data.get("security_result"),
    )

    return response
```

### 6. Frontend 연결

```jsx
// frontend/src/lib/api.js

export const analyzeRepository = async (repoUrl) => {
  const response = await api.post("/api/analyze", { repo_url: repoUrl });
  return response.data;
  // response.data.security 로 접근 가능
};
```

```jsx
// frontend/src/pages/AnalyzePage.jsx

function AnalyzePage() {
  const [result, setResult] = useState(null);

  return (
    <div>
      {/* 기존 컴포넌트들 */}
      <HealthScoreCard score={result?.score} />

      {/* 새 컴포넌트 추가 */}
      {result?.security && <SecurityResultSection data={result.security} />}
    </div>
  );
}
```

---

## 3. Frontend 연결 방법

### 1. API 호출 패턴

```jsx
// frontend/src/lib/api.js

// 1. 기본 API 호출
export const analyzeRepository = async (repoUrl) => {
  const response = await api.post("/api/analyze", { repo_url: repoUrl });
  return response.data;
};

// 2. 비교 분석 API (NEW)
export const compareRepositories = async (repositories) => {
  const response = await api.post("/api/analyze/compare", { repositories });
  return response.data;
};

// 3. 스트리밍 API 호출 (SSE)
export const sendChatMessageStream = (message, context, history, onToken, onComplete, onError) => {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, context, conversation_history: history }),
  });
  // SSE 처리...
};
```

### 2. 응답 데이터 변환

```jsx
// frontend/src/pages/AnalyzePage.jsx

const transformAnalysisResult = (apiResponse) => {
  return {
    healthScore: apiResponse.score,
    analysis: {
      documentation: apiResponse.analysis.documentation_quality,
      activity: apiResponse.analysis.activity_maintainability,
      onboarding: apiResponse.analysis.onboarding_score,
    },
    // Agentic 메타데이터 (NEW)
    warnings: apiResponse.analysis.warnings || [],
    flowAdjustments: apiResponse.analysis.flow_adjustments || [],
  };
};
```

### 3. 새 컴포넌트 생성

```jsx
// frontend/src/components/analyze/SecuritySection.jsx

export function SecuritySection({ data }) {
  if (!data) return null;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">보안 분석</h3>

      <div className="space-y-4">
        <div className="flex justify-between">
          <span>위험 수준</span>
          <span className={`font-bold ${getRiskColor(data.riskLevel)}`}>
            {data.riskLevel}
          </span>
        </div>

        {data.vulnerabilities?.map((vuln, idx) => (
          <VulnerabilityCard key={idx} data={vuln} />
        ))}
      </div>
    </div>
  );
}
```

---

## 4. 테스트 방법

### 1. Backend 단위 테스트

```python
# tests/test_security_node.py

import pytest
from backend.agents.supervisor.nodes.security_nodes import run_security_scan_node
from backend.agents.supervisor.models import SupervisorState

def test_security_scan_node():
    state = SupervisorState(
        task_type="diagnose_repo",
        owner="facebook",
        repo="react",
        user_context={},
    )

    result = run_security_scan_node(state)

    assert "security_result" in result
    assert result["security_result"] is not None
```

### 2. Agentic 라우팅 테스트 (NEW)

```python
# tests/test_supervisor_agentic.py

import pytest
from backend.agents.supervisor.nodes.routing_nodes import (
    intent_analysis_node,
    decision_node,
    infer_intent_from_context,
)
from backend.agents.supervisor.models import SupervisorState

def test_intent_inference_diagnose():
    state = SupervisorState(
        task_type="diagnose_repo",
        owner="test",
        repo="repo",
    )
    intent, confidence = infer_intent_from_context(state)
    assert intent == "diagnose"
    assert confidence == 1.0

def test_intent_inference_from_chat_message():
    state = SupervisorState(
        task_type="diagnose_repo",
        owner="test",
        repo="repo",
        chat_message="이 프로젝트에 어떻게 기여할 수 있을까요?",
    )
    intent, confidence = infer_intent_from_context(state)
    assert intent == "onboard"
```

### 3. API 테스트

```powershell
# PowerShell - 분석 API
Invoke-RestMethod -Uri "http://localhost:8000/api/analyze" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"repo_url": "https://github.com/facebook/react"}'
```

```powershell
# PowerShell - 비교 분석 API (NEW)
Invoke-RestMethod -Uri "http://localhost:8000/api/analyze/compare" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"repositories": ["facebook/react", "vuejs/vue"]}'
```

```powershell
# curl
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/facebook/react"}'
```

### 4. Frontend 확인

```javascript
// 브라우저 콘솔에서
const response = await fetch("http://localhost:8000/api/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ repo_url: "https://github.com/facebook/react" }),
});
const data = await response.json();
console.log(data.analysis.warnings);        // Agentic 경고
console.log(data.analysis.flow_adjustments); // 플로우 조정 정보
```

---

## 5. 주요 변경 사항 (v2)

### Agentic 라우팅 시스템

| 이전 | 현재 |
|------|------|
| `router_start_node` | `intent_analysis_node` + `decision_node` |
| 단순 task_type 기반 라우팅 | 의도 분석 + 동적 결정 |
| 캐시 미사용 | 캐시 자동 확인 및 재사용 |
| 단일 결과 | 품질 검사 + 자동 재실행 |

### 새로운 기능

1. **의도 분석**: 사용자 메시지에서 의도 자동 추론
2. **캐시 활용**: 이미 분석된 결과 자동 재사용
3. **품질 검사**: 분석 결과 품질 평가 및 자동 재실행
4. **비교 분석**: 여러 저장소 동시 비교
5. **채팅 통합**: Supervisor를 통한 채팅 응답 생성
6. **동적 플로우 조정**: 사용자 경험 수준에 따른 응답 조정

---

## 참고 자료

- [LangGraph overview - Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/overview)
- [FastAPI](https://fastapi.tiangolo.com/)
