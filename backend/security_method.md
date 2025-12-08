# Security Agent 기능 상세 설명서

## 목차
1. [개요](#개요)
2. [모듈 구조](#모듈-구조)
3. [핵심 클래스 및 함수](#핵심-클래스-및-함수)
4. [호출 순서 및 플로우](#호출-순서-및-플로우)
5. [사용 예시](#사용-예시)

---

## 개요

Security Agent는 GitHub 레포지토리의 의존성을 분석하고 보안 취약점을 점검하는 시스템입니다. 다양한 프로그래밍 언어와 패키지 관리자를 지원하며, 레포지토리의 의존성 파일을 자동으로 탐지하고 분석합니다.

**주요 기능:**
- GitHub 레포지토리 의존성 분석
- 다양한 언어 지원 (Python, JavaScript, Java, Go, Rust 등)
- 의존성 통계 및 요약 제공
- 보안 점수 계산 (기본 구현)
- 보안 개선 사항 제안

---

## 모듈 구조

```
backend/agents/security/
├── service.py                      # 메인 서비스 클래스
├── config/
│   └── dependency_files.py         # 지원하는 의존성 파일 패턴 정의
├── models/
│   └── dependency.py               # 데이터 모델 (Dependency, DependencyFile)
├── github/
│   ├── client.py                   # GitHub API 클라이언트
│   └── analyzer.py                 # 레포지토리 분석기
├── extractors/
│   ├── __init__.py                 # 통합 DependencyExtractor
│   ├── base.py                     # 추출기 베이스 클래스
│   ├── python.py                   # Python 의존성 추출
│   ├── javascript.py               # JavaScript/Node.js 의존성 추출
│   ├── jvm.py                      # Java/JVM 의존성 추출
│   ├── go.py                       # Go 의존성 추출
│   └── ... (기타 언어별 추출기)
└── tools/
    ├── dependency_analyzer.py      # AI 에이전트용 분석 툴 함수
    └── vulnerability_checker.py    # 취약점 체크 툴 함수 (향후 구현)
```

---

## 핵심 클래스 및 함수

### 1. 데이터 모델 (`models/dependency.py`)

#### 1.1 Dependency 클래스
**설명:** 하나의 의존성 정보를 담는 데이터 클래스

**속성:**
- `name` (str): 패키지 이름
- `version` (Optional[str]): 버전 정보
- `type` (str): 의존성 타입 ("runtime", "dev", "peer", "optional")
- `source` (Optional[str]): 패키지 소스 ("npm", "pypi", "maven", "go" 등)

**사용 예시:**
```python
dep = Dependency(name="requests", version="2.28.0", type="runtime", source="pypi")
```

#### 1.2 DependencyFile 클래스
**설명:** 의존성 파일 정보를 담는 데이터 클래스

**속성:**
- `path` (str): 파일 경로
- `sha` (str): 파일 SHA 해시
- `size` (int): 파일 크기
- `url` (str): GitHub API URL
- `content` (Optional[str]): 파일 내용
- `dependencies` (List[Dependency]): 추출된 의존성 목록

---

### 2. GitHub 클라이언트 (`github/client.py`)

#### 2.1 GitHubClient 클래스

##### `__init__(token, base_url)`
**설명:** GitHub API 클라이언트 초기화

**Input:**
- `token` (Optional[str]): GitHub Personal Access Token (환경변수 GITHUB_TOKEN에서 가져옴)
- `base_url` (Optional[str]): GitHub API 기본 URL (기본값: https://api.github.com)

**Output:** GitHubClient 인스턴스

**사용 시점:** GitHub API와 통신이 필요한 모든 작업의 시작점

---

##### `get_repository_tree(owner, repo)`
**설명:** 레포지토리의 전체 파일 트리를 재귀적으로 가져옴

**Input:**
- `owner` (str): 레포지토리 소유자 (예: "facebook")
- `repo` (str): 레포지토리 이름 (예: "react")

**Output:**
- `List[Dict]`: 파일 정보 목록
  - 각 Dict: `{'path': str, 'sha': str, 'size': int, 'url': str}`

**내부 동작:**
1. GitHub API `/repos/{owner}/{repo}/git/trees/HEAD?recursive=1` 호출
2. 응답에서 'blob' 타입만 필터링
3. 파일 정보 리스트 반환

---

##### `get_file_content(owner, repo, path)`
**설명:** 특정 파일의 내용을 가져옴

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `path` (str): 파일 경로

**Output:**
- `Optional[str]`: 파일 내용 (실패 시 None)

**내부 동작:**
1. GitHub API `/repos/{owner}/{repo}/contents/{path}` 호출
2. Base64로 인코딩된 내용을 디코딩
3. UTF-8 문자열로 반환

---

##### `get_file_content_with_retry(owner, repo, path, max_retries)`
**설명:** 재시도 로직을 포함한 파일 내용 가져오기

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `path` (str): 파일 경로
- `max_retries` (int): 최대 재시도 횟수 (기본값: 3)

**Output:**
- `Optional[str]`: 파일 내용 (실패 시 None)

**내부 동작:**
1. `get_file_content()` 호출
2. 실패 시 지수 백오프 방식으로 재시도 (2^attempt 초 대기)
3. max_retries만큼 시도 후에도 실패하면 None 반환

---

### 3. 의존성 추출기 (`extractors/`)

#### 3.1 BaseExtractor 클래스 (`base.py`)
**설명:** 모든 의존성 추출기의 추상 베이스 클래스

##### `extract(content, filename)` (추상 메서드)
**Input:**
- `content` (str): 파일 내용
- `filename` (str): 파일명

**Output:**
- `List[Dependency]`: 추출된 의존성 목록

---

##### `_safe_extract(extract_func, content, error_msg)` (정적 메서드)
**설명:** 안전하게 의존성을 추출하는 헬퍼 메서드

**Input:**
- `extract_func` (Callable): 실행할 추출 함수
- `content` (str): 파일 내용
- `error_msg` (str): 에러 메시지

**Output:**
- `List[Dependency]`: 추출된 의존성 목록 (에러 시 빈 리스트)

**내부 동작:**
1. extract_func 실행
2. 예외 발생 시 에러 메시지 출력하고 빈 리스트 반환

---

#### 3.2 DependencyExtractor 클래스 (`__init__.py`)
**설명:** 모든 언어의 의존성을 추출하는 통합 클래스

##### `__init__()`
**설명:** 모든 언어별 추출기 초기화

**내부 동작:**
- JavaScript, Python, Ruby, JVM, DotNet, Go, Rust, Mobile, C++, Others 추출기 인스턴스 생성

---

##### `extract(content, filename)`
**설명:** 파일명에 따라 적절한 추출기를 자동 선택하여 의존성 추출

**Input:**
- `content` (str): 파일 내용
- `filename` (str): 파일명

**Output:**
- `List[Dependency]`: 추출된 의존성 목록

**내부 동작:**
1. 모든 추출기를 순회하며 extract() 호출
2. 첫 번째로 의존성을 반환하는 추출기 사용
3. 해당 의존성 목록 반환

---

#### 3.3 PythonExtractor 클래스 (`python.py`)

##### `extract(content, filename)`
**설명:** Python 의존성 파일에서 의존성 추출

**지원 파일:**
- `requirements.txt`, `requirements.in`
- `Pipfile`
- `pyproject.toml`
- `setup.py`
- `poetry.lock`
- `conda.yaml`, `environment.yml`

**Output:** `List[Dependency]`

---

##### `_extract_requirements_txt(content)` (정적 메서드)
**설명:** requirements.txt 파싱

**Input:** `content` (str): 파일 내용

**Output:** `List[Dependency]`

**내부 동작:**
1. 각 줄을 파싱
2. 주석(#)과 옵션(-) 제외
3. 정규식으로 패키지명과 버전 추출
4. Dependency 객체 생성 (source="pypi", type="runtime")

---

##### `_extract_pipfile(content)` (정적 메서드)
**설명:** Pipfile (TOML) 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. TOML 파싱
2. `[packages]` → runtime 의존성
3. `[dev-packages]` → dev 의존성
4. 각 의존성의 버전 정보 추출

---

##### `_extract_pyproject_toml(content)` (정적 메서드)
**설명:** pyproject.toml 파싱 (Poetry 및 PEP 621 스타일 지원)

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. TOML 파싱
2. Poetry 스타일: `[tool.poetry.dependencies]` 및 `[tool.poetry.dev-dependencies]`
3. PEP 621 스타일: `[project.dependencies]` 및 `[project.optional-dependencies]`
4. 의존성 객체 생성

---

##### 기타 Python 추출 메서드
- `_extract_setup_py(content)`: setup.py의 install_requires, extras_require 파싱
- `_extract_poetry_lock(content)`: poetry.lock 파싱
- `_extract_conda_yaml(content)`: conda/environment 파일 파싱 (conda 및 pip 의존성 모두 추출)

---

#### 3.4 JavaScriptExtractor 클래스 (`javascript.py`)

##### 지원 파일:
- `package.json`
- `package-lock.json`
- `yarn.lock`
- `bower.json`

##### `_extract_package_json(content)` (정적 메서드)
**설명:** package.json 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. JSON 파싱
2. `dependencies` → runtime
3. `devDependencies` → dev
4. `peerDependencies` → peer
5. `optionalDependencies` → optional
6. 각 의존성 객체 생성 (source="npm")

---

##### `_extract_package_lock_json(content)` (정적 메서드)
**설명:** package-lock.json 파싱 (v1, v2 형식 지원)

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. JSON 파싱
2. v2 형식: `packages` 필드 파싱
3. v1 형식: `dependencies` 필드 파싱
4. dev 플래그에 따라 타입 결정

---

##### `_extract_yarn_lock(content)` (정적 메서드)
**설명:** yarn.lock 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. 줄 단위로 파싱
2. 패키지 선언부에서 이름 추출
3. version 필드에서 버전 추출

---

#### 3.5 JVMExtractor 클래스 (`jvm.py`)

##### 지원 파일:
- `pom.xml` (Maven)
- `build.gradle`, `build.gradle.kts` (Gradle)
- `build.sbt` (Scala SBT)
- `project.clj` (Clojure Leiningen)
- `deps.edn` (Clojure deps)

##### `_extract_pom_xml(content)` (정적 메서드)
**설명:** Maven pom.xml 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. XML 파싱
2. `<dependency>` 태그 찾기
3. `groupId`, `artifactId`, `version`, `scope` 추출
4. scope에 따라 타입 결정 (test/provided → dev, 나머지 → runtime)
5. 이름 형식: `groupId:artifactId`

---

##### `_extract_build_gradle(content)` (정적 메서드)
**설명:** Gradle 빌드 파일 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. 정규식으로 다양한 설정 파싱 (implementation, compile, testImplementation 등)
2. 문자열 표기법: `implementation 'group:name:version'`
3. 맵 표기법: `implementation group: 'group', name: 'name', version: 'version'`

---

##### 기타 JVM 추출 메서드:
- `_extract_build_sbt(content)`: Scala SBT 파싱
- `_extract_project_clj(content)`: Clojure Leiningen 파싱
- `_extract_deps_edn(content)`: Clojure deps.edn 파싱

---

#### 3.6 GoExtractor 클래스 (`go.py`)

##### 지원 파일:
- `go.mod`
- `go.sum`
- `Gopkg.toml`

##### `_extract_go_mod(content)` (정적 메서드)
**설명:** go.mod 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. `require` 블록 찾기
2. 단일 라인 및 멀티 라인 require 모두 처리
3. 모듈명과 버전 추출

---

##### `_extract_go_sum(content)` (정적 메서드)
**설명:** go.sum 파싱

**Input:** `content` (str)

**Output:** `List[Dependency]`

**내부 동작:**
1. 각 줄을 공백으로 분리
2. 모듈명과 버전 추출
3. 중복 제거

---

### 4. 레포지토리 분석기 (`github/analyzer.py`)

#### 4.1 RepositoryAnalyzer 클래스

##### `__init__(github_client)`
**설명:** 레포지토리 분석기 초기화

**Input:**
- `github_client` (Optional[GitHubClient]): GitHub 클라이언트 (없으면 새로 생성)

**Output:** RepositoryAnalyzer 인스턴스

**초기화 내용:**
- GitHubClient 인스턴스
- DependencyExtractor 인스턴스
- DEPENDENCY_FILES 설정 로드

---

##### `is_dependency_file(path)`
**설명:** 파일이 의존성 파일인지 확인

**Input:**
- `path` (str): 파일 경로

**Output:**
- `bool`: 의존성 파일이면 True

**내부 동작:**
1. 파일명 추출
2. DEPENDENCY_FILES 패턴과 비교
3. 와일드카드(*) 패턴은 fnmatch로 처리

---

##### `get_dependency_files(owner, repo)`
**설명:** 레포지토리에서 의존성 파일 목록 가져오기

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름

**Output:**
- `List[Dict]`: 의존성 파일 정보 목록

**내부 동작:**
1. `client.get_repository_tree()` 호출하여 전체 파일 목록 가져오기
2. 각 파일에 대해 `is_dependency_file()` 검사
3. 의존성 파일만 필터링하여 반환

---

##### `fetch_and_analyze_file(owner, repo, file_info)`
**설명:** 파일을 가져와서 의존성 분석

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `file_info` (Dict): 파일 정보

**Output:**
- `DependencyFile`: 분석된 의존성 파일

**내부 동작:**
1. DependencyFile 객체 생성 (path, sha, size, url 설정)
2. `client.get_file_content_with_retry()` 호출하여 파일 내용 가져오기
3. `extractor.extract()` 호출하여 의존성 추출
4. DependencyFile 객체에 내용과 의존성 저장 후 반환

---

##### `analyze_repository(owner, repo, max_workers)`
**설명:** 레포지토리의 모든 의존성 파일을 병렬로 분석

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `max_workers` (int): 병렬 처리 워커 수 (기본값: 5)

**Output:**
- `Dict[str, Any]`: 분석 결과
  ```python
  {
      'owner': str,
      'repo': str,
      'total_files': int,
      'total_dependencies': int,
      'files': List[Dict],
      'all_dependencies': List[Dict],
      'summary': {
          'by_source': Dict[str, int],
          'runtime_dependencies': int,
          'dev_dependencies': int,
          'total_unique': int
      }
  }
  ```

**내부 동작:**
1. `get_dependency_files()` 호출하여 의존성 파일 목록 가져오기
2. ThreadPoolExecutor로 병렬 처리 시작
3. 각 파일에 대해 `fetch_and_analyze_file()` 호출
4. 모든 결과 수집 후 `_build_result()` 호출

---

##### `_build_result(owner, repo, analyzed_files)`
**설명:** 분석 결과 구성

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `analyzed_files` (List[DependencyFile]): 분석된 파일 목록

**Output:**
- `Dict[str, Any]`: 분석 결과

**내부 동작:**
1. 모든 파일의 의존성을 하나의 리스트로 통합
2. 소스별 통계 계산
3. 중복 제거 (`source:name`을 키로 사용)
4. 버전이 있는 의존성 우선
5. 결과 딕셔너리 구성 및 반환

---

### 5. 메인 서비스 (`service.py`)

#### 5.1 SecurityAnalysisService 클래스

##### `__init__(github_token, github_base_url)`
**설명:** 보안 분석 서비스 초기화

**Input:**
- `github_token` (Optional[str]): GitHub 토큰
- `github_base_url` (Optional[str]): GitHub API URL

**Output:** SecurityAnalysisService 인스턴스

**초기화 내용:**
- GitHubClient 인스턴스
- RepositoryAnalyzer 인스턴스

---

##### `analyze_repository(owner, repo, max_workers)`
**설명:** GitHub 레포지토리 의존성 분석

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `max_workers` (int): 병렬 처리 워커 수 (기본값: 5)

**Output:**
- `Dict[str, Any]`: 분석 결과

**내부 동작:**
- `analyzer.analyze_repository()` 호출 및 결과 반환

---

##### `save_results(results, output_file)`
**설명:** 분석 결과를 JSON 파일로 저장

**Input:**
- `results` (Dict[str, Any]): 분석 결과
- `output_file` (Optional[str]): 출력 파일 경로 (없으면 자동 생성)

**Output:**
- `str`: 저장된 파일 경로

**내부 동작:**
1. output_file이 없으면 `{owner}_{repo}_dependencies.json` 생성
2. JSON 파일로 저장 (indent=2, ensure_ascii=False)
3. 파일 경로 반환

---

##### `print_summary(results)`
**설명:** 분석 결과 요약 출력

**Input:**
- `results` (Dict[str, Any]): 분석 결과

**Output:** None (콘솔에 출력)

**출력 내용:**
- 레포지토리 정보
- 전체 의존성 파일 수
- 전체 고유 의존성 수
- Runtime/Dev 의존성 수
- 소스별 의존성 수

---

##### `analyze_repository()` (편의 함수)
**설명:** 단축 함수 - 서비스 생성과 분석을 한 번에 수행

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `**kwargs`: 추가 옵션 (github_token, github_base_url, max_workers)

**Output:**
- `Dict[str, Any]`: 분석 결과

---

### 6. AI 에이전트 툴 함수 (`tools/dependency_analyzer.py`)

#### 6.1 `analyze_repository_dependencies(owner, repo, max_workers, github_token, github_base_url)`
**설명:** GitHub 레포지토리의 의존성을 분석하는 독립 툴 함수

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `max_workers` (int): 병렬 처리 워커 수 (기본값: 5)
- `github_token` (Optional[str]): GitHub 토큰
- `github_base_url` (Optional[str]): GitHub API URL

**Output:**
- `Dict[str, Any]`: 분석 결과 (에러 시 error 필드 포함)

**내부 동작:**
1. GitHubClient 생성
2. RepositoryAnalyzer 생성
3. analyze_repository() 호출
4. 예외 발생 시 에러 정보 포함한 딕셔너리 반환

---

#### 6.2 `get_dependencies_by_source(analysis_result, source)`
**설명:** 특정 소스의 의존성만 필터링

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `source` (str): 필터링할 소스 (예: "npm", "pypi", "maven")

**Output:**
- `List[Dict[str, Any]]`: 필터링된 의존성 목록

**내부 동작:**
- `all_dependencies`에서 source가 일치하는 항목만 반환

---

#### 6.3 `get_dependencies_by_type(analysis_result, dep_type)`
**설명:** 특정 타입의 의존성만 필터링

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `dep_type` (str): 필터링할 타입 (예: "runtime", "dev", "peer")

**Output:**
- `List[Dict[str, Any]]`: 필터링된 의존성 목록

**내부 동작:**
- `all_dependencies`에서 type이 일치하는 항목만 반환

---

#### 6.4 `get_outdated_dependencies(analysis_result, version_pattern)`
**설명:** 버전이 명시되지 않았거나 특정 패턴과 일치하는 의존성 찾기

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `version_pattern` (str): 찾을 버전 패턴 (기본값: "*")

**Output:**
- `List[Dict[str, Any]]`: 필터링된 의존성 목록

**내부 동작:**
1. version_pattern이 "*"이면 버전이 없거나 "*"인 의존성 반환
2. 그 외에는 version에 패턴이 포함된 의존성 반환

---

#### 6.5 `count_dependencies_by_language(analysis_result)`
**설명:** 언어/패키지 매니저별 의존성 개수 집계

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과

**Output:**
- `Dict[str, int]`: 소스별 의존성 개수 (예: `{'npm': 150, 'pypi': 20}`)

**내부 동작:**
- `summary.by_source` 반환

---

#### 6.6 `summarize_dependency_analysis(analysis_result)`
**설명:** 의존성 분석 결과를 자연어로 요약

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과

**Output:**
- `str`: 자연어 요약 텍스트

**출력 내용:**
- 레포지토리 정보
- 분석된 의존성 파일 수
- 고유 의존성 수
- Runtime/Dev 의존성 수
- 패키지 매니저별 의존성 수
- 에러 정보 (있는 경우)

---

#### 6.7 `find_dependency_files(owner, repo, github_token, github_base_url)`
**설명:** 레포지토리에서 의존성 파일 경로만 찾기 (분석 없이)

**Input:**
- `owner` (str): 레포지토리 소유자
- `repo` (str): 레포지토리 이름
- `github_token` (Optional[str]): GitHub 토큰
- `github_base_url` (Optional[str]): GitHub API URL

**Output:**
- `List[str]`: 의존성 파일 경로 목록

**내부 동작:**
1. GitHubClient, RepositoryAnalyzer 생성
2. `analyzer.get_dependency_files()` 호출
3. 파일 경로만 추출하여 반환

---

### 7. 취약점 체크 툴 (`tools/vulnerability_checker.py`)

> **참고:** 현재 이 모듈의 함수들은 기본 구조만 제공하며, 실제 취약점 데이터베이스 연동은 향후 구현 예정입니다.

#### 7.1 `check_vulnerabilities(analysis_result, severity_threshold)`
**설명:** 의존성에서 알려진 취약점 체크 (향후 구현)

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `severity_threshold` (str): 최소 심각도 ("low", "medium", "high", "critical")

**Output:**
- `Dict[str, Any]`: 취약점 분석 결과
  ```python
  {
      'total_vulnerabilities': int,
      'critical': int,
      'high': int,
      'medium': int,
      'low': int,
      'vulnerabilities': List,
      'note': str
  }
  ```

**현재 상태:** 기본 구조만 반환 (모든 값 0)

---

#### 7.2 `get_security_score(analysis_result, vulnerability_result)`
**설명:** 보안 점수 계산 (기본 구현)

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `vulnerability_result` (Optional[Dict[str, Any]]): 취약점 분석 결과

**Output:**
- `Dict[str, Any]`: 보안 점수
  ```python
  {
      'score': int (0-100),
      'grade': str ('A', 'B', 'C', 'D', 'F'),
      'factors': {
          'total_dependencies': int,
          'unversioned_dependencies': int,
          'unversioned_penalty': int
      },
      'note': str
  }
  ```

**계산 로직:**
1. 버전이 명시되지 않은 의존성 비율 계산
2. 비율에 따라 최대 30점 감점
3. 100점 기준에서 감점 적용
4. 점수에 따라 등급 부여:
   - 90 이상: A
   - 80-89: B
   - 70-79: C
   - 60-69: D
   - 60 미만: F

---

#### 7.3 `check_license_compliance(analysis_result, allowed_licenses)`
**설명:** 라이센스 준수 체크 (향후 구현)

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `allowed_licenses` (Optional[List[str]]): 허용된 라이센스 목록

**Output:**
- `Dict[str, Any]`: 라이센스 준수 결과

**현재 상태:** 기본 구조만 반환

---

#### 7.4 `suggest_security_improvements(analysis_result, vulnerability_result, security_score)`
**설명:** 보안 개선 사항 제안

**Input:**
- `analysis_result` (Dict[str, Any]): 분석 결과
- `vulnerability_result` (Optional[Dict[str, Any]]): 취약점 분석 결과
- `security_score` (Optional[Dict[str, Any]]): 보안 점수

**Output:**
- `List[str]`: 개선 사항 제안 목록

**제안 항목:**
1. 버전이 명시되지 않은 의존성 수정
2. 의존성 파일이 없는 경우 추가 권장
3. 잠금 파일(lock file) 추가 권장
   - Node.js: package-lock.json 또는 yarn.lock
   - Python: Pipfile.lock 또는 poetry.lock
4. Python 프로젝트에 Pipenv/Poetry 사용 권장
5. 보안 점수가 낮은 경우 개선 권장
6. 모든 것이 양호한 경우 자동 업데이트 도구 (Dependabot, Renovate) 권장

---

## 호출 순서 및 플로우

### 시나리오 1: 기본 레포지토리 분석

```
사용자 요청
    ↓
[1] SecurityAnalysisService.__init__()
    ├─ GitHubClient.__init__()          # GitHub API 클라이언트 초기화
    └─ RepositoryAnalyzer.__init__()    # 분석기 초기화
           └─ DependencyExtractor.__init__()  # 모든 언어 추출기 초기화
    ↓
[2] SecurityAnalysisService.analyze_repository(owner, repo, max_workers=5)
    ↓
[3] RepositoryAnalyzer.analyze_repository(owner, repo, max_workers)
    ↓
[4] RepositoryAnalyzer.get_dependency_files(owner, repo)
    ↓
[5] GitHubClient.get_repository_tree(owner, repo)
    │   INPUT: owner="facebook", repo="react"
    │   OUTPUT: List[{path, sha, size, url}]  # 전체 파일 목록
    ↓
[6] RepositoryAnalyzer.is_dependency_file(path)  # 각 파일마다
    │   INPUT: path="package.json"
    │   OUTPUT: True or False
    │   (DEPENDENCY_FILES 패턴과 매칭)
    ↓
[7] ThreadPoolExecutor (병렬 처리 시작, max_workers=5)
    │
    ├─ [Thread 1] RepositoryAnalyzer.fetch_and_analyze_file(owner, repo, file_info)
    │   ↓
    │   [8] GitHubClient.get_file_content_with_retry(owner, repo, path)
    │       ↓
    │       GitHubClient.get_file_content(owner, repo, path)
    │           INPUT: owner="facebook", repo="react", path="package.json"
    │           OUTPUT: "{ \"dependencies\": {...} }"
    │   ↓
    │   [9] DependencyExtractor.extract(content, filename)
    │       │   INPUT: content="{ \"dependencies\": {...} }", filename="package.json"
    │       ↓
    │       JavaScriptExtractor.extract(content, filename)
    │           ↓
    │           JavaScriptExtractor._extract_package_json(content)
    │               INPUT: content (JSON 문자열)
    │               OUTPUT: [
    │                   Dependency(name="react-dom", version="^18.0.0", type="runtime", source="npm"),
    │                   Dependency(name="jest", version="^29.0.0", type="dev", source="npm"),
    │                   ...
    │               ]
    │
    ├─ [Thread 2] ... (다른 파일에 대해 동일 프로세스)
    ├─ [Thread 3] ...
    └─ [Thread 4] ...
    ↓
[10] RepositoryAnalyzer._build_result(owner, repo, analyzed_files)
    │   INPUT:
    │       owner="facebook"
    │       repo="react"
    │       analyzed_files=[DependencyFile(...), DependencyFile(...), ...]
    │
    │   처리:
    │   - 모든 의존성 통합
    │   - 중복 제거 (source:name 기준)
    │   - 소스별 통계 계산
    │   - Runtime/Dev 의존성 집계
    │
    │   OUTPUT: {
    │       'owner': 'facebook',
    │       'repo': 'react',
    │       'total_files': 3,
    │       'total_dependencies': 120,
    │       'files': [...],
    │       'all_dependencies': [...],
    │       'summary': {
    │           'by_source': {'npm': 120},
    │           'runtime_dependencies': 80,
    │           'dev_dependencies': 40,
    │           'total_unique': 120
    │       }
    │   }
    ↓
[11] SecurityAnalysisService.print_summary(results)
    │   (콘솔에 요약 출력)
    ↓
[12] SecurityAnalysisService.save_results(results, output_file)
    │   INPUT: results (위의 딕셔너리)
    │   OUTPUT: "facebook_react_dependencies.json"
```

---

### 시나리오 2: AI 에이전트가 툴 함수 사용

```
AI 에이전트 요청: "facebook/react의 의존성을 분석해줘"
    ↓
[1] tools.dependency_analyzer.analyze_repository_dependencies(
        owner="facebook",
        repo="react",
        max_workers=5
    )
    ↓
[2] GitHubClient.__init__()
    ↓
[3] RepositoryAnalyzer.__init__()
    ↓
[4-10] (시나리오 1의 4-10 단계와 동일)
    ↓
[11] 분석 결과 반환
    │   OUTPUT: {
    │       'owner': 'facebook',
    │       'repo': 'react',
    │       'total_files': 3,
    │       'total_dependencies': 120,
    │       ...
    │   }
    ↓
AI 에이전트 요청: "npm 패키지만 보여줘"
    ↓
[12] tools.dependency_analyzer.get_dependencies_by_source(
        analysis_result=<위의 결과>,
        source="npm"
    )
    │   INPUT: analysis_result, source="npm"
    │   OUTPUT: [
    │       {'name': 'react-dom', 'version': '^18.0.0', 'type': 'runtime', 'source': 'npm'},
    │       {'name': 'jest', 'version': '^29.0.0', 'type': 'dev', 'source': 'npm'},
    │       ...
    │   ]
    ↓
AI 에이전트 요청: "보안 점수를 계산해줘"
    ↓
[13] tools.vulnerability_checker.get_security_score(
        analysis_result=<분석 결과>
    )
    │   INPUT: analysis_result
    │
    │   처리:
    │   - 버전 미명시 의존성 카운트
    │   - 비율 계산 및 감점
    │   - 점수 계산 (0-100)
    │   - 등급 계산 (A-F)
    │
    │   OUTPUT: {
    │       'score': 95,
    │       'grade': 'A',
    │       'factors': {
    │           'total_dependencies': 120,
    │           'unversioned_dependencies': 2,
    │           'unversioned_penalty': 5
    │       }
    │   }
    ↓
AI 에이전트 요청: "개선 사항을 제안해줘"
    ↓
[14] tools.vulnerability_checker.suggest_security_improvements(
        analysis_result=<분석 결과>,
        security_score=<보안 점수>
    )
    │   OUTPUT: [
    │       "Fix 2 dependencies without specific versions. Always specify exact or minimum versions...",
    │       "Add a lock file (package-lock.json or yarn.lock) to ensure consistent dependency versions..."
    │   ]
```

---

### 시나리오 3: Python 프로젝트 의존성 추출 상세 플로우

```
파일: requirements.txt
내용:
    requests>=2.28.0
    flask==2.0.1
    pytest
    # 주석
    -e git+https://github.com/user/repo.git

    ↓
DependencyExtractor.extract(content, "requirements.txt")
    ↓
PythonExtractor.extract(content, "requirements.txt")
    ↓
PythonExtractor._extract_requirements_txt(content)
    │
    │   줄 단위 처리:
    │
    │   Line 1: "requests>=2.28.0"
    │   ├─ 정규식 매칭: r'^([a-zA-Z0-9\-_\.\[\]]+)\s*([><=!~]+.*)?$'
    │   ├─ name = "requests"
    │   ├─ version = ">=2.28.0"
    │   └─ Dependency(name="requests", version=">=2.28.0", type="runtime", source="pypi")
    │
    │   Line 2: "flask==2.0.1"
    │   ├─ name = "flask"
    │   ├─ version = "==2.0.1"
    │   └─ Dependency(name="flask", version="==2.0.1", type="runtime", source="pypi")
    │
    │   Line 3: "pytest"
    │   ├─ name = "pytest"
    │   ├─ version = None
    │   └─ Dependency(name="pytest", version=None, type="runtime", source="pypi")
    │
    │   Line 4: "# 주석" → Skip (주석)
    │
    │   Line 5: "-e git+https://..." → Skip (옵션)
    │
    │   OUTPUT: [
    │       Dependency(name="requests", version=">=2.28.0", type="runtime", source="pypi"),
    │       Dependency(name="flask", version="==2.0.1", type="runtime", source="pypi"),
    │       Dependency(name="pytest", version=None, type="runtime", source="pypi")
    │   ]
```

---

### 시나리오 4: Java Maven 프로젝트 의존성 추출 상세 플로우

```
파일: pom.xml
내용:
    <?xml version="1.0"?>
    <project xmlns="http://maven.apache.org/POM/4.0.0">
        <dependencies>
            <dependency>
                <groupId>org.springframework</groupId>
                <artifactId>spring-core</artifactId>
                <version>5.3.10</version>
                <scope>compile</scope>
            </dependency>
            <dependency>
                <groupId>junit</groupId>
                <artifactId>junit</artifactId>
                <version>4.13.2</version>
                <scope>test</scope>
            </dependency>
        </dependencies>
    </project>

    ↓
DependencyExtractor.extract(content, "pom.xml")
    ↓
JVMExtractor.extract(content, "pom.xml")
    ↓
JVMExtractor._extract_pom_xml(content)
    │
    │   XML 파싱:
    │   ├─ 네임스페이스 설정: {'maven': 'http://maven.apache.org/POM/4.0.0'}
    │   └─ <dependency> 태그 찾기
    │
    │   Dependency 1:
    │   ├─ groupId = "org.springframework"
    │   ├─ artifactId = "spring-core"
    │   ├─ version = "5.3.10"
    │   ├─ scope = "compile" → type = "runtime"
    │   ├─ name = "org.springframework:spring-core"
    │   └─ Dependency(name="org.springframework:spring-core", version="5.3.10", type="runtime", source="maven")
    │
    │   Dependency 2:
    │   ├─ groupId = "junit"
    │   ├─ artifactId = "junit"
    │   ├─ version = "4.13.2"
    │   ├─ scope = "test" → type = "dev"
    │   ├─ name = "junit:junit"
    │   └─ Dependency(name="junit:junit", version="4.13.2", type="dev", source="maven")
    │
    │   OUTPUT: [
    │       Dependency(name="org.springframework:spring-core", version="5.3.10", type="runtime", source="maven"),
    │       Dependency(name="junit:junit", version="4.13.2", type="dev", source="maven")
    │   ]
```

---

## 사용 예시

### 예시 1: 간단한 레포지토리 분석

```python
from backend.agents.security import SecurityAnalysisService

# 서비스 초기화
service = SecurityAnalysisService(github_token="ghp_xxxxx")

# 레포지토리 분석
results = service.analyze_repository("facebook", "react")

# 결과 요약 출력
service.print_summary(results)

# JSON 파일로 저장
service.save_results(results)
```

**실행 과정:**
1. GitHubClient 생성 (토큰 설정)
2. RepositoryAnalyzer 생성
3. facebook/react의 모든 파일 트리 가져오기
4. 의존성 파일 필터링 (package.json, yarn.lock 등)
5. 각 파일의 내용 가져오기 (병렬 처리)
6. JavaScript 추출기로 의존성 파싱
7. 결과 통합 및 중복 제거
8. 요약 출력 및 JSON 저장

---

### 예시 2: 단축 함수 사용

```python
from backend.agents.security import analyze_repository

# 한 줄로 분석
results = analyze_repository(
    owner="django",
    repo="django",
    github_token="ghp_xxxxx"
)

print(f"Total dependencies: {results['total_dependencies']}")
```

---

### 예시 3: AI 에이전트 툴 함수 사용

```python
from backend.agents.security.tools.dependency_analyzer import (
    analyze_repository_dependencies,
    get_dependencies_by_source,
    get_dependencies_by_type,
    summarize_dependency_analysis
)

# 1. 레포지토리 분석
result = analyze_repository_dependencies(
    owner="pallets",
    repo="flask"
)

# 2. Python 패키지만 필터링
python_deps = get_dependencies_by_source(result, "pypi")
print(f"Python dependencies: {len(python_deps)}")

# 3. 개발 의존성만 필터링
dev_deps = get_dependencies_by_type(result, "dev")
print(f"Dev dependencies: {len(dev_deps)}")

# 4. 자연어 요약
summary = summarize_dependency_analysis(result)
print(summary)
```

**출력 예시:**
```
Python dependencies: 25
Dev dependencies: 15
Repository: pallets/flask
Total dependency files analyzed: 4
Total unique dependencies: 25
Runtime dependencies: 10
Development dependencies: 15

Dependencies by package manager:
  - pypi: 25
```

---

### 예시 4: 보안 점수 및 개선 사항

```python
from backend.agents.security.tools.dependency_analyzer import analyze_repository_dependencies
from backend.agents.security.tools.vulnerability_checker import (
    get_security_score,
    suggest_security_improvements
)

# 1. 분석
result = analyze_repository_dependencies("user", "repo")

# 2. 보안 점수
score = get_security_score(result)
print(f"Security Grade: {score['grade']} ({score['score']}/100)")

# 3. 개선 사항
suggestions = suggest_security_improvements(result, security_score=score)
for suggestion in suggestions:
    print(f"- {suggestion}")
```

**출력 예시:**
```
Security Grade: B (85/100)
- Fix 5 dependencies without specific versions. Always specify exact or minimum versions to ensure reproducible builds.
- Add a lock file (package-lock.json or yarn.lock) to ensure consistent dependency versions across installations.
```

---

### 예시 5: 특정 조건의 의존성 찾기

```python
from backend.agents.security.tools.dependency_analyzer import (
    analyze_repository_dependencies,
    get_outdated_dependencies
)

# 분석
result = analyze_repository_dependencies("owner", "repo")

# 버전이 명시되지 않은 의존성
unversioned = get_outdated_dependencies(result, "*")
print(f"Unversioned dependencies: {len(unversioned)}")
for dep in unversioned:
    print(f"  - {dep['name']} (source: {dep['source']})")

# 특정 패턴의 버전 (예: "^" 사용)
caret_deps = get_outdated_dependencies(result, "^")
print(f"\nDependencies with ^ version: {len(caret_deps)}")
```

---

### 예시 6: 의존성 파일만 찾기

```python
from backend.agents.security.tools.dependency_analyzer import find_dependency_files

# 파일 경로만 가져오기 (분석 없이)
files = find_dependency_files("facebook", "react")
print(f"Found {len(files)} dependency files:")
for file_path in files:
    print(f"  - {file_path}")
```

**출력 예시:**
```
Found 3 dependency files:
  - package.json
  - yarn.lock
  - scripts/rollup/package.json
```

---

## 정리

### 주요 데이터 흐름

1. **입력:** `owner`, `repo` (GitHub 레포지토리 정보)
2. **GitHub API 호출:** 파일 트리 → 파일 내용
3. **필터링:** 의존성 파일 패턴 매칭
4. **추출:** 언어별 추출기로 파싱
5. **통합:** 중복 제거 및 통계 계산
6. **출력:** 분석 결과 딕셔너리

### 핵심 함수 호출 체인

**메인 플로우:**
```
SecurityAnalysisService.analyze_repository()
  → RepositoryAnalyzer.analyze_repository()
    → RepositoryAnalyzer.get_dependency_files()
      → GitHubClient.get_repository_tree()
    → RepositoryAnalyzer.fetch_and_analyze_file() [병렬]
      → GitHubClient.get_file_content_with_retry()
      → DependencyExtractor.extract()
        → [언어별]Extractor.extract()
          → [언어별]Extractor._extract_[파일타입]()
    → RepositoryAnalyzer._build_result()
```

**툴 플로우:**
```
tools.dependency_analyzer.analyze_repository_dependencies()
  → [메인 플로우와 동일]
  → 결과 반환

tools.dependency_analyzer.get_dependencies_by_source()
  → 결과 필터링

tools.vulnerability_checker.get_security_score()
  → 점수 계산

tools.vulnerability_checker.suggest_security_improvements()
  → 개선 사항 생성
```

### 확장 가능성

현재 구조는 다음 기능들을 쉽게 추가할 수 있도록 설계되어 있습니다:

1. **새로운 언어 지원:** `extractors/` 디렉토리에 새 추출기 추가
2. **취약점 데이터베이스 연동:** `vulnerability_checker.py`의 함수들 구현
3. **라이센스 체크:** 외부 API 연동
4. **자동 업데이트 제안:** 버전 비교 로직 추가
5. **캐싱 시스템:** GitHub API 호출 결과 캐싱

---

이 문서는 Security Agent의 모든 주요 기능과 호출 흐름을 상세히 설명합니다. 각 함수의 input/output과 내부 동작을 이해하면 시스템을 효과적으로 사용하고 확장할 수 있습니다.
