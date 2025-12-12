import api from "./client";

// ============ Analysis API ============

// 캐시 관련 헬퍼 함수
const CACHE_KEY_PREFIX = "odoc_analysis_";
const CACHE_TTL_MS = 60 * 60 * 1000; // 1시간

export const getCachedAnalysis = (repoUrl) => {
  try {
    const key = CACHE_KEY_PREFIX + btoa(repoUrl);
    const cached = sessionStorage.getItem(key);
    if (!cached) return null;

    const { data, timestamp } = JSON.parse(cached);
    if (Date.now() - timestamp > CACHE_TTL_MS) {
      sessionStorage.removeItem(key);
      return null;
    }
    console.log("[Cache] Hit for:", repoUrl);
    return data;
  } catch {
    return null;
  }
};

export const setCachedAnalysis = (repoUrl, data) => {
  try {
    const key = CACHE_KEY_PREFIX + btoa(repoUrl);
    sessionStorage.setItem(
      key,
      JSON.stringify({
        data,
        timestamp: Date.now(),
      })
    );
    console.log("[Cache] Stored for:", repoUrl);
  } catch (e) {
    console.warn("[Cache] Failed to store:", e);
  }
};

/**
 * 저장소 분석 요청
 * @param {string} repoUrl - 저장소 URL
 * @param {string} userMessage - 사용자 메시지 (선택사항)
 * @param {string} priority - 분석 우선순위 (thoroughness, speed)
 * @returns {Promise<Object>} - 분석 결과
 */
export const analyzeRepository = async (
  repoUrl,
  userMessage = null,
  priority = "thoroughness"
) => {
  console.log(
    "[analyzeRepository] repoUrl:",
    repoUrl,
    "userMessage:",
    userMessage,
    "priority:",
    priority
  );

  // 메타 에이전트 요청이 없으면 캐시 확인
  if (!userMessage) {
    const cached = getCachedAnalysis(repoUrl);
    if (cached) {
      console.log("[analyzeRepository] Returning cached result");
      return cached;
    }
  }

  try {
    console.log("[analyzeRepository] Calling API (no cache)");
    const payload = { repo_url: repoUrl };
    if (userMessage) {
      payload.user_message = userMessage;
    }
    payload.priority = priority;

    const response = await api.post("/api/analyze", payload);
    console.log("[analyzeRepository] Response received");

    // 메타 에이전트 요청 없을 때만 캐시에 저장
    if (!userMessage) {
      setCachedAnalysis(repoUrl, response.data);
    }

    return response.data;
  } catch (error) {
    console.error("[analyzeRepository] Failed:", error);
    throw error;
  }
};

/**
 * 여러 저장소 비교 분석
 * @param {Array<string>} repositories - 비교할 저장소 목록 (예: ['owner1/repo1', 'owner2/repo2'])
 * @returns {Promise<Object>} - 비교 분석 결과
 */
export const compareRepositories = async (repositories) => {
  console.log("[compareRepositories] repositories:", repositories);

  try {
    const response = await api.post("/api/analyze/compare", { repositories });
    console.log("[compareRepositories] Response:", response.data);
    return response.data;
  } catch (error) {
    console.error("[compareRepositories] Failed:", error);
    throw error;
  }
};

/**
 * 온보딩 플랜 생성 API
 * @param {string} owner - 저장소 소유자
 * @param {string} repo - 저장소 이름
 * @param {Object} userContext - 사용자 컨텍스트 (경험 레벨, 목표 등)
 * @returns {Promise<Object>} - 온보딩 플랜 결과
 */
export const generateOnboardingPlan = async (owner, repo, userContext = {}) => {
  try {
    console.log("[generateOnboardingPlan] Calling API for:", owner, repo);
    const response = await api.post("/api/agent/task", {
      task_type: "build_onboarding_plan",
      owner,
      repo,
      user_context: userContext,
      use_llm_summary: true,
    });
    console.log("[generateOnboardingPlan] Response:", response.data);
    return response.data;
  } catch (error) {
    console.error("온보딩 플랜 생성 실패:", error);
    throw error;
  }
};

/**
 * PDF 리포트 전송
 * @param {Object} analysisData - 분석 데이터
 * @param {string} userEmail - 사용자 이메일
 * @returns {Promise<Object>} - 전송 결과
 */
export const sendReportPDF = async (analysisData, userEmail) => {
  try {
    const response = await api.post("/api/report/pdf", {
      analysis_data: analysisData,
      email: userEmail,
    });
    return response.data;
  } catch (error) {
    console.error("PDF 리포트 전송 실패:", error);
    throw error;
  }
};

/**
 * 분석 리포트를 Markdown 파일로 내보내기
 * @param {string} reportType - 리포트 유형 (diagnosis | onboarding | security)
 * @param {string} owner - 저장소 소유자
 * @param {string} repo - 저장소 이름
 * @param {Object} data - 리포트 데이터
 * @param {boolean} includeAiTrace - AI 판단 과정 포함 여부
 * @returns {Promise<Blob>} - Markdown 파일 Blob
 */
export const exportReportMarkdown = async (
  reportType,
  owner,
  repo,
  data,
  includeAiTrace = true
) => {
  try {
    const response = await api.post(
      "/api/export/report",
      {
        report_type: reportType,
        owner,
        repo,
        data,
        include_ai_trace: includeAiTrace,
      },
      {
        responseType: "blob",
      }
    );
    return response.data;
  } catch (error) {
    console.error("리포트 내보내기 실패:", error);
    throw error;
  }
};

/**
 * Blob 데이터를 파일로 다운로드
 * @param {Blob} blob - 다운로드할 Blob
 * @param {string} filename - 파일 이름
 */
export const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};
