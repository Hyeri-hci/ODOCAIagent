import axios from "axios";

// API 기본 설정
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
// MOCK_MODE 비활성화 - 실제 백엔드 API 사용
const MOCK_MODE = false; // import.meta.env.VITE_MOCK_MODE === "true";

// Axios 인스턴스 생성
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Mock 데이터 (백업용 - MOCK_MODE가 true일 때만 사용)
const mockData = {
  analyze: {
    job_id: "mock-job-123",
    score: 82,
    risks: [
      {
        id: 1,
        type: "security",
        severity: "high",
        description: "의존성 중 보안 취약점이 발견되었습니다",
      },
      {
        id: 2,
        type: "maintenance",
        severity: "medium",
        description: "6개월 이상 업데이트가 없습니다",
      },
    ],
    actions: [
      {
        id: 1,
        title: "의존성 업데이트",
        description: "오래된 npm 패키지를 최신 버전으로 업데이트",
        duration: "2시간",
        priority: "high",
      },
      {
        id: 2,
        title: "보안 취약점 수정",
        description: "Dependabot 알림에 대응하여 취약점 패치",
        duration: "3시간",
        priority: "high",
      },
    ],
    similar: [
      {
        name: "facebook/react",
        description:
          "A declarative, efficient, and flexible JavaScript library",
        stars: 220000,
        similarity_score: 0.85,
        url: "https://github.com/facebook/react",
        why: ["같은 프론트엔드 프레임워크", "컴포넌트 기반 구조"],
      },
    ],
    readme_summary: "이 프로젝트는 React 기반의 모던 웹 애플리케이션입니다.",
    analysis: {
      health_score: 82,
      security_score: 75,
      community_score: 88,
      maintenance_score: 79,
      stars: 1250,
      forks: 234,
    },
  },
  modules: [
    {
      id: 1,
      title: "보안 취약점 스캐너",
      description: "의존성과 코드에서 보안 취약점을 자동으로 탐지",
      icon: "lock",
      features: ["CVE 데이터베이스 연동", "실시간 알림", "자동 패치 제안"],
    },
  ],
  onboarding: [
    {
      id: 1,
      title: "GitHub URL 입력",
      description:
        "분석하고 싶은 오픈소스 프로젝트의 GitHub 리포지토리 URL을 입력하세요",
      icon: "link",
      duration: "10초",
    },
  ],
  benchmarks: [
    {
      id: 1,
      name: "GitHub Insights",
      description: "GitHub의 공식 리포지토리 분석 도구",
      features: ["기본적인 통계", "트렌드 그래프"],
      our_advantages: ["AI 기반 심층 분석", "맞춤형 기여 추천"],
    },
  ],
};

// API 함수들

// 캐시 관련 헬퍼 함수
const CACHE_KEY_PREFIX = "odoc_analysis_";
const CACHE_TTL_MS = 60 * 60 * 1000; // 1시간

const getCachedAnalysis = (repoUrl) => {
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

export const analyzeRepository = async (repoUrl) => {
  console.log("[analyzeRepository] repoUrl:", repoUrl);

  // 캐시 확인
  const cached = getCachedAnalysis(repoUrl);
  if (cached) {
    console.log("[analyzeRepository] Returning cached result");
    return cached;
  }

  if (MOCK_MODE) {
    console.warn("[analyzeRepository] MOCK_MODE is ON! Returning mock data.");
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return mockData.analyze;
  }

  try {
    console.log("[analyzeRepository] Calling API (no cache)");
    const response = await api.post("/api/analyze", { repo_url: repoUrl });
    console.log("[analyzeRepository] Response received");

    // 결과 캐시에 저장
    setCachedAnalysis(repoUrl, response.data);

    return response.data;
  } catch (error) {
    console.error("[analyzeRepository] Failed:", error);
    throw error;
  }
};

export const createMilestone = async (actions, analysis) => {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return {
      status: "created",
      milestone_id: "ms_mock_123",
      calendarEvents: actions.map((id) => ({
        id: `evt_${id}`,
        title: `작업 ${id}`,
        start_time: new Date().toISOString(),
      })),
      todoItems: actions.map((id) => ({
        id: `todo_${id}`,
        title: `할 일 ${id}`,
        completed: false,
      })),
    };
  }

  try {
    const response = await api.post("/api/milestone", { actions, analysis });
    return response.data;
  } catch (error) {
    console.error("마일스톤 생성 실패:", error);
    throw error;
  }
};

export const sendReport = async (report, actions) => {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return {
      status: "sent",
      message_id: "msg_mock_123",
      sent_at: new Date().toISOString(),
    };
  }

  try {
    const response = await api.post("/api/report/send", {
      report,
      actions,
      channel: "kakao",
    });
    return response.data;
  } catch (error) {
    console.error("리포트 전송 실패:", error);
    throw error;
  }
};

export const getModules = async () => {
  if (MOCK_MODE) {
    return { modules: mockData.modules };
  }

  try {
    const response = await api.get("/api/modules");
    return response.data;
  } catch (error) {
    console.error("모듈 정보 가져오기 실패:", error);
    throw error;
  }
};

export const getOnboarding = async () => {
  if (MOCK_MODE) {
    return { onboarding: mockData.onboarding };
  }

  try {
    const response = await api.get("/api/onboarding");
    return response.data;
  } catch (error) {
    console.error("온보딩 정보 가져오기 실패:", error);
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
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    return {
      ok: true,
      data: {
        onboarding_plan: [
          {
            week: 1,
            goals: ["프로젝트 구조 이해", "개발 환경 설정"],
            tasks: ["README.md 읽기", "로컬 환경 설정", "첫 번째 테스트 실행"],
          },
          {
            week: 2,
            goals: ["코드베이스 탐색", "이슈 파악"],
            tasks: [
              "good first issue 확인",
              "관련 코드 분석",
              "PR 프로세스 이해",
            ],
          },
        ],
      },
    };
  }

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

export const getBenchmarks = async () => {
  if (MOCK_MODE) {
    return { benchmarks: mockData.benchmarks };
  }

  try {
    const response = await api.get("/api/benchmarks");
    return response.data;
  } catch (error) {
    console.error("벤치마크 정보 가져오기 실패:", error);
    throw error;
  }
};

// Kakao OAuth2 관련 함수들
export const getKakaoAuthUrl = () => {
  const KAKAO_CLIENT_ID =
    import.meta.env.VITE_KAKAO_CLIENT_ID || "your_kakao_client_id";
  const REDIRECT_URI =
    import.meta.env.VITE_KAKAO_REDIRECT_URI ||
    "http://localhost:5173/auth/kakao/callback";

  return `https://kauth.kakao.com/oauth/authorize?client_id=${KAKAO_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code`;
};

export const kakaoLogin = async (code) => {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return {
      access_token: "mock_access_token",
      user: {
        id: 12345,
        email: "user@example.com",
        nickname: "테스트 사용자",
      },
    };
  }

  try {
    const response = await api.post("/api/auth/kakao/login", { code });
    return response.data;
  } catch (error) {
    console.error("카카오 로그인 실패:", error);
    throw error;
  }
};

export const checkKakaoAuth = async () => {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    // Mock: 50% 확률로 로그인되어 있다고 가정
    const isLoggedIn = Math.random() > 0.5;
    if (isLoggedIn) {
      return {
        authenticated: true,
        user: {
          email: "user@example.com",
          nickname: "테스트 사용자",
        },
      };
    }
    return { authenticated: false };
  }

  try {
    const response = await api.get("/api/auth/kakao/check");
    return response.data;
  } catch (error) {
    console.error("카카오 인증 확인 실패:", error);
    return { authenticated: false };
  }
};

export const sendReportPDF = async (analysisData, userEmail) => {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    return {
      status: "success",
      message: "PDF 리포트가 이메일로 전송되었습니다",
      email: userEmail,
      pdf_url: "https://example.com/reports/mock-report.pdf",
      sent_at: new Date().toISOString(),
    };
  }

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
 * AI 어시스턴트와 채팅
 * @param {string} message - 사용자 메시지
 * @param {Object} context - 분석 컨텍스트
 * @param {string} context.repoUrl - 분석 중인 저장소 URL
 * @param {Object} context.analysisResult - 분석 결과
 * @param {Array} conversationHistory - 이전 대화 기록
 * @returns {Promise<{ok: boolean, message: string, error?: string}>}
 */
export const sendChatMessage = async (
  message,
  context = {},
  conversationHistory = []
) => {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return {
      ok: true,
      message: getMockChatResponse(message, context),
    };
  }

  try {
    const response = await api.post("/api/chat", {
      message,
      repo_url: context.repoUrl || null,
      analysis_context: context.analysisResult || null,
      conversation_history: conversationHistory.map((msg) => ({
        role: msg.type === "user" ? "user" : "assistant",
        content: msg.content,
      })),
    });
    return response.data;
  } catch (error) {
    console.error("채팅 실패:", error);
    // Fallback response
    return {
      ok: false,
      message:
        "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
      error: error.message,
    };
  }
};

// Mock 채팅 응답 생성
function getMockChatResponse(message, context) {
  const messageLower = message.toLowerCase();

  if (
    messageLower.includes("기여") ||
    messageLower.includes("contribute") ||
    messageLower.includes("어떻게")
  ) {
    return (
      "오픈소스 기여를 시작하는 방법을 안내해드릴게요:\n\n" +
      "1. **저장소 Fork**: GitHub에서 저장소를 Fork합니다\n" +
      "2. **로컬 Clone**: `git clone <your-fork-url>`\n" +
      "3. **브랜치 생성**: `git checkout -b feature/your-feature`\n" +
      "4. **변경 사항 작업**: 코드 수정 또는 문서 개선\n" +
      "5. **커밋 & 푸시**: `git commit -m '설명'` 후 `git push`\n" +
      "6. **PR 생성**: GitHub에서 Pull Request를 생성합니다\n\n" +
      "처음이라면 'good first issue' 라벨이 붙은 이슈부터 시작하는 것을 추천드립니다!"
    );
  }

  if (
    messageLower.includes("점수") ||
    messageLower.includes("score") ||
    messageLower.includes("평가")
  ) {
    const score = context.analysisResult?.health_score || 0;
    let scoreComment = "";
    if (score >= 80) {
      scoreComment = `현재 점수 ${score}점은 상위 10% 수준으로 매우 건강한 프로젝트입니다.`;
    } else if (score >= 60) {
      scoreComment = `현재 점수 ${score}점은 평균 수준입니다. 문서화나 활동성 개선으로 점수를 높일 수 있습니다.`;
    } else {
      scoreComment = `현재 점수 ${score}점은 개선이 필요합니다. 문서 보완과 이슈 해결에 집중하세요.`;
    }
    return (
      `점수 해석을 도와드릴게요:\n\n${scoreComment}\n\n` +
      "**점수 구성 요소:**\n" +
      "- 문서 품질: README 완성도, 기여 가이드 유무\n" +
      "- 활동성: 최근 커밋, PR 병합 속도, 이슈 해결률\n" +
      "- 온보딩 용이성: 신규 기여자가 시작하기 쉬운 정도"
    );
  }

  return (
    "궁금한 점에 대해 답변드릴게요. 다음과 같은 주제로 질문해주시면 더 구체적인 답변을 드릴 수 있습니다:\n\n" +
    "- **기여 방법**: 오픈소스에 어떻게 기여하나요?\n" +
    "- **문서화**: README를 어떻게 개선하나요?\n" +
    "- **보안**: 취약점은 어떻게 해결하나요?\n" +
    "- **점수 해석**: 분석 점수의 의미는 무엇인가요?\n\n" +
    "자유롭게 질문해주세요!"
  );
}

/**
 * AI 어시스턴트와 스트리밍 채팅
 * 타이핑 효과를 위해 SSE로 토큰 단위 응답을 받습니다.
 *
 * @param {string} message - 사용자 메시지
 * @param {Object} context - 분석 컨텍스트
 * @param {Array} conversationHistory - 이전 대화 기록
 * @param {Function} onToken - 토큰 수신 콜백 (token: string) => void
 * @param {Function} onComplete - 완료 콜백 (fullMessage: string, isFallback: boolean) => void
 * @param {Function} onError - 에러 콜백 (error: string) => void
 * @returns {Function} 스트림 취소 함수
 */
export const sendChatMessageStream = (
  message,
  context = {},
  conversationHistory = [],
  onToken,
  onComplete,
  onError
) => {
  // Mock 모드에서는 타이핑 시뮬레이션
  if (MOCK_MODE) {
    const mockResponse = getMockChatResponse(message, context);
    let fullMessage = "";
    let index = 0;

    const intervalId = setInterval(() => {
      if (index < mockResponse.length) {
        // 단어 단위로 전송
        let endIndex = mockResponse.indexOf(" ", index);
        if (endIndex === -1) endIndex = mockResponse.length;

        const token = mockResponse.slice(index, endIndex + 1);
        fullMessage += token;
        onToken?.(token);
        index = endIndex + 1;
      } else {
        clearInterval(intervalId);
        onComplete?.(fullMessage, false);
      }
    }, 50);

    return () => clearInterval(intervalId);
  }

  // 실제 SSE 스트리밍
  const abortController = new AbortController();

  const fetchStream = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          repo_url: context.repoUrl || null,
          analysis_context: context.analysisResult || null,
          conversation_history: conversationHistory.map((msg) => ({
            role: msg.type === "user" ? "user" : "assistant",
            content: msg.content,
          })),
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullMessage = "";
      let isFallback = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "token") {
                fullMessage += data.content;
                isFallback = data.is_fallback || isFallback;
                onToken?.(data.content);
              } else if (data.type === "done") {
                onComplete?.(fullMessage, isFallback);
                return;
              } else if (data.type === "error") {
                onError?.(data.content);
                return;
              }
            } catch (e) {
              // JSON 파싱 실패 무시
            }
          }
        }
      }

      // 스트림 종료 시 완료 처리
      if (fullMessage) {
        onComplete?.(fullMessage, isFallback);
      }
    } catch (error) {
      if (error.name === "AbortError") {
        console.log("[Chat Stream] Aborted");
        return;
      }
      console.error("[Chat Stream] Error:", error);
      onError?.(error.message || "스트리밍 채팅 중 오류가 발생했습니다.");
    }
  };

  fetchStream();

  // 취소 함수 반환
  return () => abortController.abort();
};

export default api;
