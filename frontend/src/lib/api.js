import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";
const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === "true";

// create Axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Mock mode 설정
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
      icon: "🔒",
      features: ["CVE 데이터베이스 연동", "실시간 알림", "자동 패치 제안"],
    },
  ],
  onboarding: [
    {
      id: 1,
      title: "GitHub URL 입력",
      description:
        "분석하고 싶은 오픈소스 프로젝트의 GitHub 리포지토리 URL을 입력하세요",
      icon: "🔗",
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

// API Functions

// repository analysis 요청 - @Pparam {string} repoUrl - GitHub URL
export const analyzeRepository = async (repoUrl) => {
  if (MOCK_MODE) {
    console.log("MOCK_MODE: Returning mock analyze data");
    await new Promise((resolve) => setTimeout(resolve, 2000)); // 2초 딜레이
    return mockData.analyze;
  }

  // 실제 API 호출
  try {
    const response = await api.post("/api/analyze", { repo_url: repoUrl });
    return response.data;
  } catch (error) {
    console.error("Error analyzing repository:", error);
    throw error;
  }
};

/**
 * create Milestone
 * @param {number[]} actions - 선택된 작업 ID 배열
 * @param {object} analysis - 분석 결과 객체
 */
export const createMilestone = async (actions, analysis) => {
  if (MOCK_MODE) {
    console.log("MOCK_MODE: Returning mock milestone creation");
    await new Promise((resolve) => setTimeout(resolve, 1000)); // 1초 딜레이
    return {
      status: "success",
      milestone_id: "ms_mock_123",
      message: "마일스톤이 성공적으로 생성되었습니다.",
    };
  }
  try {
    const response = await api.post("/api/milestone", {
      actions,
      analysis,
    });
    return response.data;
  } catch (error) {
    console.error("Error creating milestone:", error);
    throw error;
  }
};

/**
 * send Report
 * @param {string} report - 생성된 리포트 내용
 * @param {number[]} actions - 선택된 작업 ID 배열
 */
export const sendReport = async (report, actions) => {
  if (MOCK_MODE) {
    console.log("MOCK_MODE: Returning mock report sending");
    await new Promise((resolve) => setTimeout(resolve, 1000)); // 1초 딜레이
    return {
      status: "success",
      message: "리포트가 성공적으로 전송되었습니다.",
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
    console.error("Error sending report:", error);
    throw error;
  }
};

// 기타 API 함수들 (모듈 정보, 온보딩 단계, 벤치마크 비교 등)
export const getModules = async () => {
  if (MOCK_MODE) {
    console.log("MOCK_MODE: Returning mock modules data");
    return { modules: mockData.modules };
  }

  try {
    const response = await api.get("/api/modules");
    return response.data;
  } catch (error) {
    console.error("Error fetching modules:", error);
    throw error;
  }
};

export const getOnboarding = async () => {
  if (MOCK_MODE) {
    console.log("MOCK_MODE: Returning mock onboarding data");
    return { onboarding: mockData.onboarding };
  }

  try {
    const response = await api.get("/api/onboarding");
    return response.data;
  } catch (error) {
    console.error("Error fetching onboarding data:", error);
    throw error;
  }
};

export const getBenchmarks = async () => {
  if (MOCK_MODE) {
    console.log("MOCK_MODE: Returning mock benchmarks data");
    return { benchmarks: mockData.benchmarks };
  }

  try {
    const response = await api.get("/api/benchmarks");
    return response.data;
  } catch (error) {
    console.error("Error fetching benchmarks data:", error);
    throw error;
  }
};

export default api;
