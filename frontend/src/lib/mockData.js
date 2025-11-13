/**
 * Mock 데이터 및 API 구조
 * 
 * 이 파일은 향후 Backend (Python, LangGraph, MCP Server)와 연동될 때
 * 쉽게 교체 가능하도록 설계된 Mock 데이터 구조입니다.
 * 
 * MCP (Model Context Protocol) Server 호환성을 고려하여 설계되었습니다.
 */

// ==================== 사용자 프로필 타입 ====================

/**
 * @typedef {Object} UserProfile
 * @property {string} repositoryUrl - 분석할 GitHub 저장소 URL
 * @property {string[]} techStack - 사용자의 기술 스택 (예: ['javascript', 'python'])
 * @property {string[]} interests - 관심 분야 (예: ['web', 'ai'])
 * @property {string} experienceLevel - 경험 수준 ('beginner', 'intermediate', 'advanced')
 * @property {string} preferredLanguage - 선호 언어 ('ko', 'en')
 * @property {string} additionalNotes - 추가 정보 (선택)
 */

// ==================== 분석 요청 ====================

/**
 * 분석 요청 API
 * 
 * @param {UserProfile} userProfile - 사용자 프로필
 * @returns {Promise<AnalysisResult>} 분석 결과
 * 
 * MCP Server 엔드포인트: POST /api/analyze
 */
export async function requestAnalysis(userProfile) {
  // Mock 구현 (실제로는 MCP Server 호출)
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(generateMockAnalysisResult(userProfile));
    }, 3000);
  });
}

// ==================== 분석 결과 타입 ====================

/**
 * @typedef {Object} AnalysisResult
 * @property {string} repositoryUrl - 분석된 저장소 URL
 * @property {string} analysisId - 고유 분석 ID
 * @property {AnalysisSummary} summary - 종합 요약
 * @property {Recommendation[]} recommendations - 추천 작업 목록
 * @property {TechnicalDetails} technicalDetails - 기술 상세 정보
 * @property {string} timestamp - 분석 시간 (ISO 8601)
 */

/**
 * @typedef {Object} AnalysisSummary
 * @property {number} score - 종합 점수 (0-100)
 * @property {string} healthStatus - 상태 ('excellent', 'good', 'fair', 'poor')
 * @property {number} contributionOpportunities - 기여 기회 수
 * @property {string} estimatedImpact - 예상 임팩트 ('critical', 'high', 'medium', 'low')
 */

/**
 * @typedef {Object} Recommendation
 * @property {string} id - 추천 작업 ID
 * @property {string} title - 제목
 * @property {string} description - 상세 설명
 * @property {string} difficulty - 난이도 ('easy', 'medium', 'hard')
 * @property {string} estimatedTime - 예상 소요 시간
 * @property {string} impact - 임팩트 ('critical', 'high', 'medium', 'low')
 * @property {string[]} tags - 태그 목록
 * @property {Object} metadata - 추가 메타데이터 (선택)
 */

/**
 * @typedef {Object} TechnicalDetails
 * @property {string[]} languages - 사용 언어
 * @property {string} framework - 주요 프레임워크
 * @property {number} testCoverage - 테스트 커버리지 (%)
 * @property {number} dependencies - 의존성 수
 * @property {string} lastCommit - 마지막 커밋 시간
 * @property {number} openIssues - 미해결 이슈 수
 * @property {number} contributors - 기여자 수
 * @property {Object} securityVulnerabilities - 보안 취약점 정보 (선택)
 */

// ==================== Mock 데이터 생성 함수 ====================

/**
 * Mock 분석 결과 생성
 * (실제로는 MCP Server에서 LangGraph를 통해 생성됨)
 */
function generateMockAnalysisResult(userProfile) {
  return {
    repositoryUrl: userProfile.repositoryUrl,
    analysisId: `analysis_${Date.now()}`,
    timestamp: new Date().toISOString(),
    
    summary: {
      score: 85,
      healthStatus: "excellent",
      contributionOpportunities: 12,
      estimatedImpact: "high",
    },
    
    recommendations: [
      {
        id: "rec_1",
        title: "문서화 개선",
        description:
          "README.md 파일에 설치 가이드와 사용 예제를 추가하면 사용자 경험이 크게 향상됩니다.",
        difficulty: "easy",
        estimatedTime: "2-3시간",
        impact: "high",
        tags: ["documentation", "beginner-friendly"],
        metadata: {
          relatedFiles: ["README.md", "CONTRIBUTING.md"],
          issueNumbers: [],
        },
      },
      {
        id: "rec_2",
        title: "타입스크립트 마이그레이션",
        description:
          "주요 컴포넌트들을 TypeScript로 전환하여 타입 안정성을 높일 수 있습니다.",
        difficulty: "medium",
        estimatedTime: "1-2주",
        impact: "medium",
        tags: ["typescript", "refactoring"],
        metadata: {
          relatedFiles: ["src/components/**/*.jsx"],
          estimatedFilesCount: 25,
        },
      },
      {
        id: "rec_3",
        title: "보안 취약점 수정",
        description:
          "의존성 패키지에서 발견된 2개의 중간 수준 보안 취약점을 업데이트해야 합니다.",
        difficulty: "easy",
        estimatedTime: "1시간",
        impact: "critical",
        tags: ["security", "urgent"],
        metadata: {
          vulnerabilities: [
            { package: "lodash", version: "4.17.15", severity: "medium" },
            { package: "axios", version: "0.21.1", severity: "medium" },
          ],
        },
      },
    ],
    
    technicalDetails: {
      languages: ["JavaScript", "Python", "TypeScript"],
      framework: "React",
      testCoverage: 68,
      dependencies: 45,
      lastCommit: "2일 전",
      openIssues: 8,
      contributors: 12,
      securityVulnerabilities: {
        critical: 0,
        high: 0,
        medium: 2,
        low: 1,
      },
    },
  };
}

// ==================== 채팅 API ====================

/**
 * @typedef {Object} ChatMessage
 * @property {string} id - 메시지 ID
 * @property {string} role - 역할 ('user', 'assistant')
 * @property {string} content - 메시지 내용
 * @property {Date} timestamp - 타임스탬프
 * @property {Object} metadata - 추가 메타데이터 (선택)
 */

/**
 * AI에게 질문 요청
 * 
 * @param {string} message - 사용자 메시지
 * @param {string} analysisId - 분석 ID
 * @param {ChatMessage[]} conversationHistory - 대화 히스토리
 * @returns {Promise<ChatMessage>} AI 응답
 * 
 * MCP Server 엔드포인트: POST /api/chat
 */
export async function sendChatMessage(message, analysisId, conversationHistory) {
  // Mock 구현 (실제로는 MCP Server의 LangGraph Agent 호출)
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        id: `msg_${Date.now()}`,
        role: "assistant",
        content: generateMockAIResponse(message),
        timestamp: new Date(),
        metadata: {
          analysisId,
          model: "gpt-4",
          tokensUsed: 150,
        },
      });
    }, 1500);
  });
}

/**
 * Mock AI 응답 생성
 * (실제로는 LangGraph의 Agent가 컨텍스트를 고려하여 생성)
 */
function generateMockAIResponse(userMessage) {
  const lowerMessage = userMessage.toLowerCase();
  
  if (lowerMessage.includes("보안") || lowerMessage.includes("취약점")) {
    return "현재 저장소에서 2개의 중간 수준 보안 취약점이 발견되었습니다. 주로 의존성 패키지의 오래된 버전에서 발생하고 있으며, `npm update` 또는 `npm audit fix`를 실행하여 해결할 수 있습니다.";
  }
  
  if (lowerMessage.includes("문서") || lowerMessage.includes("readme")) {
    return "README.md 개선은 초급 개발자에게 가장 좋은 첫 기여입니다. 현재 README에는 설치 가이드가 부족하고, 사용 예제가 명확하지 않습니다.";
  }
  
  return "네, 그 부분에 대해 더 자세히 설명드리겠습니다. 구체적으로 어떤 부분이 궁금하신가요?";
}

// ==================== MCP Server 연동 가이드 ====================

/**
 * MCP Server와 연동 시 교체해야 할 함수들:
 * 
 * 1. requestAnalysis(): 
 *    - 엔드포인트: POST /api/analyze
 *    - Body: UserProfile
 *    - Response: AnalysisResult
 * 
 * 2. sendChatMessage():
 *    - 엔드포인트: POST /api/chat
 *    - Body: { message, analysisId, conversationHistory }
 *    - Response: ChatMessage
 * 
 * 연동 예시:
 * 
 * ```javascript
 * import axios from 'axios';
 * 
 * const MCP_SERVER_URL = process.env.REACT_APP_MCP_SERVER_URL || 'http://localhost:8000';
 * 
 * export async function requestAnalysis(userProfile) {
 *   const response = await axios.post(`${MCP_SERVER_URL}/api/analyze`, userProfile);
 *   return response.data;
 * }
 * 
 * export async function sendChatMessage(message, analysisId, conversationHistory) {
 *   const response = await axios.post(`${MCP_SERVER_URL}/api/chat`, {
 *     message,
 *     analysisId,
 *     conversationHistory: conversationHistory.slice(-10), // 최근 10개만 전송
 *   });
 *   return response.data;
 * }
 * ```
 * 
 * LangGraph Agent 구조 권장사항:
 * 
 * 1. GitHub Repository Analyzer Node
 *    - 저장소 정보 수집 (README, 구조, 의존성 등)
 * 
 * 2. Code Quality Analyzer Node
 *    - 코드 품질 분석 (복잡도, 테스트 커버리지 등)
 * 
 * 3. Security Scanner Node
 *    - 보안 취약점 검사 (CVE 데이터베이스 연동)
 * 
 * 4. Recommendation Generator Node
 *    - 사용자 프로필 기반 맞춤형 추천 생성
 * 
 * 5. Conversational Agent Node
 *    - 사용자 질문에 대한 컨텍스트 기반 응답
 */

export default {
  requestAnalysis,
  sendChatMessage,
  generateMockAnalysisResult,
};

