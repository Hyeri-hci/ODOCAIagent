# Security Agent v0.2 개발 계획서

**작성일**: 2025-12-04
**목표 버전**: v0.2 (Multi-Agent Architecture)
**작성자**: Security Analysis Agent Development Team

---

## 📋 목차

1. [현재 상태 분석](#1-현재-상태-분석)
2. [문제점 및 개선 필요 사항](#2-문제점-및-개선-필요-사항)
3. [Supervisor 통합 아키텍처](#3-supervisor-통합-아키텍처)
4. [Task-Based 실행 모드 설계](#4-task-based-실행-모드-설계)
5. [멀티 에이전트 아키텍처 설계](#5-멀티-에이전트-아키텍처-설계)
6. [중간 결과 전달 메커니즘](#6-중간-결과-전달-메커니즘)
7. [보안 기능 확장 계획](#7-보안-기능-확장-계획)
8. [구현 우선순위 및 로드맵](#8-구현-우선순위-및-로드맵)
9. [검증 및 테스트 계획](#9-검증-및-테스트-계획)
10. [상세 구현 가이드](#10-상세-구현-가이드)

---

## 1. 현재 상태 분석

### 1.1 현재 아키텍처

```
User Input (owner, repo)
    ↓
SecurityAnalysisAgent
    ↓
[Initialize → Plan → Validate → Execute → Observe → Report]
    ↓
Final Report (완료 후 전체 결과만 반환)
```

**특징**:
- ✅ 독립 실행형 에이전트
- ✅ ReAct 패턴 기반 자율 실행
- ✅ 21개 도구, 6개 노드
- ❌ 단일 작업 모드 (전체 분석만 가능)
- ❌ 중간 결과 전달 불가
- ❌ Supervisor와 통신 메커니즘 없음

### 1.2 현재 기능

| 기능 | 상태 | 설명 |
|-----|------|------|
| 의존성 분석 | ✅ 구현 | 30+ 언어 지원 |
| 보안 점수 계산 | ✅ 구현 | 알고리즘 기반 |
| 개선 제안 | ✅ 구현 | 규칙 기반 |
| 레포트 생성 | ✅ 구현 | Markdown 형식 |
| 취약점 스캔 | ❌ 미구현 | NVD API 필요 |
| 라이센스 체크 | ❌ 미구현 | - |
| 실시간 진행 상황 | ❌ 미구현 | - |
| 부분 작업 실행 | ❌ 미구현 | - |

---

## 2. 문제점 및 개선 필요 사항

### 2.1 Supervisor 통합 관련

#### 문제점 1: 단일 작업 모드
**현재**:
```python
agent = SecurityAnalysisAgent()
result = agent.analyze(owner, repo)
# → 항상 전체 분석 수행 (의존성 + 점수 + 제안 + 레포트)
```

**필요**:
```python
# Supervisor가 요청하는 다양한 작업
result = agent.execute_task(task_type="extract_dependencies", owner=..., repo=...)
result = agent.execute_task(task_type="scan_vulnerabilities", dependencies=[...])
result = agent.execute_task(task_type="check_specific_file", file_path="package.json")
```

#### 문제점 2: 중간 결과 전달 불가
**현재**: 모든 작업 완료 후 한 번에 결과 반환
**필요**: 작업 진행 중 의미있는 정보를 supervisor에게 실시간 전달

#### 문제점 3: 유연성 부족
**현재**: 하드코딩된 계획 (의존성 → 점수 → 제안 → 레포트)
**필요**: Supervisor의 요청에 따라 동적으로 작업 구성

### 2.2 멀티 에이전트 구조 필요성

**현재 구조의 한계**:
- 모든 기능이 하나의 에이전트에 집중
- 기능 추가 시 복잡도 증가
- 병렬 처리 불가
- 특화된 전문가 에이전트 부재

**멀티 에이전트의 이점**:
- 각 에이전트가 특정 도메인에 특화
- 병렬 실행으로 성능 향상
- 유지보수 용이
- 확장성 향상

### 2.3 기능 부족

현재 누락된 중요 기능:
1. 실제 취약점 스캔 (CVE 조회)
2. 라이센스 컴플라이언스 체크
3. 의존성 트리 분석 (간접 의존성)
4. 특정 파일만 분석
5. 실시간 진행 상황 보고
6. 증분 분석 (변경사항만)
7. 자동 수정 제안 (PR 생성)
8. 보안 정책 준수 검증

---

## 3. Supervisor 통합 아키텍처

### 3.1 새로운 아키텍처 개요

```
Supervisor Agent
    ↓ (task request)
Security Orchestrator (새로운 계층)
    ↓
┌───────────────────────────────────────┐
│  Security Sub-Agents (병렬 실행 가능)  │
├───────────────────────────────────────┤
│ • Dependency Analysis Agent           │
│ • Vulnerability Scanning Agent        │
│ • License Compliance Agent            │
│ • Code Security Agent                 │
│ • Report Generation Agent             │
└───────────────────────────────────────┘
    ↓ (streaming results)
Supervisor Agent
```

### 3.2 Security Orchestrator 설계

**역할**:
- Supervisor의 요청을 받아 적절한 sub-agent에게 위임
- Sub-agent들의 실행을 조율
- 중간 결과를 수집하고 supervisor에게 전달
- 에러 처리 및 재시도

**핵심 메서드**:

```python
class SecurityOrchestrator:
    """
    Security Agent의 최상위 조율자
    Supervisor와의 인터페이스 역할
    """

    def __init__(self):
        self.dependency_agent = DependencyAnalysisAgent()
        self.vulnerability_agent = VulnerabilityAgent()
        self.license_agent = LicenseAgent()
        self.code_agent = CodeSecurityAgent()
        self.report_agent = ReportAgent()

    async def execute_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Supervisor의 요청을 받아 작업 수행

        Args:
            task_type: 작업 유형 (예: "analyze_dependencies", "scan_vulnerabilities")
            params: 작업 파라미터
            callback: 중간 결과를 supervisor에게 전달하는 콜백

        Returns:
            작업 결과
        """
        pass

    async def full_security_audit(
        self,
        owner: str,
        repo: str,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        전체 보안 감사 수행 (기존 analyze와 동일하지만 더 포괄적)
        """
        pass

    async def analyze_specific_file(
        self,
        owner: str,
        repo: str,
        file_path: str,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        특정 파일만 분석
        """
        pass
```

### 3.3 Supervisor 통신 프로토콜

#### 3.3.1 요청 형식

```python
# Task Request from Supervisor
{
    "task_id": "sec_task_12345",
    "task_type": "analyze_dependencies",  # 또는 다른 task type
    "params": {
        "owner": "facebook",
        "repo": "react",
        "file_path": "package.json",  # 선택적
        "options": {
            "include_dev_deps": True,
            "check_vulnerabilities": True
        }
    },
    "callback_url": "http://supervisor/callback",  # 중간 결과 전달용
    "priority": "normal",  # "low", "normal", "high"
    "timeout": 300  # 초
}
```

#### 3.3.2 응답 형식

```python
# Task Response to Supervisor
{
    "task_id": "sec_task_12345",
    "status": "completed",  # "running", "completed", "failed"
    "progress": 100,  # 0-100
    "result": {
        "success": True,
        "data": {...},  # 작업별 결과 데이터
        "summary": "120 dependencies analyzed, 3 vulnerabilities found"
    },
    "metadata": {
        "started_at": "2025-12-04T10:00:00Z",
        "completed_at": "2025-12-04T10:05:23Z",
        "duration_seconds": 323
    }
}
```

#### 3.3.3 중간 진행 상황 (Streaming)

```python
# Progress Update (sent via callback)
{
    "task_id": "sec_task_12345",
    "status": "running",
    "progress": 45,
    "current_step": "Scanning for vulnerabilities",
    "intermediate_results": {
        "dependencies_found": 120,
        "files_processed": 15,
        "vulnerabilities_so_far": 2
    }
}
```

---

## 4. Task-Based 실행 모드 설계

### 4.1 지원할 Task Types

| Task Type | 설명 | 입력 | 출력 |
|-----------|------|------|------|
| `extract_dependencies` | 의존성만 추출 | owner, repo, file_path(옵션) | 의존성 리스트 |
| `scan_vulnerabilities` | 취약점 스캔 | dependencies 또는 owner/repo | CVE 리스트 |
| `check_license` | 라이센스 확인 | dependencies | 라이센스 위반 목록 |
| `analyze_single_file` | 단일 파일 분석 | owner, repo, file_path | 파일 분석 결과 |
| `calculate_score` | 보안 점수만 계산 | analysis_result | 점수 및 등급 |
| `generate_report` | 레포트만 생성 | 모든 분석 결과 | Markdown 레포트 |
| `full_audit` | 전체 보안 감사 | owner, repo | 전체 결과 |
| `diff_analysis` | 변경사항 분석 | owner, repo, base_commit, head_commit | 변경 영향도 |
| `suggest_fixes` | 수정 제안 | vulnerabilities | 수정 방법 리스트 |

### 4.2 Task Routing 구현

```python
class SecurityOrchestrator:

    TASK_HANDLERS = {
        "extract_dependencies": "handle_extract_dependencies",
        "scan_vulnerabilities": "handle_scan_vulnerabilities",
        "check_license": "handle_check_license",
        "analyze_single_file": "handle_analyze_single_file",
        "calculate_score": "handle_calculate_score",
        "generate_report": "handle_generate_report",
        "full_audit": "handle_full_audit",
        "diff_analysis": "handle_diff_analysis",
        "suggest_fixes": "handle_suggest_fixes"
    }

    async def execute_task(self, task_type: str, params: Dict, callback=None):
        """Task를 적절한 handler로 라우팅"""

        # 검증
        if task_type not in self.TASK_HANDLERS:
            return {
                "success": False,
                "error": f"Unknown task type: {task_type}",
                "supported_tasks": list(self.TASK_HANDLERS.keys())
            }

        # Handler 호출
        handler_name = self.TASK_HANDLERS[task_type]
        handler = getattr(self, handler_name)

        try:
            result = await handler(params, callback)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_type": task_type
            }

    async def handle_extract_dependencies(self, params: Dict, callback=None):
        """의존성 추출만 수행"""
        owner = params["owner"]
        repo = params["repo"]
        file_path = params.get("file_path")  # 선택적

        if callback:
            await callback({
                "status": "running",
                "progress": 10,
                "message": "Starting dependency extraction"
            })

        # Dependency Agent에 위임
        result = await self.dependency_agent.extract(
            owner=owner,
            repo=repo,
            file_path=file_path
        )

        if callback:
            await callback({
                "status": "completed",
                "progress": 100,
                "message": f"Found {result['total']} dependencies"
            })

        return result

    async def handle_scan_vulnerabilities(self, params: Dict, callback=None):
        """취약점 스캔만 수행"""
        # dependencies가 직접 제공되거나, owner/repo에서 추출
        if "dependencies" in params:
            dependencies = params["dependencies"]
        else:
            # 먼저 의존성 추출
            dep_result = await self.handle_extract_dependencies(params, callback)
            dependencies = dep_result["dependencies"]

        # Vulnerability Agent에 위임
        result = await self.vulnerability_agent.scan(
            dependencies=dependencies,
            callback=callback
        )

        return result

    async def handle_full_audit(self, params: Dict, callback=None):
        """전체 보안 감사 (모든 sub-agent 실행)"""
        results = {}

        # 1. 의존성 추출
        if callback:
            await callback({"status": "running", "step": "dependencies", "progress": 20})
        results["dependencies"] = await self.dependency_agent.analyze(
            owner=params["owner"],
            repo=params["repo"]
        )

        # 2. 취약점 스캔
        if callback:
            await callback({"status": "running", "step": "vulnerabilities", "progress": 40})
        results["vulnerabilities"] = await self.vulnerability_agent.scan(
            dependencies=results["dependencies"]["data"]
        )

        # 3. 라이센스 체크
        if callback:
            await callback({"status": "running", "step": "licenses", "progress": 60})
        results["licenses"] = await self.license_agent.check(
            dependencies=results["dependencies"]["data"]
        )

        # 4. 코드 보안 분석
        if callback:
            await callback({"status": "running", "step": "code_security", "progress": 80})
        results["code_security"] = await self.code_agent.analyze(
            owner=params["owner"],
            repo=params["repo"]
        )

        # 5. 레포트 생성
        if callback:
            await callback({"status": "running", "step": "report", "progress": 90})
        results["report"] = await self.report_agent.generate(results)

        if callback:
            await callback({"status": "completed", "progress": 100})

        return {
            "success": True,
            "results": results,
            "summary": self._generate_summary(results)
        }
```

### 4.3 Task 실행 흐름

```
Supervisor Request
    ↓
[Orchestrator] Task Type 확인
    ↓
┌──────────────────────────────────┐
│  Task Handler 선택               │
├──────────────────────────────────┤
│ extract_dependencies → Dep Agent │
│ scan_vulnerabilities → Vuln Agent│
│ check_license → License Agent    │
│ full_audit → All Agents (병렬)   │
└──────────────────────────────────┘
    ↓
[Sub-Agent] 작업 수행
    ↓ (중간 결과)
[Orchestrator] Callback 호출 → Supervisor
    ↓ (최종 결과)
[Orchestrator] 결과 반환 → Supervisor
```

---

## 5. 멀티 에이전트 아키텍처 설계

### 5.1 Sub-Agent 구조 개요

```
SecurityOrchestrator (Coordinator)
    ↓
┌─────────────────────────────────────────────────────────┐
│                   Sub-Agents (전문가)                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. DependencyAnalysisAgent                            │
│     - 의존성 파일 탐색 및 파싱                          │
│     - 의존성 트리 구축                                  │
│     - 의존성 통계 생성                                  │
│                                                         │
│  2. VulnerabilityAgent                                 │
│     - CVE 데이터베이스 조회                             │
│     - 취약점 심각도 평가                                │
│     - 패치 가능 여부 확인                               │
│                                                         │
│  3. LicenseAgent                                       │
│     - 라이센스 정보 수집                                │
│     - 라이센스 호환성 검사                              │
│     - 정책 위반 감지                                    │
│                                                         │
│  4. CodeSecurityAgent                                  │
│     - 하드코딩된 시크릿 탐지                            │
│     - 안전하지 않은 코드 패턴 검사                      │
│     - 보안 베스트 프랙티스 확인                         │
│                                                         │
│  5. ComplianceAgent                                    │
│     - 보안 정책 준수 확인                               │
│     - 규제 요구사항 검증 (GDPR, SOC2, etc.)            │
│     - 감사 로그 생성                                    │
│                                                         │
│  6. ReportAgent                                        │
│     - 다양한 형식의 레포트 생성                         │
│     - 데이터 시각화                                     │
│     - 경영진 요약 생성                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5.2 각 Sub-Agent 상세 설계

#### 5.2.1 DependencyAnalysisAgent

**책임**:
- 의존성 파일 탐색 (package.json, requirements.txt, etc.)
- 의존성 파싱 및 정규화
- 의존성 트리 구축 (직접 + 간접)
- 버전 충돌 감지
- Outdated 의존성 식별

**인터페이스**:
```python
class DependencyAnalysisAgent:
    """의존성 분석 전문 에이전트"""

    def __init__(self):
        self.graph = self._create_graph()
        self.parsers = self._load_parsers()  # 30+ 언어 파서

    async def extract(
        self,
        owner: str,
        repo: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        의존성 추출

        Returns:
            {
                "success": True,
                "total": 120,
                "dependencies": [
                    {
                        "name": "react",
                        "version": "^18.0.0",
                        "source": "npm",
                        "type": "runtime",
                        "file": "package.json"
                    },
                    ...
                ]
            }
        """
        pass

    async def build_tree(
        self,
        dependencies: List[Dict]
    ) -> Dict[str, Any]:
        """
        의존성 트리 구축 (직접 + 간접)

        Returns:
            {
                "success": True,
                "tree": {
                    "react": {
                        "version": "18.0.0",
                        "dependencies": {
                            "loose-envify": {...},
                            "scheduler": {...}
                        }
                    }
                },
                "total_direct": 50,
                "total_indirect": 200
            }
        """
        pass

    async def detect_conflicts(
        self,
        dependencies: List[Dict]
    ) -> List[Dict]:
        """버전 충돌 감지"""
        pass

    async def find_outdated(
        self,
        dependencies: List[Dict]
    ) -> List[Dict]:
        """오래된 의존성 찾기"""
        pass
```

**LangGraph 구조**:
```python
def create_dependency_graph():
    workflow = StateGraph(DependencyState)

    workflow.add_node("fetch_files", fetch_dependency_files_node)
    workflow.add_node("parse", parse_dependencies_node)
    workflow.add_node("normalize", normalize_dependencies_node)
    workflow.add_node("build_tree", build_tree_node)
    workflow.add_node("detect_issues", detect_issues_node)

    workflow.set_entry_point("fetch_files")
    workflow.add_edge("fetch_files", "parse")
    workflow.add_edge("parse", "normalize")
    workflow.add_edge("normalize", "build_tree")
    workflow.add_edge("build_tree", "detect_issues")
    workflow.add_edge("detect_issues", END)

    return workflow.compile()
```

#### 5.2.2 VulnerabilityAgent

**책임**:
- CVE 데이터베이스 조회 (NVD, OSV, GitHub Advisory)
- CPE 매핑
- 취약점 심각도 평가 (CVSS 점수)
- 패치 가능 버전 추천
- Exploit 가능성 분석

**인터페이스**:
```python
class VulnerabilityAgent:
    """취약점 스캔 전문 에이전트"""

    def __init__(self):
        self.graph = self._create_graph()
        self.nvd_client = NVDClient()
        self.osv_client = OSVClient()
        self.cpe_db = CPEDatabase()

    async def scan(
        self,
        dependencies: List[Dict],
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        취약점 스캔

        Returns:
            {
                "success": True,
                "total_vulnerabilities": 5,
                "vulnerabilities": [
                    {
                        "cve_id": "CVE-2023-1234",
                        "package": "lodash",
                        "version": "4.17.0",
                        "severity": "HIGH",
                        "cvss_score": 7.5,
                        "description": "...",
                        "patched_versions": [">=4.17.21"],
                        "exploit_available": True
                    },
                    ...
                ],
                "by_severity": {
                    "critical": 1,
                    "high": 2,
                    "medium": 2,
                    "low": 0
                }
            }
        """
        pass

    async def query_cve(
        self,
        package_name: str,
        version: str,
        source: str
    ) -> List[Dict]:
        """특정 패키지의 CVE 조회"""
        pass

    async def assess_exploitability(
        self,
        cve_id: str
    ) -> Dict[str, Any]:
        """Exploit 가능성 평가"""
        pass

    async def recommend_patches(
        self,
        vulnerabilities: List[Dict]
    ) -> List[Dict]:
        """패치 권장사항 생성"""
        pass
```

**LangGraph 구조**:
```python
def create_vulnerability_graph():
    workflow = StateGraph(VulnerabilityState)

    workflow.add_node("map_cpe", map_to_cpe_node)
    workflow.add_node("query_nvd", query_nvd_node)
    workflow.add_node("query_osv", query_osv_node)
    workflow.add_node("merge_results", merge_results_node)
    workflow.add_node("assess_severity", assess_severity_node)
    workflow.add_node("check_exploits", check_exploits_node)
    workflow.add_node("recommend_patches", recommend_patches_node)

    workflow.set_entry_point("map_cpe")

    # 병렬 조회
    workflow.add_edge("map_cpe", "query_nvd")
    workflow.add_edge("map_cpe", "query_osv")

    workflow.add_edge("query_nvd", "merge_results")
    workflow.add_edge("query_osv", "merge_results")
    workflow.add_edge("merge_results", "assess_severity")
    workflow.add_edge("assess_severity", "check_exploits")
    workflow.add_edge("check_exploits", "recommend_patches")
    workflow.add_edge("recommend_patches", END)

    return workflow.compile()
```

#### 5.2.3 LicenseAgent

**책임**:
- 라이센스 정보 수집 (PyPI, npm registry, etc.)
- 라이센스 호환성 검사
- 조직 정책 위반 감지
- 라이센스 리스크 평가

**인터페이스**:
```python
class LicenseAgent:
    """라이센스 컴플라이언스 전문 에이전트"""

    def __init__(self):
        self.graph = self._create_graph()
        self.license_db = LicenseDatabase()
        self.compatibility_rules = self._load_compatibility_rules()

    async def check(
        self,
        dependencies: List[Dict],
        allowed_licenses: Optional[List[str]] = None,
        policy: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        라이센스 체크

        Returns:
            {
                "success": True,
                "total_checked": 120,
                "violations": [
                    {
                        "package": "some-package",
                        "version": "1.0.0",
                        "license": "GPL-3.0",
                        "reason": "Copyleft license not allowed",
                        "risk_level": "high"
                    }
                ],
                "by_license": {
                    "MIT": 80,
                    "Apache-2.0": 30,
                    "GPL-3.0": 5,
                    "Unknown": 5
                },
                "compliance_score": 85
            }
        """
        pass

    async def fetch_license_info(
        self,
        package_name: str,
        version: str,
        source: str
    ) -> Dict[str, Any]:
        """패키지의 라이센스 정보 조회"""
        pass

    async def check_compatibility(
        self,
        licenses: List[str]
    ) -> Dict[str, Any]:
        """라이센스 간 호환성 확인"""
        pass
```

#### 5.2.4 CodeSecurityAgent

**책임**:
- 하드코딩된 시크릿 탐지 (API keys, passwords, tokens)
- 안전하지 않은 코드 패턴 검사
- 보안 베스트 프랙티스 확인
- SAST (Static Application Security Testing)

**인터페이스**:
```python
class CodeSecurityAgent:
    """코드 보안 분석 전문 에이전트"""

    def __init__(self):
        self.graph = self._create_graph()
        self.secret_patterns = self._load_secret_patterns()
        self.unsafe_patterns = self._load_unsafe_patterns()

    async def analyze(
        self,
        owner: str,
        repo: str,
        file_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        코드 보안 분석

        Returns:
            {
                "success": True,
                "secrets_found": 3,
                "secrets": [
                    {
                        "type": "AWS Access Key",
                        "file": "config.py",
                        "line": 42,
                        "severity": "critical"
                    }
                ],
                "unsafe_patterns": [
                    {
                        "pattern": "eval() usage",
                        "file": "utils.js",
                        "line": 123,
                        "severity": "high",
                        "recommendation": "Use safer alternatives"
                    }
                ],
                "security_score": 75
            }
        """
        pass

    async def scan_secrets(
        self,
        files: List[Dict]
    ) -> List[Dict]:
        """시크릿 스캔"""
        pass

    async def check_unsafe_patterns(
        self,
        files: List[Dict],
        language: str
    ) -> List[Dict]:
        """안전하지 않은 패턴 검사"""
        pass
```

#### 5.2.5 ComplianceAgent

**책임**:
- 보안 정책 준수 확인
- 규제 요구사항 검증 (GDPR, SOC2, PCI-DSS, etc.)
- 감사 로그 생성
- 컴플라이언스 레포트 생성

**인터페이스**:
```python
class ComplianceAgent:
    """컴플라이언스 검증 전문 에이전트"""

    def __init__(self):
        self.graph = self._create_graph()
        self.policies = self._load_policies()

    async def verify(
        self,
        analysis_results: Dict[str, Any],
        standards: List[str]  # ["SOC2", "GDPR", "PCI-DSS"]
    ) -> Dict[str, Any]:
        """
        컴플라이언스 검증

        Returns:
            {
                "success": True,
                "standards": {
                    "SOC2": {
                        "compliant": False,
                        "violations": [
                            {
                                "control": "CC6.1",
                                "description": "Encryption at rest not enforced",
                                "severity": "high"
                            }
                        ],
                        "compliance_percentage": 85
                    }
                }
            }
        """
        pass
```

#### 5.2.6 ReportAgent

**책임**:
- 다양한 형식의 레포트 생성 (Markdown, HTML, PDF, JSON)
- 데이터 시각화
- 경영진 요약 (Executive Summary)
- 트렌드 분석

**인터페이스**:
```python
class ReportAgent:
    """레포트 생성 전문 에이전트"""

    def __init__(self):
        self.graph = self._create_graph()
        self.templates = self._load_templates()

    async def generate(
        self,
        analysis_results: Dict[str, Any],
        format: str = "markdown",  # "markdown", "html", "pdf", "json"
        template: str = "standard"  # "standard", "executive", "detailed"
    ) -> Dict[str, Any]:
        """
        레포트 생성

        Returns:
            {
                "success": True,
                "report": "...",  # 레포트 내용
                "file_path": "/path/to/report.md",
                "format": "markdown"
            }
        """
        pass

    async def generate_executive_summary(
        self,
        analysis_results: Dict[str, Any]
    ) -> str:
        """경영진용 요약 생성"""
        pass

    async def create_visualizations(
        self,
        data: Dict[str, Any]
    ) -> List[str]:
        """데이터 시각화 (차트, 그래프)"""
        pass
```

### 5.3 Sub-Agent 간 통신

#### 5.3.1 메시지 전달

```python
# Agent 간 메시지 형식
{
    "from_agent": "dependency_agent",
    "to_agent": "vulnerability_agent",
    "message_type": "data_transfer",
    "data": {
        "dependencies": [...]
    },
    "metadata": {
        "timestamp": "2025-12-04T10:00:00Z",
        "correlation_id": "audit_12345"
    }
}
```

#### 5.3.2 병렬 실행

```python
async def parallel_analysis(self, owner: str, repo: str):
    """여러 agent를 병렬로 실행"""

    # 1단계: 의존성 추출 (필수 선행 작업)
    dep_result = await self.dependency_agent.extract(owner, repo)
    dependencies = dep_result["dependencies"]

    # 2단계: 병렬 분석 (의존성 정보를 기반으로)
    tasks = [
        self.vulnerability_agent.scan(dependencies),
        self.license_agent.check(dependencies),
        self.code_agent.analyze(owner, repo)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    vuln_result, license_result, code_result = results

    # 3단계: 레포트 생성
    report = await self.report_agent.generate({
        "dependencies": dep_result,
        "vulnerabilities": vuln_result,
        "licenses": license_result,
        "code_security": code_result
    })

    return report
```

### 5.4 멀티 에이전트 조율 전략

#### 5.4.1 의존성 그래프

```
┌──────────────────┐
│ Dependency Agent │
└────────┬─────────┘
         │ (의존성 리스트 생성)
         ↓
    ┌────────────────────────────────┐
    │                                │
    ↓                                ↓
┌──────────────┐            ┌──────────────┐
│ Vuln Agent   │            │License Agent │
└──────────────┘            └──────────────┘
    │                                │
    └────────────┬───────────────────┘
                 ↓
         ┌──────────────┐
         │Report Agent  │
         └──────────────┘
```

#### 5.4.2 실행 순서 정의

```python
class SecurityOrchestrator:

    # Agent 간 의존성 정의
    AGENT_DEPENDENCIES = {
        "dependency_agent": [],  # 의존성 없음 (먼저 실행)
        "vulnerability_agent": ["dependency_agent"],
        "license_agent": ["dependency_agent"],
        "code_agent": [],  # 독립 실행 가능
        "compliance_agent": ["vulnerability_agent", "license_agent", "code_agent"],
        "report_agent": ["*"]  # 모든 agent 완료 후
    }

    async def execute_in_order(self, agents: List[str]):
        """의존성에 따라 순서대로 실행"""
        executed = set()
        results = {}

        while len(executed) < len(agents):
            for agent in agents:
                if agent in executed:
                    continue

                # 의존성 확인
                deps = self.AGENT_DEPENDENCIES[agent]
                if all(dep in executed for dep in deps if dep != "*"):
                    # 실행
                    results[agent] = await self._execute_agent(agent, results)
                    executed.add(agent)

        return results
```

---

## 6. 중간 결과 전달 메커니즘

### 6.1 Callback 패턴

```python
class CallbackHandler:
    """Supervisor에게 중간 결과를 전달하는 핸들러"""

    def __init__(self, callback_url: Optional[str] = None):
        self.callback_url = callback_url
        self.callbacks: List[Callable] = []

    def register(self, callback: Callable):
        """콜백 함수 등록"""
        self.callbacks.append(callback)

    async def notify(self, event: Dict[str, Any]):
        """
        이벤트 발생 시 모든 콜백 호출

        Args:
            event: {
                "type": "progress" | "intermediate_result" | "error",
                "data": {...}
            }
        """
        # 로컬 콜백 호출
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"Callback error: {e}")

        # HTTP 콜백 (Supervisor)
        if self.callback_url:
            try:
                await self._send_http_callback(event)
            except Exception as e:
                print(f"HTTP callback error: {e}")

    async def _send_http_callback(self, event: Dict[str, Any]):
        """HTTP POST로 supervisor에게 전달"""
        async with aiohttp.ClientSession() as session:
            await session.post(
                self.callback_url,
                json=event,
                timeout=aiohttp.ClientTimeout(total=5)
            )
```

### 6.2 이벤트 타입

#### 6.2.1 Progress Events

```python
# 진행 상황 업데이트
{
    "type": "progress",
    "task_id": "sec_task_12345",
    "agent": "dependency_agent",
    "progress": 45,  # 0-100
    "current_step": "Parsing package.json",
    "message": "Processing 15/30 files"
}
```

#### 6.2.2 Intermediate Result Events

```python
# 중간 결과 (의미있는 정보 발견 시)
{
    "type": "intermediate_result",
    "task_id": "sec_task_12345",
    "agent": "vulnerability_agent",
    "finding": {
        "severity": "critical",
        "cve_id": "CVE-2023-1234",
        "package": "lodash",
        "description": "Remote code execution vulnerability"
    },
    "requires_immediate_action": True
}
```

#### 6.2.3 Error Events

```python
# 에러 발생 시
{
    "type": "error",
    "task_id": "sec_task_12345",
    "agent": "vulnerability_agent",
    "error": {
        "code": "API_RATE_LIMIT",
        "message": "NVD API rate limit exceeded",
        "recoverable": True,
        "retry_after": 60
    }
}
```

### 6.3 실시간 스트리밍

```python
async def stream_analysis(
    self,
    owner: str,
    repo: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    분석 결과를 스트리밍으로 반환

    Yields:
        이벤트 딕셔너리
    """
    yield {"type": "started", "message": "Security analysis started"}

    # 의존성 추출
    async for event in self.dependency_agent.extract_stream(owner, repo):
        yield event

    dependencies = event["result"]

    # 취약점 스캔
    async for event in self.vulnerability_agent.scan_stream(dependencies):
        yield event

        # Critical 발견 시 즉시 알림
        if event.get("severity") == "critical":
            yield {
                "type": "alert",
                "severity": "critical",
                "message": f"Critical vulnerability found: {event['cve_id']}"
            }

    yield {"type": "completed", "message": "Analysis completed"}
```

### 6.4 Supervisor 통합 예시

```python
# Supervisor에서 Security Agent 호출
class SupervisorAgent:

    async def request_security_analysis(self, owner: str, repo: str):
        """Security Agent에게 분석 요청"""

        security_orchestrator = SecurityOrchestrator()

        # 콜백 등록
        async def handle_security_event(event: Dict):
            event_type = event["type"]

            if event_type == "intermediate_result":
                # 중요한 발견사항을 즉시 처리
                finding = event["finding"]
                if finding["severity"] == "critical":
                    await self.handle_critical_finding(finding)

            elif event_type == "progress":
                # 진행 상황 업데이트
                await self.update_progress(event["progress"])

            elif event_type == "error":
                # 에러 처리
                await self.handle_error(event["error"])

        # 분석 실행
        result = await security_orchestrator.execute_task(
            task_type="full_audit",
            params={"owner": owner, "repo": repo},
            callback=handle_security_event
        )

        return result
```

---

## 7. 보안 기능 확장 계획

### 7.1 우선순위 1: 필수 기능

#### 7.1.1 실제 취약점 스캔 (CVE 조회)

**구현 계획**:

1. **CPE 데이터베이스 구축**
   ```sql
   -- SQLite 또는 PostgreSQL
   CREATE TABLE cpe_mapping (
       id INTEGER PRIMARY KEY,
       package_name VARCHAR(255),
       package_source VARCHAR(50),  -- 'npm', 'pypi', 'maven', etc.
       version_pattern VARCHAR(255),
       cpe_id VARCHAR(500),
       confidence FLOAT,
       last_updated TIMESTAMP
   );

   CREATE INDEX idx_package ON cpe_mapping(package_name, package_source);
   ```

2. **NVD API 통합**
   ```python
   class NVDClient:
       """NVD API 클라이언트"""

       BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

       def __init__(self, api_key: Optional[str] = None):
           self.api_key = api_key
           self.cache = SimpleCache(ttl=3600 * 24)  # 24시간 캐시
           self.rate_limiter = RateLimiter(max_calls=5, period=30)  # API 제한

       async def query_by_cpe(self, cpe_id: str) -> List[Dict]:
           """CPE ID로 CVE 조회"""

           # 캐시 확인
           cache_key = f"nvd:cpe:{cpe_id}"
           cached = await self.cache.get(cache_key)
           if cached:
               return cached

           # Rate limit
           await self.rate_limiter.acquire()

           # API 호출
           params = {"cpeName": cpe_id}
           if self.api_key:
               params["apiKey"] = self.api_key

           async with aiohttp.ClientSession() as session:
               async with session.get(self.BASE_URL, params=params) as resp:
                   data = await resp.json()

           cves = self._parse_response(data)

           # 캐시 저장
           await self.cache.set(cache_key, cves)

           return cves
   ```

3. **OSV (Open Source Vulnerabilities) 통합**
   ```python
   class OSVClient:
       """OSV API 클라이언트 (더 빠르고 포괄적)"""

       BASE_URL = "https://api.osv.dev/v1"

       async def query_batch(
           self,
           packages: List[Dict[str, str]]
       ) -> Dict[str, List[Dict]]:
           """
           여러 패키지를 한 번에 조회

           Args:
               packages: [
                   {"name": "lodash", "version": "4.17.0", "ecosystem": "npm"},
                   ...
               ]
           """
           payload = {
               "queries": [
                   {
                       "package": {"name": p["name"], "ecosystem": p["ecosystem"]},
                       "version": p["version"]
                   }
                   for p in packages
               ]
           }

           async with aiohttp.ClientSession() as session:
               async with session.post(
                   f"{self.BASE_URL}/querybatch",
                   json=payload
               ) as resp:
                   data = await resp.json()

           return self._parse_batch_response(data)
   ```

#### 7.1.2 의존성 트리 분석

**구현 계획**:

```python
class DependencyTreeAnalyzer:
    """의존성 트리 분석기"""

    async def build_full_tree(
        self,
        owner: str,
        repo: str,
        language: str
    ) -> Dict[str, Any]:
        """
        전체 의존성 트리 구축 (직접 + 간접)

        Returns:
            {
                "root_dependencies": 50,
                "total_dependencies": 250,
                "tree": {
                    "react": {
                        "version": "18.0.0",
                        "type": "direct",
                        "dependencies": {
                            "loose-envify": {
                                "version": "1.4.0",
                                "type": "indirect",
                                "dependencies": {...}
                            }
                        }
                    }
                },
                "conflicts": [
                    {
                        "package": "minimist",
                        "versions": ["0.0.8", "1.2.0"],
                        "required_by": ["mkdirp", "optimist"]
                    }
                ]
            }
        """

        # Language별 처리
        if language == "javascript":
            return await self._build_npm_tree(owner, repo)
        elif language == "python":
            return await self._build_python_tree(owner, repo)
        # ... 다른 언어들

    async def _build_npm_tree(self, owner: str, repo: str):
        """npm 의존성 트리 구축"""

        # package-lock.json 다운로드
        lock_file = await self._fetch_file(owner, repo, "package-lock.json")

        if lock_file:
            # package-lock.json에는 이미 전체 트리 정보 있음
            return self._parse_package_lock(lock_file)
        else:
            # package.json만 있으면 npm registry에서 재귀적으로 조회
            return await self._build_tree_from_registry(owner, repo)
```

#### 7.1.3 라이센스 컴플라이언스 체크

**구현 계획**:

```python
class LicenseChecker:
    """라이센스 체크"""

    # 라이센스 분류
    LICENSE_CATEGORIES = {
        "permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"],
        "copyleft_weak": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"],
        "copyleft_strong": ["GPL-2.0", "GPL-3.0", "AGPL-3.0"],
        "proprietary": ["Commercial", "Proprietary"],
        "public_domain": ["CC0-1.0", "Unlicense"]
    }

    # 호환성 규칙
    COMPATIBILITY_MATRIX = {
        ("MIT", "Apache-2.0"): True,
        ("MIT", "GPL-3.0"): True,  # MIT는 GPL과 호환
        ("Apache-2.0", "GPL-2.0"): False,  # Apache-2.0는 GPL-2.0과 비호환
        ("GPL-3.0", "MIT"): False,  # GPL은 MIT를 포함할 수 없음 (copyleft)
        # ... 더 많은 규칙
    }

    async def check_compliance(
        self,
        dependencies: List[Dict],
        policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        라이센스 컴플라이언스 체크

        Args:
            policy: {
                "allowed_licenses": ["MIT", "Apache-2.0"],
                "forbidden_licenses": ["GPL-3.0", "AGPL-3.0"],
                "allow_unknown": False,
                "copyleft_allowed": False
            }
        """

        violations = []

        for dep in dependencies:
            license_info = await self._fetch_license(dep)
            license_name = license_info.get("license")

            # 정책 검증
            if not license_name:
                if not policy.get("allow_unknown", False):
                    violations.append({
                        "package": dep["name"],
                        "reason": "Unknown license",
                        "severity": "medium"
                    })
            elif license_name in policy.get("forbidden_licenses", []):
                violations.append({
                    "package": dep["name"],
                    "license": license_name,
                    "reason": "Forbidden license",
                    "severity": "high"
                })
            elif not policy.get("copyleft_allowed", True):
                category = self._categorize_license(license_name)
                if "copyleft" in category:
                    violations.append({
                        "package": dep["name"],
                        "license": license_name,
                        "reason": "Copyleft license not allowed",
                        "severity": "high"
                    })

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "total_checked": len(dependencies)
        }
```

### 7.2 우선순위 2: 고급 기능

#### 7.2.1 코드 보안 분석 (SAST)

```python
class CodeSecurityScanner:
    """코드 정적 분석"""

    # 시크릿 패턴
    SECRET_PATTERNS = {
        "aws_access_key": r"AKIA[0-9A-Z]{16}",
        "aws_secret_key": r"[0-9a-zA-Z/+]{40}",
        "github_token": r"ghp_[0-9a-zA-Z]{36}",
        "slack_webhook": r"https://hooks\.slack\.com/services/[A-Z0-9/]+",
        "generic_api_key": r"api[_-]?key['\"]?\s*[:=]\s*['\"]([0-9a-zA-Z]{32,})['\"]"
    }

    # 안전하지 않은 패턴 (언어별)
    UNSAFE_PATTERNS = {
        "javascript": [
            {
                "pattern": r"eval\s*\(",
                "severity": "high",
                "description": "Use of eval() can lead to code injection"
            },
            {
                "pattern": r"innerHTML\s*=",
                "severity": "medium",
                "description": "innerHTML can lead to XSS vulnerabilities"
            }
        ],
        "python": [
            {
                "pattern": r"exec\s*\(",
                "severity": "high",
                "description": "Use of exec() can lead to code injection"
            },
            {
                "pattern": r"pickle\.loads?\s*\(",
                "severity": "high",
                "description": "Unpickling untrusted data can lead to RCE"
            }
        ]
    }

    async def scan_repository(
        self,
        owner: str,
        repo: str
    ) -> Dict[str, Any]:
        """레포지토리 전체 스캔"""

        results = {
            "secrets": [],
            "unsafe_patterns": [],
            "security_score": 100
        }

        # 파일 목록 가져오기
        files = await self._fetch_all_files(owner, repo)

        for file in files:
            # 바이너리 파일 스킵
            if self._is_binary(file["path"]):
                continue

            content = await self._fetch_file_content(owner, repo, file["path"])

            # 시크릿 스캔
            secrets = self._scan_secrets(content, file["path"])
            results["secrets"].extend(secrets)

            # 안전하지 않은 패턴 스캔
            language = self._detect_language(file["path"])
            if language in self.UNSAFE_PATTERNS:
                patterns = self._scan_unsafe_patterns(
                    content,
                    file["path"],
                    language
                )
                results["unsafe_patterns"].extend(patterns)

        # 점수 계산
        results["security_score"] -= len(results["secrets"]) * 10
        results["security_score"] -= len(results["unsafe_patterns"]) * 5
        results["security_score"] = max(0, results["security_score"])

        return results
```

#### 7.2.2 증분 분석 (Diff Analysis)

```python
class DiffAnalyzer:
    """변경사항 분석"""

    async def analyze_changes(
        self,
        owner: str,
        repo: str,
        base_commit: str,
        head_commit: str
    ) -> Dict[str, Any]:
        """
        두 커밋 간 변경사항의 보안 영향도 분석

        Returns:
            {
                "new_dependencies": [...],
                "removed_dependencies": [...],
                "updated_dependencies": [...],
                "new_vulnerabilities": [...],
                "fixed_vulnerabilities": [...],
                "security_impact": "high" | "medium" | "low",
                "recommendation": "Block merge" | "Review required" | "Safe to merge"
            }
        """

        # Base와 Head의 의존성 추출
        base_deps = await self._extract_dependencies(owner, repo, base_commit)
        head_deps = await self._extract_dependencies(owner, repo, head_commit)

        # Diff 계산
        diff = self._calculate_diff(base_deps, head_deps)

        # 새로운 의존성의 취약점 스캔
        new_vulns = []
        if diff["new_dependencies"]:
            vuln_result = await self.vulnerability_agent.scan(
                diff["new_dependencies"]
            )
            new_vulns = vuln_result["vulnerabilities"]

        # 영향도 평가
        impact = self._assess_impact(diff, new_vulns)

        return {
            "diff": diff,
            "new_vulnerabilities": new_vulns,
            "security_impact": impact,
            "recommendation": self._generate_recommendation(impact, new_vulns)
        }
```

#### 7.2.3 자동 수정 제안 및 PR 생성

```python
class AutoFixer:
    """자동 수정 제안"""

    async def suggest_fixes(
        self,
        vulnerabilities: List[Dict]
    ) -> List[Dict]:
        """
        취약점에 대한 수정 제안

        Returns:
            [
                {
                    "vulnerability": {...},
                    "fix_type": "update_version",
                    "fix_details": {
                        "current_version": "4.17.0",
                        "fixed_version": "4.17.21",
                        "breaking_changes": False
                    },
                    "confidence": 0.95
                }
            ]
        """
        pass

    async def create_fix_pr(
        self,
        owner: str,
        repo: str,
        fixes: List[Dict],
        github_token: str
    ) -> Dict[str, Any]:
        """
        수정 PR 자동 생성

        Process:
        1. Fork 또는 새 브랜치 생성
        2. 의존성 파일 수정 (package.json, requirements.txt, etc.)
        3. 커밋 생성
        4. PR 생성

        Returns:
            {
                "success": True,
                "pr_url": "https://github.com/owner/repo/pull/123",
                "pr_number": 123,
                "fixes_applied": 5
            }
        """
        pass
```

### 7.3 우선순위 3: 추가 기능

1. **Supply Chain Security**: 의존성의 의존성까지 분석
2. **Malware Detection**: 악성 패키지 탐지
3. **Container Security**: Dockerfile 분석
4. **Infrastructure as Code Security**: Terraform, CloudFormation 분석
5. **API Security**: OpenAPI/Swagger 스펙 분석
6. **Continuous Monitoring**: 주기적 스캔 및 알림

---

## 8. 구현 우선순위 및 로드맵

### 8.1 Phase 1: Supervisor 통합 (2주)

**목표**: Security Agent가 Supervisor의 요청을 받아 다양한 작업 수행

**작업 항목**:

1. **Week 1**: 아키텍처 리팩토링
   - [ ] SecurityOrchestrator 클래스 구현
   - [ ] Task-based execution 메커니즘 구현
   - [ ] Task routing 로직 구현
   - [ ] 기본 task types 구현 (extract_dependencies, calculate_score, generate_report)
   - [ ] 단위 테스트 작성

2. **Week 2**: Callback 및 통신
   - [ ] CallbackHandler 구현
   - [ ] 진행 상황 이벤트 구현
   - [ ] 중간 결과 전달 구현
   - [ ] Supervisor 통신 프로토콜 구현
   - [ ] 통합 테스트

**산출물**:
- `security_orchestrator.py`
- `task_handlers.py`
- `callback_handler.py`
- 통합 테스트 스위트

### 8.2 Phase 2: 멀티 에이전트 구조 (3주)

**목표**: 기능별 전문 에이전트로 분리

**작업 항목**:

1. **Week 1**: Core Agents
   - [ ] DependencyAnalysisAgent 분리 및 강화
   - [ ] VulnerabilityAgent 기본 구조 (CPE 매핑, mock 데이터)
   - [ ] Agent 간 통신 인터페이스 정의

2. **Week 2**: Additional Agents
   - [ ] LicenseAgent 구현
   - [ ] CodeSecurityAgent 기본 구현 (시크릿 스캔)
   - [ ] ReportAgent 강화 (다양한 형식 지원)

3. **Week 3**: 통합 및 조율
   - [ ] Orchestrator의 agent 조율 로직 구현
   - [ ] 병렬 실행 구현
   - [ ] 의존성 그래프 기반 실행 순서 결정
   - [ ] End-to-end 테스트

**산출물**:
- `agents/dependency_agent.py`
- `agents/vulnerability_agent.py`
- `agents/license_agent.py`
- `agents/code_security_agent.py`
- `agents/report_agent.py`

### 8.3 Phase 3: 취약점 스캔 기능 (2-3주)

**목표**: 실제 CVE 데이터베이스 통합

**작업 항목**:

1. **Week 1**: CPE 데이터베이스
   - [ ] CPE 데이터베이스 스키마 설계
   - [ ] CPE 매핑 데이터 수집 및 저장
   - [ ] Package → CPE 매핑 로직 구현

2. **Week 2**: NVD API 통합
   - [ ] NVDClient 구현
   - [ ] Rate limiting 및 캐싱 구현
   - [ ] CVE 데이터 파싱 및 정규화

3. **Week 3**: OSV 통합 및 최적화
   - [ ] OSVClient 구현 (더 빠른 대안)
   - [ ] Batch query 최적화
   - [ ] 결과 병합 및 중복 제거
   - [ ] 성능 테스트

**산출물**:
- `cpe_database.py`
- `nvd_client.py`
- `osv_client.py`
- CPE 매핑 데이터베이스 파일

### 8.4 Phase 4: 고급 기능 (3-4주)

**목표**: 라이센스, 코드 분석, 증분 분석

**작업 항목**:

1. **Week 1**: 라이센스 체크
   - [ ] 라이센스 정보 수집 로직
   - [ ] 라이센스 호환성 매트릭스
   - [ ] 정책 기반 검증

2. **Week 2**: 코드 보안 분석
   - [ ] 시크릿 패턴 정의 및 스캔
   - [ ] 안전하지 않은 패턴 검사
   - [ ] 언어별 분석 규칙

3. **Week 3**: 의존성 트리
   - [ ] 전체 트리 구축 로직
   - [ ] 버전 충돌 감지
   - [ ] 간접 의존성 분석

4. **Week 4**: 증분 분석
   - [ ] Diff 분석 로직
   - [ ] 영향도 평가
   - [ ] PR 통합

**산출물**:
- 각 기능별 모듈
- 통합 테스트

### 8.5 전체 타임라인

```
Month 1:
Week 1-2: Phase 1 (Supervisor 통합)
Week 3-4: Phase 2 시작 (Core Agents)

Month 2:
Week 1: Phase 2 계속 (Additional Agents)
Week 2-4: Phase 3 (취약점 스캔)

Month 3:
Week 1-4: Phase 4 (고급 기능)

Total: 약 10-12주 (2.5-3개월)
```

---

## 9. 검증 및 테스트 계획

### 9.1 단위 테스트

**각 Agent별 테스트**:

```python
# tests/agents/test_dependency_agent.py
import pytest
from agents.dependency_agent import DependencyAnalysisAgent

@pytest.mark.asyncio
async def test_extract_dependencies():
    agent = DependencyAnalysisAgent()

    result = await agent.extract(
        owner="octocat",
        repo="Hello-World"
    )

    assert result["success"] == True
    assert "dependencies" in result
    assert isinstance(result["dependencies"], list)

@pytest.mark.asyncio
async def test_build_tree():
    agent = DependencyAnalysisAgent()

    dependencies = [
        {"name": "react", "version": "18.0.0", "source": "npm"}
    ]

    result = await agent.build_tree(dependencies)

    assert "tree" in result
    assert "total_direct" in result
    assert "total_indirect" in result
```

### 9.2 통합 테스트

**Orchestrator 테스트**:

```python
# tests/test_orchestrator.py
import pytest
from security_orchestrator import SecurityOrchestrator

@pytest.mark.asyncio
async def test_execute_task_extract_dependencies():
    orchestrator = SecurityOrchestrator()

    result = await orchestrator.execute_task(
        task_type="extract_dependencies",
        params={"owner": "facebook", "repo": "react"}
    )

    assert result["success"] == True
    assert result["total"] > 0

@pytest.mark.asyncio
async def test_full_audit():
    orchestrator = SecurityOrchestrator()

    events = []

    async def callback(event):
        events.append(event)

    result = await orchestrator.execute_task(
        task_type="full_audit",
        params={"owner": "facebook", "repo": "react"},
        callback=callback
    )

    assert result["success"] == True
    assert len(events) > 0  # 중간 이벤트 발생 확인
    assert any(e["type"] == "progress" for e in events)
```

### 9.3 성능 테스트

**부하 테스트**:

```python
# tests/performance/test_load.py
import asyncio
import pytest
import time

@pytest.mark.asyncio
async def test_parallel_analysis():
    """여러 레포지토리 병렬 분석"""

    orchestrator = SecurityOrchestrator()

    repos = [
        ("facebook", "react"),
        ("microsoft", "typescript"),
        ("google", "angular")
    ]

    start = time.time()

    tasks = [
        orchestrator.execute_task(
            task_type="extract_dependencies",
            params={"owner": owner, "repo": repo}
        )
        for owner, repo in repos
    ]

    results = await asyncio.gather(*tasks)

    duration = time.time() - start

    assert all(r["success"] for r in results)
    assert duration < 60  # 1분 이내 완료
```

### 9.4 E2E 테스트

**실제 시나리오**:

```python
# tests/e2e/test_supervisor_integration.py
@pytest.mark.asyncio
async def test_supervisor_requests_analysis():
    """Supervisor가 분석을 요청하는 시나리오"""

    # 1. Supervisor가 security agent에게 요청
    orchestrator = SecurityOrchestrator()

    # 2. 전체 감사 실행
    result = await orchestrator.execute_task(
        task_type="full_audit",
        params={"owner": "test-org", "repo": "test-repo"}
    )

    # 3. 결과 검증
    assert result["success"] == True
    assert "dependencies" in result["results"]
    assert "vulnerabilities" in result["results"]
    assert "licenses" in result["results"]
    assert "report" in result["results"]

    # 4. Critical 취약점이 있으면 supervisor에게 알림 확인
    vulns = result["results"]["vulnerabilities"]
    critical_vulns = [v for v in vulns["vulnerabilities"] if v["severity"] == "critical"]

    if critical_vulns:
        # Supervisor가 알림을 받았는지 확인 (mock으로 검증)
        pass
```

### 9.5 보안 테스트

**취약점 검증**:

```python
# tests/security/test_vulnerability_detection.py
@pytest.mark.asyncio
async def test_known_vulnerable_package():
    """알려진 취약점이 있는 패키지 탐지"""

    vuln_agent = VulnerabilityAgent()

    # lodash 4.17.0은 알려진 취약점이 있음
    dependencies = [
        {"name": "lodash", "version": "4.17.0", "source": "npm"}
    ]

    result = await vuln_agent.scan(dependencies)

    assert result["success"] == True
    assert result["total_vulnerabilities"] > 0

    # 특정 CVE가 발견되었는지 확인
    cve_ids = [v["cve_id"] for v in result["vulnerabilities"]]
    assert any("CVE-20" in cve for cve in cve_ids)
```

---

## 10. 상세 구현 가이드

### 10.1 SecurityOrchestrator 구현

**파일**: `backend/agents/security/security_orchestrator.py`

```python
"""
Security Agent Orchestrator
Supervisor와의 인터페이스 역할 및 sub-agent 조율
"""
import asyncio
from typing import Dict, Any, Optional, Callable, List
from .agents.dependency_agent import DependencyAnalysisAgent
from .agents.vulnerability_agent import VulnerabilityAgent
from .agents.license_agent import LicenseAgent
from .agents.code_security_agent import CodeSecurityAgent
from .agents.report_agent import ReportAgent
from .callback_handler import CallbackHandler


class SecurityOrchestrator:
    """
    Security Agent의 최상위 조율자

    역할:
    - Supervisor의 요청을 받아 적절한 작업 수행
    - Sub-agent들을 조율하여 병렬 또는 순차 실행
    - 중간 결과를 supervisor에게 전달
    - 에러 처리 및 재시도
    """

    # 지원하는 task types
    SUPPORTED_TASKS = [
        "extract_dependencies",
        "scan_vulnerabilities",
        "check_license",
        "analyze_single_file",
        "calculate_score",
        "generate_report",
        "full_audit",
        "diff_analysis",
        "suggest_fixes"
    ]

    def __init__(self):
        """초기화"""
        # Sub-agents 생성
        self.dependency_agent = DependencyAnalysisAgent()
        self.vulnerability_agent = VulnerabilityAgent()
        self.license_agent = LicenseAgent()
        self.code_agent = CodeSecurityAgent()
        self.report_agent = ReportAgent()

        # Callback handler
        self.callback_handler = CallbackHandler()

    async def execute_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        callback: Optional[Callable] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        작업 실행

        Args:
            task_type: 작업 유형
            params: 작업 파라미터
            callback: 중간 결과 전달 콜백
            task_id: 작업 ID (추적용)

        Returns:
            작업 결과
        """

        # 검증
        if task_type not in self.SUPPORTED_TASKS:
            return {
                "success": False,
                "error": f"Unsupported task type: {task_type}",
                "supported_tasks": self.SUPPORTED_TASKS
            }

        # Callback 등록
        if callback:
            self.callback_handler.register(callback)

        # 시작 알림
        await self.callback_handler.notify({
            "type": "started",
            "task_id": task_id,
            "task_type": task_type,
            "message": f"Starting {task_type}"
        })

        try:
            # Handler 메서드 이름 생성
            handler_name = f"handle_{task_type}"

            if not hasattr(self, handler_name):
                raise NotImplementedError(f"Handler for {task_type} not implemented")

            # Handler 실행
            handler = getattr(self, handler_name)
            result = await handler(params, task_id)

            # 완료 알림
            await self.callback_handler.notify({
                "type": "completed",
                "task_id": task_id,
                "task_type": task_type,
                "result": result
            })

            return result

        except Exception as e:
            # 에러 알림
            await self.callback_handler.notify({
                "type": "error",
                "task_id": task_id,
                "task_type": task_type,
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            })

            return {
                "success": False,
                "error": str(e),
                "task_type": task_type
            }

    # ===== Task Handlers =====

    async def handle_extract_dependencies(
        self,
        params: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """의존성 추출"""

        owner = params["owner"]
        repo = params["repo"]
        file_path = params.get("file_path")

        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 10,
            "message": "Extracting dependencies"
        })

        result = await self.dependency_agent.extract(
            owner=owner,
            repo=repo,
            file_path=file_path
        )

        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 100,
            "message": f"Found {result.get('total', 0)} dependencies"
        })

        return result

    async def handle_scan_vulnerabilities(
        self,
        params: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """취약점 스캔"""

        # Dependencies가 제공되지 않으면 먼저 추출
        if "dependencies" not in params:
            await self.callback_handler.notify({
                "type": "progress",
                "task_id": task_id,
                "progress": 10,
                "message": "Extracting dependencies first"
            })

            dep_result = await self.handle_extract_dependencies(params, task_id)
            dependencies = dep_result.get("dependencies", [])
        else:
            dependencies = params["dependencies"]

        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 50,
            "message": f"Scanning {len(dependencies)} dependencies for vulnerabilities"
        })

        result = await self.vulnerability_agent.scan(
            dependencies=dependencies,
            callback=lambda event: self.callback_handler.notify({
                **event,
                "task_id": task_id
            })
        )

        return result

    async def handle_full_audit(
        self,
        params: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """전체 보안 감사 (모든 agent 실행)"""

        owner = params["owner"]
        repo = params["repo"]

        results = {}

        # 1. 의존성 추출 (필수 선행)
        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 10,
            "step": "dependencies",
            "message": "Analyzing dependencies"
        })

        results["dependencies"] = await self.dependency_agent.extract(owner, repo)
        dependencies = results["dependencies"].get("dependencies", [])

        # 2-4. 병렬 분석
        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 30,
            "message": "Running parallel security scans"
        })

        parallel_tasks = [
            self.vulnerability_agent.scan(dependencies),
            self.license_agent.check(dependencies),
            self.code_agent.analyze(owner, repo)
        ]

        vuln_result, license_result, code_result = await asyncio.gather(
            *parallel_tasks,
            return_exceptions=True
        )

        results["vulnerabilities"] = vuln_result if not isinstance(vuln_result, Exception) else {"error": str(vuln_result)}
        results["licenses"] = license_result if not isinstance(license_result, Exception) else {"error": str(license_result)}
        results["code_security"] = code_result if not isinstance(code_result, Exception) else {"error": str(code_result)}

        # Critical 취약점 발견 시 즉시 알림
        if "vulnerabilities" in results and results["vulnerabilities"].get("success"):
            critical_vulns = [
                v for v in results["vulnerabilities"].get("vulnerabilities", [])
                if v.get("severity") == "critical"
            ]

            if critical_vulns:
                await self.callback_handler.notify({
                    "type": "alert",
                    "task_id": task_id,
                    "severity": "critical",
                    "message": f"{len(critical_vulns)} critical vulnerabilities found",
                    "vulnerabilities": critical_vulns
                })

        # 5. 레포트 생성
        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 90,
            "message": "Generating report"
        })

        results["report"] = await self.report_agent.generate(results)

        # 완료
        await self.callback_handler.notify({
            "type": "progress",
            "task_id": task_id,
            "progress": 100,
            "message": "Security audit completed"
        })

        return {
            "success": True,
            "results": results,
            "summary": self._generate_summary(results)
        }

    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """결과 요약 생성"""

        dep_count = results.get("dependencies", {}).get("total", 0)
        vuln_count = results.get("vulnerabilities", {}).get("total_vulnerabilities", 0)
        license_violations = len(results.get("licenses", {}).get("violations", []))

        summary = f"Analyzed {dep_count} dependencies. "
        summary += f"Found {vuln_count} vulnerabilities"

        if license_violations > 0:
            summary += f" and {license_violations} license violations"

        return summary
```

### 10.2 Callback Handler 구현

**파일**: `backend/agents/security/callback_handler.py`

```python
"""
Callback Handler
중간 결과를 supervisor에게 전달
"""
import asyncio
import aiohttp
from typing import Dict, Any, Optional, Callable, List


class CallbackHandler:
    """
    중간 결과 전달 핸들러

    지원하는 전달 방법:
    - 로컬 콜백 함수 (동기/비동기)
    - HTTP POST (Supervisor endpoint)
    - WebSocket (실시간 스트리밍)
    """

    def __init__(
        self,
        callback_url: Optional[str] = None,
        websocket_url: Optional[str] = None
    ):
        self.callback_url = callback_url
        self.websocket_url = websocket_url
        self.callbacks: List[Callable] = []
        self.websocket = None

    def register(self, callback: Callable):
        """콜백 함수 등록"""
        self.callbacks.append(callback)

    async def notify(self, event: Dict[str, Any]):
        """
        이벤트 발생 시 모든 콜백 호출

        Args:
            event: {
                "type": "progress" | "intermediate_result" | "error" | "alert",
                "task_id": "...",
                "data": {...}
            }
        """

        # 로컬 콜백 호출
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"[CallbackHandler] Local callback error: {e}")

        # HTTP 콜백
        if self.callback_url:
            asyncio.create_task(self._send_http_callback(event))

        # WebSocket
        if self.websocket:
            asyncio.create_task(self._send_websocket_message(event))

    async def _send_http_callback(self, event: Dict[str, Any]):
        """HTTP POST로 supervisor에게 전달"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.callback_url,
                    json=event,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        print(f"[CallbackHandler] HTTP callback failed: {response.status}")
        except Exception as e:
            print(f"[CallbackHandler] HTTP callback error: {e}")

    async def _send_websocket_message(self, event: Dict[str, Any]):
        """WebSocket으로 실시간 전달"""
        try:
            if self.websocket:
                await self.websocket.send_json(event)
        except Exception as e:
            print(f"[CallbackHandler] WebSocket error: {e}")
```

---

## 11. 검증 체크리스트

### 11.1 Phase 1 완료 기준

- [ ] SecurityOrchestrator가 최소 3가지 task type 지원
- [ ] Callback이 정상적으로 작동
- [ ] Supervisor와 통신 프로토콜 검증
- [ ] 단위 테스트 커버리지 80% 이상
- [ ] 통합 테스트 통과

### 11.2 Phase 2 완료 기준

- [ ] 최소 5개 sub-agent 구현
- [ ] Agent 간 통신 정상 작동
- [ ] 병렬 실행 성능 향상 확인
- [ ] 의존성 그래프 기반 실행 검증

### 11.3 Phase 3 완료 기준

- [ ] NVD API 통합 완료
- [ ] OSV API 통합 완료
- [ ] CPE 매핑 정확도 70% 이상
- [ ] 실제 CVE 탐지 성공
- [ ] 캐싱으로 성능 최적화 확인

### 11.4 Phase 4 완료 기준

- [ ] 라이센스 체크 정확도 90% 이상
- [ ] 코드 시크릿 탐지 False positive < 10%
- [ ] 의존성 트리 완전성 95% 이상
- [ ] 증분 분석 정상 작동

---

## 12. 향후 확장 방향

### 12.1 단기 (3-6개월)

1. **ML/AI 통합**
   - 취약점 위험도 예측 모델
   - 자동 수정 코드 생성 (GPT 활용)
   - 이상 패키지 탐지 (Malware)

2. **Container & Cloud Security**
   - Dockerfile 분석
   - Kubernetes 매니페스트 검사
   - IaC (Terraform, CloudFormation) 분석

3. **개발자 경험 향상**
   - IDE 플러그인 (VSCode, IntelliJ)
   - Pre-commit hook
   - CI/CD 통합 (GitHub Actions, GitLab CI)

### 12.2 중기 (6-12개월)

1. **Continuous Monitoring**
   - 주기적 자동 스캔
   - 새로운 CVE 발표 시 자동 재스캔
   - 실시간 알림 (Slack, Email, PagerDuty)

2. **Policy as Code**
   - 보안 정책 코드화
   - 조직별 커스텀 규칙
   - 정책 버전 관리

3. **Supply Chain Security**
   - 패키지 신뢰도 평가
   - Maintainer 신뢰도
   - 의존성 업데이트 이력 분석

### 12.3 장기 (12개월+)

1. **자동 복구 시스템**
   - 취약점 발견 → 자동 패치 → PR → 테스트 → 머지
   - 완전 자동화 파이프라인

2. **보안 인사이트 플랫폼**
   - 조직 전체 보안 대시보드
   - 트렌드 분석
   - 벤치마킹

3. **규제 컴플라이언스 자동화**
   - SOC2, ISO27001, GDPR 자동 검증
   - 감사 리포트 자동 생성

---

## 13. 결론

이 계획서는 Security Agent를 단순한 분석 도구에서 **Supervisor와 통합된 멀티 에이전트 시스템**으로 발전시키는 로드맵을 제시합니다.

**핵심 개선 사항**:
1. ✅ Task-based 실행으로 유연성 확보
2. ✅ 멀티 에이전트 구조로 확장성 향상
3. ✅ 중간 결과 전달로 실시간 인터랙션
4. ✅ 실제 취약점 스캔 기능 구현
5. ✅ 다양한 보안 기능 추가

**예상 효과**:
- Supervisor가 필요한 작업만 요청 가능 (효율성 ↑)
- 병렬 실행으로 성능 향상
- 실제 CVE 탐지로 실용성 확보
- 확장 가능한 아키텍처로 장기적 발전 가능

**다음 단계**: Phase 1부터 순차적으로 구현 시작!

---

**작성일**: 2025-12-04
**버전**: 1.0
**작성자**: Security Analysis Agent Development Team
