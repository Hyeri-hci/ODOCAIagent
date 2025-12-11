/**
 * UI 테스트용 Mock 분석 데이터
 * 모든 섹션(진단, 보안, 온보딩, 추천 이슈, 유사 프로젝트)을 포함
 */

export const mockAnalysisResult = {
  repositoryUrl: "https://github.com/facebook/react",
  analysisId: "mock_analysis_001",

  // 요약 정보
  summary: {
    score: 85,
    healthStatus: "excellent",
    healthLevel: "excellent",
    healthLevelDescription:
      "이 프로젝트는 매우 잘 관리되고 있으며, 문서화와 활동성 모두 우수합니다.",
    healthScoreInterpretation:
      "85점은 상위 10% 오픈소스 프로젝트에 해당하는 점수입니다. 활발한 커뮤니티와 좋은 문서화를 갖추고 있습니다.",
    onboardingScore: 78,
    onboardingLevel: "easy",
    contributionOpportunities: 5,
    estimatedImpact: "high",
  },

  // 프로젝트 요약 (AI 생성)
  projectSummary: `## React란?
React는 Facebook에서 개발한 **JavaScript UI 라이브러리**입니다. 
컴포넌트 기반 아키텍처를 사용하여 재사용 가능하고 유지보수가 쉬운 UI를 구축할 수 있습니다.

### 주요 특징
- **선언적 UI**: 상태가 변경되면 React가 자동으로 UI를 업데이트합니다
- **컴포넌트 기반**: 독립적이고 재사용 가능한 컴포넌트로 구성
- **Virtual DOM**: 효율적인 렌더링을 위한 가상 DOM 사용

### 시작하기
\`\`\`bash
npx create-react-app my-app
cd my-app
npm start
\`\`\``,

  // 추천 작업
  recommendations: [
    {
      id: "action_1",
      title: "TypeScript 마이그레이션 도움",
      description:
        "일부 컴포넌트를 TypeScript로 변환하는 작업에 참여할 수 있습니다.",
      difficulty: "medium",
      estimatedTime: "4-8시간",
      impact: "high",
      tags: ["typescript", "migration"],
      url: "https://github.com/facebook/react/issues/12345",
      issueNumber: 12345,
    },
    {
      id: "action_2",
      title: "문서 오타 수정",
      description: "README 및 공식 문서의 오타를 수정합니다.",
      difficulty: "easy",
      estimatedTime: "30분-1시간",
      impact: "low",
      tags: ["documentation", "good-first-issue"],
      url: null,
      issueNumber: null,
    },
    {
      id: "issue_1",
      title: "[Bug] useEffect cleanup not called",
      description: "GitHub Issue #28901",
      difficulty: "medium",
      estimatedTime: "2-4시간",
      impact: "medium",
      tags: ["bug", "hooks"],
      url: "https://github.com/facebook/react/issues/28901",
      issueNumber: 28901,
    },
  ],

  // 추천 이슈 목록 (별도 섹션용)
  recommendedIssues: [
    {
      number: 28901,
      title: "[Bug] useEffect cleanup not called in StrictMode",
      body: "When using StrictMode, the cleanup function of useEffect is not being called properly during the double-invoke cycle. This causes memory leaks in certain scenarios...",
      labels: ["bug", "hooks", "good first issue"],
      url: "https://github.com/facebook/react/issues/28901",
    },
    {
      number: 28756,
      title: "[Feature] Add displayName to forwardRef",
      body: "It would be helpful if forwardRef components had an automatic displayName for better debugging experience in React DevTools...",
      labels: ["enhancement", "good first issue"],
      url: "https://github.com/facebook/react/issues/28756",
    },
    {
      number: 28632,
      title: "[Docs] Update hooks documentation for React 19",
      body: "Several hooks have new behaviors in React 19 that need to be documented. This includes changes to useEffect, useMemo, and the new use() hook...",
      labels: ["documentation", "help wanted"],
      url: "https://github.com/facebook/react/issues/28632",
    },
    {
      number: 28501,
      title: "[Test] Add unit tests for Suspense boundaries",
      body: "We need more comprehensive test coverage for Suspense boundary edge cases, especially when combined with Error Boundaries...",
      labels: ["testing", "good first issue"],
      url: "https://github.com/facebook/react/issues/28501",
    },
    {
      number: 28399,
      title: "[Accessibility] Improve ARIA support in Portal",
      body: "Portal components should better handle ARIA attributes to improve accessibility for screen readers...",
      labels: ["accessibility", "enhancement"],
      url: "https://github.com/facebook/react/issues/28399",
    },
  ],

  // 위험 요소
  risks: [
    {
      id: "risk_1",
      type: "dependency",
      severity: "medium",
      description:
        "일부 개발 의존성 패키지가 6개월 이상 업데이트되지 않았습니다.",
    },
    {
      id: "risk_2",
      type: "complexity",
      severity: "low",
      description:
        "코드베이스 규모가 크므로 첫 기여 시 온보딩 시간이 필요할 수 있습니다.",
    },
    {
      id: "risk_3",
      type: "security",
      severity: "high",
      description:
        "XSS 취약점 가능성이 있는 dangerouslySetInnerHTML 사용 부분이 있습니다.",
    },
  ],

  // 상세 기술 정보
  technicalDetails: {
    stars: 225000,
    forks: 45000,
    contributors: 1600,
    openIssues: 850,
    openPRs: 120,
    lastCommit: "오늘",
    totalCommits30d: 156,
    documentationQuality: 92,
    activityMaintainability: 88,
    onboardingScore: 78,
    dependencyComplexity: 45,
    issueCloseRate: 0.73,
    issueCloseRatePct: "73%",
    medianPRMergeDays: 3.5,
    medianPRMergeDaysText: "3.5일",
    medianIssueCloseDays: 7.2,
    medianIssueCloseDaysText: "7.2일",
    readmeSections: {
      WHAT: true,
      WHY: true,
      HOW: true,
      CONTRIBUTING: true,
    },
  },

  // 온보딩 플랜
  onboardingPlan: [
    {
      step: 1,
      title: "개발 환경 설정",
      description:
        "React 저장소를 클론하고 로컬 개발 환경을 설정합니다. Node.js 18+ 버전이 필요합니다.",
      duration: "30분",
      resources: [
        {
          type: "docs",
          title: "Contributing Guide",
          url: "https://github.com/facebook/react/blob/main/CONTRIBUTING.md",
        },
      ],
    },
    {
      step: 2,
      title: "프로젝트 구조 이해",
      description:
        "packages/ 폴더 구조와 각 패키지의 역할을 파악합니다. react, react-dom, scheduler 등 핵심 패키지를 살펴봅니다.",
      duration: "1-2시간",
      resources: [
        {
          type: "docs",
          title: "Architecture Overview",
          url: "https://react.dev/learn",
        },
      ],
    },
    {
      step: 3,
      title: "테스트 실행",
      description:
        "yarn test 명령으로 테스트 스위트를 실행하고, 테스트 작성 방법을 익힙니다.",
      duration: "30분",
      resources: [],
    },
    {
      step: 4,
      title: "첫 이슈 선택",
      description:
        "'good first issue' 라벨이 붙은 이슈 중 관심 있는 것을 선택합니다.",
      duration: "15분",
      resources: [
        {
          type: "link",
          title: "Good First Issues",
          url: "https://github.com/facebook/react/labels/good%20first%20issue",
        },
      ],
    },
  ],

  // 보안 분석 결과
  security: {
    score: 78,
    grade: "B",
    vulnerability_count: 3,
    critical: 0,
    high: 1,
    medium: 2,
    low: 0,
    summary:
      "전반적으로 보안 상태가 양호하나, 1개의 High 심각도 취약점이 발견되어 검토가 필요합니다.",
    vulnerabilities: [
      {
        severity: "high",
        title: "Prototype Pollution in nested object merge",
        package: "lodash",
        version: "4.17.15",
        fix_version: "4.17.21",
      },
      {
        severity: "medium",
        title: "Regular Expression Denial of Service",
        package: "semver",
        version: "5.7.0",
        fix_version: "5.7.2",
      },
    ],
  },

  // 유사 프로젝트 추천
  similarProjects: [
    {
      name: "preact",
      owner: "preactjs",
      repo: "preactjs/preact",
      url: "https://github.com/preactjs/preact",
      stars: 36200,
      forks: 1900,
      language: "JavaScript",
      reason:
        "React와 동일한 API를 제공하는 경량 대안. 작은 번들 사이즈로 React 학습 후 쉽게 전환 가능합니다.",
      similarity: 0.92,
      tags: ["ui-library", "virtual-dom", "lightweight"],
    },
    {
      name: "vue",
      owner: "vuejs",
      repo: "vuejs/vue",
      url: "https://github.com/vuejs/vue",
      stars: 207000,
      forks: 33600,
      language: "TypeScript",
      reason:
        "컴포넌트 기반 UI 프레임워크. React와 유사한 개념을 다른 문법으로 구현하여 비교 학습에 유용합니다.",
      similarity: 0.78,
      tags: ["framework", "reactive", "template"],
    },
    {
      name: "solid",
      owner: "solidjs",
      repo: "solidjs/solid",
      url: "https://github.com/solidjs/solid",
      stars: 31500,
      forks: 900,
      language: "TypeScript",
      reason:
        "React와 유사한 JSX 문법을 사용하지만 Virtual DOM 없이 직접 DOM을 업데이트하는 반응형 라이브러리입니다.",
      similarity: 0.85,
      tags: ["reactive", "jsx", "performance"],
    },
    {
      name: "svelte",
      owner: "sveltejs",
      repo: "sveltejs/svelte",
      url: "https://github.com/sveltejs/svelte",
      stars: 77500,
      forks: 4000,
      language: "TypeScript",
      reason:
        "컴파일 타임에 최적화되는 UI 프레임워크. 런타임 없이 순수 JavaScript로 컴파일됩니다.",
      similarity: 0.72,
      tags: ["compiler", "no-virtual-dom", "lightweight"],
    },
    {
      name: "inferno",
      owner: "infernojs",
      repo: "infernojs/inferno",
      url: "https://github.com/infernojs/inferno",
      stars: 16000,
      forks: 630,
      language: "TypeScript",
      reason:
        "React와 호환되는 API를 제공하면서 더 빠른 성능을 목표로 하는 라이브러리입니다.",
      similarity: 0.88,
      tags: ["performance", "react-like", "virtual-dom"],
    },
    {
      name: "million",
      owner: "aidenybai",
      repo: "aidenybai/million",
      url: "https://github.com/aidenybai/million",
      stars: 15800,
      forks: 500,
      language: "TypeScript",
      reason:
        "React 컴포넌트를 최적화하는 Virtual DOM 대체 라이브러리. 기존 React 프로젝트에 쉽게 통합 가능합니다.",
      similarity: 0.82,
      tags: ["optimization", "react-compatible", "compiler"],
    },
  ],

  // Agentic Flow 정보 (디버깅/개발용)
  warnings: [
    "GitHub API rate limit이 80%에 도달했습니다. 잠시 후 다시 시도하세요.",
    "일부 커밋 히스토리를 가져오는 데 시간이 오래 걸렸습니다 (15초 초과).",
  ],
  flowAdjustments: [
    "대용량 저장소로 인해 파일 분석 범위를 상위 100개 파일로 제한했습니다.",
    "README가 영어가 아니어서 번역 에이전트를 추가로 호출했습니다.",
    "보안 스캔 결과가 캐시되어 있어 재사용했습니다.",
  ],

  // 원본 분석 데이터 (참조용)
  rawAnalysis: {
    repo_id: "facebook/react",
    health_score: 85,
    onboarding_score: 78,
    documentation_quality: 92,
    activity_maintainability: 88,
  },
};

/**
 * 빈 데이터용 Mock (데이터 없을 때 UI 테스트)
 * 일부 섹션만 데이터가 있는 경우를 시뮬레이션
 */
export const mockEmptyAnalysisResult = {
  repositoryUrl: "https://github.com/new-project/example",
  analysisId: "mock_empty_001",

  // 기본 요약 정보만 있음
  summary: {
    score: 45,
    healthStatus: "needs_attention",
    healthLevel: "needs_attention",
    healthLevelDescription:
      "이 프로젝트는 일부 개선이 필요합니다. 문서화나 활동성이 부족할 수 있습니다.",
    healthScoreInterpretation:
      "45점은 평균 이하의 점수입니다. 기여자가 적고 최근 활동이 부족합니다.",
    onboardingScore: 35,
    onboardingLevel: "difficult",
    contributionOpportunities: 0,
    estimatedImpact: "low",
  },

  // 기술 상세 정보 (최소한)
  technicalDetails: {
    stars: 150,
    forks: 12,
    contributors: 3,
    openIssues: 25,
    openPRs: 5,
    totalCommits30d: 2,
    lastCommit: "3개월 전",
    issueCloseRatePct: "20%",
    medianPRMergeDaysText: "14일",
    documentationQuality: 30,
    activityMaintainability: 25,
    onboardingScore: 35,
  },

  // 프로젝트 요약만 있음
  projectSummary: `## 분석 중인 프로젝트
이 프로젝트는 아직 초기 단계에 있으며, 문서화가 부족합니다.

### 현재 상태
- 기여자가 적어 활동이 저조합니다
- README가 간단하여 시작하기 어려울 수 있습니다
- 이슈 응답 시간이 긴 편입니다`,

  // 아래 섹션들은 의도적으로 비어있거나 없음
  recommendations: [], // 빈 배열
  recommendedIssues: [], // 빈 배열
  risks: [], // 빈 배열
  security: null, // 보안 분석 없음
  onboardingPlan: [], // 온보딩 플랜 없음
  similarProjects: [], // 유사 프로젝트 없음
  warnings: [], // 경고 없음
  flowAdjustments: [], // 플로우 조정 없음

  rawAnalysis: {
    repo_id: "new-project/example",
    health_score: 45,
    onboarding_score: 35,
    documentation_quality: 30,
    activity_maintainability: 25,
  },
};

/**
 * Mock 데이터를 사용하여 UI 테스트
 * AnalyzePage.jsx에서 아래와 같이 사용:
 *
 * import { mockAnalysisResult, mockEmptyAnalysisResult } from "../utils/mockAnalysisData";
 *
 * // 컴포넌트 내에서:
 * const [analysisResult, setAnalysisResult] = useState(mockAnalysisResult);
 * const [step, setStep] = useState("chat"); // 바로 chat 화면으로
 */

export default mockAnalysisResult;
