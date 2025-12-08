import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Send, ChevronLeft, ChevronRight, History } from "lucide-react";
import AnalysisReportSection from "./AnalysisReportSection";
import OnboardingPlanSection from "./OnboardingPlanSection";
import {
  sendChatMessage,
  sendChatMessageStream,
  analyzeRepository,
  generateOnboardingPlan,
  compareRepositories,
} from "../../lib/api";

// 스트리밍 모드 설정 (true: SSE 스트리밍, false: 기존 REST API)
const USE_STREAM_MODE = true;

const AnalysisChat = ({
  userProfile,
  analysisResult: initialAnalysisResult,
  onAnalysisUpdate,  // 새 분석 결과를 부모로 전달하는 콜백
}) => {
  // 초기 메시지: onboardingPlan이 있으면 간단한 안내, 없으면 기본 메시지
  const getInitialMessages = () => {
    // 온보딩 플랜이 있으면 간단한 안내 메시지만 표시 (상세 내용은 Report 영역에서)
    if (initialAnalysisResult?.onboardingPlan?.length > 0) {
      return [
        {
          id: "initial",
          role: "assistant",
          content: `${userProfile.repositoryUrl} 저장소에 대한 **온보딩 가이드**가 생성되었습니다!\n\n오른쪽 Report 영역에서 **${initialAnalysisResult.onboardingPlan.length}주 학습 플랜**을 확인해 보세요.`,
          timestamp: new Date(),
        },
      ];
    }

    // 기본 메시지
    return [
      {
        id: "initial",
        role: "assistant",
        content: `${userProfile.repositoryUrl} 저장소에 대한 분석이 완료되었습니다! 아래에서 상세 리포트를 확인하실 수 있습니다.`,
        timestamp: new Date(),
      },
    ];
  };

  const [messages, setMessages] = useState(getInitialMessages());

  const [analysisResult, setAnalysisResult] = useState(initialAnalysisResult);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState(""); // 스트리밍 중인 메시지
  const [isStreaming, setIsStreaming] = useState(false); // 스트리밍 중 여부
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false); // 온보딩 플랜 생성 중
  const [planGenerateError, setPlanGenerateError] = useState(null); // 플랜 생성 오류
  const [isComparing, setIsComparing] = useState(false); // 비교 분석 중
  const [compareResult, setCompareResult] = useState(null); // 비교 분석 결과
  const [showCompareSelector, setShowCompareSelector] = useState(false); // 비교 선택 패널 표시
  const [selectedForCompare, setSelectedForCompare] = useState(new Set()); // 비교 선택된 저장소

  // 분석 히스토리 관리
  const [analysisHistory, setAnalysisHistory] = useState(() => {
    // 초기 분석 결과가 있으면 히스토리에 추가
    return initialAnalysisResult ? [initialAnalysisResult] : [];
  });
  const [currentHistoryIndex, setCurrentHistoryIndex] = useState(0);

  const streamCancelRef = useRef(null); // 스트림 취소 함수 참조
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  // 컴포넌트 언마운트 시 스트림 취소
  useEffect(() => {
    return () => {
      if (streamCancelRef.current) {
        streamCancelRef.current();
      }
    };
  }, []);

  // 히스토리 네비게이션 함수
  const canGoBack = currentHistoryIndex > 0;
  const canGoForward = currentHistoryIndex < analysisHistory.length - 1;

  const goToPreviousAnalysis = () => {
    if (canGoBack) {
      const newIndex = currentHistoryIndex - 1;
      setCurrentHistoryIndex(newIndex);
      setAnalysisResult(analysisHistory[newIndex]);
      setPlanGenerateError(null);
    }
  };

  const goToNextAnalysis = () => {
    if (canGoForward) {
      const newIndex = currentHistoryIndex + 1;
      setCurrentHistoryIndex(newIndex);
      setAnalysisResult(analysisHistory[newIndex]);
      setPlanGenerateError(null);
    }
  };

  // 새 분석 결과를 히스토리에 추가
  const addToHistory = (newResult) => {
    setAnalysisHistory((prev) => {
      // 현재 위치 이후의 히스토리는 삭제하고 새 결과 추가
      const newHistory = [...prev.slice(0, currentHistoryIndex + 1), newResult];
      return newHistory;
    });
    setCurrentHistoryIndex((prev) => prev + 1);
  };

  // GitHub URL에서 owner/repo 파싱
  const parseGitHubUrl = (url) => {
    if (!url) return null;
    const match = url.match(/github\.com\/([\w-]+)\/([\w.-]+)/i);
    if (match) {
      return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
    }
    return null;
  };

  // 온보딩 플랜 생성 핸들러 (난이도 파라미터 추가)
  const handleGenerateOnboardingPlan = async (difficulty = "beginner") => {
    if (!analysisResult?.repositoryUrl) {
      setPlanGenerateError("저장소 정보가 없습니다.");
      return;
    }

    const repoInfo = parseGitHubUrl(analysisResult.repositoryUrl);
    if (!repoInfo) {
      setPlanGenerateError("유효하지 않은 저장소 URL입니다.");
      return;
    }

    setIsGeneratingPlan(true);
    setPlanGenerateError(null);

    try {
      const response = await generateOnboardingPlan(
        repoInfo.owner,
        repoInfo.repo,
        {
          experience_level: difficulty,
          interests: userProfile?.interests || [],
          language: "korean", // 한국어로 생성 요청
        }
      );

      console.log("온보딩 플랜 응답:", response);

      // 응답에서 온보딩 플랜 추출 (다양한 응답 구조 지원)
      const plan =
        response?.data?.onboarding_plan ||
        response?.result?.onboarding_plan ||
        response?.onboarding_plan ||
        response?.plan;

      if (plan && Array.isArray(plan) && plan.length > 0) {
        setAnalysisResult((prev) => ({
          ...prev,
          onboardingPlan: plan,
        }));
      } else {
        console.error(
          "플랜 추출 실패. 응답 구조:",
          JSON.stringify(response, null, 2)
        );
        setPlanGenerateError("플랜 생성에 실패했습니다. 다시 시도해주세요.");
      }
    } catch (error) {
      console.error("온보딩 플랜 생성 오류:", error);
      setPlanGenerateError(
        error.response?.data?.detail ||
        error.message ||
        "플랜 생성 중 오류가 발생했습니다."
      );
    } finally {
      setIsGeneratingPlan(false);
    }
  };

  // 비교 선택 토글
  const toggleCompareSelection = (repoKey) => {
    setSelectedForCompare((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(repoKey)) {
        newSet.delete(repoKey);
      } else if (newSet.size < 2) {
        newSet.add(repoKey);
      }
      return newSet;
    });
  };

  // 히스토리에서 유니크한 저장소 목록 추출
  const getUniqueRepositories = () => {
    const seen = new Set();
    return analysisHistory
      .map((result, index) => {
        const url = result.repositoryUrl;
        const info = parseGitHubUrl(url);
        if (!info) return null;
        const repoKey = `${info.owner}/${info.repo}`;
        if (seen.has(repoKey)) return null;
        seen.add(repoKey);
        return {
          key: repoKey,
          owner: info.owner,
          repo: info.repo,
          healthScore: result.healthScore || 0,
          index,
        };
      })
      .filter(Boolean);
  };

  // 비교 분석 핸들러
  const handleCompareAnalysis = async () => {
    const repositories = Array.from(selectedForCompare);

    if (repositories.length !== 2) {
      const errorMessage = {
        id: `compare_error_${Date.now()}`,
        role: "assistant",
        content: "비교하려면 2개의 저장소를 선택해주세요.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      return;
    }

    setIsComparing(true);
    setCompareResult(null);
    setShowCompareSelector(false);

    try {
      console.log("[handleCompareAnalysis] repositories:", repositories);
      const response = await compareRepositories(repositories);
      console.log("비교 분석 결과:", response);

      if (response.ok) {
        setCompareResult(response);

        // Backend에서 생성한 비교 분석 메시지 표시
        const compareMessage = {
          id: `compare_${Date.now()}`,
          role: "assistant",
          content: response.summary || `${repositories[0]}과 ${repositories[1]}의 비교 분석이 완료되었습니다.`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, compareMessage]);
      } else {
        const errorMessage = {
          id: `compare_error_${Date.now()}`,
          role: "assistant",
          content: `비교 분석 중 오류가 발생했습니다: ${response.error || '결과를 가져올 수 없습니다'}`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error("비교 분석 오류:", error);
      const errorMessage = {
        id: `compare_error_${Date.now()}`,
        role: "assistant",
        content: `비교 분석 중 오류가 발생했습니다: ${error.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsComparing(false);
      setSelectedForCompare(new Set());
    }
  };

  // GitHub URL 감지 함수
  const detectGitHubUrl = (message) => {
    // github.com 포함된 전체 URL
    const fullUrlMatch = message.match(
      /(?:https?:\/\/)?(?:www\.)?github\.com\/([\w-]+\/[\w.-]+)/i
    );
    if (fullUrlMatch) {
      return fullUrlMatch[0].startsWith("http")
        ? fullUrlMatch[0]
        : `https://${fullUrlMatch[0]}`;
    }

    // 간단한 owner/repo 형식 (공백 없이)
    const trimmed = message.trim();
    const shortMatch = trimmed.match(/^([\w-]+)\/([\w.-]+)$/);
    if (shortMatch) {
      return `https://github.com/${shortMatch[0]}`;
    }

    return null;
  };

  // API 응답을 프론트엔드 형식으로 변환 (AnalyzePage.jsx와 동일한 로직)
  const transformApiResponse = (apiResponse, repositoryUrl) => {
    const analysis = apiResponse.analysis || apiResponse;

    return {
      repositoryUrl: repositoryUrl,
      analysisId:
        apiResponse.job_id || analysis.repo_id || `analysis_${Date.now()}`,
      summary: {
        score: apiResponse.score || analysis.health_score || 0,
        healthStatus:
          analysis.health_level === "good"
            ? "excellent"
            : analysis.health_level === "warning"
              ? "moderate"
              : "needs-attention",
        contributionOpportunities: (apiResponse.recommended_issues || [])
          .length,
        estimatedImpact:
          (analysis.health_score || 0) >= 70
            ? "high"
            : (analysis.health_score || 0) >= 50
              ? "medium"
              : "low",
      },
      projectSummary:
        apiResponse.readme_summary ||
        analysis.summary_for_user ||
        `이 저장소의 건강 점수는 ${apiResponse.score || analysis.health_score
        }점입니다.`,
      recommendations: [
        // 기존 actions
        ...(apiResponse.actions || []).map((action, idx) => ({
          id: `action_${idx + 1}`,
          title: action.title,
          description: action.description,
          difficulty: action.priority === "high" ? "easy" : "medium",
          estimatedTime: action.duration,
          impact: action.priority,
          tags: action.url ? ["good-first-issue"] : ["improvement"],
          url: action.url,
          issueNumber: action.issue_number,
        })),
        // recommended_issues에서 추가 (analysis fallback 포함)
        ...(
          apiResponse.recommended_issues ||
          analysis.recommended_issues ||
          []
        ).map((issue, idx) => ({
          id: `issue_${issue.number || idx}`,
          title: issue.title,
          description: `GitHub Issue #${issue.number}`,
          difficulty: issue.labels?.some(
            (l) =>
              l.toLowerCase().includes("easy") ||
              l.toLowerCase().includes("first")
          )
            ? "easy"
            : "medium",
          estimatedTime: "2-4시간",
          impact: "medium",
          tags: issue.labels || ["issue"],
          url: issue.url,
          issueNumber: issue.number,
        })),
      ],
      risks: (apiResponse.risks || []).map((risk, idx) => ({
        id: `risk_${idx + 1}`,
        type: risk.type || "general",
        severity: risk.severity || "medium",
        description: risk.description,
      })),
      technicalDetails: {
        languages: [],
        framework: "Unknown",
        testCoverage: 0,
        dependencies: analysis.dependency_complexity_score || 0,
        lastCommit: analysis.days_since_last_commit
          ? `${analysis.days_since_last_commit}일 전`
          : "알 수 없음",
        openIssues: analysis.open_issues_count || 0,
        contributors: analysis.unique_contributors || 0,
        stars: analysis.stars || 0,
        forks: analysis.forks || 0,
        documentationQuality: analysis.documentation_quality || 0,
        activityMaintainability: analysis.activity_maintainability || 0,
      },
      relatedProjects: [],
      rawAnalysis: analysis,
      // 온보딩 플랜 (API 응답에서 가져오기)
      onboardingPlan:
        apiResponse.onboarding_plan || analysis.onboarding_plan || null,
    };
  };

  // Mock: 다른 프로젝트 분석 결과 생성 (더 이상 사용되지 않음, 백업용으로 유지)
  const generateMockAnalysisForProject = (projectUrl) => {
    const projectName = projectUrl.split("/").slice(-2).join("/");

    // Mock 데이터 (실제로는 Backend에서 분석)
    const mockProjects = {
      "microsoft/vscode": {
        score: 92,
        projectSummary:
          "Visual Studio Code는 TypeScript로 작성된 대규모 오픈소스 코드 에디터입니다. Electron 프레임워크를 기반으로 하며, 확장 가능한 아키텍처와 우수한 개발자 경험을 제공합니다.",
        recommendations: [
          {
            id: "vscode_1",
            title: "확장 프로그램 개발",
            description:
              "VS Code의 API를 활용하여 새로운 확장 프로그램을 개발할 수 있습니다.",
            difficulty: "medium",
            estimatedTime: "1주",
            impact: "high",
            tags: ["extension", "typescript"],
          },
          {
            id: "vscode_2",
            title: "번역 기여",
            description:
              "한국어 번역을 개선하여 한국 개발자들의 경험을 향상시킬 수 있습니다.",
            difficulty: "easy",
            estimatedTime: "3-4시간",
            impact: "medium",
            tags: ["i18n", "translation"],
          },
        ],
        risks: [
          {
            id: "vscode_risk_1",
            type: "general",
            severity: "low",
            description:
              "일부 확장 프로그램 API 문서가 업데이트되지 않았습니다.",
          },
        ],
        technicalDetails: {
          languages: ["TypeScript", "JavaScript"],
          framework: "Electron",
          testCoverage: 85,
          contributors: 1500,
          stars: 150000,
          forks: 25000,
        },
        relatedProjects: [
          {
            name: "atom/atom",
            description: "Electron 기반 해커블 텍스트 에디터",
            score: 78,
            stars: 60000,
            match: 85,
            recommendationReason:
              "VS Code와 동일하게 Electron 프레임워크를 사용하는 텍스트 에디터입니다. 아키텍처 설계와 플러그인 시스템을 비교 학습하기 좋으며, 커뮤니티 기여 방법을 익히기에 적합합니다.",
          },
          {
            name: "microsoft/TypeScript",
            description: "JavaScript에 정적 타입을 추가한 프로그래밍 언어",
            score: 90,
            stars: 95000,
            match: 80,
            recommendationReason:
              "VS Code가 TypeScript로 작성되어 있어 TypeScript 언어 자체에 기여하면 에디터 개발에도 도움이 됩니다. 컴파일러와 타입 시스템에 대한 깊은 이해를 얻을 수 있습니다.",
          },
          {
            name: "theia-ide/theia",
            description: "클라우드 및 데스크톱 IDE 플랫폼",
            score: 82,
            stars: 19000,
            match: 78,
            recommendationReason:
              "VS Code의 오픈소스 대안으로, 비슷한 확장 API를 제공합니다. 클라우드 IDE 개발과 분산 아키텍처에 관심이 있다면 적합한 프로젝트입니다.",
          },
          {
            name: "neovim/neovim",
            description: "Vim 기반 확장 가능한 텍스트 에디터",
            score: 85,
            stars: 75000,
            match: 70,
            recommendationReason:
              "다른 접근 방식의 에디터 개발을 경험할 수 있습니다. Lua 스크립팅과 플러그인 아키텍처를 통해 에디터 확장성에 대한 폭넓은 시각을 얻을 수 있습니다.",
          },
        ],
      },
      "tensorflow/tensorflow": {
        score: 88,
        projectSummary:
          "TensorFlow는 Google이 개발한 머신러닝 프레임워크입니다. Python, C++, JavaScript 등 다양한 언어를 지원하며, 대규모 머신러닝 모델 학습에 최적화되어 있습니다.",
        recommendations: [
          {
            id: "tf_1",
            title: "튜토리얼 예제 추가",
            description:
              "한국어 튜토리얼 예제를 추가하여 한국 개발자들의 접근성을 높일 수 있습니다.",
            difficulty: "easy",
            estimatedTime: "4-5시간",
            impact: "high",
            tags: ["documentation", "tutorial"],
          },
          {
            id: "tf_2",
            title: "모델 최적화",
            description:
              "모바일 디바이스를 위한 모델 최적화 작업에 기여할 수 있습니다.",
            difficulty: "hard",
            estimatedTime: "2-3주",
            impact: "high",
            tags: ["optimization", "mobile"],
          },
        ],
        risks: [
          {
            id: "tf_risk_1",
            type: "general",
            severity: "medium",
            description:
              "일부 deprecated API가 아직 코드베이스에 남아있습니다.",
          },
        ],
        technicalDetails: {
          languages: ["Python", "C++", "JavaScript"],
          framework: "TensorFlow",
          testCoverage: 78,
          contributors: 2800,
          stars: 180000,
          forks: 88000,
        },
        relatedProjects: [
          {
            name: "pytorch/pytorch",
            description: "Python 기반 딥러닝 프레임워크",
            score: 90,
            stars: 75000,
            match: 88,
            recommendationReason:
              "TensorFlow와 함께 가장 인기 있는 딥러닝 프레임워크입니다. 동적 계산 그래프와 Pythonic한 API 설계를 통해 ML 프레임워크의 다양한 접근 방식을 비교 학습할 수 있습니다.",
          },
          {
            name: "keras-team/keras",
            description: "고수준 신경망 API",
            score: 85,
            stars: 60000,
            match: 82,
            recommendationReason:
              "TensorFlow의 공식 고수준 API로 통합되었습니다. 사용자 친화적인 API 설계와 문서화 작업에 기여하면서 ML 라이브러리 개발을 경험할 수 있습니다.",
          },
          {
            name: "scikit-learn/scikit-learn",
            description: "Python 머신러닝 라이브러리",
            score: 88,
            stars: 57000,
            match: 75,
            recommendationReason:
              "전통적인 머신러닝 알고리즘에 집중한 라이브러리입니다. TensorFlow보다 진입 장벽이 낮으며, 알고리즘 구현과 최적화에 대한 실전 경험을 쌓기 좋습니다.",
          },
          {
            name: "huggingface/transformers",
            description: "최신 NLP 모델 라이브러리",
            score: 92,
            stars: 120000,
            match: 80,
            recommendationReason:
              "TensorFlow와 PyTorch를 모두 지원하는 최신 NLP 모델 라이브러리입니다. 최신 AI 모델 활용과 배포에 관심이 있다면 매우 유용하며, 활발한 커뮤니티에서 협업 경험을 쌓을 수 있습니다.",
          },
        ],
      },
    };

    // 프로젝트 이름에서 매칭
    const normalizedName = projectName.toLowerCase();
    for (const [key, value] of Object.entries(mockProjects)) {
      if (normalizedName.includes(key.toLowerCase())) {
        return {
          repositoryUrl: projectUrl,
          analysisId: `analysis_${Date.now()}`,
          timestamp: new Date().toISOString(),
          summary: {
            score: value.score,
            healthStatus: value.score >= 80 ? "excellent" : "good",
            contributionOpportunities: value.recommendations.length,
            estimatedImpact: "high",
          },
          projectSummary: value.projectSummary,
          recommendations: value.recommendations,
          risks: value.risks,
          technicalDetails: value.technicalDetails,
          relatedProjects: value.relatedProjects || [],
        };
      }
    }

    // 기본 Mock 데이터
    return {
      repositoryUrl: projectUrl,
      analysisId: `analysis_${Date.now()}`,
      summary: {
        score: 75,
        healthStatus: "good",
        contributionOpportunities: 5,
        estimatedImpact: "medium",
      },
      projectSummary: `${projectName} 저장소에 대한 분석이 완료되었습니다. 전반적으로 양호한 상태의 프로젝트입니다.`,
      recommendations: [
        {
          id: "generic_1",
          title: "문서화 개선",
          description:
            "프로젝트 문서를 개선하여 새로운 기여자들의 진입 장벽을 낮출 수 있습니다.",
          difficulty: "easy",
          estimatedTime: "3-4시간",
          impact: "medium",
          tags: ["documentation"],
        },
      ],
      risks: [],
      technicalDetails: {
        languages: ["JavaScript", "TypeScript"],
        framework: "Unknown",
        testCoverage: 65,
        contributors: 50,
        stars: 5000,
        forks: 1000,
      },
      relatedProjects: [
        {
          name: "facebook/react",
          description:
            "사용자 인터페이스를 구축하기 위한 자바스크립트 라이브러리",
          score: 85,
          stars: 220000,
          match: 75,
          recommendationReason:
            "React는 가장 인기 있는 JavaScript UI 라이브러리로, 컴포넌트 기반 개발과 상태 관리를 배우기에 최적입니다. 활발한 커뮤니티와 풍부한 문서로 처음 오픈소스 기여를 시작하기 좋습니다.",
        },
        {
          name: "nodejs/node",
          description: "Chrome V8 기반 JavaScript 런타임",
          score: 88,
          stars: 100000,
          match: 72,
          recommendationReason:
            "JavaScript 백엔드 개발의 기반이 되는 런타임입니다. 저수준 시스템 프로그래밍과 성능 최적화에 관심이 있다면 매우 유익하며, 다양한 난이도의 이슈를 제공합니다.",
        },
        {
          name: "vercel/next.js",
          description: "프로덕션을 위한 React 프레임워크",
          score: 82,
          stars: 120000,
          match: 70,
          recommendationReason:
            "React 기반 풀스택 프레임워크로 서버사이드 렌더링과 정적 사이트 생성을 지원합니다. 모던 웹 개발 트렌드를 익히고 실전 경험을 쌓기에 적합합니다.",
        },
        {
          name: "microsoft/TypeScript",
          description: "JavaScript에 정적 타입을 추가한 프로그래밍 언어",
          score: 90,
          stars: 95000,
          match: 68,
          recommendationReason:
            "타입 시스템과 컴파일러 개발을 배울 수 있는 프로젝트입니다. JavaScript 생태계에서 매우 중요한 도구이며, 언어 설계와 구현에 대한 깊은 이해를 얻을 수 있습니다.",
        },
      ],
    };
  };

  // AI 응답 요청 (실제 LLM API 호출)
  const fetchAIResponse = async (userMessage) => {
    try {
      // 채팅 히스토리 구성 (초기 메시지 제외)
      const conversationHistory = messages
        .filter((msg) => msg.id !== "initial")
        .map((msg) => ({
          type: msg.role === "assistant" ? "assistant" : "user",
          content: msg.content,
        }));

      // API 호출
      const response = await sendChatMessage(
        userMessage,
        {
          repoUrl: analysisResult?.repositoryUrl || userProfile?.repositoryUrl,
          analysisResult: analysisResult
            ? {
              health_score: analysisResult.summary?.score,
              documentation_quality:
                analysisResult.technicalDetails?.documentationQuality,
              activity_maintainability:
                analysisResult.technicalDetails?.activityMaintainability,
              stars: analysisResult.technicalDetails?.stars,
              forks: analysisResult.technicalDetails?.forks,
            }
            : null,
        },
        conversationHistory
      );

      return (
        response.message || "죄송합니다. 응답을 생성하는데 문제가 발생했습니다."
      );
    } catch (error) {
      console.error("AI 응답 요청 실패:", error);
      return "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
    }
  };

  // 스트리밍 AI 응답 요청
  const fetchAIResponseStream = (userMessage) => {
    // 채팅 히스토리 구성 (초기 메시지 제외)
    const conversationHistory = messages
      .filter((msg) => msg.id !== "initial")
      .map((msg) => ({
        type: msg.role === "assistant" ? "assistant" : "user",
        content: msg.content,
      }));

    const context = {
      repoUrl: analysisResult?.repositoryUrl || userProfile?.repositoryUrl,
      analysisResult: analysisResult
        ? {
          health_score: analysisResult.summary?.score,
          documentation_quality:
            analysisResult.technicalDetails?.documentationQuality,
          activity_maintainability:
            analysisResult.technicalDetails?.activityMaintainability,
          stars: analysisResult.technicalDetails?.stars,
          forks: analysisResult.technicalDetails?.forks,
        }
        : null,
    };

    setStreamingMessage("");
    setIsStreaming(true);

    // 스트리밍 시작
    streamCancelRef.current = sendChatMessageStream(
      userMessage,
      context,
      conversationHistory,
      // onToken 콜백
      (token) => {
        setStreamingMessage((prev) => prev + token);
      },
      // onComplete 콜백
      (fullMessage, isFallback) => {
        setIsStreaming(false);
        setStreamingMessage("");

        const aiResponse = {
          id: `ai_${Date.now()}`,
          role: "assistant",
          content: fullMessage,
          timestamp: new Date(),
          isFallback,
        };
        setMessages((prev) => [...prev, aiResponse]);
        setIsTyping(false);
      },
      // onError 콜백
      (error) => {
        setIsStreaming(false);
        setStreamingMessage("");

        const errorResponse = {
          id: `ai_${Date.now()}`,
          role: "assistant",
          content:
            "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorResponse]);
        setIsTyping(false);
        console.error("Streaming error:", error);
      }
    );
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isAnalyzing || isStreaming) return;

    const userMessageContent = inputValue;
    const userMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      content: userMessageContent,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");

    // GitHub URL 감지
    const detectedUrl = detectGitHubUrl(userMessageContent);

    if (detectedUrl) {
      // URL이 감지되면 새로운 프로젝트 분석 시작 (실제 API 호출)
      setIsAnalyzing(true);
      setIsTyping(true);

      // 분석 중 메시지 표시
      const analyzingMessageId = `analyzing_${Date.now()}`;
      const analyzingMessage = {
        id: analyzingMessageId,
        role: "assistant",
        content: `${detectedUrl} 프로젝트를 분석하고 있습니다... 잠시만 기다려주세요. (실제 API 호출 중)`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, analyzingMessage]);

      try {
        // 실제 Backend API 호출 (userMessage도 전달하여 온보딩 등 메타 에이전트 처리)
        const apiResponse = await analyzeRepository(detectedUrl, userMessageContent);
        const newAnalysisResult = transformApiResponse(
          apiResponse,
          detectedUrl
        );
        setAnalysisResult(newAnalysisResult);

        // 부모 컴포넌트(AnalyzePage)의 Report 영역도 업데이트
        if (onAnalysisUpdate) {
          onAnalysisUpdate(newAnalysisResult);
        }

        // 히스토리에 추가
        addToHistory(newAnalysisResult);

        // 분석 중 메시지를 완료 메시지로 교체
        setMessages((prev) => {
          const filtered = prev.filter((msg) => msg.id !== analyzingMessageId);
          return [
            ...filtered,
            {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: `${detectedUrl} 저장소에 대한 분석이 완료되었습니다! 오른쪽 리포트에서 상세 정보를 확인하실 수 있습니다.`,
              timestamp: new Date(),
            },
          ];
        });
      } catch (error) {
        console.error("분석 실패:", error);
        setMessages((prev) => {
          const filtered = prev.filter((msg) => msg.id !== analyzingMessageId);
          return [
            ...filtered,
            {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: `죄송합니다. ${detectedUrl} 분석 중 오류가 발생했습니다. 다시 시도해주세요.`,
              timestamp: new Date(),
            },
          ];
        });
      } finally {
        setIsTyping(false);
        setIsAnalyzing(false);
      }
    } else {
      // 일반 질문 처리
      setIsTyping(true);

      if (USE_STREAM_MODE) {
        // 스트리밍 모드: SSE로 토큰 단위 응답 받기
        fetchAIResponseStream(userMessageContent);
      } else {
        // 기존 모드: REST API로 전체 응답 받기
        try {
          const aiResponseContent = await fetchAIResponse(userMessageContent);
          const aiResponse = {
            id: `ai_${Date.now()}`,
            role: "assistant",
            content: aiResponseContent,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, aiResponse]);
        } catch (error) {
          console.error("AI 응답 실패:", error);
          const errorResponse = {
            id: `ai_${Date.now()}`,
            role: "assistant",
            content:
              "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errorResponse]);
        } finally {
          setIsTyping(false);
        }
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-4xl font-black text-gray-900 mb-2">분석 결과</h1>
          <p className="text-gray-600">
            리포트를 확인하시고, 궁금한 점을 질문해보세요
          </p>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
          {/* 왼쪽: 채팅 영역 */}
          <div className="xl:col-span-2 bg-white rounded-3xl shadow-xl border border-gray-100 flex flex-col h-[calc(100vh-200px)] min-h-[600px]">
            {/* 채팅 메시지 영역 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}

              {/* 스트리밍 중인 메시지 표시 */}
              {isStreaming && (
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-white font-bold text-sm">ODOC</span>
                  </div>
                  <div className="max-w-[85%] bg-gray-100 rounded-2xl rounded-tl-none px-5 py-3">
                    {streamingMessage ? (
                      <div className="prose prose-sm max-w-none text-gray-800">
                        <ReactMarkdown>{streamingMessage}</ReactMarkdown>
                        {/* 타이핑 커서 효과 */}
                        <span className="inline-block w-2 h-4 bg-blue-600 ml-1 animate-pulse"></span>
                      </div>
                    ) : (
                      /* 첫 토큰 오기 전 ... 애니메이션 */
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div
                          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                          style={{ animationDelay: "0.1s" }}
                        ></div>
                        <div
                          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                          style={{ animationDelay: "0.2s" }}
                        ></div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 일반 타이핑 인디케이터 (비스트리밍 모드 또는 분석 중) */}
              {isTyping && !isStreaming && (
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-white font-bold text-sm">ODOC</span>
                  </div>
                  <div className="bg-gray-100 rounded-2xl rounded-tl-none px-5 py-3">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: "0.1s" }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* 입력 영역 */}
            <div className="border-t border-gray-100 p-4">
              {isAnalyzing && (
                <div className="mb-3 text-sm text-blue-600 font-semibold flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  분석 중입니다...
                </div>
              )}
              {isStreaming && (
                <div className="mb-3 text-sm text-green-600 font-semibold flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin"></div>
                  AI가 응답 중입니다...
                </div>
              )}
              <div className="flex gap-3">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="궁금한 점을 물어보세요... (GitHub URL 입력 시 바로 분석)"
                  disabled={isAnalyzing || isStreaming || isComparing}
                  className="flex-1 px-5 py-3 border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:outline-none transition-all disabled:bg-gray-100"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={
                    !inputValue.trim() || isTyping || isAnalyzing || isStreaming || isComparing
                  }
                  className="bg-blue-600 text-white p-3 rounded-2xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-105"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>

              {/* 추천 질문 */}
              <div className="mt-3 flex flex-wrap gap-2">
                <SuggestedQuestion
                  text="어떻게 시작하나요?"
                  onClick={() => setInputValue("어떻게 시작하나요?")}
                />
                <SuggestedQuestion
                  text="보안 취약점은?"
                  onClick={() =>
                    setInputValue("보안 취약점에 대해 자세히 알려주세요")
                  }
                />
                <SuggestedQuestion
                  text="microsoft/vscode 분석"
                  onClick={() => setInputValue("microsoft/vscode")}
                />
              </div>
            </div>
          </div>

          {/* 오른쪽: 분석 리포트 영역 */}
          <div className="xl:col-span-3 space-y-4">
            {/* 히스토리 네비게이션 바 */}
            {analysisHistory.length > 1 && (
              <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <History className="w-4 h-4" />
                  <span>분석 기록</span>
                  <span className="bg-gray-100 px-2 py-0.5 rounded-full text-xs font-medium">
                    {currentHistoryIndex + 1} / {analysisHistory.length}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {/* 비교 분석 버튼 */}
                  <div className="relative">
                    <button
                      onClick={() => setShowCompareSelector(!showCompareSelector)}
                      disabled={isComparing || getUniqueRepositories().length < 2}
                      className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${isComparing
                        ? "bg-purple-100 text-purple-600"
                        : getUniqueRepositories().length < 2
                          ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                          : showCompareSelector
                            ? "bg-purple-700 text-white"
                            : "bg-purple-600 hover:bg-purple-700 text-white"
                        }`}
                      title="저장소 비교 분석"
                    >
                      {isComparing ? (
                        <>
                          <div className="w-3 h-3 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
                          비교 중...
                        </>
                      ) : (
                        <>1:1 비교</>
                      )}
                    </button>

                    {/* 비교 선택 패널 */}
                    {showCompareSelector && (
                      <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-xl shadow-xl border border-gray-200 z-50 overflow-hidden">
                        <div className="p-3 bg-purple-50 border-b border-purple-100">
                          <h4 className="font-semibold text-purple-800 text-sm">비교할 저장소 선택</h4>
                          <p className="text-xs text-purple-600 mt-0.5">2개를 선택하세요 ({selectedForCompare.size}/2)</p>
                        </div>
                        <div className="max-h-48 overflow-y-auto">
                          {getUniqueRepositories().map((item) => (
                            <label
                              key={item.key}
                              className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors ${selectedForCompare.has(item.key) ? "bg-purple-50" : ""
                                }`}
                            >
                              <input
                                type="checkbox"
                                checked={selectedForCompare.has(item.key)}
                                onChange={() => toggleCompareSelection(item.key)}
                                disabled={!selectedForCompare.has(item.key) && selectedForCompare.size >= 2}
                                className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                              />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-800 truncate">{item.repo}</p>
                                <p className="text-xs text-gray-500">{item.owner}</p>
                              </div>
                              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${item.healthScore >= 70 ? "bg-green-100 text-green-700" :
                                item.healthScore >= 40 ? "bg-yellow-100 text-yellow-700" :
                                  "bg-red-100 text-red-700"
                                }`}>
                                {item.healthScore}점
                              </span>
                            </label>
                          ))}
                        </div>
                        <div className="p-2 bg-gray-50 border-t border-gray-200 flex gap-2">
                          <button
                            onClick={() => {
                              setShowCompareSelector(false);
                              setSelectedForCompare(new Set());
                            }}
                            className="flex-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
                          >
                            취소
                          </button>
                          <button
                            onClick={handleCompareAnalysis}
                            disabled={selectedForCompare.size !== 2}
                            className={`flex-1 px-3 py-1.5 text-sm rounded-lg transition-colors ${selectedForCompare.size === 2
                              ? "bg-purple-600 text-white hover:bg-purple-700"
                              : "bg-gray-300 text-gray-500 cursor-not-allowed"
                              }`}
                          >
                            비교 시작
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={goToPreviousAnalysis}
                    disabled={!canGoBack}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${canGoBack
                      ? "bg-gray-100 hover:bg-gray-200 text-gray-700"
                      : "bg-gray-50 text-gray-300 cursor-not-allowed"
                      }`}
                  >
                    <ChevronLeft className="w-4 h-4" />
                    이전
                  </button>
                  <button
                    onClick={goToNextAnalysis}
                    disabled={!canGoForward}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${canGoForward
                      ? "bg-gray-100 hover:bg-gray-200 text-gray-700"
                      : "bg-gray-50 text-gray-300 cursor-not-allowed"
                      }`}
                  >
                    다음
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            <AnalysisReportSection
              analysisResult={analysisResult}
              isLoading={isAnalyzing}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

const ChatMessage = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "items-start gap-3"}`}>
      {!isUser && (
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-sm">ODOC</span>
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-2xl px-5 py-3 break-words overflow-hidden ${isUser
          ? "bg-blue-600 text-white rounded-tr-none"
          : "bg-gray-100 text-gray-900 rounded-tl-none"
          }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed break-words">
            {message.content}
          </p>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong className="font-bold">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-4 mb-2 space-y-1">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li className="text-sm">{children}</li>,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    className="text-blue-600 hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

const SuggestedQuestion = ({ text, onClick }) => {
  return (
    <button
      onClick={onClick}
      className="text-sm px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-all"
    >
      {text}
    </button>
  );
};

export default AnalysisChat;
