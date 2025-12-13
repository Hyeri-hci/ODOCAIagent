// ============ Central API Export Module ============
// 모든 API 함수를 한 곳에서 재export
// 사용법:
//   import { sendChatMessageV2, analyzeRepository } from '@/lib/api';

// Client & Base Configuration
export { default as api, API_BASE_URL } from "./client";

// Chat APIs (V2 - Session-based)
export {
  sendChatMessageV2,
  sendChatMessageStreamV2,
  getSessionInfo,
  listActiveSessions,
  deleteSession,
} from "./chat";

// Analysis & Repository APIs
export {
  analyzeRepository,
  compareRepositories,
  generateOnboardingPlan,
  sendReportPDF,
  // Cache helpers
  getCachedAnalysis,
  setCachedAnalysis,
} from "./analysis";

