import React, { useState, useRef, useEffect } from "react";
import AnalysisReportSection from "./AnalysisReportSection";
import ChatMessage from "./ChatMessage";
import { StreamingMessage, TypingIndicator } from "./ChatIndicators";
import MessageInput from "./MessageInput";
import AnalysisHistoryNav from "./AnalysisHistoryNav";
import { useChat } from "../../hooks/useChat";
import { useAnalysisStream } from "../../hooks/useAnalysisStream";
import { useSessionManagement } from "../../hooks/useSessionManagement";
import { useAnalysisHistory } from "../../hooks/useAnalysisHistory";
import { parseGitHubUrl, detectGitHubUrl } from "../../utils/githubUrlParser";
import { transformApiResponse } from "../../utils/apiResponseTransformer";
import {
  sendChatMessageV2,
  analyzeRepository,
  compareRepositories,
} from "../../lib/api";

// 스트리밍 모드 설정
const USE_STREAM_MODE = true;

const AnalysisChat = ({
  userProfile,
  analysisResult: initialAnalysisResult,
  onAnalysisUpdate,
}) => {
  // 보고서 생성 섹션 상태 관리
  const [reportSections, setReportSections] = useState({});
  const [reportMessageId, setReportMessageId] = useState(null);
  const reportRef = useRef(null);

  // 초기 메시지 생성 - 보고서 생성 카드 형태로
  const getInitialMessages = () => {
    // 분석 대기 중이거나 자연어 쿼리일 때는 빈 메시지로 시작
    if (
      initialAnalysisResult?.isNaturalLanguageQuery ||
      initialAnalysisResult?.shouldStartAnalysis
    ) {
      return [];
    }

    // 실제 데이터가 있는지 확인
    const hasRealData =
      initialAnalysisResult?.summary?.score > 0 ||
      initialAnalysisResult?.technicalDetails?.stars > 0 ||
      initialAnalysisResult?.technicalDetails?.forks > 0;

    // 데이터가 없으면 빈 배열 반환
    if (!hasRealData) {
      return [];
    }

    // 초기 보고서 생성 메시지 생성
    const initialSections = {};

    // 데이터가 실제로 있는 섹션만 complete로 설정
    if (initialAnalysisResult?.summary?.score > 0)
      initialSections.overview = "complete";
    if (
      initialAnalysisResult?.technicalDetails?.stars > 0 ||
      initialAnalysisResult?.technicalDetails?.forks > 0 ||
      initialAnalysisResult?.technicalDetails?.documentationQuality > 0
    )
      initialSections.metrics = "complete";
    if (
      initialAnalysisResult?.projectSummary &&
      initialAnalysisResult.projectSummary.trim()
    )
      initialSections.projectSummary = "complete";
    if (
      initialAnalysisResult?.security?.vulnerabilities?.length > 0 ||
      initialAnalysisResult?.security?.summary
    )
      initialSections.security = "complete";
    if (initialAnalysisResult?.risks?.length > 0)
      initialSections.risks = "complete";
    if (initialAnalysisResult?.recommendedIssues?.length > 0)
      initialSections.recommendedIssues = "complete";
    if (initialAnalysisResult?.recommendations?.length > 0)
      initialSections.recommendations = "complete";
    if (initialAnalysisResult?.similarProjects?.length > 0)
      initialSections.similarProjects = "complete";
    if (
      initialAnalysisResult?.onboardingPlan?.weeks?.length > 0 ||
      (Array.isArray(initialAnalysisResult?.onboardingPlan) &&
        initialAnalysisResult.onboardingPlan.length > 0)
    )
      initialSections.onboardingPlan = "complete";

    const reportMsgId = `report_${Date.now()}`;

    return [
      {
        id: reportMsgId,
        role: "assistant",
        type: "report_generation",
        sections: initialSections,
        isComplete: Object.keys(initialSections).length > 0,
        timestamp: new Date(),
      },
      {
        id: "initial_text",
        role: "assistant",
        content: `**${
          userProfile?.repositoryUrl || "저장소"
        }** 분석이 완료되었습니다!\n\n위의 보고서 카드에서 각 섹션을 클릭하면 상세 정보를 확인할 수 있습니다. 궁금한 점이 있으시면 질문해주세요.`,
        timestamp: new Date(),
      },
    ];
  };

  // Hooks
  const {
    messages,
    setMessages,
    inputValue,
    setInputValue,
    isTyping,
    setIsTyping,
    addMessage,
    clearInput,
  } = useChat(getInitialMessages);

  const [analysisResult, setAnalysisResult] = useState(initialAnalysisResult);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [showCompareSelector, setShowCompareSelector] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState(new Set());
  // suggestions 기능 비활성화 (필요시 재활성화)
  // const [suggestions, setSuggestions] = useState([]);

  // 리포트 영역 표시 상태 (데이터 있을 때만 표시)
  const hasInitialData =
    initialAnalysisResult?.summary?.score > 0 ||
    initialAnalysisResult?.technicalDetails;
  const [showReport, setShowReport] = useState(hasInitialData);
  // 사용자가 의도적으로 리포트를 닫았는지 추적 (자동 열림 방지용)
  const [userClosedReport, setUserClosedReport] = useState(false);

  const {
    sessionId,
    setSessionId,
    sessionRepo,
    setSessionRepo,
    clearSession,
    showSessionHistory,
    sessionList,
    toggleSessionHistory,
    switchToSession,
  } = useSessionManagement();

  const {
    streamingMessage,
    isStreaming,
    startStream,
    cancelStream,
    progressMessage,
  } = useAnalysisStream({
    parseGitHubUrl,
    transformApiResponse,
    setSessionId,
    setSessionRepo, // 백엔드와 저장소 정보 동기화
    setSuggestions: () => {}, // suggestions 기능 비활성화
    setAnalysisResult,
    setIsGeneratingPlan: () => {}, // noop
    onAnalysisUpdate,
  });

  const {
    analysisHistory,
    currentHistoryIndex,
    canGoBack,
    canGoForward,
    goToPreviousAnalysis,
    goToNextAnalysis,
    addToHistory,
  } = useAnalysisHistory(initialAnalysisResult);

  const messagesEndRef = useRef(null);

  // 분석 결과 변경 시 보고서 메시지 업데이트
  useEffect(() => {
    if (!analysisResult) return;

    // 실제 데이터가 도착하면 보고서 패널 표시 (사용자가 의도적으로 닫지 않은 경우에만)
    const hasData =
      analysisResult.summary?.score > 0 ||
      analysisResult.technicalDetails ||
      analysisResult.security ||
      analysisResult.similarProjects?.length > 0; // 추천 결과도 포함
    if (hasData && !showReport && !userClosedReport) {
      setShowReport(true);
    }

    setMessages((prevMessages) => {
      return prevMessages.map((msg) => {
        if (msg.type === "report_generation") {
          const updatedSections = { ...msg.sections };

          // 각 섹션 데이터 확인하여 상태 업데이트
          if (analysisResult.summary) updatedSections.overview = "complete";
          if (analysisResult.technicalDetails)
            updatedSections.metrics = "complete";
          if (analysisResult.projectSummary)
            updatedSections.projectSummary = "complete";
          // 보안: 결과가 있거나, 보안 요청이 완료된 경우
          if (analysisResult.security || analysisResult.securityRequested)
            updatedSections.security = "complete";
          if (analysisResult.risks?.length > 0)
            updatedSections.risks = "complete";
          if (analysisResult.recommendedIssues?.length > 0)
            updatedSections.recommendedIssues = "complete";
          if (analysisResult.recommendations?.length > 0)
            updatedSections.recommendations = "complete";
          if (analysisResult.similarProjects?.length > 0)
            updatedSections.similarProjects = "complete";
          if (analysisResult.onboardingPlan?.length > 0)
            updatedSections.onboardingPlan = "complete";

          return {
            ...msg,
            sections: updatedSections,
            progressMessage, // 진행 메시지 추가
            isComplete:
              Object.values(updatedSections).filter((s) => s === "complete")
                .length >= 3,
          };
        }
        return msg;
      });
    });
  }, [
    analysisResult,
    analysisResult?.similarProjects?.length,
    progressMessage,
    setMessages,
  ]);

  // analysisResult의 repositoryUrl이 변경되면 세션 저장소 정보 업데이트
  useEffect(() => {
    if (analysisResult?.repositoryUrl) {
      const { owner, repo } = parseGitHubUrl(analysisResult.repositoryUrl);
      if (owner && repo) {
        // sessionRepo가 없거나 다른 저장소일 때만 업데이트
        if (
          !sessionRepo ||
          sessionRepo.owner !== owner ||
          sessionRepo.repo !== repo
        ) {
          setSessionRepo({ owner, repo, full_name: `${owner}/${repo}` });
          console.log("[AnalysisChat] Session repo updated:", owner, repo);
        }
      }
    }
  }, [analysisResult?.repositoryUrl, sessionRepo, setSessionRepo]);

  // 섹션 클릭 핸들러 - 해당 섹션으로 스크롤
  const handleSectionClick = (sectionId) => {
    if (sectionId === "scrollToReport" && reportRef.current) {
      reportRef.current.scrollIntoView({ behavior: "smooth" });
      return;
    }

    // 특정 섹션으로 스크롤하고 싶다면 여기서 처리
    // AnalysisReportSection의 해당 섹션을 펼치는 로직 추가 가능
    if (reportRef.current) {
      reportRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  // 가이드 메시지 핸들러 - 물음표 클릭 시 채팅으로 가이드 전송
  // options.asUserMessage === true 이면 사용자 메시지로 표시하고 스트리밍 요청 전송
  const handleSendGuideMessage = (guideMessage, options = {}) => {
    if (options.asUserMessage) {
      // 사용자 메시지로 표시
      const userMessage = {
        id: `user_${Date.now()}`,
        role: "user",
        content: guideMessage,
        timestamp: new Date(),
      };
      addMessage(userMessage);

      // 스트리밍 요청 전송
      setIsTyping(true);
      startStream(
        guideMessage,
        sessionId,
        analysisResult,
        addMessage,
        setIsTyping,
        sessionRepo
      );
    } else {
      // 기존 동작: 어시스턴트 가이드 메시지로 표시
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          type: "guide",
          content: guideMessage,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
    // 채팅창으로 스크롤
    setTimeout(() => scrollToBottom(), 100);
  };

  // Auto-scroll
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

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelStream();
    };
  }, [cancelStream]);

  // 자연어 쿼리로 진입 시 초기 메시지 자동 전송
  const hasAutoSentInitialMessage = useRef(false);
  useEffect(() => {
    if (hasAutoSentInitialMessage.current) return;

    // Case 1: 자연어 쿼리 (URL 없음) - 초기 메시지 전송
    if (
      initialAnalysisResult?.isNaturalLanguageQuery &&
      initialAnalysisResult?.initialMessage
    ) {
      hasAutoSentInitialMessage.current = true;
      const initialMsg = initialAnalysisResult.initialMessage;
      console.log("[AnalysisChat] 자연어 쿼리 자동 전송:", initialMsg);

      setTimeout(() => {
        const userMessage = {
          id: `user_${Date.now()}`,
          role: "user",
          content: initialMsg,
          timestamp: new Date(),
        };
        addMessage(userMessage);

        startStream(initialMsg, null, sessionId, addMessage);
      }, 300);
      return;
    }

    // Case 2: URL 있음 - 자동 분석 시작
    if (
      initialAnalysisResult?.shouldStartAnalysis &&
      initialAnalysisResult?.repositoryUrl
    ) {
      hasAutoSentInitialMessage.current = true;
      const repoUrl = initialAnalysisResult.repositoryUrl;
      // 사용자가 입력한 원본 메시지 사용 (없으면 기본 분석 요청)
      const originalMessage =
        initialAnalysisResult?.originalMessage || `${repoUrl} 분석해줘`;
      console.log(
        "[AnalysisChat] 자동 분석 시작:",
        repoUrl,
        "원본 메시지:",
        originalMessage
      );

      // 시스템 메시지 대신 사용자 메시지로 분석 요청
      setTimeout(() => {
        const userMessage = {
          id: `user_${Date.now()}`,
          role: "user",
          content: originalMessage,
          timestamp: new Date(),
        };
        addMessage(userMessage);

        startStream(originalMessage, repoUrl, sessionId, addMessage);
      }, 300);
    }
  }, [initialAnalysisResult, sessionId, addMessage, startStream]);

  // History navigation handlers
  const handleGoBack = () => {
    const result = goToPreviousAnalysis();
    if (result) {
      setAnalysisResult(result);
    }
  };

  const handleGoForward = () => {
    const result = goToNextAnalysis();
    if (result) {
      setAnalysisResult(result);
    }
  };

  // Compare analysis handlers
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

  const getUniqueRepositories = () => {
    const seen = new Set();
    return analysisHistory
      .map((result, index) => {
        const url = result.repositoryUrl;
        const info = parseGitHubUrl(url);
        if (!info || !info.owner || !info.repo) return null;
        const repoKey = `${info.owner}/${info.repo}`;
        if (seen.has(repoKey)) return null;
        seen.add(repoKey);
        return {
          key: repoKey,
          owner: info.owner,
          repo: info.repo,
          healthScore: result.summary?.score || 0,
          index,
        };
      })
      .filter(Boolean);
  };

  const handleCompareAnalysis = async () => {
    const repositories = Array.from(selectedForCompare);

    if (repositories.length !== 2) {
      const errorMessage = {
        id: `compare_error_${Date.now()}`,
        role: "assistant",
        content: "비교하려면 2개의 저장소를 선택해주세요.",
        timestamp: new Date(),
      };
      addMessage(errorMessage);
      return;
    }

    setIsComparing(true);
    setShowCompareSelector(false);

    try {
      const response = await compareRepositories(repositories);

      if (response.ok) {
        const compareMessage = {
          id: `compare_${Date.now()}`,
          role: "assistant",
          content:
            response.summary ||
            `${repositories[0]}과 ${repositories[1]}의 비교 분석이 완료되었습니다.`,
          timestamp: new Date(),
        };
        addMessage(compareMessage);
      } else {
        const errorMessage = {
          id: `compare_error_${Date.now()}`,
          role: "assistant",
          content: `비교 분석 중 오류가 발생했습니다: ${
            response.error || "결과를 가져올 수 없습니다"
          }`,
          timestamp: new Date(),
        };
        addMessage(errorMessage);
      }
    } catch (error) {
      console.error("비교 분석 오류:", error);
      const errorMessage = {
        id: `compare_error_${Date.now()}`,
        role: "assistant",
        content: `비교 분석 중 오류가 발생했습니다: ${error.message}`,
        timestamp: new Date(),
      };
      addMessage(errorMessage);
    } finally {
      setIsComparing(false);
      setSelectedForCompare(new Set());
    }
  };

  // AI 응답 요청 (비스트리밍)
  const fetchAIResponse = async (userMessage) => {
    try {
      const repoUrl =
        analysisResult?.repositoryUrl || userProfile?.repositoryUrl;
      const { owner, repo } = parseGitHubUrl(repoUrl);

      const response = await sendChatMessageV2(
        userMessage,
        sessionId,
        owner,
        repo
      );

      if (response.session_id) {
        setSessionId(response.session_id);
      }

      // suggestions 기능 비활성화
      // if (response.suggestions && response.suggestions.length > 0) {
      //   setSuggestions(response.suggestions);
      // }

      if (response.context) {
        const { agent_result, target_agent } = response.context;

        if (target_agent === "diagnosis" && agent_result) {
          const repoUrl =
            analysisResult?.repositoryUrl ||
            `https://github.com/${owner}/${repo}`;
          const updatedResult = transformApiResponse(
            { context: response.context, analysis: agent_result },
            repoUrl
          );

          setAnalysisResult((prev) => ({
            ...prev,
            ...updatedResult,
            repositoryUrl: repoUrl,
          }));

          if (onAnalysisUpdate) {
            onAnalysisUpdate(updatedResult);
          }
        }

        if (target_agent === "onboarding" && agent_result) {
          // contributor_guide 타입 처리 (마크다운이 직접 포함된 경우)
          if (
            agent_result.type === "contributor_guide" &&
            agent_result.markdown
          ) {
            setAnalysisResult((prev) => ({
              ...prev,
              contributorGuide: agent_result,
              onboardingPlan: [], // 빈 배열로 설정
            }));
          } else {
            setAnalysisResult((prev) => ({
              ...prev,
              onboardingPlan: agent_result,
            }));
          }
        }

        // contributor 에이전트 결과 처리
        if (target_agent === "contributor" && agent_result) {
          const features = agent_result.features || {};
          setAnalysisResult((prev) => ({
            ...prev,
            contributorGuide: agent_result,
            firstContributionGuide: features.first_contribution_guide || null,
            contributionChecklist: features.contribution_checklist || null,
            communityAnalysis: features.community_analysis || null,
            issueMatching: features.issue_matching || null,
            structureVisualization: features.structure_visualization || null,
          }));
        }
      }

      return (
        response.answer || "죄송합니다. 응답을 생성하는데 문제가 발생했습니다."
      );
    } catch (error) {
      console.error("AI 응답 요청 실패:", error);
      return "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
    }
  };

  // 메시지 전송 핸들러
  const handleSendMessage = async () => {
    if (!inputValue.trim() || isAnalyzing || isStreaming) return;

    const userMessageContent = inputValue;
    clearInput();

    const userMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      content: userMessageContent,
      timestamp: new Date(),
    };

    addMessage(userMessage);

    // GitHub URL 감지
    const detectedUrl = detectGitHubUrl(userMessageContent);

    if (detectedUrl) {
      // 새로운 프로젝트 분석
      setIsAnalyzing(true);
      setIsTyping(true);

      // 보고서 생성 메시지 추가 (진행 상황 표시용)
      const reportMessageId = `report_${Date.now()}`;
      const reportMessage = {
        id: reportMessageId,
        role: "assistant",
        type: "report_generation",
        sections: {
          overview: "loading",
        },
        isComplete: false,
        timestamp: new Date(),
      };
      addMessage(reportMessage);
      setReportMessageId(reportMessageId);

      // 섹션별 로딩 상태 시뮬레이션 (실제로는 API 응답에 따라 업데이트)
      const updateSectionStatus = (sectionId, status, delay) => {
        setTimeout(() => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === reportMessageId) {
                return {
                  ...msg,
                  sections: { ...msg.sections, [sectionId]: status },
                };
              }
              return msg;
            })
          );
        }, delay);
      };

      // 순차적으로 섹션 로딩 표시
      updateSectionStatus("metrics", "loading", 500);
      updateSectionStatus("projectSummary", "loading", 1000);
      updateSectionStatus("security", "loading", 1500);
      updateSectionStatus("risks", "loading", 2000);

      try {
        const apiResponse = await analyzeRepository(
          detectedUrl,
          userMessageContent
        );
        const newAnalysisResult = transformApiResponse(
          apiResponse,
          detectedUrl
        );
        setAnalysisResult(newAnalysisResult);

        // 세션에 저장소 정보 저장 (멀티턴 대화용)
        const { owner, repo } = parseGitHubUrl(detectedUrl);
        if (owner && repo) {
          setSessionRepo({ owner, repo, full_name: `${owner}/${repo}` });
        }

        if (onAnalysisUpdate) {
          onAnalysisUpdate(newAnalysisResult);
        }

        addToHistory(newAnalysisResult);

        // 보고서 메시지를 완료 상태로 업데이트
        setMessages((prev) => {
          return prev.map((msg) => {
            if (msg.id === reportMessageId) {
              const completeSections = {};
              if (newAnalysisResult.summary)
                completeSections.overview = "complete";
              if (newAnalysisResult.technicalDetails)
                completeSections.metrics = "complete";
              if (newAnalysisResult.projectSummary)
                completeSections.projectSummary = "complete";
              if (newAnalysisResult.security)
                completeSections.security = "complete";
              if (newAnalysisResult.risks?.length > 0)
                completeSections.risks = "complete";
              if (newAnalysisResult.recommendedIssues?.length > 0)
                completeSections.recommendedIssues = "complete";
              if (newAnalysisResult.recommendations?.length > 0)
                completeSections.recommendations = "complete";
              if (newAnalysisResult.similarProjects?.length > 0)
                completeSections.similarProjects = "complete";
              if (newAnalysisResult.onboardingPlan?.length > 0)
                completeSections.onboardingPlan = "complete";

              return {
                ...msg,
                sections: completeSections,
                isComplete: true,
              };
            }
            return msg;
          });
        });

        // 완료 텍스트 메시지 추가
        addMessage({
          id: `complete_${Date.now()}`,
          role: "assistant",
          content: `**${detectedUrl}** 분석이 완료되었습니다! 🎉\n\n위 보고서 카드에서 각 섹션을 클릭하거나, 오른쪽 리포트에서 상세 정보를 확인하세요.`,
          timestamp: new Date(),
        });
      } catch (error) {
        console.error("분석 실패:", error);

        // 에러 시 보고서 메시지 업데이트
        setMessages((prev) => {
          return prev.map((msg) => {
            if (msg.id === reportMessageId) {
              return {
                ...msg,
                sections: { ...msg.sections, overview: "error" },
                isComplete: false,
              };
            }
            return msg;
          });
        });

        addMessage({
          id: `error_${Date.now()}`,
          role: "assistant",
          content: `죄송합니다. **${detectedUrl}** 분석 중 오류가 발생했습니다. 다시 시도해주세요.`,
          timestamp: new Date(),
        });
      } finally {
        setIsTyping(false);
        setIsAnalyzing(false);
      }
    } else {
      // 일반 질문 처리
      setIsTyping(true);

      if (USE_STREAM_MODE) {
        startStream(
          userMessageContent,
          sessionId,
          analysisResult,
          addMessage,
          setIsTyping,
          sessionRepo // 세션에 저장된 저장소 정보 전달
        );
      } else {
        try {
          const aiResponseContent = await fetchAIResponse(userMessageContent);
          const aiResponse = {
            id: `ai_${Date.now()}`,
            role: "assistant",
            content: aiResponseContent,
            timestamp: new Date(),
          };
          addMessage(aiResponse);
        } catch (error) {
          console.error("AI 응답 실패:", error);
          const errorResponse = {
            id: `ai_${Date.now()}`,
            role: "assistant",
            content:
              "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            timestamp: new Date(),
          };
          addMessage(errorResponse);
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

  // Clarification 버튼 클릭 핸들러
  const handleClarificationClick = (text) => {
    setInputValue(text);
    handleSendMessage();
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto px-4 py-6">
        {/* Header - 더 컴팩트하게 */}
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            분석 결과
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            리포트를 확인하고 궁금한 점을 질문해보세요
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-start">
          {/* 왼쪽: 채팅 영역 - 리포트 숨김 시 전체 너비 */}
          <div
            className={`${
              showReport ? "md:col-span-2" : "md:col-span-5"
            } bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 flex flex-col h-[calc(100vh-140px)] min-h-[500px] transition-all duration-300`}
          >
            {/* 채팅 헤더 */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">ODOC</span>
              </div>
              {/* 데스크톱에서만 보이는 토글 버튼 */}
              <button
                onClick={() => setShowReport(!showReport)}
                className="hidden xl:flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                title={showReport ? "리포트 숨기기" : "리포트 보기"}
              >
                {showReport ? (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 5l7 7-7 7M5 5l7 7-7 7"
                      />
                    </svg>
                    <span>숨기기</span>
                  </>
                ) : (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
                      />
                    </svg>
                    <span>리포트</span>
                  </>
                )}
              </button>
            </div>

            {/* 채팅 메시지 영역 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  onSendMessage={handleClarificationClick}
                  onSectionClick={handleSectionClick}
                  analysisResult={analysisResult}
                />
              ))}

              <StreamingMessage
                streamingMessage={streamingMessage}
                isStreaming={isStreaming}
              />

              <TypingIndicator isTyping={isTyping} isStreaming={isStreaming} />

              <div ref={messagesEndRef} />
            </div>

            {/* 입력 영역 */}
            <MessageInput
              inputValue={inputValue}
              setInputValue={setInputValue}
              onSendMessage={handleSendMessage}
              onKeyPress={handleKeyPress}
              isAnalyzing={isAnalyzing}
              isStreaming={isStreaming}
              isComparing={isComparing}
              isTyping={isTyping}
              suggestions={[]} // suggestions 기능 비활성화
            />
          </div>

          {/* 오른쪽: 분석 리포트 영역 - showReport가 true일 때만 표시 */}
          {showReport && (
            <div
              className="md:col-span-3 space-y-3 h-[calc(100vh-140px)] overflow-y-auto"
              ref={reportRef}
            >
              {/* 리포트 헤더 with 닫기 버튼 */}
              <div className="flex items-center justify-between sticky top-0 bg-gray-50 dark:bg-gray-900 z-10 pb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    📊 분석 리포트
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <AnalysisHistoryNav
                    analysisHistory={analysisHistory}
                    currentHistoryIndex={currentHistoryIndex}
                    canGoBack={canGoBack}
                    canGoForward={canGoForward}
                    onGoBack={handleGoBack}
                    onGoForward={handleGoForward}
                    showCompareSelector={showCompareSelector}
                    setShowCompareSelector={setShowCompareSelector}
                    isComparing={isComparing}
                    selectedForCompare={selectedForCompare}
                    onToggleCompareSelection={toggleCompareSelection}
                    onCompareAnalysis={handleCompareAnalysis}
                    setSelectedForCompare={setSelectedForCompare}
                    getUniqueRepositories={getUniqueRepositories}
                    showSessionHistory={showSessionHistory}
                    onToggleSessionHistory={toggleSessionHistory}
                    sessionList={sessionList}
                    sessionId={sessionId}
                    onSwitchToSession={switchToSession}
                  />
                  {/* 리포트 닫기 버튼 */}
                  <button
                    onClick={() => {
                      setShowReport(false);
                      setUserClosedReport(true);
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    title="리포트 닫기"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                    <span className="hidden lg:inline">닫기</span>
                  </button>
                </div>
              </div>

              <div className="mt-4">
                <AnalysisReportSection
                  analysisResult={analysisResult}
                  isLoading={isAnalyzing}
                  onSendGuideMessage={handleSendGuideMessage}
                />
              </div>
            </div>
          )}
        </div>

        {/* 플로팅 리포트 버튼 - 리포트가 숨겨져 있고 데이터가 있을 때만 표시 */}
        {!showReport &&
          (analysisResult?.summary?.score > 0 ||
            analysisResult?.security ||
            analysisResult?.onboardingPlan?.length > 0 ||
            analysisResult?.contributorGuide) && (
            <button
              onClick={() => setShowReport(true)}
              className="hidden md:flex fixed bottom-6 right-6 items-center gap-2 px-4 py-2.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-lg shadow-md hover:bg-gray-800 dark:hover:bg-gray-600 transition-colors z-50"
              title="분석 리포트 보기"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span>리포트 보기</span>
            </button>
          )}
      </div>
    </div>
  );
};

export default AnalysisChat;
