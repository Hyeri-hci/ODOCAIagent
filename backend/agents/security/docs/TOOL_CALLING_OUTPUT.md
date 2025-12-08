# Tool Calling 출력 개선 사항

## 개선 내용

Security Agent V2의 도구 호출 시 상세한 정보가 출력되도록 개선되었습니다.

### 1. THINK 단계 출력

**위치:** `react_executor.py` - `_think()` 메서드

**개선 전:**
```
[ReAct] THINK phase...
[ReAct] Thought: I need to...
[ReAct] Next Action: detect_lock_files
```

**개선 후:**
```
[ReAct] THINK phase...
[ReAct]   Thought: I need to first detect lock files to determine which parsers to use...
[ReAct]   Reasoning: This will help us identify the package managers used in the repository...
[ReAct]   → Selected Tool: 'detect_lock_files'
```

**추가된 정보:**
- ✅ Thought (사고 과정) - 150자까지
- ✅ Reasoning (이유) - 150자까지
- ✅ Selected Tool (선택된 도구) - 강조 표시

---

### 2. ACT 단계 출력

**위치:** `react_executor.py` - `_act()` 메서드

**개선 전:**
```
[ReAct] ACT phase: detect_lock_files
[ReAct] Action completed: detect_lock_files
```

**개선 후:**
```
[ReAct] ACT phase: Calling tool 'detect_lock_files'
[ReAct]   Parameters: {"owner": "facebook", "repo": "react"}
[ReAct]   ✓ Result: {"lock_files": ["package.json", "package-lock.json"], "count": 2}
```

또는 파라미터가 없는 경우:
```
[ReAct] ACT phase: Calling tool 'detect_lock_files'
[ReAct]   Parameters: (using state only)
[ReAct]   ✓ Completed successfully
```

에러 발생 시:
```
[ReAct] ACT phase: Calling tool 'invalid_tool'
[ReAct]   Parameters: {...}
[ReAct]   ✗ Error: Tool 'invalid_tool' not found
```

**추가된 정보:**
- ✅ 호출 중인 도구 이름
- ✅ 파라미터 (state 제외, 200자까지)
- ✅ 결과 요약 (성공/실패, 주요 데이터)
- ✅ 성공: ✓, 실패: ✗ 아이콘

**결과에서 표시되는 주요 필드:**
- `success`, `count`, `total`, `total_count`
- `lock_files`, `vulnerabilities`
- 기타 중요 필드

---

### 3. OBSERVE 단계 출력

**위치:** `react_executor.py` - `_observe()` 메서드

**개선 전:**
```
[ReAct] OBSERVE phase...
[ReAct] Observation: Found package.json...
```

**개선 후:**
```
[ReAct] OBSERVE phase...
[ReAct]   Observation: Successfully detected 2 lock files (package.json, package-lock.json). Ready to parse dependencies...
[ReAct]   Learned: The repository uses npm as the package manager...
```

Fallback 시:
```
[ReAct] OBSERVE phase...
[ReAct] Observe phase error: LLM timeout
[ReAct]   Observation (fallback): Executed detect_lock_files: Success
```

**추가된 정보:**
- ✅ Observation (관찰 내용) - 150자까지
- ✅ Learned (학습 내용) - 100자까지
- ✅ Fallback 시 명시적 표시

---

### 4. Fallback Think 출력

**위치:** `react_executor.py` - `_fallback_think()` 메서드

**개선 전:**
(출력 없음)

**개선 후:**
```
[ReAct] Think phase error: LLM connection failed
[ReAct]   Using fallback thinking (rule-based)...
[ReAct]   → Following plan: Step 2 - parse_package_json
```

계획이 없는 경우:
```
[ReAct]   Using fallback thinking (rule-based)...
[ReAct]   → No plan available, cannot proceed
```

모든 단계 완료:
```
[ReAct]   Using fallback thinking (rule-based)...
[ReAct]   → All planned steps completed
```

**추가된 정보:**
- ✅ Fallback 모드 진입 명시
- ✅ 선택된 단계 정보
- ✅ 완료/중단 이유

---

## 전체 실행 출력 예시

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
[ReAct]   Thought: I need to first fetch repository information to understand the project structure and identify the main language...
[ReAct]   Reasoning: This will help me determine which dependency files to look for and which vulnerability databases to query...
[ReAct]   → Selected Tool: 'fetch_repository_info'

[ReAct] ACT phase: Calling tool 'fetch_repository_info'
[ReAct]   Parameters: {"owner": "facebook", "repo": "react"}
[ReAct]   ✓ Result: {"name": "react", "language": "JavaScript", "stars": 220000}

[ReAct] OBSERVE phase...
[ReAct]   Observation: Successfully fetched repository info. This is a JavaScript project with 220k stars. I should look for package.json and package-lock.json...
[ReAct]   Learned: The repository uses JavaScript/Node.js ecosystem...

==================================================
[Node: Execute ReAct] Iteration 2
==================================================
[ReAct] Cycle 2
[ReAct] THINK phase...
[ReAct]   Thought: Now I should detect lock files to identify all dependencies...
[ReAct]   Reasoning: Lock files contain the exact versions of all dependencies, which is crucial for vulnerability scanning...
[ReAct]   → Selected Tool: 'detect_lock_files'

[ReAct] ACT phase: Calling tool 'detect_lock_files'
[ReAct]   Parameters: (using state only)
[ReAct]   ✓ Result: {"lock_files": ["package.json", "package-lock.json"], "count": 2}

[ReAct] OBSERVE phase...
[ReAct]   Observation: Found 2 lock files. The repository uses npm. Ready to parse dependencies...
[ReAct]   Learned: Can proceed with npm dependency parsing...

==================================================
[Node: Execute ReAct] Iteration 3
==================================================
[ReAct] Cycle 3
[ReAct] THINK phase...
[ReAct]   Thought: I should parse the package.json to extract all dependencies...
[ReAct]   Reasoning: This will give me a complete list of packages to scan for vulnerabilities...
[ReAct]   → Selected Tool: 'parse_package_json'

[ReAct] ACT phase: Calling tool 'parse_package_json'
[ReAct]   Parameters: {"file_path": "package.json"}
[ReAct]   ✓ Result: {"total_count": 50, "dependencies": {...}}

[ReAct] OBSERVE phase...
[ReAct]   Observation: Successfully parsed 50 dependencies from package.json. Ready to scan for vulnerabilities...
[ReAct]   Learned: The project has 50 direct dependencies to scan...

... (계속)

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

---

## 출력 포맷 규칙

### 계층 구조
```
[Component] 단계 설명
[Component]   세부 사항 (들여쓰기)
[Component]   → 강조된 정보 (화살표)
[Component]   ✓ 성공 (체크)
[Component]   ✗ 실패 (X)
```

### 길이 제한
- Thought: 150자
- Reasoning: 150자
- Observation: 150자
- Learned: 100자
- Parameters: 200자
- Result: 200자

### 컴포넌트 태그
- `[ReAct]` - ReAct 실행기
- `[Planner]` - 계획 수립기
- `[Node: ...]` - LangGraph 노드
- `[SecurityAgentV2]` - 메인 에이전트

---

## 디버깅 활용

### 도구 호출 추적
출력을 보면:
1. **어떤 도구**를 호출했는지 (`Selected Tool`)
2. **어떤 파라미터**로 호출했는지 (`Parameters`)
3. **결과**가 무엇인지 (`Result`)
4. **성공/실패** 여부 (`✓` / `✗`)

### 문제 진단
- `✗ Error`가 표시되면 어떤 도구에서 문제가 발생했는지 즉시 파악
- Fallback 메시지가 보이면 LLM 연결 문제 또는 응답 파싱 문제
- 파라미터 출력으로 잘못된 값이 전달되었는지 확인

---

## 요약

**추가된 출력 정보:**
1. ✅ THINK 단계: Thought, Reasoning, Selected Tool
2. ✅ ACT 단계: 도구 이름, 파라미터, 결과 요약, 성공/실패
3. ✅ OBSERVE 단계: Observation, Learned
4. ✅ Fallback 단계: 모드 전환 알림, 선택된 단계

**개선 효과:**
- 🔍 도구 호출 과정 투명하게 추적 가능
- 🐛 디버깅이 쉬워짐
- 📊 에이전트의 사고 과정 이해 가능
- ⚡ 문제 발생 시 빠른 진단 가능
